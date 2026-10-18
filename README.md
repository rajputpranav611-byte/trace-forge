# TraceForge 🔍

Trace intelligence, blast radius visualization, and incident root cause analysis engine powered by **FalkorDB**.

Built for the **WeMakeDevs × FalkorDB Graph Hacks** hackathon.

---

## Architecture Overview

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide Icons (`/frontend`)
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, Uvicorn (`/backend`)
- **Database**: FalkorDB (in-memory graph database running via Docker on port 6379, UI on port 3000)
- **Containerization**: Docker Compose (`docker-compose.yml`)

---

## Prerequisites

1. **Docker & Docker Desktop** (running)
2. **Node.js** (v20+ or v22+) & **npm** (v10+)
3. **Python** (3.11+ or 3.14+)

---

## Quickstart (Local Development)

### 1. Start FalkorDB
If the container `traceforge-db` is not already running:
```bash
docker run --name traceforge-db -d -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```
*(Or use `docker-compose up falkordb -d`)*

### 2. Configure Environment
Copy [.env.example](file:///f:/SessionSmith/.env.example) to `.env`:
```bash
cp .env.example .env
```

### 3. Setup and Run Backend
In the project root:
```bash
# Create virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Run backend test suite
$env:PYTHONPATH = "backend"
pytest backend/tests -v

# Start FastAPI server (runs on http://localhost:8000)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Setup and Run Frontend
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
The frontend is accessible at **[http://localhost:5173](http://localhost:5173)**.

---

## Verifying Endpoints

- **Backend Liveness**: `GET http://localhost:8000/api/v1/health`
- **FalkorDB Connectivity Check**: `GET http://localhost:8000/api/v1/health/db`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **FalkorDB Web Visualizer**: `http://localhost:3000`
- **TraceForge Frontend Dashboard**: `http://localhost:5173`

---

## Running with Docker Compose (Full Stack)

To run the database, backend, and frontend together in containers:
```bash
docker compose up --build
```
