import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db


def get_recent_activities_q2(
    user_id: str, limit: int = 20, db=None
) -> tuple[list[dict[str, Any]], float]:
    """
    Q2: Retrieve a user's last 20 activities sorted newest-first,
    regardless of differing document fields (polymorphic safe).
    """
    if db is None:
        db = get_db()

    start = time.perf_counter()
    cursor = (
        db["activities"]
        .find({"user_id": user_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    results = []
    for doc in cursor:
        if isinstance(doc.get("timestamp"), datetime):
            doc["timestamp"] = doc["timestamp"].isoformat()
        results.append(doc)

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return results, latency_ms

def detect_multicity_24h_q4(
    window_hours: int = 24, db=None
) -> tuple[list[dict[str, Any]], float]:
    """
    Q4: Identify users who logged workouts in two different cities
    within a 24-hour window.
    """
    if db is None:
        db = get_db()

    start = time.perf_counter()
    pipeline = [
        {"$match": {"city": {"$exists": True, "$ne": None}}},
        {"$sort": {"user_id": 1, "timestamp": 1}},
        {
            "$group": {
                "_id": "$user_id",
                "events": {
                    "$push": {
                        "city": "$city",
                        "timestamp": "$timestamp",
                        "activity_type": "$activity_type",
                    }
                },
            }
        },
        {"$match": {"events.1": {"$exists": True}}},
    ]

    flagged_users = []
    max_seconds = window_hours * 3600

    for row in db["activities"].aggregate(pipeline):
        events = row["events"]
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                diff_sec = (events[j]["timestamp"] - events[i]["timestamp"]).total_seconds()
                if diff_sec > max_seconds:
                    break
                if events[i]["city"] != events[j]["city"]:
                    flagged_users.append(
                        {
                            "user_id": row["_id"],
                            "city_1": events[i]["city"],
                            "time_1": events[i]["timestamp"].isoformat(),
                            "city_2": events[j]["city"],
                            "time_2": events[j]["timestamp"].isoformat(),
                            "hours_apart": round(diff_sec / 3600, 2),
                        }
                    )
                    break
            else:
                continue
            break

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return flagged_users, latency_ms

def get_daily_calorie_rollup_q5(
    user_id: str, days: int = 14, db=None
) -> tuple[list[dict[str, Any]], float]:
    """
    Q5: Generate a daily calorie expenditure rollup for a given user
    over the last N days.
    """
    if db is None:
        db = get_db()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    start = time.perf_counter()
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "category": "workout",
                "timestamp": {"$gte": cutoff},
            }
        },
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "total_calories_burned": {"$sum": {"$ifNull": ["$calories", 0]}},
                "total_duration_minutes": {"$sum": {"$ifNull": ["$duration_minutes", 0]}},
                "workout_count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "total_calories_burned": 1,
                "total_duration_minutes": 1,
                "workout_count": 1,
            }
        },
    ]

    daily_summary = list(db["activities"].aggregate(pipeline))
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return daily_summary, latency_ms

def find_nearby_workouts(
    lon: float,
    lat: float,
    radius_km: float = 10.0,
    activity_type: str | None = None,
    limit: int = 20,
    db=None,
) -> tuple[list[dict[str, Any]], float]:
    """
    Geospatial Search: Find workouts within `radius_km` of [lon, lat]
    using the 2dsphere index, ordered from nearest to farthest.
    """
    if db is None:
        db = get_db()

    match_filter: dict[str, Any] = {"category": "workout"}
    if activity_type:
        match_filter["activity_type"] = activity_type

    start = time.perf_counter()
    pipeline = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [lon, lat]},
                "distanceField": "distance_meters",
                "maxDistance": radius_km * 1000,
                "spherical": True,
                "query": match_filter,
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "activity_id": 1,
                "user_id": 1,
                "activity_type": 1,
                "device_type": 1,
                "city": 1,
                "location": 1,
                "duration_minutes": 1,
                "calories": 1,
                "timestamp": 1,
                "distance_km": {"$round": [{"$divide": ["$distance_meters", 1000]}, 3]},
            }
        },
    ]

    results = []
    for doc in db["activities"].aggregate(pipeline):
        if isinstance(doc.get("timestamp"), datetime):
            doc["timestamp"] = doc["timestamp"].isoformat()
        results.append(doc)

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return results, latency_ms