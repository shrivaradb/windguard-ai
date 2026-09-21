"""SCADA Data Preprocessor and Validation Engine.

Implements range checking, plausibility filters, rate-of-change validation,
and documented missing value handling (1-2 step linear interpolation with provenance tracking;
>2 step dropout detection).

Source:
- docs/10_data_architecture.md §5
- docs/07_srs.md §3.1
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from pydantic import ValidationError

from backend.config import settings
from backend.data.schema import (
    OperatingStatus,
    TelemetryRecord,
    ValidationIssue,
    ValidationSummary,
)


class SCADAPreprocessor:
    """Validates, cleans, and standardizes SCADA telemetry records."""

    def __init__(self):
        self.val_cfg = settings.VALIDATION
        self.turb_cfg = settings.TURBINE

    def validate_and_clean_record(
        self,
        raw_data: Dict[str, Any],
        row_idx: int = 0,
        prev_record: Optional[TelemetryRecord] = None
    ) -> Tuple[Optional[TelemetryRecord], List[ValidationIssue]]:
        """Validates a single telemetry dictionary and flags physical/rate violations."""
        issues: List[ValidationIssue] = []
        turbine_id = raw_data.get("turbine_id", f"WTG-{row_idx+1:02d}")

        # 1. Pydantic schema validation & legacy alias mapping
        try:
            record = TelemetryRecord.model_validate(raw_data)
        except ValidationError as err:
            for error in err.errors():
                loc = ".".join(str(x) for x in error["loc"])
                issues.append(ValidationIssue(
                    row_index=row_idx,
                    turbine_id=str(turbine_id),
                    field_name=loc,
                    issue_type="MALFORMED",
                    observed_value=raw_data.get(loc, "MISSING"),
                    expected_rule=error["msg"],
                    action_taken="REJECTED"
                ))
            return None, issues

        # 2. Physical Range Checks (docs/10_data_architecture.md §5)
        # Wind Speed
        if not (self.val_cfg.WIND_SPEED_MIN <= record.wind_speed <= self.val_cfg.WIND_SPEED_MAX):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="wind_speed",
                issue_type="RANGE_VIOLATION",
                observed_value=record.wind_speed,
                expected_rule=f"[{self.val_cfg.WIND_SPEED_MIN}, {self.val_cfg.WIND_SPEED_MAX}] m/s",
                action_taken="REJECTED"
            ))

        # Ambient Temp
        if not (self.val_cfg.AMBIENT_TEMP_MIN <= record.ambient_temp <= self.val_cfg.AMBIENT_TEMP_MAX):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="ambient_temp",
                issue_type="RANGE_VIOLATION",
                observed_value=record.ambient_temp,
                expected_rule=f"[{self.val_cfg.AMBIENT_TEMP_MIN}, {self.val_cfg.AMBIENT_TEMP_MAX}] °C",
                action_taken="REJECTED"
            ))

        # Active Power
        if not (self.val_cfg.ACTIVE_POWER_MIN <= record.active_power <= self.val_cfg.ACTIVE_POWER_MAX):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="active_power",
                issue_type="RANGE_VIOLATION",
                observed_value=record.active_power,
                expected_rule=f"[{self.val_cfg.ACTIVE_POWER_MIN}, {self.val_cfg.ACTIVE_POWER_MAX}] kW",
                action_taken="REJECTED"
            ))

        # Gearbox Bearing Temp
        if not (self.val_cfg.GEARBOX_BEARING_TEMP_MIN <= record.gearbox_bearing_temp <= self.val_cfg.GEARBOX_BEARING_TEMP_MAX):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="gearbox_bearing_temp",
                issue_type="RANGE_VIOLATION",
                observed_value=record.gearbox_bearing_temp,
                expected_rule=f"[{self.val_cfg.GEARBOX_BEARING_TEMP_MIN}, {self.val_cfg.GEARBOX_BEARING_TEMP_MAX}] °C",
                action_taken="REJECTED"
            ))

        # Generator Stator Temp
        if not (self.val_cfg.GENERATOR_STATOR_TEMP_MIN <= record.generator_stator_temp <= self.val_cfg.GENERATOR_STATOR_TEMP_MAX):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="generator_stator_temp",
                issue_type="RANGE_VIOLATION",
                observed_value=record.generator_stator_temp,
                expected_rule=f"[{self.val_cfg.GENERATOR_STATOR_TEMP_MIN}, {self.val_cfg.GENERATOR_STATOR_TEMP_MAX}] °C",
                action_taken="REJECTED"
            ))

        # Pitch Angle
        if not (self.val_cfg.PITCH_ANGLE_MIN <= record.pitch_angle <= self.val_cfg.PITCH_ANGLE_MAX):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="pitch_angle",
                issue_type="RANGE_VIOLATION",
                observed_value=record.pitch_angle,
                expected_rule=f"[{self.val_cfg.PITCH_ANGLE_MIN}, {self.val_cfg.PITCH_ANGLE_MAX}] deg",
                action_taken="REJECTED"
            ))

        # 3. Plausibility Rules (Thermocouple Disconnection)
        if record.gearbox_bearing_temp < (record.ambient_temp + self.val_cfg.THERMAL_PLAUSIBILITY_DELTA):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="gearbox_bearing_temp",
                issue_type="PLAUSIBILITY",
                observed_value=record.gearbox_bearing_temp,
                expected_rule=f"T_GB >= T_amb - 5.0°C (Ambient: {record.ambient_temp}°C)",
                action_taken="FLAGGED_SENSOR_DROPOUT"
            ))
            record.operating_status = OperatingStatus.SENSOR_DROPOUT.value
            record.quality_flags = record.quality_flags or {}
            record.quality_flags["gearbox_bearing_temp"] = "SENSOR_DROPOUT"

        if record.generator_stator_temp < (record.ambient_temp + self.val_cfg.THERMAL_PLAUSIBILITY_DELTA):
            issues.append(ValidationIssue(
                row_index=row_idx,
                turbine_id=record.turbine_id,
                field_name="generator_stator_temp",
                issue_type="PLAUSIBILITY",
                observed_value=record.generator_stator_temp,
                expected_rule=f"T_Gen >= T_amb - 5.0°C (Ambient: {record.ambient_temp}°C)",
                action_taken="FLAGGED_SENSOR_DROPOUT"
            ))
            record.operating_status = OperatingStatus.SENSOR_DROPOUT.value
            record.quality_flags = record.quality_flags or {}
            record.quality_flags["generator_stator_temp"] = "SENSOR_DROPOUT"

        # 4. Rate-of-Change Checks against previous record
        if prev_record and prev_record.turbine_id == record.turbine_id:
            # Wind speed delta
            delta_v = abs(record.wind_speed - prev_record.wind_speed)
            if delta_v > self.val_cfg.WIND_SPEED_MAX_DELTA_10MIN:
                issues.append(ValidationIssue(
                    row_index=row_idx,
                    turbine_id=record.turbine_id,
                    field_name="wind_speed",
                    issue_type="RATE_OF_CHANGE",
                    observed_value=round(delta_v, 2),
                    expected_rule=f"|Delta v| <= {self.val_cfg.WIND_SPEED_MAX_DELTA_10MIN} m/s per 10min",
                    action_taken="REJECTED"
                ))

            # Ambient temperature delta
            delta_t = abs(record.ambient_temp - prev_record.ambient_temp)
            if delta_t > self.val_cfg.AMBIENT_TEMP_MAX_DELTA_10MIN:
                issues.append(ValidationIssue(
                    row_index=row_idx,
                    turbine_id=record.turbine_id,
                    field_name="ambient_temp",
                    issue_type="RATE_OF_CHANGE",
                    observed_value=round(delta_t, 2),
                    expected_rule=f"|Delta T| <= {self.val_cfg.AMBIENT_TEMP_MAX_DELTA_10MIN} °C per 10min",
                    action_taken="REJECTED"
                ))

        # Determine rejection: if any critical range violation exists, reject record
        has_rejection = any(iss.action_taken == "REJECTED" for iss in issues)
        if has_rejection:
            return None, issues

        return record, issues

    def process_dataframe(self, df: pd.DataFrame) -> Tuple[List[TelemetryRecord], ValidationSummary]:
        """Processes a pandas DataFrame, applying missing-value interpolation (1-2 gaps)

        and flagging >2 gaps as SENSOR_DROPOUT.
        """
        raw_records = df.to_dict(orient="records")
        total_records = len(raw_records)
        all_issues: List[ValidationIssue] = []
        validated_records: List[TelemetryRecord] = []
        interpolated_count = 0
        dropout_count = 0

        # Numeric sensor columns eligible for missing-data interpolation (only those present in DataFrame)
        all_sensor_cols = [
            "wind_speed", "wind_direction", "ambient_temp", "active_power",
            "reactive_power", "rotor_speed", "generator_speed",
            "gearbox_bearing_temp", "generator_stator_temp", "nacelle_temp", "pitch_angle"
        ]
        sensor_cols = [c for c in all_sensor_cols if c in df.columns]

        # Group DataFrame by turbine_id for gap analysis
        if "turbine_id" in df.columns:
            turbine_groups = df.groupby("turbine_id")
        else:
            turbine_groups = [("WTG-01", df)]

        for turbine_id, group_df in turbine_groups:
            group_records = group_df.to_dict(orient="records")
            # Track consecutive NaNs per sensor
            gap_trackers = {col: 0 for col in sensor_cols}

            for row_idx, row in enumerate(group_records):
                quality_flags = {}

                # Check for missing values / NaNs
                for col in sensor_cols:
                    val = row.get(col)
                    if val is None or pd.isna(val):
                        gap_trackers[col] += 1
                    else:
                        gap_trackers[col] = 0

                # Perform interpolation or mark dropout
                for col in sensor_cols:
                    consecutive_gaps = gap_trackers[col]
                    if consecutive_gaps > 0:
                        if consecutive_gaps <= self.val_cfg.MAX_CONSECUTIVE_MISSING_FOR_INTERPOLATION:
                            # 1-2 gap: Linear interpolation or forward-fill from previous valid
                            prev_val = None
                            next_val = None
                            # Look back
                            for k in range(row_idx - consecutive_gaps, -1, -1):
                                if k >= 0 and not pd.isna(group_records[k].get(col)):
                                    prev_val = group_records[k][col]
                                    break
                            # Look forward
                            for k in range(row_idx + 1, len(group_records)):
                                if not pd.isna(group_records[k].get(col)):
                                    next_val = group_records[k][col]
                                    break

                            if prev_val is not None and next_val is not None:
                                # Linear interpolation
                                interp_val = (prev_val + next_val) / 2.0
                            elif prev_val is not None:
                                interp_val = prev_val
                            elif next_val is not None:
                                interp_val = next_val
                            else:
                                interp_val = 0.0

                            row[col] = float(round(interp_val, 2))
                            quality_flags[col] = "INTERPOLATED_LINEAR"
                            interpolated_count += 1
                            all_issues.append(ValidationIssue(
                                row_index=row_idx,
                                turbine_id=str(turbine_id),
                                field_name=col,
                                issue_type="MISSING_VALUE",
                                observed_value="NaN",
                                expected_rule="Valid sensor float",
                                action_taken="INTERPOLATED"
                            ))
                        else:
                            # >2 consecutive gaps: Flag as SENSOR_DROPOUT
                            dropout_count += 1
                            row[col] = 0.0  # safe numeric fill for typing
                            quality_flags[col] = "SENSOR_DROPOUT"
                            row["operating_status"] = OperatingStatus.SENSOR_DROPOUT.value
                            all_issues.append(ValidationIssue(
                                row_index=row_idx,
                                turbine_id=str(turbine_id),
                                field_name=col,
                                issue_type="MISSING_VALUE",
                                observed_value=f"{consecutive_gaps} consecutive NaNs",
                                expected_rule=f"<= {self.val_cfg.MAX_CONSECUTIVE_MISSING_FOR_INTERPOLATION} consecutive NaNs",
                                action_taken="FLAGGED_SENSOR_DROPOUT"
                            ))

                if quality_flags:
                    row["quality_flags"] = quality_flags

                prev_rec = validated_records[-1] if validated_records else None
                rec, issues = self.validate_and_clean_record(row, row_idx=row_idx, prev_record=prev_rec)
                all_issues.extend(issues)
                if rec is not None:
                    validated_records.append(rec)

        summary = ValidationSummary(
            total_records=total_records,
            accepted_records=len(validated_records),
            rejected_records=total_records - len(validated_records),
            interpolated_values_count=interpolated_count,
            dropout_records_count=dropout_count,
            is_valid=(len(validated_records) == total_records and not any(i.action_taken == "REJECTED" for i in all_issues)),
            issues=all_issues
        )

        return validated_records, summary
