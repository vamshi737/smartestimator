# app.py — Week5 Day24.1 hot-fix: pass preproc path to geometry (enables manual scale even w/o bbox)
import os, sys, json, uuid, shutil, subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

APP_ROOT = Path(__file__).parent.resolve()
DATA_DIR = APP_ROOT / "data" / "output"
RUNS_DIR = APP_ROOT / "runs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATES = Jinja2Templates(directory=str(APP_ROOT / "templates"))
app = FastAPI(title="SmartEstimator AI — Week 5 Day 24.1")

# ------------------------------- helpers ----------------------------------
def run(cmd, cwd=None) -> int:
    print("->", " ".join(map(str, cmd)))
    r = subprocess.run(cmd, cwd=cwd)
    return r.returncode

def safe_json_parse(s: str) -> Optional[dict]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception as e:
        print("JSON parse error:", e)
        return None

def read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def get_last_status() -> Optional[dict]:
    if not RUNS_DIR.exists():
        return None
    latest_path = None
    latest_mtime = -1.0
    for run_dir in RUNS_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        s = run_dir / "status.json"
        if s.exists():
            try:
                m = s.stat().st_mtime
                if m > latest_mtime:
                    latest_mtime = m
                    latest_path = s
            except Exception:
                pass
    if not latest_path:
        return None
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        return None

# -------------------------------- routes ----------------------------------
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def form(request: Request):
    last_status = get_last_status()
    try:
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "last_status": last_status}
        )
    except Exception:
        scale_val = (last_status or {}).get("scale_ft_per_px")
        scale_str = f"{scale_val:.6f} ft/px" if scale_val else "n/a"
        t = (last_status or {}).get("totals") or {}
        ta = t.get("total_area_ft2", 0)
        tp = t.get("total_perimeter_ft", 0)
        tw = t.get("total_wall_length_ft", 0)
        ocr_used = (last_status or {}).get("ocr_geometry_used", False)
        last_block = ""
        if last_status:
            last_block = f"""
            <div class="card" style="margin-top:18px; padding:14px; border:1px solid #e5e7eb; border-radius:10px;">
              <h3>Last Run</h3>
              <p><b>Run ID:</b> {last_status.get('run_id')}</p>
              <p><b>OCR geometry used:</b> {'✅ Yes' if ocr_used else '❌ No (fallback)'}</p>
              <p><b>Scale:</b> {scale_str}</p>
              <p>
                <b>Total Area:</b> {ta} ft² ·
                <b>Total Perimeter:</b> {tp} ft ·
                <b>Total Wall Length:</b> {tw} ft
              </p>
              <p class="links">
                <a href="/runs/{last_status.get('run_id')}/status.json">status.json</a> |
                <a href="/runs/{last_status.get('run_id')}/metrics/metrics_area.json">metrics_area.json</a> |
                <a href="/runs/{last_status.get('run_id')}/metrics/metrics_walls.json">metrics_walls.json</a>
              </p>
            </div>
            """
        return HTMLResponse(f"""<!doctype html><html><body><div class="wrap">
          <form action="/estimate" method="post" enctype="multipart/form-data">
            <input type="file" name="plan" required/>
            <button type="submit">Estimate</button>
          </form>
          {last_block}
        </div></body></html>""")

