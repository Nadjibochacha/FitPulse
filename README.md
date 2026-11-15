# FitPulse — Distributed Fitness-Tracking Backend & Real-Time Analytics

## Overview

**FitPulse** is a scalable, high-availability backend and live analytics dashboard architected for a multi-device fitness-tracking platform. The system ingests heterogeneous, rapidly evolving telemetry (workouts, meals, body metrics, GPS routes, heart-rate time series, and photo attachments) while maintaining **< 100 ms read/write latency** and surviving brief node failures without interrupting data ingestion.

## Architecture & Tech Stack

* **Database Layer:** **MongoDB (3-Node Replica Set)** orchestrated via Docker Compose (`mongo1`, `mongo2`, `mongo3`) for schema-less BSON storage, compound/geospatial indexing, tunable consistency, and automatic primary failover.

* **Backend & Ingestion Layer:** **FastAPI + Python (`pymongo`)** providing lightweight REST endpoints for polymorphic activity ingestion, high-frequency profile updates, and atomic streak counters.

* **Live Dashboard Layer:** **Streamlit + Plotly** reading live from the MongoDB replica set to visualize timelines, calorie aggregations, streak leaderboards, and schema heterogeneity.

* **Data Seeding & Benchmarking:** **Python (`Faker`, `pandas`, `requests`)** for multi-device synthetic telemetry generation and `< 100 ms` query latency verification.

```
[Wearable Devices / Seeder]
            │
            ▼  (JSON Payloads via REST / PyMongo)
   [FastAPI Backend Layer]
            │
            ▼  (Read/Write with Tunable Write Concern)
[MongoDB 3-Node Replica Set] ◄── Primary + 2 Secondaries (Auto-Failover)
            │
            ▼  (Indexed Queries & Aggregation Pipelines)
  [Streamlit Live Dashboard]

```

## Repository Structure

```
fitpulse/
├── docker-compose.yml        # 3-node MongoDB replica set & cluster initialization
├── requirements.txt          # Python dependencies (FastAPI, Streamlit, PyMongo, etc.)
├── api/                      # FastAPI ingestion, profile update & streak endpoints
├── data_generator/           # Index initialization & synthetic multi-device seeder
├── queries/                  # Mandatory queries (Q1–Q6) & < 100 ms benchmark scripts
├── dashboard/                # Live Streamlit web dashboard application
├── report/                   # Excalidraw architecture diagrams & academic PDF report
└── README.md

```

## Getting Started

### 1. Clone the Repository

```
git clone <your-github-repo-url>
cd fitpulse

```

### 2. Start the 3-Node MongoDB Replica Set

```
docker compose up -d

```

Verify that all three nodes (`mongo1`, `mongo2`, `mongo3`) are healthy and a primary node has been elected:

```
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, stateStr: m.stateStr}))"

```

### 3. Install Python Dependencies

```
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt

```

### 4. Seed Synthetic Data & Run Query Benchmarks

```
python data_generator/seed.py
python queries/run_queries.py

```

### 5. Start the FastAPI Backend & Streamlit Dashboard

Open two terminals inside your activated virtual environment:

* **Terminal 1 — FastAPI Backend:**

  ```
  fastapi dev api/main.py
  
  ```

* **Terminal 2 — Streamlit Live Dashboard:**

  ```
  streamlit run dashboard/app.py
  
  ```

## Mandatory Data & Query Patterns

| Query | Requirement | MongoDB & Backend Implementation | Target Latency | 
| ----- | ----- | ----- | ----- | 
| **Q1** | Polymorphic Workout Ingestion | Schema-less `insert_many()` / `POST /activities` accepting varied payloads (GPS routes, duration-only, photo attachments) across 3+ users. | `< 100 ms` | 
| **Q2** | Dynamic Recent Activity Feed | Indexed lookup on `{ user_id: 1, timestamp: -1 }` sorted descending and limited to 20 records without rigid schema assumptions. | `< 100 ms` | 
| **Q3** | High-Frequency Profile Updates | In-place atomic `update_one()` (`$set`) via `PATCH /users/{id}` supporting hundreds of daily updates to goals, weight, and contact info. | `< 100 ms` | 
| **Q4** | 24h Multi-City Detection | Aggregation pipeline grouping user workouts within 24-hour sliding windows where distinct `city` count $\ge 2$. | `< 100 ms` | 
| **Q5** | Daily Calorie-Burn Report | Aggregation pipeline grouping activities by `user_id` and calendar date (`$dateToString`) to sum daily calories burned. | `< 100 ms` | 
| **Q6** | Activity Streak Counter | Date-gap check + atomic `$inc` update on `current_streak` in the `users` collection upon activity ingestion. | `< 100 ms` | 

## Live Dashboard Views

1. **User Activity Timeline (`Q2`):** Interactive user selector displaying the last 20 activities with dynamic field rendering and live query execution time.

2. **Daily Calorie Burn (`Q5`):** Bar chart visualizing daily energy expenditure per user.

3. **Current Streak Leaderboard (`Q6`):** Real-time ranking of top users by consecutive active days.

4. **Schema Variety Explorer:** Live comparison table highlighting records with heterogeneous attributes (e.g., GPS coordinates vs. photo URLs vs. duration-only) plus a form to ingest new device schemas live.

## High-Availability & Node Failover Test

To verify uninterrupted write availability during a node failure:

1. Start continuous activity ingestion via the benchmark/ingestion script.

2. Stop the current primary container:

   ```
   docker stop mongo1
   
   ```

3. Observe automatic primary election among the remaining secondary nodes (`mongo2` / `mongo3`) and confirm zero dropped writes.

4. Restart the node when finished:

   ```
   docker start mongo1
   
   ```

## Team & Deliverables

* **Developers:** CHACHA MOHAMMED NADJIB & KERROUCHE FOUAD
