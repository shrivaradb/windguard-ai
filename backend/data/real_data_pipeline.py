"""Universal Real-World SCADA Data Ingestion & Preprocessing Pipeline for WindGuard AI.

Provides fuzzy/regex column header matching, flexible timestamp parsing,
physics-based smart fallbacks for missing optional channels, variable turbine capacity
auto-detection/scaling, and comprehensive data quality scorecards.
"""

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from backend.config import settings
from backend.data.schema import (
    OperatingStatus,
    TelemetryRecord,
    ValidationIssue,
    ValidationSummary,
)


# Canonical target channels required or optional for WindGuard AI
CANONICAL_CHANNELS = {
    "wind_speed": {
        "required": True,
        "description": "Wind speed (m/s)",
        "unit": "m/s",
        "default": 0.0,
        "patterns": [
            r"^(wind[_\s]?speed|wspd|ws|wind[_\s]?spd|v[_\s]?wind|wind[_\s]?velocity|speed|anemometer)([_\s]?(avg|mean|mps|ms|m_s))?$",
            r"wind[_\s]?speed",
            r"wspd",
            r"wind_spd",
            r"ws_avg",
        ]
    },
    "active_power": {
        "required": True,
        "description": "Active grid power (kW)",
        "unit": "kW",
        "default": 0.0,
        "patterns": [
            r"^(active[_\s]?power|power|power[_\s]?kw|p[_\s]?active|grid[_\s]?power|activepower|p[_\s]?act|generated[_\s]?power|wtg[_\s]?power|p[_\s]?kw|kw|mw)([_\s]?(avg|mean|kw|mw))?$",
            r"active[_\s]?power",
            r"power_kw",
            r"grid_power",
            r"p_avg",
        ]
    },
    "ambient_temp": {
        "required": False,
        "description": "Ambient temperature (°C)",
        "unit": "°C",
        "default": 25.0,
        "patterns": [
            r"^(ambient[_\s]?temp(erature)?|temp[_\s]?ambient|amb[_\s]?temp|amb[_\s]?t|temperature|external[_\s]?temp|t[_\s]?amb|outside[_\s]?temp|temp[_\s]?out)([_\s]?(avg|mean|c|deg|degc))?$",
            r"amb[_\s]?t",
            r"ambient[_\s]?temp",
            r"temp_ambient",
            r"amb_temp",
            r"t_ambient",
            r"outdoor_temp",
            r"outside_temp",
        ]
    },
    "gearbox_bearing_temp": {
        "required": False,
        "description": "Gearbox high-speed bearing temp (°C)",
        "unit": "°C",
        "default": None,
        "patterns": [
            r"^(gearbox[_\s]?(bearing[_\s]?)?temp(erature)?|temp[_\s]?gearbox([_\s]?bearing)?|gear[_\s]?oil[_\s]?temp|gear[_\s]?bearing[_\s]?temp|gb[_\s]?temp|gearbox[_\s]?oil[_\s]?temp|gb[_\s]?bearing[_\s]?temp|gear[_\s]?temp)([_\s]?(avg|mean|c|deg|degc))?$",
            r"gearbox.*temp",
            r"gb.*temp",
            r"gear.*temp",
        ]
    },
    "generator_stator_temp": {
        "required": False,
        "description": "Generator stator winding temp (°C)",
        "unit": "°C",
        "default": None,
        "patterns": [
            r"^(generator[_\s]?(stator[_\s]?)?temp(erature)?|stator[_\s]?temp|temp[_\s]?gen([_\s]?stator)?|gen[_\s]?temp|generator[_\s]?bearing[_\s]?temp|gen[_\s]?stator[_\s]?temp|generator[_\s]?temp|gen[_\s]?bearing[_\s]?temp)([_\s]?(avg|mean|c|deg|degc))?$",
            r"generator.*temp",
            r"stator.*temp",
            r"gen.*temp",
        ]
    },
    "pitch_angle": {
        "required": False,
        "description": "Blade pitch angle (°)",
        "unit": "°",
        "default": None,
        "patterns": [
            r"^(pitch[_\s]?angle|pitch|blade[_\s]?pitch|blade[_\s]?angle|pitch[_\s]?deg|pitch[_\s]?angle[_\s]?avg|pitch[_\s]?setpoint|blade1[_\s]?pitch|blade[_\s]?pitch[_\s]?angle)([_\s]?(avg|mean|deg))?$",
            r"pitch.*angle",
            r"blade.*pitch",
            r"pitch",
        ]
    },
    "rotor_speed": {
        "required": False,
        "description": "Rotor rotational speed (RPM)",
        "unit": "RPM",
        "default": None,
        "patterns": [
            r"^(rotor[_\s]?speed|rotor[_\s]?rpm|rot[_\s]?spd|rotor[_\s]?speed[_\s]?rpm|blade[_\s]?speed|hub[_\s]?speed|rotor[_\s]?velocity)([_\s]?(avg|mean|rpm))?$",
            r"rotor.*speed",
            r"rotor.*rpm",
            r"rot_spd",
        ]
    },
    "generator_speed": {
        "required": False,
        "description": "Generator rotational speed (RPM)",
        "unit": "RPM",
        "default": None,
        "patterns": [
            r"^(generator[_\s]?speed|gen[_\s]?speed|gen[_\s]?rpm|generator[_\s]?rpm|gen[_\s]?speed[_\s]?rpm)([_\s]?(avg|mean|rpm))?$",
            r"generator.*speed",
            r"gen.*speed",
            r"gen.*rpm",
        ]
    },
    "wind_direction": {
        "required": False,
        "description": "Wind direction (°)",
        "unit": "°",
        "default": 180.0,
        "patterns": [
            r"^(wind[_\s]?direction|wind[_\s]?dir|wdir|v[_\s]?dir|direction)([_\s]?(avg|mean|deg))?$",
            r"wind.*direction",
            r"wind.*dir",
            r"wdir",
        ]
    },
    "reactive_power": {
        "required": False,
        "description": "Reactive power (kVAR)",
        "unit": "kVAR",
        "default": 0.0,
        "patterns": [
            r"^(reactive[_\s]?power|q[_\s]?reactive|reactivepower|kvar|q[_\s]?kvar)([_\s]?(avg|mean|kvar))?$",
            r"reactive.*power",
            r"kvar",
        ]
    },
    "nacelle_temp": {
        "required": False,
        "description": "Nacelle internal temp (°C)",
        "unit": "°C",
        "default": 30.0,
        "patterns": [
            r"^(nacelle[_\s]?temp(erature)?|temp[_\s]?nacelle|internal[_\s]?temp|nacelle[_\s]?temperature)([_\s]?(avg|mean|c|deg))?$",
            r"nacelle.*temp",
        ]
    },
    "is_curtailed": {
        "required": False,
        "description": "Grid curtailment flag (bool)",
        "unit": "boolean",
        "default": False,
        "patterns": [
            r"^(is[_\s]?curtailed|curtailment|curtailment[_\s]?flag|curtailed|curtailment[_\s]?state|derated)$",
            r"curtail.*",
        ]
    },
    "turbine_id": {
        "required": False,
        "description": "Turbine identifier",
        "unit": "string",
        "default": "WTG-01",
        "patterns": [
            r"^(turbine[_\s]?id|turbine|wtg|wtg[_\s]?id|unit[_\s]?id|asset[_\s]?id|turbine[_\s]?name|device[_\s]?id|wind[_\s]?turbine)$",
            r"turbine.*id",
            r"wtg.*id",
            r"turbine",
        ]
    },
    "timestamp": {
        "required": False,
        "description": "Timestamp",
        "unit": "datetime",
        "default": None,
        "patterns": [
            r"^(timestamp|datetime|date[_\s]?time|time|date|ts|time[_\s]?stamp|date[_\s]?and[_\s]?time)$",
            r"time.*stamp",
            r"date.*time",
            r"timestamp",
        ]
    },
}


