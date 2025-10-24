# app.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, PlainTextResponse
from uuid import uuid4
from pathlib import Path
import shutil, subprocess, json, os, sys
import config

# Make sure RUNS dir exists
Path(config.RUNS_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SmartEstimator API", version="1.0")

# --- Simple landing page so / shows something useful ---
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>SmartEstimator AI</title>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;margin:32px;line-height:1.5}
    .card{max-width:720px;margin:auto;border:1px solid #e5e7eb;border-radius:14px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
    h1{margin:0 0 10px}
    label{display:block;margin:12px 0 6px}
    input,select,textarea,button{font:inherit}
    input[type=file],select,textarea{width:100%}
    button{margin-top:16px;padding:10px 16px;border:0;border-radius:10px;background:#111827;color:#fff;cursor:pointer}
    .log{white-space:pre-wrap;background:#1118270d;border:1px dashed #cbd5e1;padding:12px;border-radius:8px;margin-top:14px}
    .links a{display:inline-block;margin-right:12px}
    .muted{color:#64748b}
  </style>
</head>
<body>
  <div class="card">
    <h1>SmartEstimator AI</h1>
    <p class="muted">Upload a plan image, choose mode, and get Excel/PDF.</p>

    <form id="f">
      <label>Plan image</label>
      <input type="file" name="image" accept="image/*" required />

      <label>Mode</label>
      <select name="mode">
        <option value="all" selected>all (India + USA + reports)</option>
        <option value="india">india</option>
        <option value="usa">usa</option>
        <option value="both">both</option>
      </select>

      <label>Optional price overrides (JSON)</label>
      <textarea name="prices_json" rows="4" placeholder='{"cement_bag": 390, "steel_kg": 66}'></textarea>

      <button type="submit">Estimate</button>
    </form>

    <div id="out" class="log"></div>
    <div id="links" class="links"></div>

    <p class="muted" style="margin-top:18px">
      Health: <a href="/health" target="_blank">/health</a> • API: <code>POST /estimate</code>
    </p>
  </div>

<script>
const form = document.getElementById('f');
const out = document.getElementById('out');
const links = document.getElementById('links');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  out.textContent = 'Running estimation… (this can take ~10–60s)';
  links.innerHTML = '';

  const fd = new FormData(form);
  try {
    const res = await fetch('/estimate', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      out.textContent = 'Error: ' + (data.error || res.statusText);
      return;
    }
    out.textContent = 'OK • Run ID: ' + data.run_id;

    function fileName(p){ return p ? p.split(/[\\\\/]/).pop() : ''; }

    const run = data.run_id;
    const excel = fileName(data.artifacts.excel);
    const pdf   = fileName(data.artifacts.pdf);

    if (excel) {
      const a = document.createElement('a');
      a.href = `/download/${run}/${excel}`;
      a.textContent = 'Download Excel';
      links.appendChild(a);
    }
    if (pdf) {
      const a = document.createElement('a');
      a.href = `/download/${run}/${pdf}`;
      a.textContent = 'Download PDF';
      links.appendChild(a);
    }
  } catch (err) {
    out.textContent = 'Request failed: ' + err;
  }
});
</script>
</body>
</html>
    """

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

    # Optional price override
    prices_path = outdir / "prices.override.json"
    try:
        # validate JSON early (don’t crash pipeline later)
        json.loads(prices_json or "{}")
        prices_path.write_text(prices_json or "{}", encoding="utf-8")
    except Exception as ex:
        return JSONResponse(status_code=400, content={"error": f"prices_json invalid: {ex}"})

    # Always run our unified CLI
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

# Optional: simple robots.txt to avoid indexing
@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /"
