import os
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db


def update_user_streak_q6(user_id: str, activity_ts: datetime, db=None) -> dict[str, Any]:
    if db is None:
        db = get_db()

    users_col = db["users"]
    user = users_col.find_one(
        {"user_id": user_id},
        {"_id": 0, "current_streak": 1, "longest_streak": 1, "last_active_date": 1},
    )
    if not user:
        return {"updated": False, "reason": f"User {user_id} not found"}

    event_day = activity_ts.strftime("%Y-%m-%d")
    yesterday_day = (activity_ts - timedelta(days=1)).strftime("%Y-%m-%d")
    last_active = user.get("last_active_date")
    current_streak = user.get("current_streak", 0)
    longest_streak = user.get("longest_streak", 0)

    if last_active == event_day:
        new_streak = max(1, current_streak)
    elif last_active == yesterday_day:
        new_streak = current_streak + 1
    else:
        new_streak = 1

    new_longest = max(longest_streak, new_streak)

    users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "current_streak": new_streak,
                "longest_streak": new_longest,
                "last_active_date": event_day,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    return {
        "user_id": user_id,
        "current_streak": new_streak,
        "longest_streak": new_longest,
        "last_active_date": event_day,
    }


def get_streak_leaderboard_q6(limit: int = 10, db=None) -> tuple[list[dict[str, Any]], float]:
    if db is None:
        db = get_db()

    start = time.perf_counter()
    leaderboard = list(
        db["users"]
        .find(
            {},
            {
                "_id": 0,
                "user_id": 1,
                "name": 1,
                "fitness_goal": 1,
                "current_streak": 1,
                "longest_streak": 1,
                "last_active_date": 1,
            },
        )
        .sort([("current_streak", -1), ("longest_streak", -1)])
        .limit(limit)
    )
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return leaderboard, latency_ms


def ingest_activity_q1(payload: dict[str, Any], db=None) -> tuple[dict[str, Any], float]:
    if db is None:
        db = get_db()

    doc = dict(payload)
    doc.setdefault("activity_id", f"act_{uuid.uuid4().hex[:12]}")
    doc.setdefault("category", "workout")

    ts = doc.get("timestamp")
    if ts is None:
        ts = datetime.now(timezone.utc)
    elif isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    doc["timestamp"] = ts

    start = time.perf_counter()
    db["activities"].insert_one(doc)
    streak_info = update_user_streak_q6(doc["user_id"], ts, db=db)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    # Remove MongoDB internal ObjectId before returning JSON-safe dict
    doc.pop("_id", None)
    doc["timestamp"] = ts.isoformat()
    return {"activity": doc, "streak": streak_info}, latency_ms


