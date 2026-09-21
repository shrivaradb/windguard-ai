"""SCADA Dataset Loader and Ingestion Pipeline.

Supports ingestion from CSV, JSON, and in-memory tabular structures.
Enforces canonical schema standardization with backward-compatible alias parsing.

Source:
- docs/07_srs.md §3.1 (SRS-DATA-01)
- docs/09_technical_design.md §2.1
- docs/10_data_architecture.md §4.1
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from backend.data.preprocessor import SCADAPreprocessor
from backend.data.schema import TelemetryRecord, ValidationSummary


class SCADADataLoader:
    """Ingests, standardizes, and validates SCADA telemetry streams."""

    def __init__(self, preprocessor: Optional[SCADAPreprocessor] = None):
        self.preprocessor = preprocessor or SCADAPreprocessor()

    def load_from_csv(self, file_path: Union[str, Path]) -> Tuple[List[TelemetryRecord], ValidationSummary]:
        """Loads and processes SCADA telemetry from a CSV file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"SCADA data file not found at: {path}")

        try:
            df = pd.read_csv(path)
        except Exception as err:
            raise ValueError(f"Failed to parse CSV file at {path}: {err}")

        return self.process_dataframe(df)

    def load_from_json(self, file_path: Union[str, Path]) -> Tuple[List[TelemetryRecord], ValidationSummary]:
        """Loads and processes SCADA telemetry from a JSON file (array of records)."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"SCADA data file not found at: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "records" in data:
                data = data["records"]
            if not isinstance(data, list):
                raise ValueError("JSON payload must be a list of telemetry records.")
            df = pd.DataFrame(data)
        except Exception as err:
            raise ValueError(f"Failed to parse JSON file at {path}: {err}")

        return self.process_dataframe(df)

    def load_from_dicts(self, records: List[Dict[str, Any]]) -> Tuple[List[TelemetryRecord], ValidationSummary]:
        """Loads and processes an in-memory list of telemetry dictionaries."""
        if not records:
            return [], ValidationSummary(
                total_records=0,
                accepted_records=0,
                rejected_records=0,
                interpolated_values_count=0,
                dropout_records_count=0,
                is_valid=True,
                issues=[]
            )
        df = pd.DataFrame(records)
        return self.process_dataframe(df)

    def process_dataframe(self, df: pd.DataFrame) -> Tuple[List[TelemetryRecord], ValidationSummary]:
        """Standardizes column headers and delegates to SCADAPreprocessor."""
        # 1. Normalize column headers: lowercase, trim, replace spaces with underscores
        df = df.copy()
        df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

        # 2. Map standard legacy aliases
        alias_map = {
            "curtailment_flag": "is_curtailed",
            "curtailment": "is_curtailed",
            "power": "active_power",
            "power_kw": "active_power",
            "windspeed": "wind_speed",
            "wind_speed_ms": "wind_speed",
            "ambient_temperature": "ambient_temp",
            "temp_ambient": "ambient_temp",
            "gearbox_temp": "gearbox_bearing_temp",
            "temp_gearbox_bearing": "gearbox_bearing_temp",
            "stator_temp": "generator_stator_temp",
            "temp_gen_stator": "generator_stator_temp",
            "pitch": "pitch_angle"
        }

        for old_col, new_col in alias_map.items():
            if old_col in df.columns and new_col not in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)

        return self.preprocessor.process_dataframe(df)

    def export_to_csv(self, records: List[TelemetryRecord], output_path: Union[str, Path]) -> Path:
        """Exports validated telemetry records to a CSV file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump() for r in records]
        df = pd.DataFrame(data)
        df.to_csv(path, index=False)
        return path

    def export_to_json(self, records: List[TelemetryRecord], output_path: Union[str, Path]) -> Path:
        """Exports validated telemetry records to a JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump() for r in records]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path
