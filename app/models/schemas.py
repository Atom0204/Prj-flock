from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime

T = TypeVar("T")

class GeoCoordinates(BaseModel):
    latitude: float = Field(..., description="Latitude coordinate in WGS84 decimal degrees", examples=[26.93896])
    longitude: float = Field(..., description="Longitude coordinate in WGS84 decimal degrees", examples=[75.83095])

class HierarchyLevel(BaseModel):
    name: str = Field(..., description="Human-readable name of the hierarchy node", examples=["Jaipur Zone 1"])
    code: str = Field(..., description="Unique utility code for the node", examples=["Z-01"])

class MeterHierarchy(BaseModel):
    zone: Optional[HierarchyLevel] = None
    circle: Optional[HierarchyLevel] = None
    division: Optional[HierarchyLevel] = None
    subdivision: Optional[HierarchyLevel] = None
    substation: Optional[HierarchyLevel] = None
    feeder: Optional[HierarchyLevel] = None
    dt: Optional[HierarchyLevel] = Field(None, description="Distribution Transformer")

class MeterSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meter_id: str = Field(..., alias="meterId", description="Unique smart meter identifier", examples=["J100000"])
    serial_no: str = Field(..., alias="serialNo", description="Hardware serial number", examples=["SE33962"])
    make: str = Field(..., description="Meter manufacturer (e.g., HPL, Secure, Genus, L&T, Allied)", examples=["HPL"])
    phase_type: str = Field(..., alias="phaseType", description="Electrical phase configuration ('single' or 'three')", examples=["single"])
    install_status: str = Field(..., alias="installStatus", description="Operational status ('Installed', 'Decommissioned', 'Faulty')", examples=["Installed"])
    install_type: Optional[str] = Field(None, alias="installType", description="Installation connection type ('Whole Current', 'CT Operated')", examples=["Whole Current"])
    build: Optional[str] = Field(None, description="Internal telemetry schema build ('legacy' or 'v2')", examples=["legacy"])
    dt_code: Optional[str] = Field(None, alias="dtCode", description="Code of parent Distribution Transformer", examples=["DT-001"])
    geo: Optional[GeoCoordinates] = Field(None, description="Physical coordinates of the meter")

class EnergyReading(BaseModel):
    timestamp: str = Field(..., description="Raw timestamp from portal (DD/MM/YYYY HH:MM)", examples=["23/06/2026 23:30"])
    iso_timestamp: Optional[str] = Field(None, description="Normalized ISO 8601 UTC timestamp", examples=["2026-06-23T23:30:00Z"])
    kwh: float = Field(..., description="Cumulative Active Energy in kilowatt-hours (kWh)", examples=[48438.74])
    kvah: float = Field(..., description="Cumulative Apparent Energy in kilovolt-ampere-hours (kVAh)", examples=[52313.84])
    volt_r: float = Field(..., description="R-phase Voltage reading (V)", examples=[226.0])

class EnergySummary(BaseModel):
    readings_count: int = Field(..., description="Total number of logged energy readings available")
    latest_reading: Optional[EnergyReading] = None
    first_reading: Optional[EnergyReading] = None
    kwh_consumption: Optional[float] = Field(None, description="Net active energy consumption across logged interval (kWh)")
    min_voltage: Optional[float] = Field(None, description="Minimum recorded voltage (V)")
    max_voltage: Optional[float] = Field(None, description="Maximum recorded voltage (V)")
    avg_voltage: Optional[float] = Field(None, description="Average recorded voltage (V)")

class MeterDetail(MeterSummary):
    hierarchy: Optional[MeterHierarchy] = Field(None, description="Full electrical network hierarchy")
    nameplate_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Unified nameplate parameters parsed and normalized from legacy or v2 schemas"
    )
    energy_summary: Optional[EnergySummary] = Field(None, description="High-level consumption analytics")

class EnergyResponse(BaseModel):
    meter_id: str = Field(..., description="Meter identifier", examples=["J100000"])
    readings_count: int = Field(..., description="Total number of readings in this response")
    summary: EnergySummary = Field(..., description="Statistical summary over readings")
    readings: List[EnergyReading] = Field(..., description="Chronological series of consumption readings")

class DistributionTransformer(BaseModel):
    code: str = Field(..., description="Unique Distribution Transformer code", examples=["DT-001"])
    name: str = Field(..., description="Transformer location/asset name", examples=["Malviya Nagar DT 1"])
    feeder_code: str = Field(..., description="Parent feeder line code", examples=["F-001"])
    capacity_kva: float = Field(..., description="Rated transformer capacity in kVA", examples=[100.0])
    meter_count: int = Field(0, description="Number of connected meters")

class HierarchyTreeNode(BaseModel):
    id: str = Field(..., description="Unique code or composite key of node")
    name: str = Field(..., description="Display name of node")
    level: str = Field(..., description="Hierarchy tier ('zone', 'circle', 'division', 'subdivision', 'substation', 'feeder', 'dt')")
    meter_count: int = Field(0, description="Total meters connected underneath this node")
    children: List["HierarchyTreeNode"] = Field(default_factory=list, description="Child nodes in hierarchy")

class NearbyMeter(BaseModel):
    meter: MeterSummary = Field(..., description="Meter summary data")
    distance_km: float = Field(..., description="Geodesic distance from query coordinates in kilometers")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

class FleetStats(BaseModel):
    total_meters: int
    total_transformers: int
    by_status: Dict[str, int]
    by_make: Dict[str, int]
    by_phase: Dict[str, int]
    by_build: Dict[str, int]
    by_install_type: Dict[str, int]

class SyncResult(BaseModel):
    status: str
    synced_meters: int
    synced_transformers: int
    duration_ms: float
    timestamp: str

class HealthStatus(BaseModel):
    status: str = Field("ok", description="Overall service status ('ok', 'degraded', 'unhealthy')")
    portal_connected: bool = Field(..., description="Whether upstream Urja Meter Ops portal is reachable and authenticated")
    cached_meters: int = Field(..., description="Number of meters currently indexed in memory")
    cached_transformers: int = Field(..., description="Number of transformers indexed in memory")
    last_sync: Optional[str] = Field(None, description="ISO timestamp of last successful portal sync")
