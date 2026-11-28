import os
import random
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db

try:
    from queries.queries import ingest_activity_q1
except ImportError:
    from queries.dev_a_queries import ingest_activity_q1

CITIES = {
    "Constantine": [6.6147, 36.3650],
    "Algiers": [3.0588, 36.7538],
    "Oran": [-0.6331, 35.6971],
    "Annaba": [7.7667, 36.9000],
    "Setif": [5.4137, 36.1898],
    "Batna": [6.1741, 35.5559],
}

_stop_event = threading.Event()
_state_lock = threading.Lock()

STREAM_STATE: dict[str, Any] = {
    "is_running": False,
    "events_ingested": 0,
    "target_events": 0,
    "avg_latency_ms": 0.0,
    "last_event": None,
    "started_at": None,
    "finished_at": None,
}


def generate_live_wearable_event(forced_user: str = None, forced_city: str = None) -> dict[str, Any]:
    """Build a single randomized polymorphic telemetry document."""
    user_id = forced_user or f"user_{random.randint(1, 25):03d}"
    city = forced_city or random.choice(list(CITIES.keys()))
    coords = CITIES[city]
    now = datetime.now(timezone.utc)

    profile = random.choice(["smartwatch", "smart_ring", "cycling_meter", "mobile_photo"])

    base = {
        "activity_id": f"live_{uuid.uuid4().hex[:10]}",
        "user_id": user_id,
        "timestamp": now,
        "category": "workout",
        "city": city,
        "location": {"type": "Point", "coordinates": coords},
    }

    if profile == "smartwatch":
        duration = random.randint(20, 75)
        return {
            **base,
            "activity_type": random.choice(["running", "hiit", "walking"]),
            "device_type": "smartwatch_pro_v2",
            "duration_minutes": duration,
            "calories": round(duration * random.uniform(8.0, 12.5)),
            "heart_rate_series": [random.randint(118, 178) for _ in range(6)],
            "gps_route": [
                {"lon": coords[0], "lat": coords[1]},
                {"lon": round(coords[0] + 0.002, 6), "lat": round(coords[1] + 0.002, 6)},
            ],
        }

    if profile == "smart_ring":
        # New schema variant showcasing zero-migration schema evolution
        return {
            **base,
            "category": "biometric_recovery",
            "activity_type": "recovery_scan",
            "device_type": "oura_ring_gen4",
            "hrv_ms": random.randint(38, 92),
            "spo2_pct": round(random.uniform(96.0, 99.8), 1),
            "skin_temp_delta_c": round(random.uniform(-0.4, 0.6), 2),
        }

    if profile == "cycling_meter":
        duration = random.randint(30, 90)
        return {
            **base,
            "activity_type": "cycling",
            "device_type": "garmin_rally_power",
            "duration_minutes": duration,
            "calories": round(duration * random.uniform(9.5, 14.0)),
            "avg_power_watts": random.randint(165, 285),
            "cadence_rpm": random.randint(78, 102),
            "elevation_gain_m": random.randint(120, 680),
        }

    # profile == "mobile_photo"
    duration = random.randint(25, 60)
    return {
        **base,
        "activity_type": "strength_training",
        "device_type": "mobile_app_ios",
        "duration_minutes": duration,
        "calories": round(duration * random.uniform(6.0, 9.5)),
        "photos": [
            {
                "url": f"https://cdn.fitpulse.local/photos/live_{uuid.uuid4().hex[:8]}.jpg",
                "caption": f"Live check-in from {city}",
            }
        ],
    }


def run_wearable_stream(
    duration_seconds: int = 30,
    interval_seconds: float = 0.5,
    include_multicity_anomaly: bool = True,
) -> None:
    """Ingest live wearable events at a steady interval until duration expires or stop is requested."""
    with _state_lock:
        if STREAM_STATE["is_running"]:
            return
        _stop_event.clear()
        total_steps = max(1, int(duration_seconds / max(0.1, interval_seconds)))
        STREAM_STATE.update(
            {
                "is_running": True,
                "events_ingested": 0,
                "target_events": total_steps,
                "avg_latency_ms": 0.0,
                "last_event": None,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
            }
        )

    db = get_db()
    latencies: list[float] = []

    try:
        for step in range(total_steps):
            if _stop_event.is_set():
                break

            # Inject a 2-city anomaly on steps 2 and 4 for live Q4 demonstration
            if include_multicity_anomaly and step == 1:
                payload = generate_live_wearable_event(forced_user="user_005", forced_city="Constantine")
            elif include_multicity_anomaly and step == 3:
                payload = generate_live_wearable_event(forced_user="user_005", forced_city="Algiers")
            else:
                payload = generate_live_wearable_event()

            res, latency_ms = ingest_activity_q1(payload, db=db)
            latencies.append(latency_ms)

            with _state_lock:
                STREAM_STATE["events_ingested"] = len(latencies)
                STREAM_STATE["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
                STREAM_STATE["last_event"] = {
                    "activity_id": res["activity"]["activity_id"],
                    "user_id": res["activity"]["user_id"],
                    "device_type": res["activity"]["device_type"],
                    "city": res["activity"].get("city"),
                    "streak": res["streak"].get("current_streak"),
                    "latency_ms": latency_ms,
                }

            time.sleep(max(0.1, interval_seconds))
    finally:
        with _state_lock:
            STREAM_STATE["is_running"] = False
            STREAM_STATE["finished_at"] = datetime.now(timezone.utc).isoformat()


def stop_wearable_stream() -> dict[str, Any]:
    """Signal the active background stream to stop gracefully."""
    _stop_event.set()
    with _state_lock:
        return dict(STREAM_STATE)


def get_stream_status() -> dict[str, Any]:
    """Return a thread-safe snapshot of the stream simulator state."""
    with _state_lock:
        return dict(STREAM_STATE)


if __name__ == "__main__":
    print("Starting 10-second CLI wearable stream test (1 event/sec)...")
    run_wearable_stream(duration_seconds=10, interval_seconds=1.0)
    print("Stream finished:", get_stream_status())