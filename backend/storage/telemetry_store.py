"""In-Memory 24-Hour Sliding Telemetry Cache and Query Store.

Implements Layer 1 Telemetry Cache holding up to 144 records (24 hours at 10-minute resolution)
per turbine, with atomic disk persistence.

Source:
- docs/10_data_architecture.md §6
- docs/07_srs.md §3.1
"""

from collections import deque
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union

from backend.config import settings
from backend.data.schema import TelemetryRecord
from backend.storage.file_store import AtomicFileStore


class TelemetryStore:
    """Thread-safe in-memory sliding window telemetry cache with persistent disk backing."""

    def __init__(self, max_records_per_turbine: int = 144, file_store: Optional[AtomicFileStore] = None):
        self.max_records = max_records_per_turbine
        self.file_store = file_store or AtomicFileStore()
        self._lock = threading.RLock()
        # Mapping from turbine_id -> deque of TelemetryRecord
        self._cache: Dict[str, deque] = {}

    def add_record(self, record: TelemetryRecord) -> None:
        """Adds a single record to the turbine's sliding window cache."""
        with self._lock:
            if record.turbine_id not in self._cache:
                self._cache[record.turbine_id] = deque(maxlen=self.max_records)
            self._cache[record.turbine_id].append(record)

    def add_records(self, records: List[TelemetryRecord]) -> int:
        """Batch-adds a list of telemetry records to the sliding window cache."""
        with self._lock:
            for rec in records:
                self.add_record(rec)
            return len(records)

    def get_turbine_ids(self) -> List[str]:
        """Returns a sorted list of all active turbine identifiers in the cache."""
        with self._lock:
            return sorted(list(self._cache.keys()))

    def get_telemetry(self, turbine_id: str, limit: Optional[int] = None) -> List[TelemetryRecord]:
        """Retrieves time-series telemetry records for a specific turbine."""
        with self._lock:
            if turbine_id not in self._cache:
                return []
            records = list(self._cache[turbine_id])
            if limit and limit > 0:
                records = records[-limit:]
            return records

    def get_latest_record(self, turbine_id: str) -> Optional[TelemetryRecord]:
        """Retrieves the most recent telemetry record for a given turbine."""
        with self._lock:
            if turbine_id in self._cache and len(self._cache[turbine_id]) > 0:
                return self._cache[turbine_id][-1]
            return None

    def get_fleet_summary(self) -> Dict[str, Any]:
        """Calculates high-level aggregated operational metrics across all active turbines."""
        with self._lock:
            turbines = self.get_turbine_ids()
            if not turbines:
                return {
                    "total_turbines": 0,
                    "total_records_cached": 0,
                    "active_turbines": [],
                    "latest_timestamp": None,
                    "total_fleet_power_kw": 0.0,
                    "average_wind_speed_mps": 0.0,
                    "curtailed_turbines_count": 0
                }

            latest_records = [self.get_latest_record(t) for t in turbines]
            latest_records = [r for r in latest_records if r is not None]

            total_records = sum(len(self._cache[t]) for t in turbines)
            latest_power = sum(r.active_power for r in latest_records)
            curtailed_count = sum(1 for r in latest_records if r.is_curtailed)
            avg_wind = (sum(r.wind_speed for r in latest_records) / len(latest_records)) if latest_records else 0.0
            latest_ts = max((r.timestamp for r in latest_records), default=None)

            return {
                "total_turbines": len(turbines),
                "total_records_cached": total_records,
                "active_turbines": turbines,
                "latest_timestamp": latest_ts,
                "total_fleet_power_kw": round(latest_power, 2),
                "average_wind_speed_mps": round(avg_wind, 2),
                "curtailed_turbines_count": curtailed_count
            }

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        """Persists the current cache state to a JSON file atomically."""
        with self._lock:
            data = {
                turbine_id: [r.model_dump() for r in records]
                for turbine_id, records in self._cache.items()
            }
            return self.file_store.write_json_atomic(data, target_path)

    def load_from_disk(self, target_path: Union[str, Path]) -> int:
        """Loads telemetry cache from a JSON file."""
        with self._lock:
            data = self.file_store.read_json_safe(target_path)
            if not isinstance(data, dict):
                raise ValueError("Corrupted telemetry cache file format.")

            loaded_count = 0
            for turbine_id, rec_list in data.items():
                if turbine_id not in self._cache:
                    self._cache[turbine_id] = deque(maxlen=self.max_records)
                for item in rec_list:
                    rec = TelemetryRecord.model_validate(item)
                    self._cache[turbine_id].append(rec)
                    loaded_count += 1

            return loaded_count

    def clear(self) -> None:
        """Clears all cached telemetry data."""
        with self._lock:
            self._cache.clear()


# Global telemetry store singleton
telemetry_store = TelemetryStore(max_records_per_turbine=settings.SIMULATION.SLIDING_WINDOW_CACHE_SIZE)
