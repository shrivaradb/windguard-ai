"""SCADA Dataset Loader and Ingestion Pipeline.

Supports ingestion from CSV, JSON, and in-memory tabular structures.
Enforces canonical schema standardization with backward-compatible alias parsing
and universal real-world dataset fuzzy matching.

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
from backend.data.real_data_pipeline import UniversalSCADAPipeline
from backend.data.schema import TelemetryRecord, ValidationSummary


class SCADADataLoader:
    """Ingests, standardizes, and validates SCADA telemetry streams."""

    def __init__(
        self,
        preprocessor: Optional[SCADAPreprocessor] = None,
        universal_pipeline: Optional[UniversalSCADAPipeline] = None
    ):
        self.preprocessor = preprocessor or SCADAPreprocessor()
        self.universal_pipeline = universal_pipeline or UniversalSCADAPipeline()

    def load_from_csv(
        self,
        file_path: Union[str, Path],
        use_universal: bool = False,
        custom_mapping: Optional[Dict[str, str]] = None,
        rated_power_kw_override: Optional[float] = None
    ) -> Tuple[List[TelemetryRecord], ValidationSummary]:
        """Loads and processes SCADA telemetry from a CSV file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"SCADA data file not found at: {path}")

        try:
            df = pd.read_csv(path)
        except Exception as err:
            raise ValueError(f"Failed to parse CSV file at {path}: {err}")

        if use_universal:
            records, summary, _ = self.universal_pipeline.process_dataframe(
                df,
                custom_mapping=custom_mapping,
                rated_power_kw_override=rated_power_kw_override
            )
            return records, summary

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
        """Standardizes column headers and delegates to SCADAPreprocessor with universal fallback."""
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

        # Check if canonical features exist; if not, use universal pipeline
        has_canonical = ("wind_speed" in df.columns and "active_power" in df.columns)
        if not has_canonical:
            records, summary, _ = self.universal_pipeline.process_dataframe(df)
            return records, summary

        # Try standard preprocessor
        records, summary = self.preprocessor.process_dataframe(df)
        if summary.accepted_records == 0 and len(df) > 0:
            # Fallback to universal pipeline for real datasets with missing non-critical channels
            records, summary, _ = self.universal_pipeline.process_dataframe(df)

        return records, summary

    def process_dataframe_universal(
        self,
        df: pd.DataFrame,
        custom_mapping: Optional[Dict[str, str]] = None,
        rated_power_kw_override: Optional[float] = None
    ) -> Tuple[List[TelemetryRecord], ValidationSummary, Dict[str, Any]]:
        """Directly invokes universal pipeline with custom mappings and turbine rating."""
        return self.universal_pipeline.process_dataframe(
            df,
            custom_mapping=custom_mapping,
            rated_power_kw_override=rated_power_kw_override
        )

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
