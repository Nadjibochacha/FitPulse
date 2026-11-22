import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker

# Allow running directly via `python data_generator/seed.py` from repo root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db, init_indexes

fake = Faker()
random.seed(42)
Faker.seed(42)

CITIES = {
    "Constantine": [6.6147, 36.3650],   # [longitude, latitude]
    "Algiers": [3.0588, 36.7538],
    "Oran": [-0.6331, 35.6971],
    "Annaba": [7.7667, 36.9000],
    "Setif": [5.4137, 36.1898],
    "Batna": [6.1741, 35.5559],
}

GOALS = ["Weight Loss", "Marathon Prep", "Muscle Gain", "General Fitness", "Endurance"]
WORKOUT_TYPES = ["running", "cycling", "swimming", "hiit", "walking", "strength_training"]
DEVICE_PROFILES = ["smartwatch_pro_v2", "mobile_app_ios", "mobile_app_android", "basic_band_lite", "manual_entry"]


def generate_gps_route(base_coords: list[float], points: int = 8) -> list[dict]:
    """Generate a small sequence of GPS waypoints around a city's coordinates."""
    lon, lat = base_coords
    route = []
    for i in range(points):
        lon += random.uniform(-0.003, 0.003)
        lat += random.uniform(-0.003, 0.003)
        route.append({"lon": round(lon, 6), "lat": round(lat, 6), "offset_sec": i * 60})
    return route


def generate_heart_rate_series(samples: int = 12) -> list[int]:
    """Generate realistic BPM telemetry samples."""
    base_hr = random.randint(115, 145)
    return [max(75, min(195, base_hr + random.randint(-15, 25))) for _ in range(samples)]


def build_polymorphic_activity(user_id: str, ts: datetime, forced_city: str = None, forced_variant: str = None) -> dict:
    """Create a workout, meal, or body-metric document with deliberately varied fields."""
    variant = forced_variant or random.choices(
        ["workout_full_telemetry", "workout_photos", "workout_minimal", "meal", "body_metric"],
        weights=[35, 20, 25, 12, 8],
        k=1,
    )[0]

    base_doc = {
        "activity_id": f"act_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "timestamp": ts,
    }

    if variant == "workout_full_telemetry":
        city = forced_city or random.choice(list(CITIES.keys()))
        coords = CITIES[city]
        hr_series = generate_heart_rate_series()
        duration = random.randint(25, 95)
        return {
            **base_doc,
            "category": "workout",
            "activity_type": random.choice(["running", "cycling", "hiit"]),
            "device_type": "smartwatch_pro_v2",
            "city": city,
            "location": {"type": "Point", "coordinates": coords},
            "duration_minutes": duration,
            "distance_km": round(duration * random.uniform(0.12, 0.35), 2),
            "calories": round(duration * random.uniform(8.5, 13.0)),
            "gps_route": generate_gps_route(coords),
            "heart_rate_series": hr_series,
            "avg_heart_rate": round(sum(hr_series) / len(hr_series)),
            "max_heart_rate": max(hr_series),
        }

    if variant == "workout_photos":
        city = forced_city or random.choice(list(CITIES.keys()))
        coords = CITIES[city]
        duration = random.randint(30, 80)
        return {
            **base_doc,
            "category": "workout",
            "activity_type": random.choice(["running", "walking", "strength_training"]),
            "device_type": random.choice(["mobile_app_ios", "mobile_app_android"]),
            "city": city,
            "location": {"type": "Point", "coordinates": coords},
            "duration_minutes": duration,
            "calories": round(duration * random.uniform(6.0, 10.5)),
            "photos": [
                {
                    "url": f"https://cdn.fitpulse.local/photos/{uuid.uuid4().hex[:10]}.jpg",
                    "caption": random.choice(["Morning trail view", "Post-workout check-in", "New personal best"]),
                }
            ],
            "notes": fake.sentence(nb_words=8),
        }

    if variant == "workout_minimal":
        duration = random.randint(15, 60)
        return {
            **base_doc,
            "category": "workout",
            "activity_type": random.choice(WORKOUT_TYPES),
            "device_type": random.choice(["manual_entry", "basic_band_lite"]),
            "duration_minutes": duration,
            "calories": round(duration * random.uniform(5.0, 9.0)),
        }

    if variant == "meal":
        return {
            **base_doc,
            "category": "meal",
            "meal_type": random.choice(["breakfast", "lunch", "dinner", "snack"]),
            "food_items": random.sample(["Oats", "Grilled Chicken", "Brown Rice", "Eggs", "Almonds", "Banana", "Salmon"], k=3),
            "calories_intake": random.randint(320, 850),
            "macros": {
                "protein_g": random.randint(18, 55),
                "carbs_g": random.randint(25, 95),
                "fat_g": random.randint(8, 32),
            },
        }

    # variant == "body_metric"
    return {
        **base_doc,
        "category": "body_metric",
        "device_type": "smart_scale_s1",
        "weight_kg": round(random.uniform(54.0, 96.0), 1),
        "body_fat_pct": round(random.uniform(11.0, 28.0), 1),
        "resting_hr": random.randint(52, 74),
        "sleep_hours": round(random.uniform(5.5, 8.8), 1),
    }


