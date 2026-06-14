"""Saved simulation persistence API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.api.database import get_db
from backend.api.models import SavedSimulation, User

CONSTANTS: dict[str, Any] = {
    "ROUTER_PREFIX": "/api/simulations",
    "DEFAULT_PIPELINE_VERSION": "prototype-v1",
    "DEFAULT_HORIZON": 11,
}

router = APIRouter(prefix=CONSTANTS["ROUTER_PREFIX"], tags=["simulations"])


class SaveSimulationRequest(BaseModel):
    """Payload to persist a completed simulation."""

    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    scenarios: dict[str, dict[str, float]] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    horizon: int = CONSTANTS["DEFAULT_HORIZON"]


class SimulationSummary(BaseModel):
    """List item for saved simulations."""

    id: str
    name: str
    description: str | None
    horizon: int
    county_count: int
    uplift_final_year: float | None
    final_year: int | None
    created_at: str
    updated_at: str


class SimulationDetail(BaseModel):
    """Full saved simulation payload."""

    id: str
    name: str
    description: str | None
    scenarios: dict[str, dict[str, float]]
    result: dict[str, Any]
    horizon: int
    pipeline_version: str | None
    created_at: str
    updated_at: str


def _summary_from_model(row: SavedSimulation) -> SimulationSummary:
    """Build list summary including optional uplift metadata."""
    result = row.result_json or {}
    by_county = result.get("by_county", {})
    county_count = len(row.scenarios_json or {})
    uplift_final_year: float | None = None
    final_year: int | None = result.get("final_year")
    if isinstance(by_county, dict) and by_county:
        first_block = next(iter(by_county.values()))
        if isinstance(first_block, dict):
            uplift_final_year = float(first_block.get("uplift_final_year", 0.0))
    return SimulationSummary(
        id=str(row.id),
        name=row.name,
        description=row.description,
        horizon=row.horizon,
        county_count=county_count,
        uplift_final_year=uplift_final_year,
        final_year=int(final_year) if final_year is not None else None,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _detail_from_model(row: SavedSimulation) -> SimulationDetail:
    """Build full simulation detail response."""
    return SimulationDetail(
        id=str(row.id),
        name=row.name,
        description=row.description,
        scenarios=dict(row.scenarios_json or {}),
        result=dict(row.result_json or {}),
        horizon=row.horizon,
        pipeline_version=row.pipeline_version,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _get_owned_simulation(db: Session, user: User, simulation_id: uuid.UUID) -> SavedSimulation:
    """Load one simulation owned by the current user."""
    row = (
        db.query(SavedSimulation)
        .filter(SavedSimulation.id == simulation_id, SavedSimulation.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Saved simulation not found.")
    return row


@router.get("", response_model=list[SimulationSummary])
async def list_simulations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SimulationSummary]:
    """Return saved simulations for the authenticated user."""
    rows = (
        db.query(SavedSimulation)
        .filter(SavedSimulation.user_id == current_user.id)
        .order_by(SavedSimulation.updated_at.desc())
        .all()
    )
    return [_summary_from_model(row) for row in rows]


@router.post("", response_model=SimulationDetail)
async def save_simulation(
    payload: SaveSimulationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationDetail:
    """Persist a completed simulation for the authenticated user."""
    if not payload.scenarios:
        raise HTTPException(status_code=400, detail="scenarios cannot be empty.")
    if not payload.result:
        raise HTTPException(status_code=400, detail="result cannot be empty.")
    row = SavedSimulation(
        user_id=current_user.id,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        scenarios_json=payload.scenarios,
        result_json=payload.result,
        horizon=payload.horizon,
        pipeline_version=CONSTANTS["DEFAULT_PIPELINE_VERSION"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _detail_from_model(row)


@router.get("/{simulation_id}", response_model=SimulationDetail)
async def get_simulation(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationDetail:
    """Return one saved simulation owned by the authenticated user."""
    row = _get_owned_simulation(db, current_user, simulation_id)
    return _detail_from_model(row)


@router.delete("/{simulation_id}")
async def delete_simulation(
    simulation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete one saved simulation owned by the authenticated user."""
    row = _get_owned_simulation(db, current_user, simulation_id)
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": str(simulation_id)}
