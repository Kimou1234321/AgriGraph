"""FastAPI application entrypoint for AgriGraph AI."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from backend.api.auth_routes import router as auth_router
from backend.api.database import init_db
from backend.api.routes import router
from backend.api.simulation_routes import router as simulation_router
from backend.api.state import load_state
from backend.pipeline.run_pipeline import run_pipeline

CONSTANTS: dict[str, Any] = {
    "APP_NAME": "AgriGraph AI API",
    "APP_VERSION": "0.1.0",
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "FRONTEND_ORIGIN_ENV": "FRONTEND_ORIGIN",
}

FORECAST_WEIGHTS = Path(__file__).resolve().parent / "models" / "stgnn_forecast_weights.pt"
FORECAST_RESULTS = Path(__file__).resolve().parent / "data" / "forecast_2026_2036.csv"


def _frontend_origins() -> list[str]:
    """Return allowed CORS origins for cookie-based auth."""
    origin = os.getenv(CONSTANTS["FRONTEND_ORIGIN_ENV"], CONSTANTS["FRONTEND_ORIGIN"])
    return [origin]


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Run startup checks and cache API state once."""
    init_db()
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
    allow_origins=_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_api_caching(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Prevent browsers from serving stale JSON after pipeline or artifact updates."""
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


app.include_router(auth_router)
app.include_router(simulation_router)
app.include_router(router)


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return a uniform unexpected error payload."""
    return JSONResponse(status_code=500, content={"error": str(exc), "phase": "unknown"})


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a basic health status."""
    return {"status": "ok"}
