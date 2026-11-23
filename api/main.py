import os
import sys
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from queries.queries import (
    get_streak_leaderboard_q6,
    ingest_activity_q1,
    run_q1_ten_varied_workouts,
    update_user_profile_q3,
)

app = FastAPI(
    title="FitPulse Ingestion & Profile API",
    description="High-availability FastAPI backend for polymorphic wearable telemetry.",
    version="1.0.0",
)


class ProfileUpdateRequest(BaseModel):
    fitness_goal: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    preferred_device: Optional[str] = None


@app.get("/health")
def health_check():
    db = get_db()
    db.client.admin.command("ping")
    return {
        "status": "healthy",
        "primary_node": str(db.client.primary),
    }


@app.post("/activities")
def create_activity(payload: dict[str, Any]):

    if "user_id" not in payload:
        raise HTTPException(status_code=400, detail="Missing required field: user_id")

    result, latency_ms = ingest_activity_q1(payload)
    return {
        "status": "ingested",
        "latency_ms": latency_ms,
        **result,
    }


@app.post("/activities/demo-q1")
def trigger_q1_demo():
    stats = run_q1_ten_varied_workouts()
    return {"status": "completed", **stats}


@app.patch("/users/{user_id}")
def patch_user_profile(user_id: str, body: ProfileUpdateRequest):
    result, latency_ms = update_user_profile_q3(user_id, body.model_dump(exclude_none=True))
    if result["matched"] == 0:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return {
        "status": "updated",
        "latency_ms": latency_ms,
        **result,
    }


@app.get("/leaderboard")
def read_leaderboard(limit: int = 10):
    leaderboard, latency_ms = get_streak_leaderboard_q6(limit=limit)
    return {
        "latency_ms": latency_ms,
        "count": len(leaderboard),
        "leaderboard": leaderboard,
    }