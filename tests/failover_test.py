import os
import sys
import time
import uuid
from datetime import datetime, timezone

from pymongo import MongoClient, WriteConcern
from pymongo.errors import PyMongoError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import DB_NAME, MONGO_URI


def benchmark_write_concerns(samples: int = 50) -> None:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=15000, retryWrites=True)
    db = client[DB_NAME]

    col_w1 = db["activities"].with_options(write_concern=WriteConcern(w=1))
    col_maj = db["activities"].with_options(write_concern=WriteConcern(w="majority"))

    latencies_w1 = []
    latencies_maj = []

    for i in range(samples):
        doc = {
            "activity_id": f"cap_w1_{uuid.uuid4().hex[:10]}",
            "user_id": "user_001",
            "timestamp": datetime.now(timezone.utc),
            "category": "workout",
            "activity_type": "running",
            "device_type": "cap_benchmark",
            "duration_minutes": 15,
            "calories": 150,
        }
        t0 = time.perf_counter()
        col_w1.insert_one(doc)
        latencies_w1.append((time.perf_counter() - t0) * 1000)

    for i in range(samples):
        doc = {
            "activity_id": f"cap_maj_{uuid.uuid4().hex[:10]}",
            "user_id": "user_001",
            "timestamp": datetime.now(timezone.utc),
            "category": "workout",
            "activity_type": "running",
            "device_type": "cap_benchmark",
            "duration_minutes": 15,
            "calories": 150,
        }
        t0 = time.perf_counter()
        col_maj.insert_one(doc)
        latencies_maj.append((time.perf_counter() - t0) * 1000)

    # Clean up temporary benchmark records
    db["activities"].delete_many({"device_type": "cap_benchmark"})

    print("=== CAP Theorem Write Concern Benchmark (50 inserts each) ===")
    print(f"w=1 (Primary ack only)     -> avg: {sum(latencies_w1)/samples:.2f} ms | max: {max(latencies_w1):.2f} ms")
    print(f"w='majority' (2/3 nodes)   -> avg: {sum(latencies_maj)/samples:.2f} ms | max: {max(latencies_maj):.2f} ms\n")


def run_live_failover_test(total_writes: int = 60, interval_sec: float = 0.25) -> None:

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=15000, retryWrites=True, w="majority")
    col = client[DB_NAME]["activities"]

    client.admin.command("ping")
    initial_primary = client.primary
    print(f"=== Live Primary Failover Test (Initial Primary: {initial_primary}) ===")
    print("INSTRUCTIONS: When write #10 appears, run `docker stop mongo1` in a second terminal!\n")

    succeeded = 0
    failed = 0
    election_window_ms = 0.0
    new_primary = initial_primary

    for seq in range(1, total_writes + 1):
        doc = {
            "activity_id": f"failover_{seq}_{uuid.uuid4().hex[:8]}",
            "user_id": "user_001",
            "timestamp": datetime.now(timezone.utc),
            "category": "workout",
            "activity_type": "cycling",
            "device_type": "failover_probe",
            "duration_minutes": 20,
            "calories": 210,
        }

        t0 = time.perf_counter()
        try:
            col.insert_one(doc)
            latency_ms = (time.perf_counter() - t0) * 1000
            succeeded += 1
            current_primary = client.primary

            if current_primary != new_primary and current_primary is not None:
                new_primary = current_primary
                election_window_ms = latency_ms
                print(f"[Write #{seq:02d}] FAILOVER DETECTED! New Primary: {new_primary} | Recovery latency: {latency_ms:.2f} ms")
            else:
                print(f"[Write #{seq:02d}] OK -> Primary: {current_primary} | Latency: {latency_ms:.2f} ms")

        except PyMongoError as exc:
            failed += 1
            print(f"[Write #{seq:02d}] FAILED: {exc}")

        time.sleep(interval_sec)

    # Clean up probe records
    col.delete_many({"device_type": "failover_probe"})

    print("\n=== Failover Test Summary (Save for Report Section 5.3) ===")
    print(f"Initial Primary : {initial_primary}")
    print(f"Elected Primary : {new_primary}")
    print(f"Total Attempted : {total_writes}")
    print(f"Succeeded       : {succeeded} ({(succeeded/total_writes)*100:.1f}%)")
    print(f"Dropped Writes  : {failed}")
    if election_window_ms > 0:
        print(f"Failover Window : {election_window_ms:.2f} ms (handled transparently via retryWrites=True)")


if __name__ == "__main__":
    benchmark_write_concerns(samples=50)
    run_live_failover_test(total_writes=60, interval_sec=0.25)