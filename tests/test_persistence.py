"""Unit Tests for Atomic Persistence and Telemetry Cache."""

import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import pytest

from backend.data.schema import TelemetryRecord
from backend.storage.file_store import AtomicFileStore
from backend.storage.telemetry_store import TelemetryStore


def test_atomic_json_write_and_read(file_store: AtomicFileStore, temp_dir: Path):
    """Verifies atomic write and safe read of JSON files."""
    json_path = temp_dir / "test_data.json"
    data = {"system": "WindGuard AI", "status": "active", "records": [1, 2, 3]}

    file_store.write_json_atomic(data, json_path)
    assert json_path.exists()

    loaded = file_store.read_json_safe(json_path)
    assert loaded == data


def test_atomic_csv_write_and_read(file_store: AtomicFileStore, temp_dir: Path):
    """Verifies atomic write and safe read of CSV files."""
    csv_path = temp_dir / "test_data.csv"
    df = pd.DataFrame({"turbine_id": ["WTG-01", "WTG-02"], "power": [1400.0, 1500.0]})

    file_store.write_csv_atomic(df, csv_path)
    assert csv_path.exists()

    loaded_df = file_store.read_csv_safe(csv_path)
    assert len(loaded_df) == 2
    assert list(loaded_df["turbine_id"]) == ["WTG-01", "WTG-02"]


def test_telemetry_store_sliding_window_144_records(clean_telemetry_store: TelemetryStore, valid_telemetry_dict):
    """Verifies that TelemetryStore enforces a sliding window max length of 144 records per turbine."""
    start_dt = datetime(2026, 9, 20, 0, 0, 0)
    # Feed 200 records
    for i in range(200):
        data = valid_telemetry_dict.copy()
        ts = (start_dt + timedelta(minutes=i * 10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["timestamp"] = ts
        data["active_power"] = 1000.0 + i
        rec = TelemetryRecord.model_validate(data)
        clean_telemetry_store.add_record(rec)

    records = clean_telemetry_store.get_telemetry("WTG-01")
    assert len(records) == 144
    # The oldest records (0 to 55) should have dropped off; first remaining should be i=56
    assert records[0].active_power == 1000.0 + 56
    assert records[-1].active_power == 1000.0 + 199


def test_telemetry_store_disk_persistence_and_reload(clean_telemetry_store: TelemetryStore, temp_dir: Path, valid_telemetry_dict):
    """Verifies persisting telemetry cache to disk and reloading it into a fresh store."""
    start_dt = datetime(2026, 9, 20, 12, 0, 0)
    for i in range(10):
        data = valid_telemetry_dict.copy()
        ts = (start_dt + timedelta(minutes=i * 10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["timestamp"] = ts
        rec = TelemetryRecord.model_validate(data)
        clean_telemetry_store.add_record(rec)

    persist_file = temp_dir / "telemetry_cache.json"
    clean_telemetry_store.save_to_disk(persist_file)
    assert persist_file.exists()

    # Fresh store
    new_store = TelemetryStore(max_records_per_turbine=144)
    loaded_count = new_store.load_from_disk(persist_file)

    assert loaded_count == 10
    recs = new_store.get_telemetry("WTG-01")
    assert len(recs) == 10
    assert recs[0].turbine_id == "WTG-01"


def test_concurrent_atomic_writes(file_store: AtomicFileStore, temp_dir: Path):
    """Verifies thread-safety and lock safety under concurrent writing."""
    target_path = temp_dir / "concurrent_log.json"

    def write_worker(worker_id: int):
        payload = {"worker": worker_id, "timestamp": f"2026-09-20T12:00:{worker_id:02d}Z"}
        file_store.write_json_atomic(payload, target_path)
        return worker_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(write_worker, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20
    # Final file must be valid readable JSON
    final_data = file_store.read_json_safe(target_path)
    assert "worker" in final_data