def run_q1_ten_varied_workouts(db=None) -> dict[str, Any]:

    if db is None:
        db = get_db()

    now = datetime.now(timezone.utc)
    varied_workouts = [
        # User 1: 4 varied entries
        {
            "user_id": "user_001",
            "activity_type": "running",
            "device_type": "smartwatch_pro_v2",
            "city": "Constantine",
            "location": {"type": "Point", "coordinates": [6.6147, 36.3650]},
            "duration_minutes": 42,
            "calories": 480,
            "gps_route": [{"lon": 6.6147, "lat": 36.3650}, {"lon": 6.6182, "lat": 36.3679}],
            "heart_rate_series": [128, 145, 162, 158],
        },
        {
            "user_id": "user_001",
            "activity_type": "stretching",
            "device_type": "manual_entry",
            "duration_minutes": 20,
            "calories": 85,
        },
        {
            "user_id": "user_001",
            "activity_type": "hiking",
            "device_type": "mobile_app_ios",
            "city": "Constantine",
            "duration_minutes": 95,
            "calories": 640,
            "photos": [{"url": "https://cdn.fitpulse.local/photos/q1_hike_01.jpg", "caption": "Sidi M'Cid ridge"}],
        },
        {
            "user_id": "user_001",
            "activity_type": "cycling",
            "device_type": "smart_bike_meter_v3",  # Simulates a newly launched device schema
            "duration_minutes": 50,
            "calories": 530,
            "avg_power_watts": 215,
            "cadence_rpm": 88,
        },
        # User 2: 3 varied entries
        {
            "user_id": "user_002",
            "activity_type": "yoga",
            "device_type": "manual_entry",
            "duration_minutes": 35,
            "calories": 140,
        },
        {
            "user_id": "user_002",
            "activity_type": "running",
            "device_type": "mobile_app_android",
            "city": "Oran",
            "location": {"type": "Point", "coordinates": [-0.6331, 35.6971]},
            "duration_minutes": 30,
            "calories": 320,
            "photos": [
                {"url": "https://cdn.fitpulse.local/photos/q1_oran_1.jpg", "caption": "Waterfront 5K"},
                {"url": "https://cdn.fitpulse.local/photos/q1_oran_2.jpg", "caption": "Medal check-in"},
            ],
        },
        {
            "user_id": "user_002",
            "activity_type": "hiit",
            "device_type": "smartwatch_pro_v2",
            "duration_minutes": 25,
            "calories": 310,
            "heart_rate_series": [140, 172, 181, 165],
        },
        # User 3: 3 varied entries
        {
            "user_id": "user_003",
            "activity_type": "swimming",
            "device_type": "swim_band_x1",
            "duration_minutes": 45,
            "calories": 410,
            "pool_length_m": 50,
            "laps": 32,
        },
        {
            "user_id": "user_003",
            "activity_type": "walking",
            "device_type": "basic_band_lite",
            "duration_minutes": 40,
            "calories": 190,
        },
        {
            "user_id": "user_003",
            "activity_type": "cycling",
            "device_type": "smartwatch_pro_v2",
            "city": "Algiers",
            "location": {"type": "Point", "coordinates": [3.0588, 36.7538]},
            "duration_minutes": 60,
            "calories": 590,
            "gps_route": [{"lon": 3.0588, "lat": 36.7538}, {"lon": 3.0640, "lat": 36.7590}],
        },
    ]

    latencies = []
    for idx, workout in enumerate(varied_workouts):
        workout["timestamp"] = now - timedelta(minutes=idx * 5)
        _, ms = ingest_activity_q1(workout, db=db)
        latencies.append(ms)

    return {
        "inserted_count": len(varied_workouts),
        "target_users": ["user_001", "user_002", "user_003"],
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
        "max_latency_ms": max(latencies),
    }


def update_user_profile_q3(user_id: str, updates: dict[str, Any], db=None) -> tuple[dict[str, Any], float]:

    if db is None:
        db = get_db()

    allowed_fields = {"fitness_goal", "weight_kg", "height_cm", "phone", "email", "preferred_device"}
    clean_updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}
    clean_updates["updated_at"] = datetime.now(timezone.utc)

    start = time.perf_counter()
    result = db["users"].update_one({"user_id": user_id}, {"$set": clean_updates})
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return {
        "user_id": user_id,
        "matched": result.matched_count,
        "modified": result.modified_count,
        "updated_fields": list(clean_updates.keys()),
    }, latency_ms


def simulate_high_frequency_updates_q3(num_updates: int = 300, db=None) -> dict[str, Any]:
    if db is None:
        db = get_db()

    goals = ["Weight Loss", "Marathon Prep", "Muscle Gain", "General Fitness", "Endurance"]
    latencies = []

    for i in range(num_updates):
        uid = f"user_{(i % 25) + 1:03d}"
        payload = {
            "weight_kg": round(random.uniform(55.0, 95.0), 1),
            "fitness_goal": random.choice(goals),
            "phone": f"+213-555-{random.randint(100000, 999999)}",
        }
        _, ms = update_user_profile_q3(uid, payload, db=db)
        latencies.append(ms)

    return {
        "total_updates": num_updates,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
        "max_latency_ms": max(latencies),
    }


if __name__ == "__main__":
    database = get_db()

    print("Insert 10 Varied Workouts Across 3 Users")
    q1_stats = run_q1_ten_varied_workouts(database)
    print(q1_stats)

    print("\n300 High-Frequency User Profile Updates")
    q3_stats = simulate_high_frequency_updates_q3(300, database)
    print(q3_stats)

    print("\nTop 5 Streak Leaderboard")
    top_users, q6_ms = get_streak_leaderboard_q6(limit=5, db=database)
    print(f"Query latency: {q6_ms} ms")
    for rank, u in enumerate(top_users, start=1):
        print(f"#{rank} {u['user_id']} ({u['name']}): {u['current_streak']} days (best: {u['longest_streak']})")