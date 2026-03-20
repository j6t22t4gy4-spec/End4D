"""Organic4D Engine — FastAPI 앱 뼈대 (Phase 3.1)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_cors_origins
from app.api.worlds import router as worlds_router
from app.api.run import router as run_router
from app.api.snapshots import router as snapshots_router
from app.api.ws import router as ws_router
from app.api.inject import router as inject_router
from app.api.timeline import router as timeline_router

app = FastAPI(title="Organic4D Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(worlds_router)
app.include_router(run_router)
app.include_router(snapshots_router)
app.include_router(ws_router)
app.include_router(inject_router)
app.include_router(timeline_router)


@app.get("/health")
def health():
    return {"status": "ok"}
