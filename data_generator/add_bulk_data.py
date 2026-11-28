import os
import random
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db, init_indexes

fake = Faker()

# 12 Algerian cities in GeoJSON [longitude, latitude] order
CITIES = {
    "Constantine": [6.6147, 36.3650],
    "Algiers": [3.0588, 36.7538],
    "Oran": [-0.6331, 35.6971],
    "Annaba": [7.7667, 36.9000],
    "Setif": [5.4137, 36.1898],
    "Batna": [6.1741, 35.5559],
    "Touggourt": [6.0580, 33.1053],
    "Ouargla": [5.3250, 31.9493],
    "Bejaia": [5.0843, 36.7559],
    "Tlemcen": [-1.3167, 34.8828],
    "Ghardaia": [3.6785, 32.4891],
    "Biskra": [5.7281, 34.8504],
}

GOALS = ["Weight Loss", "Marathon Prep", "Muscle Gain", "General Fitness", "Endurance", "Triathlon Prep"]
WORKOUT_TYPES = ["running", "cycling", "swimming", "hiit", "walking", "strength_training", "trail_running"]
DEVICE_PROFILES = [
    "smartwatch_pro_v2",
    "oura_ring_gen4",
    "garmin_rally_power",
    "mobile_app_ios",
    "mobile_app_android",
    "basic_band_lite",
]


def get_next_user_index(users_col) -> int:
    """Find the highest numeric suffix among existing `user_XXX` IDs."""
    max_idx = 0
    for uid in users_col.distinct("user_id"):
        match = re.match(r"^user_(\d+)$", str(uid))
        if match:
            max_idx = max(max_idx, int(match.group(1)))
    return max_idx + 1


def jitter_coords(base_coords: list[float], max_offset: float = 0.015) -> list[float]:
    """Slightly scatter coordinates (~1.5 km radius) around a city center for realistic $geoNear tests."""
    lon = round(base_coords[0] + random.uniform(-max_offset, max_offset), 6)
    lat = round(base_coords[1] + random.uniform(-max_offset, max_offset), 6)
    return [lon, lat]


def build_polymorphic_record(user_id: str, ts: datetime, forced_city: str = None) -> dict:
    """Generate a varied polymorphic activity document across 6 device/schema shapes."""
    variant = random.choices(
        [
            "smartwatch_telemetry",
            "smart_ring_recovery",
            "cycling_power_meter",
            "mobile_photo_checkin",
            "minimal_workout",
            "meal_or_metric",
        ],
        weights=[30, 15, 15, 15, 15, 10],
        k=1,
    )[0]

    city = forced_city or random.choice(list(CITIES.keys()))
    coords = jitter_coords(CITIES[city])

    base = {
        "activity_id": f"bulk_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "timestamp": ts,
    }

    if variant == "smartwatch_telemetry":
        duration = random.randint(20, 95)
        hr_series = [random.randint(115, 182) for _ in range(8)]
        return {
            **base,
            "category": "workout",
            "activity_type": random.choice(["running", "trail_running", "hiit"]),
            "device_type": "smartwatch_pro_v2",
            "city": city,
            "location": {"type": "Point", "coordinates": coords},
            "duration_minutes": duration,
            "distance_km": round(duration * random.uniform(0.13, 0.32), 2),
            "calories": round(duration * random.uniform(8.5, 13.0)),
            "heart_rate_series": hr_series,
            "avg_heart_rate": round(sum(hr_series) / len(hr_series)),
            "gps_route": [
                {"lon": coords[0], "lat": coords[1], "offset_sec": 0},
                {"lon": round(coords[0] + 0.0025, 6), "lat": round(coords[1] + 0.0020, 6), "offset_sec": 300},
            ],
        }

    if variant == "smart_ring_recovery":
        return {
            **base,
            "category": "biometric_recovery",
            "activity_type": "recovery_scan",
            "device_type": "oura_ring_gen4",
            "city": city,
            "location": {"type": "Point", "coordinates": coords},
            "hrv_ms": random.randint(35, 96),
            "spo2_pct": round(random.uniform(95.8, 99.9), 1),
            "skin_temp_delta_c": round(random.uniform(-0.5, 0.7), 2),
            "sleep_score": random.randint(62, 97),
        }

    if variant == "cycling_power_meter":
        duration = random.randint(35, 120)
        return {
            **base,
            "category": "workout",
            "activity_type": "cycling",
            "device_type": "garmin_rally_power",
            "city": city,
            "location": {"type": "Point", "coordinates": coords},
            "duration_minutes": duration,
            "distance_km": round(duration * random.uniform(0.35, 0.58), 2),
            "calories": round(duration * random.uniform(9.5, 14.5)),
            "avg_power_watts": random.randint(155, 295),
            "cadence_rpm": random.randint(75, 105),
            "elevation_gain_m": random.randint(80, 850),
        }

    if variant == "mobile_photo_checkin":
        duration = random.randint(25, 75)
        return {
            **base,
            "category": "workout",
            "activity_type": random.choice(["strength_training", "walking", "running"]),
            "device_type": random.choice(["mobile_app_ios", "mobile_app_android"]),
            "city": city,
            "location": {"type": "Point", "coordinates": coords},
            "duration_minutes": duration,
            "calories": round(duration * random.uniform(5.5, 10.0)),
            "photos": [
                {
                    "url": f"https://cdn.fitpulse.local/photos/{uuid.uuid4().hex[:10]}.jpg",
                    "caption": f"{city} session check-in",
                }
            ],
            "notes": fake.sentence(nb_words=7),
        }

    if variant == "minimal_workout":
        duration = random.randint(15, 60)
        return {
            **base,
            "category": "workout",
            "activity_type": random.choice(WORKOUT_TYPES),
            "device_type": "basic_band_lite",
            "duration_minutes": duration,
            "calories": round(duration * random.uniform(5.0, 9.0)),
        }

    # variant == "meal_or_metric"
    if random.random() < 0.5:
        return {
            **base,
            "category": "meal",
            "meal_type": random.choice(["breakfast", "lunch", "dinner", "post_workout"]),
            "calories_intake": random.randint(350, 900),
            "macros": {
                "protein_g": random.randint(20, 60),
                "carbs_g": random.randint(30, 100),
                "fat_g": random.randint(8, 35),
            },
        }
    return {
        **base,
        "category": "body_metric",
        "device_type": "smart_scale_s1",
        "weight_kg": round(random.uniform(52.0, 98.0), 1),
        "body_fat_pct": round(random.uniform(10.5, 29.0), 1),
        "resting_hr": random.randint(50, 75),
    }


