import os
from pathlib import Path

def env(key, default=None, cast=str):
    val = os.getenv(key, default)
    if val is None:
        return None
    if cast is int: return int(val)
    if cast is float: return float(val)
    if cast is bool: return str(val).lower() in ("1","true","yes","y","on")
    return val

BASE_DIR = Path(__file__).resolve().parent
APP_ENV  = env("APP_ENV", "dev")
PORT     = env("PORT", 8000, int)

RUNS_DIR = Path(env("RUNS_DIR", BASE_DIR / "runs"))
RUNS_DIR.mkdir(parents=True, exist_ok=True)

TESSERACT_CMD = env("TESSERACT_CMD", "")
OCR_LANG      = env("OCR_LANG", "eng")
PROJECT_LOGO  = env("PROJECT_LOGO", str(BASE_DIR / "data" / "logo.png"))
