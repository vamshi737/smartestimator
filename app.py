# app.py — Week5 Day24: UI -> OCR live integration with safe fallback
import os, sys, json, uuid, shutil, subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse

APP_ROOT = Path(__file__).parent.resolve()
DATA_DIR = APP_ROOT / "data" / "output"
RUNS_DIR = APP_ROOT / "runs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SmartEstimator AI — Week 5 Day 24")

def run(cmd, cwd=None) -> int:
    """Run a subprocess and stream output."""
    print("->", " ".join(cmd))
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

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def form():
    return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>SmartEstimator AI — Final Test (Week 5 · Day 24)</title>
    <link rel="icon" href="data:,">
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#f8fafc; }}
      .wrap {{ max-width: 880px; margin: 30px auto; background:#fff; padding:28px; border-radius:12px; box-shadow:0 6px 20px rgba(0,0,0,.08); }}
      label {{ font-weight: 600; }}
      input[type="number"], select, textarea {{ width:100%; padding:10px; margin:8px 0 16px; }}
      .row {{ display:flex; gap:18px; }}
      .col {{ flex:1; }}
      .note {{ background:#eef6ff; border:1px dashed #84a9ff; padding:12px 14px; border-radius:10px; color:#173b6d; }}
      .btn {{ background:#111827; color:#fff; border:0; padding:10px 18px; border-radius:10px; cursor:pointer; }}
      .small {{ color:#666; font-size:12px; }}
      .links a {{ display:inline-block; margin-right:12px; }}
      code {{ background:#f1f5f9; padding:2px 6px; border-radius:6px; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <h2>SmartEstimator AI — Week 5 · Day 24 (UI → OCR)</h2>
      <p class="note"><strong>Note:</strong> Current version reads dimensions via OCR from your uploaded plan. If OCR confidence is low or a step fails, we safely fallback to the internal sample metrics. Use the wall height fields and optional pricing JSON to tune totals.</p>

      <form action="/estimate" method="post" enctype="multipart/form-data">
        <label>Plan file (image or PDF)</label><br/>
        <input type="file" name="plan" required/>

        <div class="row">
          <div class="col">
            <label>India wall height (ft)</label>
            <input type="number" step="0.1" name="in_height" value="10"/>
          </div>
          <div class="col">
            <label>USA wall height (ft)</label>
            <input type="number" step="0.1" name="us_height" value="8"/>
          </div>
        </div>

        <label>Mode</label>
        <select name="mode">
          <option value="india">india</option>
          <option value="usa">usa</option>
          <option value="both" selected>both</option>
        </select>

        <label>Optional price overrides (JSON)</label>
        <textarea name="prices_json" rows="7" placeholder='{{"GLOBAL":{{"currency":"INR"}}}}'></textarea>

        <button class="btn" type="submit">Estimate</button>
      </form>

      <p class="small" style="margin-top:16px;">Health: <a href="/health">/health</a></p>
    </div>
  </body>
</html>
    """

@app.post("/estimate", response_class=HTMLResponse)
async def estimate(
    plan: UploadFile = File(...),
    in_height: float = Form(10.0),
    us_height: float = Form(8.0),
    mode: str = Form("both"),
    prices_json: str = Form("")
):
    # 1) Create run workspace
    run_id = uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    out_dir = run_dir / "out"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 2) Save upload
    plan_ext = Path(plan.filename).suffix.lower() or ".png"
    plan_path = run_dir / ("plan" + plan_ext)
    with open(plan_path, "wb") as f:
        f.write(await plan.read())

    # 3) Optional price overrides
    custom_prices = safe_json_parse(prices_json)
    prices_path = APP_ROOT / "data" / "prices.json"
    # If user pasted JSON, write a temp file and point to it
    if custom_prices:
        temp_prices = run_dir / "prices_overrides.json"
        with open(temp_prices, "w", encoding="utf-8") as f:
            json.dump(custom_prices, f, indent=2)
        prices_path = temp_prices

    # 4) OCR pipeline (preprocess -> OCR -> geometry)
    ocr_ok = True
    preproc = run_dir / "preproc.png"
    ocr_json = DATA_DIR / "ocr_dims.json"              # keep paths consistent with src tools
    area_json = DATA_DIR / "metrics_area.json"
    walls_json = DATA_DIR / "metrics_walls.json"

    # clean previous metrics so we know if OCR produced them
    for p in (ocr_json, area_json, walls_json):
        try:
            if p.exists(): p.unlink()
        except Exception:
            pass

    # preprocess
    code = run([sys.executable, "src/vision/preprocess.py",
                "--input", str(plan_path),
                "--out", str(preproc),
                "--deskew"])
    if code != 0 or not preproc.exists():
        ocr_ok = False

    # OCR dims
    if ocr_ok:
        code = run([sys.executable, "src/vision/ocr_dims.py",
                    "--input", str(preproc),
                    "--out", str(ocr_json)])
        if code != 0 or not ocr_json.exists():
            ocr_ok = False

    # Geometry mapping
    if ocr_ok:
        code = run([sys.executable, "src/vision/geometry_from_dims.py",
                    "--ocr", str(ocr_json),
                    "--out_area", str(area_json),
                    "--out_walls", str(walls_json)])
        if code != 0 or not walls_json.exists():
            ocr_ok = False

    # 5) Main pipeline (now prefers OCR geometry automatically if present)
    code = run([
        sys.executable, "src/main.py",
        "--mode", mode,
        "--prices", str(prices_path),
        "--in_height_ft", str(in_height),
        "--us_height_ft", str(us_height),
        "--outdir", str(out_dir)
    ])
    if code != 0:
        return HTMLResponse(
            f"<h3>Run failed.</h3><p>Check server logs.</p>",
            status_code=500
        )

    # 6) Links to outputs
    links = []
    for name in ["final_estimate.xlsx", "final_estimate.pdf",
                 "final_estimate_detailed.pdf", "final_breakdown.json",
                 "compare_preview.png"]:
        p = out_dir / name
        if p.exists():
            links.append(f'<a href="/download/{run_id}/{name}">{name}</a>')

    ocr_msg = "OCR geometry used" if (ocr_ok and walls_json.exists()) else "Fallback to sample metrics"

    return HTMLResponse(f"""
    <div class="wrap" style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; max-width:880px; margin:30px auto">
      <h3>Run complete (run-id: {run_id})</h3>
      <p><b>Status:</b> {ocr_msg}</p>
      <div class="links">{' | '.join(links)}</div>
      <p style="margin-top:16px"><a href="/">⟵ New estimate</a></p>
    </div>
    """)

@app.get("/download/{run_id}/{filename}")
def download(run_id: str, filename: str):
    p = RUNS_DIR / run_id / "out" / filename
    if not p.exists():
        return PlainTextResponse("File not found", status_code=404)
    return FileResponse(path=p, filename=filename)
