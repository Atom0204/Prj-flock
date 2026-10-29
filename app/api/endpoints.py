from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional

from app.client.urja_client import UrjaNotFoundError, UrjaClientError, urja_client
from app.models.schemas import (
    DistributionTransformer,
    EnergyResponse,
    FleetStats,
    GeoCoordinates,
    HealthStatus,
    HierarchyTreeNode,
    MeterDetail,
    MeterSummary,
    NearbyMeter,
    PaginatedResponse,
    SyncResult
)
from app.services.meter_service import meter_service

router = APIRouter(prefix="/api/v1", tags=["Urja Meter Operations"])

@router.get(
    "/meters",
    response_model=PaginatedResponse[MeterSummary],
    summary="List and filter smart meters",
    description="Retrieve a paginated list of smart meters with optional filtering across manufacturer, phase type, status, installation type, DT code, or feeder code."
)
async def list_meters(
    q: Optional[str] = Query(None, description="Free-text search query matching Meter ID, Serial Number, Make, or DT Code"),
    make: Optional[str] = Query(None, description="Filter by manufacturer (e.g., HPL, Secure, Genus, L&T, Allied)"),
    phase: Optional[str] = Query(None, description="Filter by electrical phase ('single' or 'three')"),
    status: Optional[str] = Query(None, description="Filter by installation status ('Installed', 'Decommissioned', 'Faulty')"),
    install_type: Optional[str] = Query(None, description="Filter by connection type ('Whole Current', 'CT Operated')"),
    build: Optional[str] = Query(None, description="Filter by portal telemetry build ('legacy' or 'v2')"),
    dt_code: Optional[str] = Query(None, description="Filter by Distribution Transformer code (e.g., DT-001)"),
    feeder_code: Optional[str] = Query(None, description="Filter by Feeder code (e.g., F-001)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("meter_id", description="Field to sort by ('meter_id', 'serial_no', 'make', 'phase', 'status', 'dt_code')"),
    sort_desc: bool = Query(False, description="Sort descending if true")
):
    try:
        return await meter_service.get_meters(
            query=q,
            make=make,
            phase=phase,
            status=status,
            install_type=install_type,
            build=build,
            dt_code=dt_code,
            feeder_code=feeder_code,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_desc=sort_desc
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to query meters: {str(e)}")

@router.get(
    "/meters/nearby",
    response_model=List[NearbyMeter],
    summary="Find meters near coordinates",
    description="Calculates great-circle distance (Haversine) from target latitude and longitude to find nearest meters within radius_km."
)
async def find_nearby(
    lat: float = Query(..., description="Latitude in decimal degrees", examples=[26.9389]),
    lng: float = Query(..., description="Longitude in decimal degrees", examples=[75.8309]),
    radius_km: float = Query(5.0, ge=0.1, le=50.0, description="Proximity search radius in kilometers"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return")
):
    try:
        return await meter_service.find_nearby_meters(lat=lat, lng=lng, radius_km=radius_km, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/meters/{meter_id}",
    response_model=MeterDetail,
    summary="Get detailed meter metadata",
    description="Returns consolidated meter information including nameplate parameters (normalized across legacy and v2 schemas), full distribution hierarchy path, and energy summary."
)
async def get_meter(meter_id: str):
    try:
        return await meter_service.get_meter_detail(meter_id)
    except UrjaNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meter '{meter_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/meters/{meter_id}/energy",
    response_model=EnergyResponse,
    summary="Get meter energy consumption readings",
    description="Returns time-series consumption readings (kWh, kVAh, Voltage) and analytical summary (net consumption delta, min/max/avg voltage)."
)
async def get_meter_energy(
    meter_id: str,
    limit: Optional[int] = Query(None, ge=1, description="Optional cap on number of recent readings to return")
):
    try:
        # First verify meter exists
        raw = meter_service._meters_by_id.get(meter_id)
        if not raw:
            try:
                await meter_service.get_meter_detail(meter_id)
            except UrjaNotFoundError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meter '{meter_id}' not found.")

        return await meter_service.get_meter_energy(meter_id, limit=limit)
    except HTTPException:
        raise
    except UrjaNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meter '{meter_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/meters/{meter_id}/geo",
    response_model=GeoCoordinates,
    summary="Get meter geospatial coordinates",
    description="Returns latitude and longitude coordinates for a specific meter."
)
async def get_meter_geo(meter_id: str):
    try:
        detail = await meter_service.get_meter_detail(meter_id)
        if not detail.geo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Geolocation coordinates not available for meter '{meter_id}'.")
        return detail.geo
    except HTTPException:
        raise
    except UrjaNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meter '{meter_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/transformers",
    response_model=List[DistributionTransformer],
    summary="List distribution transformers (DTs)",
    description="Returns all distribution transformers in the network with their parent feeder code, rated capacity, and active meter count."
)
async def list_transformers(
    feeder_code: Optional[str] = Query(None, description="Optional filter by feeder code (e.g., F-001)")
):
    try:
        return await meter_service.get_transformers(feeder_code=feeder_code)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/hierarchy",
    response_model=List[HierarchyTreeNode],
    summary="Get reconstructed network hierarchy",
    description="Returns the full 7-tier hierarchical distribution tree (Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT) with aggregated meter counts."
)
async def get_hierarchy():
    try:
        return await meter_service.get_hierarchy_tree()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/stats",
    response_model=FleetStats,
    summary="Get fleet overview metrics",
    description="Returns comprehensive fleet statistics across manufacturer, phase type, operational status, and schema builds."
)
async def get_stats():
    try:
        return await meter_service.get_fleet_stats()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post(
    "/sync",
    response_model=SyncResult,
    summary="Trigger portal data synchronization",
    description="Forces an immediate re-sync of all meter and transformer records from the Urja portal via HMAC export."
)
async def trigger_sync():
    try:
        return await meter_service.sync_portal_data()
    except UrjaClientError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to sync with upstream Urja portal: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Service and upstream health check",
    description="Checks local service health and verifies active authentication against the upstream Urja portal."
)
async def health_check():
    portal_ok = False
    try:
        await urja_client.search_meters(query="", page=1)
        portal_ok = True
    except Exception as e:
        logger.warning(f"Health check probe failed: {e}")
        portal_ok = False

    return HealthStatus(
        status="ok" if portal_ok else "degraded",
        portal_connected=portal_ok,
        cached_meters=meter_service.total_indexed_meters,
        cached_transformers=meter_service.total_indexed_transformers,
        last_sync=meter_service.last_sync_time
    )
