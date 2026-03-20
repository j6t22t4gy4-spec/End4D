"""Organic4D Engine — FastAPI 앱 뼈대 (Phase 3.1)."""
from fastapi import FastAPI

app = FastAPI(title="Organic4D Engine", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
