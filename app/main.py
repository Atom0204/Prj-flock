from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os

from app.api.endpoints import router as api_router
from app.client.urja_client import urja_client
from app.config import settings
from app.services.meter_service import meter_service

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("urja.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Urja Meter Ops Gateway API service...")
    if settings.auto_sync_on_startup:
        try:
            logger.info("Performing initial dataset synchronization from Urja portal...")
            await meter_service.sync_portal_data()
            logger.info("Initial sync completed successfully.")
        except Exception as e:
            logger.error(f"Initial sync warning: {e}. Service will retry on demand.")
    yield
    logger.info("Shutting down Urja Gateway service...")
    await urja_client.close()

app = FastAPI(
    title="Urja Meter Ops Gateway API",
    description="""
# Urja Meter Ops Clean API Service

A modern, high-performance RESTful API gateway built on top of the legacy **Urja Meter Ops** internal portal for electricity distribution utilities.

---

### Core Capabilities
* **Full Smart Meter Directory**: High-speed search, filtering (by manufacturer, phase, installation status, connection type), and sorting.
* **Network Hierarchy Reconstruction**: 7-tier utility distribution tree (`Zone` → `Circle` → `Division` → `Subdivision` → `Substation` → `Feeder` → `DT` → `Meters`).
* **Time-Series Consumption Analytics**: Granular 30-minute interval readings (kWh, kVAh, Voltage) with net consumption deltas and voltage stats.
* **Geospatial Proximity Search**: Instant geodesic (Haversine) distance queries finding meters near any latitude/longitude coordinate.
* **Distribution Transformers (DTs)**: Mapping transformers to feeder lines, kVA capacities, and connected meter counts.
* **Normalized Data Schemas**: Transparently reconciles divergent legacy attribute arrays and modern JSON nameplate specifications.
* **Resilient Upstream Session Management**: Automated HMAC authentication, CSRF bypass, token expiry detection, and transparent 401 re-authentication.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Enable CORS for programmatic consumers and frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(api_router)

# Mount Static Files directory if it exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root to UI dashboard."""
    return RedirectResponse(url="/ui")

@app.get("/scalar", include_in_schema=False, response_class=HTMLResponse)
async def scalar_docs():
    """Renders modern interactive Scalar API reference documentation."""
    return """
    <!doctype html>
    <html>
      <head>
        <title>Urja Gateway API - Scalar Reference</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚡</text></svg>">
      </head>
      <body>
        <script id="api-reference" data-url="/openapi.json"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    """

@app.get("/ui", include_in_schema=False, response_class=HTMLResponse)
async def web_client_ui():
    """Serves the modern web client dashboard."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>Urja Web Client UI</h1><p>Static index.html not found.</p>")