class UniversalSCADAPipeline:
    """Universal pipeline for parsing, standardizing, and enhancing real-world SCADA datasets."""

    def __init__(self, target_rated_power_kw: Optional[float] = None):
        self.target_rated_power_kw = target_rated_power_kw or settings.TURBINE.RATED_POWER_KW

    @staticmethod
    def clean_column_name(col: str) -> str:
        """Cleans and standardizes column string."""
        col_str = str(col).strip().lower()
        # Strip unit in parentheses e.g. "Wind Speed (m/s)" -> "wind speed"
        col_str = re.sub(r"\s*\([^)]*\)", "", col_str)
        # Strip square brackets e.g. "Power [kW]" -> "power"
        col_str = re.sub(r"\s*\[[^\]]*\]", "", col_str)
        # Replace non-alphanumeric with underscores
        col_str = re.sub(r"[^a-z0-9]+", "_", col_str).strip("_")
        return col_str

    @staticmethod
    def normalize_turbine_id(val: Any) -> str:
        """Normalizes arbitrary turbine identifiers to standard clean string (e.g. 'WTG-01', 'WTG-03')."""
        if val is None or pd.isna(val):
            return "WTG-01"

        val_str = str(val).strip()
        if not val_str or val_str.lower() in ("nan", "none", "null", ""):
            return "WTG-01"

        # 1. Check for parenthesized WTG/Turbine ID like "R80711 (WTG-01)" or "Wind Farm A (T-02)"
        paren_match = re.search(r"\(\s*([A-Za-z0-9_-]+)\s*\)", val_str)
        if paren_match:
            candidate = paren_match.group(1).strip()
            wtg_sub = re.search(r"(?:WTG|Turbine|T)[-_]?(\d+)", candidate, re.IGNORECASE)
            if wtg_sub:
                return f"WTG-{int(wtg_sub.group(1)):02d}"
            val_str = candidate

        # 2. Check for explicit WTG-xx, Turbine_xx, or Txx pattern
        turb_match = re.search(r"\b(?:WTG|Turbine|T)[-_]?(\d+)\b", val_str, re.IGNORECASE)
        if turb_match:
            num = int(turb_match.group(1))
            return f"WTG-{num:02d}"

        # 3. Check for pure integer/number
        if val_str.isdigit():
            num = int(val_str)
            return f"WTG-{num:02d}"

        # 4. Fallback: sanitize string, remove special chars, prefix WTG- if needed
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", val_str).strip("-")
        if not cleaned.upper().startswith("WTG") and not cleaned.upper().startswith("T"):
            cleaned = f"WTG-{cleaned}"
        return cleaned


    def auto_match_columns(self, raw_columns: List[str]) -> Dict[str, Dict[str, Any]]:
        """Matches raw CSV column headers to canonical SCADA channels with confidence scores."""
        matched: Dict[str, Dict[str, Any]] = {}
        cleaned_map = {orig: self.clean_column_name(orig) for orig in raw_columns}
        used_raw = set()

        for canonical_name, spec in CANONICAL_CHANNELS.items():
            best_match: Optional[str] = None
            best_score = 0.0

            # 1. Exact match
            for orig, cleaned in cleaned_map.items():
                if orig in used_raw:
                    continue
                if cleaned == canonical_name:
                    best_match = orig
                    best_score = 1.0
                    break

            # 2. Pattern matching
            if not best_match:
                for orig, cleaned in cleaned_map.items():
                    if orig in used_raw:
                        continue
                    for pat in spec["patterns"]:
                        if re.search(pat, cleaned, re.IGNORECASE) or re.search(pat, str(orig), re.IGNORECASE):
                            best_match = orig
                            best_score = 0.85
                            break
                    if best_match:
                        break

            if best_match:
                used_raw.add(best_match)
                matched[canonical_name] = {
                    "raw_column": best_match,
                    "confidence": best_score,
                    "status": "AUTO_MATCHED",
                    "description": spec["description"],
                    "unit": spec["unit"],
                    "required": spec["required"],
                }
            else:
                matched[canonical_name] = {
                    "raw_column": None,
                    "confidence": 0.0,
                    "status": "SMART_ESTIMATED" if not spec["required"] else "MISSING_REQUIRED",
                    "description": spec["description"],
                    "unit": spec["unit"],
                    "required": spec["required"],
                }

        return matched

    @staticmethod
    def parse_flexible_timestamp(val: Any, row_idx: int = 0, base_dt: Optional[datetime] = None) -> str:
        """Parses diverse timestamp representations into ISO-8601 UTC string."""
        if val is None or pd.isna(val) or str(val).strip() == "":
            ref = base_dt or datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
            dt = ref + pd.Timedelta(minutes=10 * row_idx)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        if isinstance(val, (int, float)):
            # Epoch timestamp (seconds or milliseconds)
            try:
                num = float(val)
                if num > 1e11:  # milliseconds
                    num = num / 1000.0
                dt = datetime.fromtimestamp(num, tz=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass

        val_str = str(val).strip()

        # Try pandas to_datetime parsing
        try:
            dt_parsed = pd.to_datetime(val_str, utc=True)
            return dt_parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

        # Fallback timestamp
        ref = base_dt or datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
        dt = ref + pd.Timedelta(minutes=10 * row_idx)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def detect_turbine_rating(self, df: pd.DataFrame, power_col: Optional[str] = None) -> float:
        """Auto-detects turbine rated capacity in kW based on peak generation percentiles."""
        if not power_col or power_col not in df.columns:
            return self.target_rated_power_kw

        valid_power = pd.to_numeric(df[power_col], errors="coerce").dropna()
        if len(valid_power) < 10:
            return self.target_rated_power_kw

        p99 = float(valid_power.quantile(0.99))
        p_max = float(valid_power.max())

        # If data appears to be in MW instead of kW (e.g. max < 15.0), scale by 1000
        if 0.5 <= p_max <= 20.0:
            p99 = p99 * 1000.0

        # Match to nearest standard turbine rating class
        standard_ratings = [750.0, 1000.0, 1500.0, 1800.0, 2000.0, 2100.0, 2500.0, 3000.0, 3450.0, 4000.0, 5000.0, 6000.0]
        # Choose standard rating where p99 is between 70% and 110% of rating
        for rating in standard_ratings:
            if p99 <= rating * 1.08:
                return rating

        return max(round(p99 / 100.0) * 100.0, 1000.0)

    def inspect_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Inspects raw dataframe and returns column match suggestions, quality profile, and stats."""
        raw_cols = list(df.columns)
        matched_cols = self.auto_match_columns(raw_cols)

        # Detect power column for rating check
        power_raw = matched_cols.get("active_power", {}).get("raw_column")
        detected_rating_kw = self.detect_turbine_rating(df, power_raw)

        # Detect turbine IDs
        turb_col = matched_cols.get("turbine_id", {}).get("raw_column")
        if turb_col and turb_col in df.columns:
            unique_turbines = [self.normalize_turbine_id(x) for x in df[turb_col].dropna().unique()[:10]]
            turbine_count = int(df[turb_col].nunique())
        else:
            unique_turbines = ["WTG-01"]
            turbine_count = 1

        # Calculate missingness per raw column
        missing_stats = {}
        for col in raw_cols:
            n_missing = int(df[col].isna().sum())
            missing_stats[col] = {
                "missing_count": n_missing,
                "missing_pct": round((n_missing / max(len(df), 1)) * 100.0, 1)
            }

        # Date range preview
        time_col = matched_cols.get("timestamp", {}).get("raw_column")
        date_start = None
        date_end = None
        if time_col and time_col in df.columns and len(df) > 0:
            try:
                date_start = str(df[time_col].dropna().iloc[0])
                date_end = str(df[time_col].dropna().iloc[-1])
            except Exception:
                pass

        preview_records = df.head(5).replace({np.nan: None}).to_dict(orient="records")

        return {
            "total_rows": len(df),
            "total_columns": len(raw_cols),
            "raw_columns": raw_cols,
            "column_mappings": matched_cols,
            "detected_turbine_rating_kw": detected_rating_kw,
            "detected_turbines": unique_turbines,
            "turbine_count": turbine_count,
            "date_range": {"start": date_start, "end": date_end},
            "missing_stats": missing_stats,
            "sample_preview": preview_records,
        }

    def process_dataframe(
        self,
        df: pd.DataFrame,
        custom_mapping: Optional[Dict[str, str]] = None,
        rated_power_kw_override: Optional[float] = None
    ) -> Tuple[List[TelemetryRecord], ValidationSummary, Dict[str, Any]]:
        """Processes real-world SCADA dataframe into canonical TelemetryRecords.

        Applies column mapping, physics-based fallback imputation, and generates quality scorecard.
        """
        df = df.copy()
        raw_cols = list(df.columns)

        # 1. Determine active column mapping
        auto_map = self.auto_match_columns(raw_cols)
        active_map: Dict[str, str] = {}
        for canonical, spec in auto_map.items():
            if spec.get("raw_column"):
                active_map[canonical] = spec["raw_column"]

        # Apply user overrides if provided
        if custom_mapping:
            for canonical, user_raw in custom_mapping.items():
                if user_raw and str(user_raw) in df.columns:
                    active_map[canonical] = str(user_raw)
                elif user_raw == "__NONE__":
                    active_map.pop(canonical, None)

        # Check required fields
        if "wind_speed" not in active_map or "active_power" not in active_map:
            raise ValueError("CSV is missing mandatory aerodynamic fields: Wind Speed and Active Power must be mapped.")

        # Determine rated power
        rated_kw = rated_power_kw_override or self.detect_turbine_rating(df, active_map.get("active_power"))

        # Detect MW vs kW in active power
        power_raw_col = active_map["active_power"]
        p_max = pd.to_numeric(df[power_raw_col], errors="coerce").max()
        scale_power_by_1000 = (0.5 <= p_max <= 25.0)  # Data given in MW

        records: List[TelemetryRecord] = []
        issues: List[ValidationIssue] = []
        interpolated_count = 0
        dropout_count = 0

        # Parse rows
        base_dt = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
        turb_cfg = settings.TURBINE
        val_cfg = settings.VALIDATION

        # Group by turbine if present
        turb_col = active_map.get("turbine_id")
        if turb_col and turb_col in df.columns:
            grouped = df.groupby(turb_col)
        else:
            grouped = [("WTG-01", df)]

        for turbine_id, group_df in grouped:
            t_id_str = self.normalize_turbine_id(turbine_id)

            rows = group_df.to_dict(orient="records")
            for idx, row in enumerate(rows):
                quality_flags = {}

                # Timestamp
                ts_val = row.get(active_map.get("timestamp")) if "timestamp" in active_map else None
                ts_str = self.parse_flexible_timestamp(ts_val, row_idx=idx, base_dt=base_dt)

                # Wind Speed
                ws_raw = row.get(active_map.get("wind_speed"))
                try:
                    wind_speed = float(ws_raw) if ws_raw is not None and not pd.isna(ws_raw) else 0.0
                    wind_speed = float(np.clip(wind_speed, 0.0, val_cfg.WIND_SPEED_MAX))
                except Exception:
                    wind_speed = 0.0

                # Active Power
                p_raw = row.get(active_map.get("active_power"))
                try:
                    active_power = float(p_raw) if p_raw is not None and not pd.isna(p_raw) else 0.0
                    if scale_power_by_1000:
                        active_power = active_power * 1000.0
                    # Clip to plausible physical bounds
                    active_power = float(np.clip(active_power, -50.0, rated_kw * 1.35))
                except Exception:
                    active_power = 0.0

                # Load fraction for physics estimations
                load_fraction = max(0.0, min(1.2, active_power / max(rated_kw, 100.0)))

                # Ambient Temperature
                if "ambient_temp" in active_map and row.get(active_map["ambient_temp"]) is not None and not pd.isna(row.get(active_map["ambient_temp"])):
                    try:
                        ambient_temp = float(row[active_map["ambient_temp"]])
                    except Exception:
                        ambient_temp = 25.0
                else:
                    ambient_temp = 25.0
                    quality_flags["ambient_temp"] = "ESTIMATED_DEFAULT"

                # Wind Direction
                if "wind_direction" in active_map and row.get(active_map["wind_direction"]) is not None and not pd.isna(row.get(active_map["wind_direction"])):
                    try:
                        wind_direction = float(row[active_map["wind_direction"]]) % 360.0
                    except Exception:
                        wind_direction = 180.0
                else:
                    wind_direction = 180.0

                # Rotor Speed (RPM)
                if "rotor_speed" in active_map and row.get(active_map["rotor_speed"]) is not None and not pd.isna(row.get(active_map["rotor_speed"])):
                    try:
                        rotor_speed = float(row[active_map["rotor_speed"]])
                    except Exception:
                        rotor_speed = float(round(turb_cfg.RATED_ROTOR_RPM * (load_fraction ** 0.5), 2))
                else:
                    rotor_speed = float(round(turb_cfg.RATED_ROTOR_RPM * (load_fraction ** 0.5), 2))
                    quality_flags["rotor_speed"] = "ESTIMATED_PHYSICAL_ODE"

                # Generator Speed (RPM)
                if "generator_speed" in active_map and row.get(active_map["generator_speed"]) is not None and not pd.isna(row.get(active_map["generator_speed"])):
                    try:
                        generator_speed = float(row[active_map["generator_speed"]])
                    except Exception:
                        generator_speed = float(round(rotor_speed * turb_cfg.GEARBOX_RATIO, 1))
                else:
                    generator_speed = float(round(rotor_speed * turb_cfg.GEARBOX_RATIO, 1))
                    quality_flags["generator_speed"] = "ESTIMATED_GEAR_RATIO"

                # Blade Pitch Angle (deg)
                if "pitch_angle" in active_map and row.get(active_map["pitch_angle"]) is not None and not pd.isna(row.get(active_map["pitch_angle"])):
                    try:
                        pitch_angle = float(row[active_map["pitch_angle"]])
                    except Exception:
                        pitch_angle = 0.5 if wind_speed < turb_cfg.RATED_SPEED_MPS else float(round(0.5 + 1.8 * (wind_speed - turb_cfg.RATED_SPEED_MPS), 2))
                else:
                    if wind_speed < turb_cfg.RATED_SPEED_MPS:
                        pitch_angle = 0.5
                    else:
                        pitch_angle = float(round(0.5 + 1.8 * (wind_speed - turb_cfg.RATED_SPEED_MPS), 2))
                    quality_flags["pitch_angle"] = "ESTIMATED_AERODYNAMIC_CURVE"

                # Gearbox Bearing Temperature (°C)
                if "gearbox_bearing_temp" in active_map and row.get(active_map["gearbox_bearing_temp"]) is not None and not pd.isna(row.get(active_map["gearbox_bearing_temp"])):
                    try:
                        gb_temp = float(row[active_map["gearbox_bearing_temp"]])
                    except Exception:
                        gb_temp = float(round(ambient_temp + 15.0 + (turb_cfg.GB_TEMP_RISE_COEFF * load_fraction), 2))
                else:
                    gb_temp = float(round(ambient_temp + 15.0 + (turb_cfg.GB_TEMP_RISE_COEFF * load_fraction), 2))
                    quality_flags["gearbox_bearing_temp"] = "ESTIMATED_THERMAL_EQUILIBRIUM"

                # Generator Stator Temperature (°C)
                if "generator_stator_temp" in active_map and row.get(active_map["generator_stator_temp"]) is not None and not pd.isna(row.get(active_map["generator_stator_temp"])):
                    try:
                        gen_temp = float(row[active_map["generator_stator_temp"]])
                    except Exception:
                        gen_temp = float(round(ambient_temp + 20.0 + (turb_cfg.GEN_TEMP_RISE_COEFF * load_fraction), 2))
                else:
                    gen_temp = float(round(ambient_temp + 20.0 + (turb_cfg.GEN_TEMP_RISE_COEFF * load_fraction), 2))
                    quality_flags["generator_stator_temp"] = "ESTIMATED_THERMAL_EQUILIBRIUM"

                # Reactive Power (kVAR)
                if "reactive_power" in active_map and row.get(active_map["reactive_power"]) is not None and not pd.isna(row.get(active_map["reactive_power"])):
                    try:
                        reactive_power = float(row[active_map["reactive_power"]])
                    except Exception:
                        reactive_power = float(round(0.08 * active_power, 2))
                else:
                    reactive_power = float(round(0.08 * active_power, 2))

                # Nacelle Temp (°C)
                if "nacelle_temp" in active_map and row.get(active_map["nacelle_temp"]) is not None and not pd.isna(row.get(active_map["nacelle_temp"])):
                    try:
                        nacelle_temp = float(row[active_map["nacelle_temp"]])
                    except Exception:
                        nacelle_temp = float(round(ambient_temp + 5.0 + (8.0 * load_fraction), 2))
                else:
                    nacelle_temp = float(round(ambient_temp + 5.0 + (8.0 * load_fraction), 2))

                # Curtailment Flag
                is_curtailed = False
                if "is_curtailed" in active_map and row.get(active_map["is_curtailed"]) is not None:
                    c_val = row[active_map["is_curtailed"]]
                    if isinstance(c_val, bool):
                        is_curtailed = c_val
                    elif isinstance(c_val, (int, float)):
                        is_curtailed = bool(c_val)
                    elif isinstance(c_val, str):
                        is_curtailed = c_val.strip().lower() in ("true", "1", "t", "yes", "curtailed")
                else:
                    # Heuristic curtailment check: strong wind with pitch shedding but lower power
                    if wind_speed > 8.0 and pitch_angle > 12.0 and active_power < 0.7 * rated_kw:
                        is_curtailed = True

                # Determine Operating Status
                operating_status = OperatingStatus.RUNNING.value
                if is_curtailed:
                    operating_status = OperatingStatus.CURTAILED.value
                elif wind_speed < turb_cfg.CUT_IN_SPEED_MPS:
                    operating_status = OperatingStatus.IDLING.value
                elif gb_temp < ambient_temp - 5.0 or gen_temp < ambient_temp - 5.0:
                    operating_status = OperatingStatus.SENSOR_DROPOUT.value
                    dropout_count += 1

                record = TelemetryRecord(
                    timestamp=ts_str,
                    turbine_id=t_id_str,
                    wind_speed=round(wind_speed, 2),
                    wind_direction=round(wind_direction, 1),
                    ambient_temp=round(ambient_temp, 2),
                    active_power=round(active_power, 2),
                    reactive_power=round(reactive_power, 2),
                    rotor_speed=round(rotor_speed, 2),
                    generator_speed=round(generator_speed, 2),
                    gearbox_bearing_temp=round(gb_temp, 2),
                    generator_stator_temp=round(gen_temp, 2),
                    nacelle_temp=round(nacelle_temp, 2),
                    pitch_angle=round(pitch_angle, 2),
                    is_curtailed=is_curtailed,
                    curtailment_limit_kw=float(active_power) if is_curtailed else None,
                    operating_status=operating_status,
                    quality_flags=quality_flags if quality_flags else None,
                    is_synthetic=False,
                )
                records.append(record)

        summary = ValidationSummary(
            total_records=len(df),
            accepted_records=len(records),
            rejected_records=len(df) - len(records),
            interpolated_values_count=interpolated_count,
            dropout_records_count=dropout_count,
            is_valid=len(records) > 0,
            issues=issues
        )

        metadata = {
            "rated_power_kw": rated_kw,
            "active_column_mappings": active_map,
            "turbines_ingested": list({r.turbine_id for r in records}),
            "records_count": len(records),
            "is_real_data": True,
        }

        return records, summary, metadata
