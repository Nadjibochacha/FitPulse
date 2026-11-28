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
from queries.analytics_queries import (
    detect_multicity_24h_q4,
    get_daily_calorie_rollup_q5,
    get_recent_activities_q2,
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

@app.get("/users/{user_id}/activities")
def read_recent_activities(user_id: str, limit: int = 20):
    """Q2: Retrieve a user's last 20 polymorphic activities."""
    activities, latency_ms = get_recent_activities_q2(user_id=user_id, limit=limit)
    return {
        "user_id": user_id,
        "latency_ms": latency_ms,
        "count": len(activities),
        "activities": activities,
    }


@app.get("/analytics/multi-city")
def read_multicity_anomalies(window_hours: int = 24):
    """Q4: Flag users logging workouts in 2+ different cities within 24 hours."""
    flagged, latency_ms = detect_multicity_24h_q4(window_hours=window_hours)
    return {
        "window_hours": window_hours,
        "latency_ms": latency_ms,
        "flagged_count": len(flagged),
        "users": flagged,
    }


@app.get("/users/{user_id}/calories/daily")
def read_daily_calories(user_id: str, days: int = 14):
    """Q5: Daily calorie expenditure rollup for a user."""
    rollup, latency_ms = get_daily_calorie_rollup_q5(user_id=user_id, days=days)
    return {
        "user_id": user_id,
        "days": days,
        "latency_ms": latency_ms,
        "daily_rollup": rollup,
    }