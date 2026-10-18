# InternRadar

InternRadar is an internship discovery and recommendation platform designed for students and early-career engineers. It aggregates internship listings directly from public applicant tracking systems (Greenhouse, Lever, Ashby), authorized feeds, and career portals, matching them against student skill profiles with an explainable scoring engine.

---

## Key Features

- **Direct ATS & Board Discovery:** Ingests public job listings from official career APIs (Greenhouse, Lever, Ashby) and permitted feeds without scraping restricted platforms.
- **Explainable Skill Matching:** Weighted multi-factor recommendation engine (`app/ai/matching.py`) that evaluates skills overlap, role relevance, location preference, and work type (remote/hybrid/onsite).
- **Authentication & Verification:** Secure JWT authentication with bcrypt password hashing, refresh tokens, and optional email OTP verification via SMTP/Brevo.
- **Application & Bookmark Tracking:** Save positions, track application lifecycle states (`applied`, `interviewing`, `offered`, `rejected`), and review application history.
- **Peer Student Network:** Connect with fellow students, discover mutual skills, and share application insights.
- **Lifecycle & Broken-Link Auditing:** Automated verification of listing availability via HTTP HEAD checks and closed-page pattern detection (`app/services/status.py`).

---

## Technology Stack

- **Backend:** Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/), [Pydantic v2](https://docs.pydantic.dev/), [Uvicorn](https://www.uvicorn.org/)
- **Database:** SQLite (default for development; compatible with PostgreSQL via `DATABASE_URL`)
- **Frontend:** [React 18](https://react.dev/), [TypeScript](https://www.typescriptlang.org/), [Vite](https://vitejs.dev/), [Tailwind CSS](https://tailwindcss.com/), [Lucide React](https://lucide.dev/)
- **Testing:** [pytest](https://docs.pytest.org/), pytest-asyncio, FastAPI TestClient

---

## Project Structure

```text
internradar/
├── app/                        # FastAPI application core
│   ├── ai/                     # Recommendation logic, skill ontologies, and matching algorithms
│   ├── models.py               # SQLAlchemy database models
│   ├── schemas.py              # Pydantic schemas and validation
│   ├── database.py             # Database engine and session management
│   ├── config.py               # Environment configuration settings
│   ├── deps.py                 # Dependency injection (authentication, db session)
│   ├── scheduler.py            # Background sync and health check tasks (APScheduler)
│   ├── routers/                # API route handlers
│   │   ├── auth.py             # Login, registration, password updates, email OTP
│   │   ├── internships.py      # Search, filter, and detail endpoints
│   │   ├── recommendations.py  # Profile-based candidate scoring
│   │   ├── saved.py            # Saved/bookmarked listings
│   │   ├── activity.py         # Application lifecycle tracking
│   │   ├── network.py          # Student directory and peer connections
│   │   ├── users.py            # Profile management and resume upload
│   │   └── admin.py            # Administrative import runs and diagnostics
│   └── services/               # Ingestion pipeline, source adapters, status checkers
├── data/                       # Seed files and company directories
├── docs/                       # Architectural documentation (AI_ENGINE.md)
├── frontend/                   # React + TypeScript + Vite single-page application
│   ├── src/                    # UI components, pages, context, and API client
│   ├── package.json            # Node.js dependencies and scripts
│   └── vite.config.ts          # Vite build and proxy configuration
├── scripts/                    # Maintenance and benchmark scripts
├── static/                     # Compiled frontend production bundle (served by FastAPI)
├── tests/                      # Automated test suite (88 unit and integration tests)
├── .env.example                # Documented configuration template
├── .gitignore                  # Git exclusion rules
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Python dependencies
└── sources.example.json        # ATS boards and source configuration template
```

---

## Getting Started (Local Setup)

### Prerequisites

- **Python 3.11+** installed (`python --version`)
- **Node.js 18+** and `npm` installed (`node --version`, `npm --version`)
- **Git** installed (`git --version`)

---

### 1. Backend Setup (Windows PowerShell)

From the project root directory (`internradar`):

```powershell
# Create and activate a Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Create your local environment configuration
Copy-Item .env.example .env
```

Open `.env` in your editor and configure your secrets (generate a strong `SECRET_KEY` and set `ADMIN_API_KEY`).

To start the FastAPI development server:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive API Documentation (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative Documentation (ReDoc):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

### 2. Frontend Setup & Build

The frontend is a React application built with Vite.

#### Running the Vite Development Server (Hot Reload)

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server will run on [http://localhost:5173](http://localhost:5173) and proxy API requests to `http://localhost:8000`.

#### Building for Production (Served Directly by FastAPI)

FastAPI automatically serves the compiled frontend assets from `static/`:

```powershell
cd frontend
npm install
npm run build
```

Once built, visiting [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser serves the complete application directly from FastAPI.

---

## Running Tests

InternRadar includes an automated test suite covering authentication, API routing, data discovery, normalization, and scoring logic:

```powershell
# Run the complete test suite
pytest

# Run matching regression benchmark
python scripts/benchmark_matching.py
```

---

## Configuration Reference

Key variables in `.env`:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./internradar.db` |
| `SECRET_KEY` | Hex secret used for JWT signature | (Set in `.env`) |
| `ADMIN_API_KEY` | Header key (`X-Admin-Key`) for admin routes | (Set in `.env`) |
| `ENABLE_SCHEDULER` | Run background board synchronization | `false` in dev |
| `SMTP_HOST` | SMTP server for OTP verification | Optional (Brevo/standard SMTP) |
| `SOURCES_FILE` | Ingestion source definitions | `sources.json` |

---

## Production Deployment Notes

1. **Database:** Use PostgreSQL in production by updating `DATABASE_URL=postgresql://user:password@host:5432/dbname`.
2. **Background Scheduler:** In multi-worker deployments (e.g., Gunicorn/Uvicorn `workers > 1`), ensure `ENABLE_SCHEDULER=true` is enabled on only one worker instance to prevent duplicate runs.
3. **CORS:** Restrict `CORS_ORIGINS` to your production frontend domains.
