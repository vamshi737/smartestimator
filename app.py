from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from uuid import uuid4
from pathlib import Path
import shutil, subprocess, json, os
import config

app = FastAPI(title="SmartEstimator API", version="1.0")

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
    outdir = config.RUNS_DIR / run_id
    outdir.mkdir(parents=True, exist_ok=True)

    # Save input
    in_path = outdir / image.filename
    with in_path.open("wb") as f:
        shutil.copyfileobj(image.file, f)

    # Optional price override
    prices_path = outdir / "prices.override.json"
    prices_path.write_text(prices_json or "{}", encoding="utf-8")

    # Choose your CLI path here (adjust if you use src/)
    cli = "main.py" if Path("main.py").exists() else "src/main.py"
    cmd = ["python", cli, "--input", str(in_path), "--prices", str(prices_path),
           "--mode", mode, "--outdir", str(outdir)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        artifacts = {
            "excel": str(next(outdir.glob("*.xlsx"), "")),
            "pdf":   str(next(outdir.glob("*.pdf"), "")),
            "dir":   str(outdir)
        }
        return {"run_id": run_id, "artifacts": artifacts, "log": proc.stdout}
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=500, content={"error": e.stderr})

@app.get("/download/{run_id}/{filename}")
def download(run_id: str, filename: str):
    path = config.RUNS_DIR / run_id / filename
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "file not found"})
    return FileResponse(path)
