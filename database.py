import os
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://mongo1:27017,mongo2:27018,mongo3:27019/fitpulse?replicaSet=rs0",
)
DB_NAME = os.getenv("MONGO_DB_NAME", "fitpulse")


def get_client() -> MongoClient:
    """Return a MongoClient connected to the 3-node FitPulse replica set."""
    return MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
        retryWrites=True,
        w="majority",
    )


def get_db():
    """Return the FitPulse database instance."""
    client = get_client()
    return client[DB_NAME]


def init_indexes(db=None) -> None:
    """Create indexes supporting sub-100ms latency for Q2, Q3, Q4, Q5, and Q6."""
    if db is None:
        db = get_db()

    users = db["users"]
    activities = db["activities"]

    # Users collection indexes (Q3 profile updates & Q6 streak leaderboard)
    users.create_index([("user_id", pymongo.ASCENDING)], unique=True, name="idx_user_id_unique")
    users.create_index([("current_streak", pymongo.DESCENDING)], name="idx_user_streak_desc")

    # Activities collection indexes (Q2 recent timeline, Q4 24h multi-city, Q5 daily calories)
    activities.create_index(
        [("user_id", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
        name="idx_user_timestamp_desc",
    )
    activities.create_index(
        [("user_id", pymongo.ASCENDING), ("city", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)],
        name="idx_user_city_timestamp",
    )
    # 2dsphere automatically skips documents without a 'location' field (polymorphic safe)
    activities.create_index([("location", pymongo.GEOSPHERE)], name="idx_location_2dsphere")


if __name__ == "__main__":
    client = get_client()
    try:
        client.admin.command("ping")
        print(f"Connected to Replica Set. Current Primary: {client.primary}")
        database = client[DB_NAME]
        init_indexes(database)
        print("Users indexes:", list(database["users"].index_information().keys()))
        print("Activities indexes:", list(database["activities"].index_information().keys()))
    except ConnectionFailure as exc:
        print(f"Connection failed: {exc}")