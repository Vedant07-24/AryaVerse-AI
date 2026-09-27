from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import json, time
from dotenv import load_dotenv
from .models import ExecuteRequest
from .openapi_engine import parse_spec, compact_spec
from .agent import run_agent

load_dotenv()
BASE = Path(__file__).resolve().parents[2]
app = FastAPI(title="Arya Verse AI", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
AUDIT = []

@app.get("/api/health")
async def health():
    return {"ok": True, "name": "Arya Verse AI"}

@app.post("/api/spec")
async def load_spec(source: str):
    try:
        spec = parse_spec(source)
        compact = compact_spec(spec)
        return {"spec": spec, "summary": compact}
    except Exception as e:
        raise HTTPException(400, f"Could not parse OpenAPI specification: {e}")

@app.post("/api/spec/upload")
async def upload_spec(file: UploadFile = File(...)):
    raw = (await file.read()).decode("utf-8", errors="ignore")
    try:
        spec = parse_spec(raw)
        return {"spec": spec, "summary": compact_spec(spec)}
    except Exception as e:
        raise HTTPException(400, f"Could not parse uploaded specification: {e}")

@app.post("/api/agent/run")
async def agent(req: ExecuteRequest):
    spec = req.spec
    if not spec:
        raise HTTPException(400, "Load an OpenAPI specification first.")
    started = time.time()
    result = await run_agent(req.goal, spec, req.auth, req.max_steps)
    event = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "goal": req.goal, "plan": result["plan"], "duration_ms": round((time.time()-started)*1000)}
    AUDIT.insert(0, event)
    return {**result, "audit_id": len(AUDIT), "duration_ms": event["duration_ms"]}

@app.get("/api/audit")
async def audit():
    return {"items": AUDIT[:50]}

@app.get("/api/demo-spec")
async def demo_spec():
    path = BASE / "sample_specs" / "demo_api.json"
    return json.loads(path.read_text(encoding="utf-8"))

frontend = BASE / "frontend"
app.mount("/assets", StaticFiles(directory=str(frontend)), name="assets")

@app.get("/")
async def root():
    return FileResponse(frontend / "index.html")