def seed_database(num_users: int = 25, activities_per_user: int = 22) -> None:
    db = get_db()
    users_col = db["users"]
    activities_col = db["activities"]

    # Reset collections for clean, repeatable seeding
    users_col.delete_many({})
    activities_col.delete_many({})
    init_indexes(db)

    now = datetime.now(timezone.utc)
    users_batch = []
    activities_batch = []

    # Guaranteed active streaks for top users (Q6 showcase)
    preset_streaks = {"user_001": 14, "user_002": 9, "user_003": 11, "user_004": 6, "user_005": 8}

    for i in range(1, num_users + 1):
        user_id = f"user_{i:03d}"
        streak = preset_streaks.get(user_id, random.randint(0, 7))
        last_active = (now - timedelta(days=0 if streak > 0 else random.randint(2, 10))).strftime("%Y-%m-%d")

        users_batch.append(
            {
                "user_id": user_id,
                "name": fake.name(),
                "email": f"{user_id}@fitpulse.local",
                "phone": fake.phone_number(),
                "fitness_goal": random.choice(GOALS),
                "weight_kg": round(random.uniform(55.0, 95.0), 1),
                "height_cm": random.randint(158, 192),
                "preferred_device": random.choice(DEVICE_PROFILES),
                "current_streak": streak,
                "longest_streak": max(streak, random.randint(streak, streak + 10)),
                "last_active_date": last_active,
                "updated_at": now,
            }
        )

        # Generate consecutive streak workouts for streak users
        for day_offset in range(streak):
            streak_ts = now - timedelta(days=day_offset, hours=random.randint(1, 5))
            activities_batch.append(build_polymorphic_activity(user_id, streak_ts))

        # Generate historical varied activities over the past 14 days
        remaining = max(5, activities_per_user - streak)
        for _ in range(remaining):
            random_ts = now - timedelta(
                days=random.randint(0, 14),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            activities_batch.append(build_polymorphic_activity(user_id, random_ts))

    # Inject explicit Q4 test cases: same user logging workouts in 2 different cities within 24 hours
    q4_cases = [
        ("user_001", "Constantine", now - timedelta(hours=10)),
        ("user_001", "Algiers", now - timedelta(hours=3)),
        ("user_002", "Oran", now - timedelta(hours=18)),
        ("user_002", "Annaba", now - timedelta(hours=5)),
        ("user_007", "Setif", now - timedelta(hours=15)),
        ("user_007", "Batna", now - timedelta(hours=2)),
    ]
    for uid, city_name, event_ts in q4_cases:
        activities_batch.append(
            build_polymorphic_activity(
                user_id=uid,
                ts=event_ts,
                forced_city=city_name,
                forced_variant="workout_full_telemetry",
            )
        )

    users_col.insert_many(users_batch)
    activities_col.insert_many(activities_batch)

    print(f"Seeded {len(users_batch)} users and {len(activities_batch)} polymorphic activities.")
    print("Injected Q4 multi-city 24h test cases for: user_001, user_002, user_007.")


if __name__ == "__main__":
    seed_database()