@app.post("/estimate", response_class=HTMLResponse)
async def estimate(
    plan: UploadFile = File(...),
    in_height: float = Form(10.0),
    us_height: float = Form(8.0),
    mode: str = Form("both"),
    prices_json: str = Form(""),
    known_width_ft: Optional[float] = Form(None),
    known_height_ft: Optional[float] = Form(None),
):
    run_id = uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    out_dir = run_dir / "out"
    mets_dir = run_dir / "metrics"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    mets_dir.mkdir(parents=True, exist_ok=True)

    plan_ext = Path(plan.filename).suffix.lower() or ".png"
    plan_path = run_dir / ("plan" + plan_ext)
    with open(plan_path, "wb") as f:
        f.write(await plan.read())

    custom_prices = safe_json_parse(prices_json)
    prices_path = APP_ROOT / "data" / "prices.json"
    if custom_prices:
        temp_prices = run_dir / "prices_overrides.json"
        temp_prices.write_text(json.dumps(custom_prices, indent=2), encoding="utf-8")
        prices_path = temp_prices

    manual_scale_payload = {
        "known_width_ft": float(known_width_ft) if known_width_ft else None,
        "known_height_ft": float(known_height_ft) if known_height_ft else None,
    }
    (run_dir / "manual_scale.json").write_text(json.dumps(manual_scale_payload, indent=2), encoding="utf-8")
    (DATA_DIR / "manual_scale.json").write_text(json.dumps(manual_scale_payload, indent=2), encoding="utf-8")

    ocr_ok = True
    preproc = run_dir / "preproc.png"
    ocr_json_tmp = DATA_DIR / "ocr_dims.json"
    area_json_tmp = DATA_DIR / "metrics_area.json"
    walls_json_tmp = DATA_DIR / "metrics_walls.json"

    for p in (ocr_json_tmp, area_json_tmp, walls_json_tmp):
        try:
            if p.exists(): p.unlink()
        except Exception:
            pass

    code = run([sys.executable, "src/vision/preprocess.py",
                "--input", str(plan_path),
                "--out", str(preproc),
                "--deskew"])
    if code != 0 or not preproc.exists():
        ocr_ok = False

    if ocr_ok:
        code = run([sys.executable, "src/vision/ocr_dims.py",
                    "--input", str(preproc),
                    "--out", str(ocr_json_tmp)])
        if code != 0 or not ocr_json_tmp.exists():
            ocr_ok = False

    if ocr_ok:
        # >>> HOT-FIX: pass --preproc to enable image-size fallback for manual scale
        code = run([sys.executable, "src/vision/geometry_from_dims.py",
                    "--ocr", str(ocr_json_tmp),
                    "--out_area", str(area_json_tmp),
                    "--out_walls", str(walls_json_tmp),
                    "--preproc", str(preproc)])
        if code != 0 or not walls_json_tmp.exists():
            ocr_ok = False

    area_json = mets_dir / "metrics_area.json"
    walls_json = mets_dir / "metrics_walls.json"
    scale_ft_per_px = None
    totals = {"total_area_ft2": 0.0, "total_perimeter_ft": 0.0, "total_wall_length_ft": 0.0}
    ocr_used_flag = bool(ocr_ok)

    if ocr_ok and area_json_tmp.exists():
        shutil.copy2(area_json_tmp, area_json)
        shutil.copy2(walls_json_tmp, walls_json)
        area_payload = read_json(area_json) or {}
        rooms0 = (area_payload.get("rooms") or [])
        if rooms0 and rooms0[0].get("name") == "SyntheticArea":
            ocr_used_flag = False
        scale_ft_per_px = area_payload.get("scale_ft_per_px")
        t = (area_payload.get("totals") or {})
        totals["total_area_ft2"] = t.get("total_area_ft2", 0.0)
        totals["total_perimeter_ft"] = t.get("total_perimeter_ft", 0.0)
        totals["total_wall_length_ft"] = t.get("total_wall_length_ft", 0.0)
    else:
        placeholder = {
            "source": "ocr",
            "scale_ft_per_px": None,
            "rooms": [{
                "name": "SyntheticArea",
                "polygon_ft": [[0,0],[10,0],[10,10],[0,10]],
                "area_ft2": 100.0,
                "perimeter_ft": 40.0
            }],
            "totals": {"total_area_ft2": 100.0, "total_perimeter_ft": 40.0, "total_wall_length_ft": 0.0}
        }
        area_json.write_text(json.dumps(placeholder, indent=2), encoding="utf-8")
        walls_json.write_text(json.dumps({"source":"ocr","walls":[],"totals":{"total_wall_length_ft":0.0}}, indent=2), encoding="utf-8")
        totals = placeholder["totals"]
        scale_ft_per_px = None
        ocr_used_flag = False

    status = {
        "run_id": run_id,
        "ocr_geometry_used": bool(ocr_used_flag),
        "scale_ft_per_px": scale_ft_per_px,
        "totals": totals,
        "metrics_area": str(area_json.relative_to(APP_ROOT)),
        "metrics_walls": str(walls_json.relative_to(APP_ROOT)),
        "manual_scale": manual_scale_payload,
    }
    (run_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    engine_args = [
        sys.executable, "src/main.py",
        "--mode", mode,
        "--prices", str(prices_path),
        "--in_height_ft", str(in_height),
        "--us_height_ft", str(us_height),
        "--outdir", str(out_dir),
        "--metrics_area", str(area_json),
        "--metrics_walls", str(walls_json),
        "--metrics_source", "ocr"
    ]
    code = run(engine_args)
    if code != 0:
        return HTMLResponse("<h3>Run failed.</h3><p>Check server logs.</p>", status_code=500)

    links = []
    for name in ["final_estimate.xlsx","final_estimate.pdf","final_estimate_detailed.pdf","final_breakdown.json","compare_preview.png"]:
        p = out_dir / name
        if p.exists():
            links.append(f'<a href="/download/{run_id}/{name}">{name}</a>')

    if (known_width_ft or known_height_ft):
        status_note = "✅ Manual scale used (override)" if scale_ft_per_px else "✅ Manual scale requested"
    elif status["ocr_geometry_used"]:
        status_note = "✅ OCR geometry used"
    else:
        status_note = "⚠️ Default scale used (fallback)"

    scale_str = f"{status['scale_ft_per_px']:.6f} ft/px" if status["scale_ft_per_px"] else "n/a"
    ta = status["totals"]["total_area_ft2"]; tp = status["totals"]["total_perimeter_ft"]; tw = status["totals"]["total_wall_length_ft"]

    return HTMLResponse(f"""
    <div class="wrap" style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; max-width:920px; margin:30px auto;">
      <h3>Estimate Ready (Run {run_id})</h3>
      <p><b>Status:</b> {status_note}</p>
      <p><b>Scale:</b> {scale_str}</p>
      <p><b>Total Area:</b> {ta} ft² &nbsp;|&nbsp; <b>Total Perimeter:</b> {tp} ft &nbsp;|&nbsp; <b>Total Wall Length:</b> {tw} ft</p>
      <div class="links" style="margin-top:10px">{' | '.join(links)}</div>
      <div class="links" style="margin-top:8px; color:#64748b">
        <a href="/runs/{run_id}/status.json">status.json</a> |
        <a href="/runs/{run_id}/metrics/metrics_area.json">metrics_area.json</a> |
        <a href="/runs/{run_id}/metrics/metrics_walls.json">metrics_walls.json</a>
      </div>
      <p style="margin-top:16px"><a href="/">⟵ New estimate</a></p>
    </div>
    """)

# ------------------------------ downloads ----------------------------------
@app.get("/download/{run_id}/{filename}")
def download(run_id: str, filename: str):
    p = RUNS_DIR / run_id / "out" / filename
    if not p.exists():
        return PlainTextResponse("File not found", status_code=404)
    return FileResponse(path=p, filename=filename)

@app.get("/runs/{run_id}/status.json")
def get_status(run_id: str):
    p = RUNS_DIR / run_id / "status.json"
    if not p.exists():
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(path=p, filename="status.json")

@app.get("/runs/{run_id}/metrics/{filename}")
def get_metrics(run_id: str, filename: str):
    p = RUNS_DIR / run_id / "metrics" / filename
    if not p.exists():
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(path=p, filename=filename)
