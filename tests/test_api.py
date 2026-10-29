import pytest
import pytest_asyncio
import httpx
from app.main import app
from app.services.meter_service import meter_service

@pytest_asyncio.fixture
async def client():
    # Pre-seed meter service with mock data to test endpoints independently of live network
    sample_data = [
        {
            "meterId": "TEST_001",
            "serialNo": "SN_001",
            "make": "HPL",
            "phaseType": "single",
            "installStatus": "Installed",
            "installType": "Whole Current",
            "build": "legacy",
            "dtCode": "DT-001",
            "hierarchy": {
                "zone": {"name": "Test Zone", "code": "Z-01"},
                "circle": {"name": "Test Circle", "code": "C-01"},
                "division": {"name": "Test Div", "code": "D-01"},
                "subdivision": {"name": "Test SubDiv", "code": "SD-01"},
                "substation": {"name": "Test Substation", "code": "SS-01"},
                "feeder": {"name": "Test Feeder", "code": "F-001"},
                "dt": {"name": "Test DT", "code": "DT-001"}
            },
            "geo": {"lat": 26.9124, "lng": 75.7873}
        },
        {
            "meterId": "TEST_002",
            "serialNo": "SN_002",
            "make": "Secure",
            "phaseType": "three",
            "installStatus": "Faulty",
            "installType": "CT Operated",
            "build": "v2",
            "dtCode": "DT-002",
            "hierarchy": {
                "zone": {"name": "Test Zone", "code": "Z-01"},
                "circle": {"name": "Test Circle", "code": "C-01"},
                "division": {"name": "Test Div", "code": "D-01"},
                "subdivision": {"name": "Test SubDiv", "code": "SD-01"},
                "substation": {"name": "Test Substation", "code": "SS-01"},
                "feeder": {"name": "Test Feeder", "code": "F-001"},
                "dt": {"name": "Test DT 2", "code": "DT-002"}
            },
            "geo": {"lat": 26.9200, "lng": 75.7900}
        }
    ]

    meter_service._raw_export_data = sample_data
    meter_service._meters_by_id = {m["meterId"]: m for m in sample_data}
    from datetime import datetime, timezone
    meter_service._last_sync = datetime.now(timezone.utc)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

@pytest.mark.asyncio
async def test_list_meters(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/meters")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["meterId"] == "TEST_001"

@pytest.mark.asyncio
async def test_filter_meters_by_make(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/meters?make=Secure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["make"] == "Secure"

@pytest.mark.asyncio
async def test_get_meter_detail(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/meters/TEST_001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meterId"] == "TEST_001"
    assert data["hierarchy"]["zone"]["code"] == "Z-01"

@pytest.mark.asyncio
async def test_get_meter_not_found(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/meters/NON_EXISTENT")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_get_stats(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_meters"] == 2
    assert data["by_status"]["Installed"] == 1
    assert data["by_status"]["Faulty"] == 1

@pytest.mark.asyncio
async def test_nearby_meters(client: httpx.AsyncClient):
    resp = await client.get("/api/v1/meters/nearby?lat=26.9124&lng=75.7873&radius_km=2.0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["meter"]["meterId"] == "TEST_001"
    assert data[0]["distance_km"] < 0.05