def append_bulk_data(new_users_count: int = 35, new_activities_count: int = 5000) -> None:
    """Append new users and thousands of polymorphic records without deleting existing data."""
    db = get_db()
    init_indexes(db)

    users_col = db["users"]
    activities_col = db["activities"]

    start_idx = get_next_user_index(users_col)
    now = datetime.now(timezone.utc)

    new_users = []
    for offset in range(new_users_count):
        uid = f"user_{start_idx + offset:03d}"
        streak = random.choices([0, 1, 3, 5, 8, 12, 16], weights=[25, 20, 18, 15, 10, 7, 5], k=1)[0]
        last_active = (now - timedelta(days=0 if streak > 0 else random.randint(2, 12))).strftime("%Y-%m-%d")

        new_users.append(
            {
                "user_id": uid,
                "name": fake.name(),
                "email": f"{uid}@fitpulse.local",
                "phone": f"+213-6{random.randint(50, 99)}-{random.randint(100000, 999999)}",
                "home_city": random.choice(list(CITIES.keys())),
                "fitness_goal": random.choice(GOALS),
                "weight_kg": round(random.uniform(53.0, 97.0), 1),
                "height_cm": random.randint(156, 194),
                "preferred_device": random.choice(DEVICE_PROFILES),
                "current_streak": streak,
                "longest_streak": max(streak, random.randint(streak, streak + 14)),
                "last_active_date": last_active,
                "updated_at": now,
            }
        )

    if new_users:
        users_col.insert_many(new_users, ordered=False)

    all_user_ids = users_col.distinct("user_id")
    activities_batch = []

    for _ in range(new_activities_count):
        uid = random.choice(all_user_ids)
        ts = now - timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        activities_batch.append(build_polymorphic_record(uid, ts))

    # Inject extra Q4 multi-city 24h anomalies across the new Algerian cities
    if len(new_users) >= 3:
        u_south, u_coast, u_desert = new_users[0]["user_id"], new_users[1]["user_id"], new_users[2]["user_id"]
        extra_q4 = [
            (u_south, "Touggourt", now - timedelta(hours=7)),
            (u_south, "Ouargla", now - timedelta(hours=2)),
            (u_coast, "Bejaia", now - timedelta(hours=11)),
            (u_coast, "Algiers", now - timedelta(hours=4)),
            (u_desert, "Ghardaia", now - timedelta(hours=14)),
            (u_desert, "Biskra", now - timedelta(hours=3)),
        ]
        for uid, city_name, event_ts in extra_q4:
            activities_batch.append(build_polymorphic_record(uid, event_ts, forced_city=city_name))

    t0 = time.perf_counter()
    # Insert in 1,000-doc unordered chunks for fast replica set replication
    chunk_size = 1000
    for i in range(0, len(activities_batch), chunk_size):
        activities_col.insert_many(activities_batch[i : i + chunk_size], ordered=False)
    elapsed_sec = round(time.perf_counter() - t0, 2)

    print(f"Appended {len(new_users)} users (user_{start_idx:03d} -> user_{start_idx + new_users_count - 1:03d}).")
    print(f"Appended {len(activities_batch)} polymorphic activities across 12 cities in {elapsed_sec}s.")
    print(f"Database Totals -> Users: {users_col.count_documents({})} | Activities: {activities_col.count_documents({})}")


if __name__ == "__main__":
    append_bulk_data(new_users_count=35, new_activities_count=5000)