import asyncio
from datetime import datetime, timezone
import json
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from app.client.urja_client import urja_client, UrjaNotFoundError, UrjaClientError
from app.config import settings
from app.models.schemas import (
    DistributionTransformer,
    EnergyReading,
    EnergyResponse,
    EnergySummary,
    FleetStats,
    GeoCoordinates,
    HierarchyLevel,
    HierarchyTreeNode,
    MeterDetail,
    MeterHierarchy,
    MeterSummary,
    NearbyMeter,
    PaginatedResponse,
    SyncResult
)
from app.services.hierarchy import build_hierarchy_tree

logger = logging.getLogger("urja.service")

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in kilometers using Haversine formula."""
    r = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c

def parse_dd_mm_yyyy_hh_mm(ts_str: str) -> Optional[str]:
    """Converts portal's 'DD/MM/YYYY HH:MM' format to ISO 8601 string 'YYYY-MM-DDTHH:MM:00Z'."""
    try:
        dt = datetime.strptime(ts_str.strip(), "%d/%m/%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return None

class MeterService:
    """
    Core service coordinating the Urja client, local indexing, multi-attribute querying,
    geospatial filtering, and data normalization.
    """

    def __init__(self):
        self._meters_by_id: Dict[str, Dict[str, Any]] = {}
        self._raw_export_data: List[Dict[str, Any]] = []
        self._transformers: Dict[str, DistributionTransformer] = {}
        self._hierarchy_tree: List[HierarchyTreeNode] = []
        self._nameplate_cache: Dict[str, Dict[str, Any]] = {}
        self._last_sync: Optional[datetime] = None
        self._sync_lock = asyncio.Lock()

    @property
    def last_sync_time(self) -> Optional[str]:
        return self._last_sync.isoformat() if self._last_sync else None

    @property
    def total_indexed_meters(self) -> int:
        return len(self._meters_by_id)

    @property
    def total_indexed_transformers(self) -> int:
        return len(self._transformers)

    async def sync_portal_data(self) -> SyncResult:
        """
        Synchronizes the full dataset from Urja portal via HMAC-signed export
        and DT endpoint. Rebuilds the in-memory indexes and hierarchy tree.
        """
        async with self._sync_lock:
            start_time = time.time()
            logger.info("Starting synchronization with Urja portal...")

            # 1. Fetch full export via HMAC
            export_meters = await urja_client.get_full_export()

            # 2. Fetch all DTs
            dts_data = await urja_client.get_all_distribution_transformers()

            # Update DT dictionary
            new_transformers: Dict[str, DistributionTransformer] = {}
            for dt in dts_data:
                code = dt.get("code")
                if code:
                    new_transformers[code] = DistributionTransformer(
                        code=code,
                        name=dt.get("name") or code,
                        feeder_code=dt.get("feederCode") or "",
                        capacity_kva=float(dt.get("capacityKva") or 0.0),
                        meter_count=0
                    )

            # Update meter dictionary & count DT assignments
            new_meters: Dict[str, Dict[str, Any]] = {}
            for m in export_meters:
                m_id = m.get("meterId")
                if not m_id:
                    continue
                new_meters[m_id] = m
                dt_code = m.get("dtCode")
                if dt_code and dt_code in new_transformers:
                    new_transformers[dt_code].meter_count += 1

            # Rebuild hierarchy tree
            tree = build_hierarchy_tree(export_meters)

            # Atomic swap
            self._meters_by_id = new_meters
            self._raw_export_data = export_meters
            self._transformers = new_transformers
            self._hierarchy_tree = tree
            self._last_sync = datetime.now(timezone.utc)

            duration = round((time.time() - start_time) * 1000, 2)
            logger.info(f"Sync complete in {duration}ms: {len(new_meters)} meters, {len(new_transformers)} transformers.")

            return SyncResult(
                status="success",
                synced_meters=len(new_meters),
                synced_transformers=len(new_transformers),
                duration_ms=duration,
                timestamp=self._last_sync.isoformat()
            )

    async def ensure_synced(self):
        """Ensures index is populated; triggers sync if empty or TTL expired."""
        now = datetime.now(timezone.utc)
        needs_sync = False

        if not self._meters_by_id or not self._last_sync:
            needs_sync = True
        elif (now - self._last_sync).total_seconds() > settings.cache_ttl_seconds:
            needs_sync = True

        if needs_sync:
            await self.sync_portal_data()

    def _normalize_meter_summary(self, raw: Dict[str, Any]) -> MeterSummary:
        geo = None
        raw_geo = raw.get("geo")
        if raw_geo and raw_geo.get("lat") is not None and raw_geo.get("lng") is not None:
            try:
                geo = GeoCoordinates(
                    latitude=float(raw_geo["lat"]),
                    longitude=float(raw_geo["lng"])
                )
            except (ValueError, TypeError):
                pass

        return MeterSummary(
            meterId=raw.get("meterId", ""),
            serialNo=raw.get("serialNo", ""),
            make=raw.get("make", ""),
            phaseType=raw.get("phaseType", ""),
            installStatus=raw.get("installStatus", ""),
            installType=raw.get("installType"),
            build=raw.get("build"),
            dtCode=raw.get("dtCode"),
            geo=geo
        )

    async def get_meters(
        self,
        query: Optional[str] = None,
        make: Optional[str] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None,
        install_type: Optional[str] = None,
        build: Optional[str] = None,
        dt_code: Optional[str] = None,
        feeder_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "meter_id",
        sort_desc: bool = False
    ) -> PaginatedResponse[MeterSummary]:
        """Multi-attribute search, filtering, and pagination over meters index."""
        await self.ensure_synced()

        filtered = self._raw_export_data

        if query:
            q_lower = query.strip().lower()
            filtered = [
                m for m in filtered
                if q_lower in m.get("meterId", "").lower()
                or q_lower in m.get("serialNo", "").lower()
                or q_lower in m.get("make", "").lower()
                or q_lower in (m.get("dtCode") or "").lower()
            ]

        if make:
            m_lower = make.strip().lower()
            filtered = [m for m in filtered if m.get("make", "").lower() == m_lower]

        if phase:
            p_lower = phase.strip().lower()
            filtered = [m for m in filtered if m.get("phaseType", "").lower() == p_lower]

        if status:
            s_lower = status.strip().lower()
            filtered = [m for m in filtered if m.get("installStatus", "").lower() == s_lower]

        if install_type:
            it_lower = install_type.strip().lower()
            filtered = [m for m in filtered if (m.get("installType") or "").lower() == it_lower]

        if build:
            b_lower = build.strip().lower()
            filtered = [m for m in filtered if (m.get("build") or "").lower() == b_lower]

        if dt_code:
            dt_upper = dt_code.strip().upper()
            filtered = [m for m in filtered if (m.get("dtCode") or "").upper() == dt_upper]

        if feeder_code:
            f_upper = feeder_code.strip().upper()
            filtered = [
                m for m in filtered
                if (m.get("hierarchy", {}).get("feeder", {}).get("code") or "").upper() == f_upper
            ]

        # Sorting
        sort_key_map = {
            "meter_id": lambda x: x.get("meterId", ""),
            "serial_no": lambda x: x.get("serialNo", ""),
            "make": lambda x: x.get("make", ""),
            "phase": lambda x: x.get("phaseType", ""),
            "status": lambda x: x.get("installStatus", ""),
            "dt_code": lambda x: x.get("dtCode") or ""
        }
        key_fn = sort_key_map.get(sort_by, sort_key_map["meter_id"])
        filtered.sort(key=key_fn, reverse=sort_desc)

        total = len(filtered)
        total_pages = max(1, math.ceil(total / page_size))
        page = max(1, min(page, total_pages)) if total > 0 else 1

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = [self._normalize_meter_summary(m) for m in filtered[start_idx:end_idx]]

        return PaginatedResponse[MeterSummary](
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    async def get_meter_detail(self, meter_id: str) -> MeterDetail:
        """
        Retrieves complete meter details, merging export data, parsed hierarchy,
        nameplate parameters (normalized across legacy/v2), and optional energy summary.
        """
        await self.ensure_synced()

        raw = self._meters_by_id.get(meter_id)
        if not raw:
            try:
                geo = await urja_client.get_meter_geo(meter_id)
                if not geo:
                    raise UrjaNotFoundError(f"Meter {meter_id} not found.")
                await self.sync_portal_data()
                raw = self._meters_by_id.get(meter_id)
            except UrjaClientError:
                raise UrjaNotFoundError(f"Meter {meter_id} not found.")

        if not raw:
            raise UrjaNotFoundError(f"Meter {meter_id} not found.")

        # Build hierarchy model
        raw_h = raw.get("hierarchy") or {}
        hierarchy = MeterHierarchy(
            zone=HierarchyLevel(**raw_h["zone"]) if "zone" in raw_h and raw_h["zone"] else None,
            circle=HierarchyLevel(**raw_h["circle"]) if "circle" in raw_h and raw_h["circle"] else None,
            division=HierarchyLevel(**raw_h["division"]) if "division" in raw_h and raw_h["division"] else None,
            subdivision=HierarchyLevel(**raw_h["subdivision"]) if "subdivision" in raw_h and raw_h["subdivision"] else None,
            substation=HierarchyLevel(**raw_h["substation"]) if "substation" in raw_h and raw_h["substation"] else None,
            feeder=HierarchyLevel(**raw_h["feeder"]) if "feeder" in raw_h and raw_h["feeder"] else None,
            dt=HierarchyLevel(**raw_h["dt"]) if "dt" in raw_h and raw_h["dt"] else None,
        )

        # Nameplate attributes: parse and normalize
        nameplate = await self._get_normalized_nameplate(meter_id, raw)

        # Fetch recent energy summary
        energy_summary = None
        try:
            energy_resp = await self.get_meter_energy(meter_id, limit=50)
            energy_summary = energy_resp.summary
        except Exception as e:
            logger.debug(f"Energy summary unavailable for {meter_id}: {e}")

        summary_base = self._normalize_meter_summary(raw)

        return MeterDetail(
            meterId=summary_base.meter_id,
            serialNo=summary_base.serial_no,
            make=summary_base.make,
            phaseType=summary_base.phase_type,
            installStatus=summary_base.install_status,
            installType=summary_base.install_type,
            build=summary_base.build,
            dtCode=summary_base.dt_code,
            geo=summary_base.geo,
            hierarchy=hierarchy,
            nameplate_attributes=nameplate,
            energy_summary=energy_summary
        )

    async def _get_normalized_nameplate(self, meter_id: str, raw_export: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts nameplate attributes from the portal's SvelteKit page data.
        Handles both legacy (parameterName / parameterValue array) and v2 (JSON in classData).
        """
        if meter_id in self._nameplate_cache:
            return self._nameplate_cache[meter_id]

        attrs: Dict[str, Any] = {
            "Meter ID": raw_export.get("meterId"),
            "Serial No": raw_export.get("serialNo"),
            "Make": raw_export.get("make"),
            "Phase Type": raw_export.get("phaseType"),
            "Installation Status": raw_export.get("installStatus"),
            "Installation Type": raw_export.get("installType"),
            "Build": raw_export.get("build")
        }

        try:
            route_data = await urja_client.get_meter_route_data(meter_id)
            if route_data and "nodes" in route_data:
                nodes = route_data["nodes"]
                # SvelteKit devalue data format: nodes[2].data contains the payload
                if len(nodes) > 2 and nodes[2] and "data" in nodes[2]:
                    data_block = nodes[2]["data"]
                    # If data_block is a list of elements (devalue serialization format)
                    if isinstance(data_block, list):
                        for item in data_block:
                            if isinstance(item, dict):
                                # Check for v2 classData format
                                if "classData" in item:
                                    # string may be an index in devalue or direct string
                                    class_val = item["classData"]
                                    if isinstance(class_val, int) and class_val < len(data_block):
                                        json_str = data_block[class_val]
                                    else:
                                        json_str = class_val
                                    if isinstance(json_str, str):
                                        try:
                                            parsed = json.loads(json_str)
                                            installed = parsed.get("installed_meter", {})
                                            for k, v in installed.items():
                                                attrs[k] = v
                                        except Exception:
                                            pass
                                # Check for legacy parameterName format
                                elif "parameterName" in item and "parameterValue" in item:
                                    p_name_idx = item["parameterName"]
                                    p_val_idx = item["parameterValue"]
                                    p_name = data_block[p_name_idx] if isinstance(p_name_idx, int) and p_name_idx < len(data_block) else str(p_name_idx)
                                    p_val = data_block[p_val_idx] if isinstance(p_val_idx, int) and p_val_idx < len(data_block) else str(p_val_idx)
                                    attrs[str(p_name)] = p_val
        except Exception as e:
            logger.debug(f"Could not parse SSR nameplate for {meter_id}: {e}")

        self._nameplate_cache[meter_id] = attrs
        return attrs

    async def get_meter_energy(self, meter_id: str, limit: Optional[int] = None) -> EnergyResponse:
        """Fetches, cleans, and summarizes meter consumption readings."""
        raw_readings = await urja_client.get_meter_energy(meter_id)

        clean_readings: List[EnergyReading] = []
        voltages: List[float] = []

        for r in raw_readings:
            try:
                kwh = float(r.get("kwh", 0))
                kvah = float(r.get("kvah", 0))
                volt = float(r.get("voltR", 0))
                ts_raw = str(r.get("timestamp", ""))
                iso_ts = parse_dd_mm_yyyy_hh_mm(ts_raw)

                clean_readings.append(
                    EnergyReading(
                        timestamp=ts_raw,
                        iso_timestamp=iso_ts,
                        kwh=kwh,
                        kvah=kvah,
                        volt_r=volt
                    )
                )
                if volt > 0:
                    voltages.append(volt)
            except (ValueError, TypeError):
                continue

        summary = EnergySummary(readings_count=len(clean_readings))
        if clean_readings:
            summary.first_reading = clean_readings[0]
            summary.latest_reading = clean_readings[-1]
            summary.kwh_consumption = round(max(0.0, clean_readings[-1].kwh - clean_readings[0].kwh), 2)

            if voltages:
                summary.min_voltage = round(min(voltages), 1)
                summary.max_voltage = round(max(voltages), 1)
                summary.avg_voltage = round(sum(voltages) / len(voltages), 1)

        result_readings = clean_readings[-limit:] if limit and limit > 0 else clean_readings

        return EnergyResponse(
            meter_id=meter_id,
            readings_count=len(result_readings),
            summary=summary,
            readings=result_readings
        )

    async def find_nearby_meters(self, lat: float, lng: float, radius_km: float = 5.0, limit: int = 50) -> List[NearbyMeter]:
        """Finds all meters within radius_km using the Haversine distance index."""
        await self.ensure_synced()

        nearby: List[NearbyMeter] = []
        for m in self._raw_export_data:
            geo = m.get("geo")
            if not geo or geo.get("lat") is None or geo.get("lng") is None:
                continue
            try:
                m_lat = float(geo["lat"])
                m_lng = float(geo["lng"])
                dist = haversine_distance_km(lat, lng, m_lat, m_lng)
                if dist <= radius_km:
                    summary = self._normalize_meter_summary(m)
                    nearby.append(NearbyMeter(meter=summary, distance_km=round(dist, 3)))
            except (ValueError, TypeError):
                continue

        nearby.sort(key=lambda x: x.distance_km)
        return nearby[:limit]

    async def get_hierarchy_tree(self) -> List[HierarchyTreeNode]:
        """Returns the pre-computed distribution hierarchy tree."""
        await self.ensure_synced()
        return self._hierarchy_tree

    async def get_transformers(self, feeder_code: Optional[str] = None) -> List[DistributionTransformer]:
        """Returns all transformers with associated meter counts and feeder mappings."""
        await self.ensure_synced()
        dts = list(self._transformers.values())
        if feeder_code:
            f_code = feeder_code.strip().upper()
            dts = [dt for dt in dts if dt.feeder_code.upper() == f_code]
        dts.sort(key=lambda x: x.code)
        return dts

    async def get_fleet_stats(self) -> FleetStats:
        """Returns fleet-wide aggregates across manufacturers, statuses, phase types, and builds."""
        await self.ensure_synced()

        by_status: Dict[str, int] = {}
        by_make: Dict[str, int] = {}
        by_phase: Dict[str, int] = {}
        by_build: Dict[str, int] = {}
        by_install_type: Dict[str, int] = {}

        for m in self._raw_export_data:
            status = m.get("installStatus") or "Unknown"
            by_status[status] = by_status.get(status, 0) + 1

            make = m.get("make") or "Unknown"
            by_make[make] = by_make.get(make, 0) + 1

            phase = m.get("phaseType") or "Unknown"
            by_phase[phase] = by_phase.get(phase, 0) + 1

            build = m.get("build") or "Unknown"
            by_build[build] = by_build.get(build, 0) + 1

            install_type = m.get("installType") or "Unknown"
            by_install_type[install_type] = by_install_type.get(install_type, 0) + 1

        return FleetStats(
            total_meters=len(self._raw_export_data),
            total_transformers=len(self._transformers),
            by_status=by_status,
            by_make=by_make,
            by_phase=by_phase,
            by_build=by_build,
            by_install_type=by_install_type
        )

# Global singleton service
meter_service = MeterService()
