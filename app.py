from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, PlainTextResponse
from pathlib import Path
from uuid import uuid4
import shutil, subprocess, json, sys
import config

# Ensure runs dir exists
Path(config.RUNS_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SmartEstimator API", version="1.0")

# ---------- Root page (so / is not 404) ----------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html><html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SmartEstimator AI</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;margin:32px;line-height:1.5}
.card{max-width:760px;margin:auto;border:1px solid #e5e7eb;border-radius:14px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
label{display:block;margin:12px 0 6px} input,select,textarea,button{font:inherit;width:100%}
button{margin-top:16px;padding:10px 16px;border:0;border-radius:10px;background:#111827;color:#fff;cursor:pointer;width:auto}
.log{white-space:pre-wrap;background:#1118270d;border:1px dashed #cbd5e1;padding:12px;border-radius:8px;margin-top:14px}
a{color:#2563eb}
</style>
</head><body>
<div class="card">
  <h1>SmartEstimator AI</h1>
  <p>Upload a plan image → choose mode → get Excel/PDF.</p>

  <form id="f">
    <label>Plan image</label>
    <input type="file" name="image" accept="image/*" required />

    <label>Mode</label>
    <select name="mode">
      <option value="all" selected>all (India+USA+reports)</option>
      <option value="india">india</option>
      <option value="usa">usa</option>
      <option value="both">both</option>
    </select>

    <label>Optional price overrides (JSON)</label>
    <textarea name="prices_json" rows="4">{}</textarea>

    <button type="submit">Estimate</button>
  </form>

  <div id="out" class="log"></div>
  <div id="links"></div>

  <p style="margin-top:12px">Health: <a href="/health" target="_blank">/health</a></p>
</div>

<script>
const form = document.getElementById('f');
const out  = document.getElementById('out');
const links= document.getElementById('links');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  out.textContent = 'Running…';
  links.innerHTML = '';
  const fd = new FormData(form);
  try {
    const r = await fetch('/estimate', { method:'POST', body: fd });
    const data = await r.json();
    if (!r.ok || !data.ok) {
      out.textContent = 'Error: ' + (data.error || r.statusText);
      return;
    }
    out.textContent = 'OK  Run: ' + data.run_id;
    const run = data.run_id;
    const excel = (data.artifacts.excel||'').split(/[\\\\/]/).pop();
    const pdf   = (data.artifacts.pdf||'').split(/[\\\\/]/).pop();
    if (excel) links.innerHTML += `<p><a href="/download/${run}/${excel}">Download Excel</a></p>`;
    if (pdf)   links.innerHTML += `<p><a href="/download/${run}/${pdf}">Download PDF</a></p>`;
  } catch (e) { out.textContent = 'Request failed: ' + e; }
});
</script>
</body></html>
    """

# ---------- API ----------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/estimate")
async def estimate(
    image: UploadFile = File(...),
    mode: str = Form("all"),
    prices_json: str = Form("{}")
):
    run_id = str(uuid4())[:8]
    outdir: Path = config.RUNS_DIR / run_id
    outdir.mkdir(parents=True, exist_ok=True)

    # Save input
    in_path = outdir / image.filename
    with in_path.open("wb") as f:
        shutil.copyfileobj(image.file, f)

    # Optional price override (validate quickly)
    prices_path = outdir / "prices.override.json"
    try:
        json.loads(prices_json or "{}")
        prices_path.write_text(prices_json or "{}", encoding="utf-8")
    except Exception as ex:
        return JSONResponse(status_code=400, content={"error": f"prices_json invalid: {ex}"})

    cmd = [
        sys.executable, "src/main.py",
        "--input", str(in_path),
        "--prices", str(prices_path),
        "--mode", mode,
        "--outdir", str(outdir),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        artifacts = {
            "excel": str(next(outdir.glob("*.xlsx"), "")),
            "pdf":   str(next(outdir.glob("*.pdf"), "")),
            "dir":   str(outdir)
        }
        return {"ok": True, "run_id": run_id, "artifacts": artifacts, "log": proc.stdout}
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=500, content={"error": e.stderr or e.stdout})

@app.get("/download/{run_id}/{filename}")
def download(run_id: str, filename: str):
    path = config.RUNS_DIR / run_id / filename
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "file not found"})
    return FileResponse(path)

# Optional robots.txt
@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /"
