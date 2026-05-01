"""FastAPI application entrypoint for AgriGraph AI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router
from backend.api.state import load_state
from backend.pipeline.run_pipeline import run_pipeline

CONSTANTS: dict[str, Any] = {
    "APP_NAME": "AgriGraph AI API",
    "APP_VERSION": "0.1.0",
    "FRONTEND_ORIGIN": "http://localhost:5173",
}

FORECAST_WEIGHTS = Path(__file__).resolve().parent / "models" / "stgnn_forecast_weights.pt"
FORECAST_RESULTS = Path(__file__).resolve().parent / "data" / "forecast_2026_2036.csv"


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Run startup checks and cache API state once."""
    if not FORECAST_WEIGHTS.exists() or not FORECAST_RESULTS.exists():
        run_pipeline()
    app.state.cache = load_state()
    yield


app = FastAPI(
    title=CONSTANTS["APP_NAME"],
    version=CONSTANTS["APP_VERSION"],
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CONSTANTS["FRONTEND_ORIGIN"]],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return a uniform unexpected error payload."""
    return JSONResponse(status_code=500, content={"error": str(exc), "phase": "unknown"})


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a basic health status."""
    return {"status": "ok"}
