# Urja Meter Ops — Clean API Gateway Service

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Documentation](https://img.shields.io/badge/OpenAPI-3.1.0-6BA539.svg)](./openapi.json)
[![Tests](https://img.shields.io/badge/Tests-13%20Passed-brightgreen.svg)](./tests)

A production-ready, asynchronous RESTful API gateway built in front of the legacy **Urja Meter Ops** internal utility portal (`https://urja-ops.flockenergy.tech`).

This service reverse-engineers the portal's SvelteKit session protocol, CSRF defenses, and cryptographic HMAC export mechanisms to provide a clean, documented, strongly-typed JSON API for product and data engineering teams.

---

## ⚡ Quick Navigation

* 📖 **Reverse-Engineering Protocol Write-Up**: [PROTOCOL.md](./PROTOCOL.md) *(How the portal actually works under the hood)*
* 🧠 **Engineering Reflection & Self-Critique**: [REFLECTION.md](./REFLECTION.md) *(Assumptions, challenges, mistakes & lessons)*
* 📄 **OpenAPI 3.1 Specification**: [openapi.json](./openapi.json) *(Full machine-readable API contract)*
* 🌐 **Interactive Documentation**:
  * **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
  * **Scalar Reference**: [http://localhost:8000/scalar](http://localhost:8000/scalar)
  * **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* 📊 **Modern Web Client Dashboard**: [http://localhost:8000/ui](http://localhost:8000/ui) *(Interactive fleet analytics, charts, hierarchy tree & map)*

---

## 🎯 What Was Built

```
┌───────────────────────────────────────────────────────────────────────┐
│                          CONSUMERS / CLIENTS                          │
│     Product Teams  •  Data Pipelines  •  Modern Web Dashboard (/ui)   │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │ JSON HTTP (REST)
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     URJA API GATEWAY (FASTAPI)                        │
│                                                                       │
│  ┌───────────────────────┐  ┌──────────────────────────────────────┐  │
│  │   FastAPI Endpoints   │  │       In-Memory Index & Cache        │  │
│  │   • /api/v1/meters    │  │   • Multi-attribute indexing         │  │
│  │   • /api/v1/hierarchy │  │   • Haversine spatial proximity      │  │
│  │   • /api/v1/energy    │  │   • 7-tier hierarchy reconstruction  │  │
│  │   • /api/v1/stats     │  │   • TTL-based auto-synchronization   │  │
│  └───────────┬───────────┘  └──────────────────┬───────────────────┘  │
│              │                                 │                      │
│              └────────────────┬────────────────┘                      │
│                               ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                 UrjaClient (Session & Auth Engine)              │  │
│  │   • Better-Auth cookie manager with 120s buffer renewal         │  │
│  │   • SvelteKit Origin header injection (CSRF bypass)             │  │
│  │   • HMAC-SHA256 request signer for bulk export                  │  │
│  │   • Transparent 401 interceptor & automatic retry mutex         │  │
│  └────────────────────────────┬────────────────────────────────────┘  │
└───────────────────────────────┼───────────────────────────────────────┘
                                │ HTTP / JSON / Devalue
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                 UPSTREAM "URJA METER OPS" PORTAL                      │
│      (SvelteKit + Better-Auth + 403 CSRF Protection + 1h Cookie)      │
└───────────────────────────────────────────────────────────────────────┘
```

### Core Features:
1. **Full Smart Meter Directory**: Fast, paginated listing with multi-attribute filtering across Manufacturer (`make`), Phase (`single`/`three`), Status (`Installed`/`Faulty`/`Decommissioned`), Connection Type, and DT Code.
2. **Reconstructed 7-Tier Network Hierarchy**: Automatically aggregates meters into the utility's distribution tree: `Zone` → `Circle` → `Division` → `Subdivision` → `Substation` → `Feeder` → `Distribution Transformer (DT)`.
3. **Consumption & Voltage Analytics**: Granular 30-minute interval readings (kWh, kVAh, Voltage) with calculated net energy consumption deltas, voltage minimum/maximum/averages, and ISO 8601 timestamps.
4. **Geospatial Proximity Search**: Instant geodesic (Haversine) distance queries finding meters within $X$ km of any given latitude/longitude.
5. **Schema Reconciliation**: Transparently normalizes divergent `legacy` parameter arrays and modern `v2` escaped JSON class data into a unified dictionary.
6. **Robust Upstream Session Management**: Automatic authentication on startup, periodic cookie refresh, and transparent 401 retry handling so consumers never experience upstream token drops.
7. **Modern Web Client**: A rich single-page dashboard featuring KPI cards, manufacturer distribution doughnut charts, interactive filterable meter table, meter inspection drawer with Chart.js consumption curves, hierarchy tree view, and Leaflet.js spatial map!

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
* Python 3.10+ (tested on Python 3.11 and 3.12)
* `pip`

### 2. Clone Repository & Install Dependencies
```bash
git clone <repository_url>
cd Flock

# Optional: Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration (`.env`)
The service comes pre-configured with the default Urja credentials. To modify settings, create or edit `.env`:
```ini
# Portal Credentials
URJA_PORTAL_URL=https://urja-ops.flockenergy.tech
URJA_USERNAME=operator@urja.local
URJA_PASSWORD=urja-ops-2026

# Server Settings
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Cache & Sync Settings
CACHE_TTL_SECONDS=300
AUTO_SYNC_ON_STARTUP=true
SESSION_REFRESH_BUFFER_SECONDS=120
```

### 4. Run the Service
```bash
python run.py
```
*Alternatively, run with Uvicorn directly:*
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📡 Sample Requests & Usage

### 1. List & Filter Meters
```bash
# Search by query, filter by make and status
curl -X GET "http://localhost:8000/api/v1/meters?make=Secure&status=Installed&page=1&page_size=5"
```
**Sample Response:**
```json
{
  "items": [
    {
      "meterId": "J100003",
      "serialNo": "SE47035",
      "make": "Secure",
      "phaseType": "single",
      "installStatus": "Installed",
      "installType": "Whole Current",
      "build": "legacy",
      "dtCode": "DT-001",
      "geo": {
        "latitude": 26.93896,
        "longitude": 75.83095
      }
    }
  ],
  "total": 48,
  "page": 1,
  "page_size": 5,
  "total_pages": 10
}
```

### 2. Detailed Meter Metadata & Normalized Nameplate
```bash
curl -X GET "http://localhost:8000/api/v1/meters/J100000"
```
**Sample Response:**
```json
{
  "meterId": "J100000",
  "serialNo": "SE33962",
  "make": "HPL",
  "phaseType": "single",
  "installStatus": "Decommissioned",
  "installType": "Whole Current",
  "build": "legacy",
  "dtCode": "DT-001",
  "geo": {
    "latitude": 26.93896,
    "longitude": 75.83095
  },
  "hierarchy": {
    "zone": { "name": "Jaipur Zone 1", "code": "Z-01" },
    "circle": { "name": "Circle 1", "code": "C-01" },
    "division": { "name": "Division 1", "code": "D-01" },
    "subdivision": { "name": "Subdivision 1", "code": "SD-01" },
    "substation": { "name": "Substation 1", "code": "SS-01" },
    "feeder": { "name": "Feeder 1", "code": "F-001" },
    "dt": { "name": "Malviya Nagar DT 1", "code": "DT-001" }
  },
  "nameplate_attributes": {
    "Meter ID": "J100000",
    "Serial No": "SE33962",
    "Make": "HPL",
    "Phase Type": "single",
    "Installation Status": "Decommissioned",
    "Installation Type": "Whole Current"
  },
  "energy_summary": {
    "readings_count": 337,
    "kwh_consumption": 142.05,
    "min_voltage": 220.0,
    "max_voltage": 240.0,
    "avg_voltage": 229.8
  }
}
```

### 3. Consumption & Voltage Time-Series Readings
```bash
curl -X GET "http://localhost:8000/api/v1/meters/J100000/energy?limit=3"
```
**Sample Response:**
```json
{
  "meter_id": "J100000",
  "readings_count": 3,
  "summary": {
    "readings_count": 337,
    "kwh_consumption": 142.05,
    "min_voltage": 220.0,
    "max_voltage": 240.0,
    "avg_voltage": 229.8
  },
  "readings": [
    {
      "timestamp": "30/06/2026 23:00",
      "iso_timestamp": "2026-06-30T23:00:00+00:00",
      "kwh": 48580.36,
      "kvah": 52466.79,
      "volt_r": 230.0
    },
    {
      "timestamp": "30/06/2026 23:30",
      "iso_timestamp": "2026-06-30T23:30:00+00:00",
      "kwh": 48580.79,
      "kvah": 52467.25,
      "volt_r": 220.0
    }
  ]
}
```

### 4. Geospatial Proximity Search
```bash
# Find meters within 2.5 km of target coordinates
curl -X GET "http://localhost:8000/api/v1/meters/nearby?lat=26.9389&lng=75.8309&radius_km=2.5&limit=5"
```

### 5. Distribution Network Hierarchy Tree
```bash
curl -X GET "http://localhost:8000/api/v1/hierarchy"
```

### 6. Fleet Overview Statistics
```bash
curl -X GET "http://localhost:8000/api/v1/stats"
```

---

## 🧪 Running Automated Tests

A comprehensive test suite is included covering data models, coordinate math, hierarchy tree generation, API endpoints, and client authentication:

```bash
# Run tests with pytest
python -m pytest tests/ -v
```

Output:
```text
tests/test_api.py::test_list_meters PASSED
tests/test_api.py::test_filter_meters_by_make PASSED
tests/test_api.py::test_get_meter_detail PASSED
tests/test_api.py::test_get_meter_not_found PASSED
tests/test_api.py::test_get_stats PASSED
tests/test_api.py::test_nearby_meters PASSED
tests/test_client.py::test_hmac_signature_generation PASSED
tests/test_client.py::test_urja_client_initialization PASSED
tests/test_hierarchy.py::test_hierarchy_tree_reconstruction PASSED
tests/test_hierarchy.py::test_hierarchy_tree_handles_missing_data PASSED
tests/test_schemas.py::test_meter_summary_aliases PASSED
tests/test_schemas.py::test_haversine_distance PASSED
tests/test_schemas.py::test_timestamp_parsing PASSED
======================== 13 passed in 1.13s ========================
```

---

## 📂 Project Structure

```
Flock/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app configuration, lifespan, and static routing
│   ├── config.py                # Pydantic BaseSettings environment configuration
│   ├── client/
│   │   ├── __init__.py
│   │   └── urja_client.py       # Reverse-engineered async portal client with auth & HMAC signing
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic v2 schemas for meters, readings, and hierarchy
│   ├── services/
│   │   ├── __init__.py
│   │   ├── meter_service.py     # In-memory indexing, multi-attribute querying & proximity
│   │   └── hierarchy.py         # 7-tier distribution hierarchy reconstruction
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py         # RESTful API route definitions
│   └── static/
│       └── index.html           # Modern Web Client UI (Chart.js + Leaflet.js dashboard)
├── tests/
│   ├── __init__.py
│   ├── test_api.py              # API endpoint integration tests
│   ├── test_client.py           # HMAC signature and client logic unit tests
│   ├── test_hierarchy.py        # Network hierarchy reconstruction tests
│   └── test_schemas.py          # Coordinate math and model parsing tests
├── scripts/
│   └── generate_openapi.py      # Automated generator for openapi.json
├── openapi.json                 # Exported OpenAPI 3.1 specification
├── PROTOCOL.md                  # Comprehensive write-up of portal reverse engineering
├── REFLECTION.md                # Detailed engineering reflection & self-critique
├── requirements.txt             # Pinned Python package dependencies
├── run.py                       # Service entrypoint launcher
├── .env.example                 # Example configuration template
└── README.md                    # System documentation (you are here)
```

---

## ⚖️ Design Decisions & Trade-Offs

| Decision | Rationale | Trade-Off |
| :--- | :--- | :--- |
| **HMAC Bulk Export Ingestion** | The portal provides a cryptographically signed `/portal/export` endpoint that returns all 403 meters at once in ~200ms. | Requires reverse-engineering the HMAC-SHA256 signing algorithm rather than scraping HTML or crawling 21 search pages. |
| **In-Memory Query Indexing** | For 403 meters, in-memory filtering delivers sub-millisecond query responses and zero external database operational overhead. | In-memory indexing is bounded by RAM. At scale ($>500,000$ meters), this should be migrated to PostgreSQL + PostGIS. |
| **Automatic 401 Session Interceptor** | The upstream portal expires sessions after 1 hour (`Max-Age=3600`). Re-authenticating transparently prevents dropped requests. | Introduces a 200ms latency spike once every hour for whichever request triggers the renewal. |
| **Dual Schema Normalization** | The portal has two conflicting formats (`data` parameter array for legacy vs stringified JSON in `classData` for v2). | We reconcile both into a uniform `nameplate_attributes` dictionary, shielding consumers from upstream technical debt. |

---

## 🚫 What Was Intentionally Left Out & What We'd Improve Next

### Intentionally Skipped:
* **Direct Database Storage (PostgreSQL)**: With 403 smart meters and 40 transformers, requiring PostgreSQL or Docker would add unnecessary setup friction for reviewers. Python's in-memory data structures provide higher performance without infrastructure dependencies.
* **Write Operations (PUT/POST/DELETE on meters)**: As noted in the ground rules, the upstream portal represents an operational utility system and must be treated as strictly read-only.

### Next Steps with More Time:
* **Time-Series Engine (TimescaleDB / ClickHouse)**: For storing millions of 30-minute interval readings over multi-year spans and calculating complex feeder loss balances.
* **Proactive Webhooks & Anomaly Detection**: An alert engine detecting voltage sags ($<210\text{V}$), tamper indicators, or power outages and publishing events to webhooks.
* **PostGIS Native Spatial Indexing**: R-tree bounding box indexing for ultra-high-density urban meter grids.
