import pytest
from app.models.schemas import MeterSummary, GeoCoordinates, EnergyReading
from app.services.meter_service import haversine_distance_km, parse_dd_mm_yyyy_hh_mm

def test_meter_summary_aliases():
    data = {
        "meterId": "J100000",
        "serialNo": "SE12345",
        "make": "Secure",
        "phaseType": "three",
        "installStatus": "Installed",
        "dtCode": "DT-001"
    }
    meter = MeterSummary(**data)
    assert meter.meter_id == "J100000"
    assert meter.serial_no == "SE12345"
    assert meter.phase_type == "three"
    assert meter.install_status == "Installed"
    assert meter.dt_code == "DT-001"

def test_haversine_distance():
    # Distance between Jaipur center (26.9124, 75.7873) and nearby point
    dist = haversine_distance_km(26.9124, 75.7873, 26.9200, 75.7900)
    assert 0.8 < dist < 1.2  # around 0.9 km

    # Zero distance for identical points
    assert haversine_distance_km(26.9124, 75.7873, 26.9124, 75.7873) == 0.0

def test_timestamp_parsing():
    parsed = parse_dd_mm_yyyy_hh_mm("23/06/2026 23:30")
    assert parsed == "2026-06-23T23:30:00+00:00"

    invalid = parse_dd_mm_yyyy_hh_mm("not-a-timestamp")
    assert invalid is None
