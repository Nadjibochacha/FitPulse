import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from queries.analytics_queries import (
    detect_multicity_24h_q4,
    get_daily_calorie_rollup_q5,
    get_recent_activities_q2,
)
from queries.queries import (
    get_streak_leaderboard_q6,
    run_q1_ten_varied_workouts,
    simulate_high_frequency_updates_q3,
)


def run_full_benchmark() -> None:
    db = get_db()

    q1 = run_q1_ten_varied_workouts(db=db)
    _, q2_ms = get_recent_activities_q2("user_001", limit=20, db=db)
    q3 = simulate_high_frequency_updates_q3(100, db=db)
    q4_users, q4_ms = detect_multicity_24h_q4(window_hours=24, db=db)
    _, q5_ms = get_daily_calorie_rollup_q5("user_001", days=14, db=db)
    _, q6_ms = get_streak_leaderboard_q6(limit=10, db=db)

    rows = [
        ("Q1", "Polymorphic Workout Ingestion (avg/10)", q1["avg_latency_ms"]),
        ("Q2", "User Last 20 Activities Feed", q2_ms),
        ("Q3", "High-Frequency Profile Updates (avg/100)", q3["avg_latency_ms"]),
        ("Q4", f"Multi-City 24h Detection ({len(q4_users)} flagged)", q4_ms),
        ("Q5", "Daily Calorie Aggregation Rollup", q5_ms),
        ("Q6", "Per-User Streak Leaderboard", q6_ms),
    ]

    print("| Query | Description | Latency (ms) | Target (< 100 ms) |")
    print("| :--- | :--- | ---: | :---: |")
    for code, desc, ms in rows:
        status = "PASS" if ms < 100.0 else "FAIL"
        print(f"| {code} | {desc} | {ms:.2f} ms | {status} |")


if __name__ == "__main__":
    run_full_benchmark()