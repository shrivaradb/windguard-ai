"""Unit Tests for SCADA Dataset Loader and Ingestion Pipeline."""

from pathlib import Path
import pytest

from backend.config import settings
from backend.data.dataset_loader import SCADADataLoader


def test_load_from_benchmark_csv(data_loader: SCADADataLoader):
    """Verifies that the benchmark sample SCADA CSV file is ingested and validated."""
    csv_path = settings.PATHS.BENCHMARKS_DIR / "sample_scada.csv"
    assert csv_path.exists()

    records, summary = data_loader.load_from_csv(csv_path)
    assert len(records) == 10
    assert summary.total_records == 10
    assert summary.accepted_records == 10
    assert summary.rejected_records == 0
    # Check that curtailment_flag alias was correctly mapped to is_curtailed
    curtailed_recs = [r for r in records if r.is_curtailed]
    assert len(curtailed_recs) == 3


def test_load_from_json_and_export(data_loader: SCADADataLoader, temp_dir: Path, valid_telemetry_dict):
    """Verifies export to JSON and subsequent load from JSON."""
    records_in, _ = data_loader.load_from_dicts([valid_telemetry_dict])
    assert len(records_in) == 1

    json_file = temp_dir / "exported_telemetry.json"
    data_loader.export_to_json(records_in, json_file)
    assert json_file.exists()

    records_out, summary = data_loader.load_from_json(json_file)
    assert len(records_out) == 1
    assert records_out[0].turbine_id == "WTG-01"
    assert records_out[0].wind_speed == 8.5


def test_load_from_nonexistent_file(data_loader: SCADADataLoader):
    """Verifies FileNotFoundError when attempting to load a missing file."""
    with pytest.raises(FileNotFoundError):
        data_loader.load_from_csv("nonexistent_path_to_scada_file.csv")


def test_load_from_empty_dicts(data_loader: SCADADataLoader):
    """Verifies graceful handling of empty list."""
    records, summary = data_loader.load_from_dicts([])
    assert records == []
    assert summary.total_records == 0
