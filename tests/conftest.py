"""Shared Pytest Fixtures for WindGuard AI Phase 1 Tests."""

import tempfile
from pathlib import Path
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from backend.data.dataset_loader import SCADADataLoader
from backend.data.preprocessor import SCADAPreprocessor
from backend.data.scada_generator import SCADASimulator
from backend.data.schema import TelemetryRecord
from backend.main import app
from backend.storage.file_store import AtomicFileStore
from backend.storage.telemetry_store import TelemetryStore


@pytest.fixture
def test_client() -> TestClient:
    """FastAPI test client fixture."""
    return TestClient(app)


@pytest.fixture
def preprocessor() -> SCADAPreprocessor:
    """SCADAPreprocessor instance fixture."""
    return SCADAPreprocessor()


@pytest.fixture
def data_loader(preprocessor: SCADAPreprocessor) -> SCADADataLoader:
    """SCADADataLoader instance fixture."""
    return SCADADataLoader(preprocessor=preprocessor)


@pytest.fixture
def simulator() -> SCADASimulator:
    """SCADASimulator instance fixture with deterministic seed."""
    return SCADASimulator(default_seed=42)


@pytest.fixture
def temp_dir() -> Path:
    """Temporary directory fixture for testing persistence."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def file_store() -> AtomicFileStore:
    """AtomicFileStore instance fixture."""
    return AtomicFileStore()


@pytest.fixture
def clean_telemetry_store(file_store: AtomicFileStore) -> TelemetryStore:
    """Isolated TelemetryStore fixture."""
    return TelemetryStore(max_records_per_turbine=144, file_store=file_store)


@pytest.fixture
def valid_telemetry_dict() -> Dict[str, Any]:
    """Sample valid telemetry record dictionary."""
    return {
        "timestamp": "2026-09-20T12:00:00Z",
        "turbine_id": "WTG-01",
        "wind_speed": 8.5,
        "wind_direction": 220.0,
        "ambient_temp": 30.0,
        "active_power": 1400.0,
        "reactive_power": 110.0,
        "rotor_speed": 14.2,
        "generator_speed": 1450.0,
        "gearbox_bearing_temp": 65.0,
        "generator_stator_temp": 72.0,
        "nacelle_temp": 35.0,
        "pitch_angle": 0.5,
        "is_curtailed": False,
        "operating_status": "Running"
    }


@pytest.fixture
def sample_telemetry_batch(valid_telemetry_dict: Dict[str, Any]) -> List[TelemetryRecord]:
    """Batch of 10 valid TelemetryRecord objects."""
    records = []
    for i in range(10):
        data = valid_telemetry_dict.copy()
        data["timestamp"] = f"2026-09-20T12:{i*10:02d}:00Z"
        data["active_power"] = 1400.0 + i * 10
        records.append(TelemetryRecord.model_validate(data))
    return records
