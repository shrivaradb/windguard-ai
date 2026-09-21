"""Thread-Safe and Process-Safe Persistent Maintenance Case Store (Layer 6).

Implements persistent case storage conforming to OD-P6-01 (Atomic File Persistence)
using AtomicFileStore, with in-memory query indexing, append-only operator review history,
and strict immutability of analytical outputs.

Source:
- docs/08_system_architecture.md Principle 6 & ADR-006
- docs/09_technical_design.md §2.6, §4
- docs/10_data_architecture.md §6
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-01, OD-P6-04, OD-P6-05)
"""

from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.api.schemas import CaseStatus, HITLAction, MaintenanceCase, OperatorDecision
from backend.config import settings
from backend.storage.file_store import AtomicFileStore


class CaseStore:
    """Thread-safe in-memory indexed Case Store with atomic disk persistence backing."""

    def __init__(
        self,
        store_path: Optional[Union[str, Path]] = None,
        file_store: Optional[AtomicFileStore] = None,
        auto_load: bool = True,
    ):
        self.store_path = Path(store_path).resolve() if store_path else settings.PATHS.STORAGE_DIR / "cases.json"
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_store = file_store or AtomicFileStore()
        self._lock = threading.RLock()
        # In-memory mapping: case_id -> MaintenanceCase
        self._cases: Dict[str, MaintenanceCase] = {}

        if auto_load and self.store_path.exists():
            try:
                self.load_from_disk()
            except Exception:
                # If existing file is invalid, initialize clean store without crashing
                pass

    def save_case(self, case: MaintenanceCase) -> MaintenanceCase:
        """Persists a new diagnostic case or updates decisions atomically."""
        with self._lock:
            # Immutability Check: Do not allow overwriting analytical fields of an existing case
            if case.case_id in self._cases:
                existing = self._cases[case.case_id]
                # If case exists, analytical and telemetry fields must remain unchanged
                if (
                    existing.turbine_id != case.turbine_id
                    or existing.created_at != case.created_at
                    or existing.source_telemetry.timestamp != case.source_telemetry.timestamp
                ):
                    raise ValueError(f"Cannot overwrite immutable historical case '{case.case_id}' with divergent data.")

            self._cases[case.case_id] = case
            self.save_to_disk()
            return case

    def get_case(self, case_id: str) -> Optional[MaintenanceCase]:
        """Retrieves a specific case by its unique identifier."""
        with self._lock:
            return self._cases.get(case_id)

    def find_case_by_telemetry(self, turbine_id: str, timestamp: str) -> Optional[MaintenanceCase]:
        """Finds an existing case diagnosed for the exact turbine_id and telemetry timestamp."""
        with self._lock:
            for case in self._cases.values():
                if case.turbine_id == turbine_id and case.source_telemetry.timestamp == timestamp:
                    return case
            return None

    def list_cases(
        self,
        limit: int = 50,
        offset: int = 0,
        turbine_id: Optional[str] = None,
        status: Optional[Union[CaseStatus, str]] = None,
        severity: Optional[str] = None,
    ) -> Tuple[List[MaintenanceCase], int]:
        """Queries and filters persisted cases with stable pagination."""
        with self._lock:
            filtered: List[MaintenanceCase] = list(self._cases.values())

            # Filter by turbine_id
            if turbine_id:
                filtered = [c for c in filtered if c.turbine_id == turbine_id]

            # Filter by status
            if status:
                status_str = status.value if hasattr(status, "value") else str(status)
                filtered = [c for c in filtered if c.status.value == status_str or str(c.status) == status_str]

            # Filter by severity
            if severity:
                sev_str = severity.value if hasattr(severity, "value") else str(severity)
                filtered = [c for c in filtered if c.severity.value == sev_str or str(c.severity) == sev_str]

            # Stable sort: descending by creation timestamp, then case_id
            filtered.sort(key=lambda c: (c.created_at, c.case_id), reverse=True)

            total_count = len(filtered)
            clamped_limit = max(1, min(100, limit))
            clamped_offset = max(0, offset)

            paginated = filtered[clamped_offset : clamped_offset + clamped_limit]
            return paginated, total_count

    def record_decision(self, case_id: str, decision: OperatorDecision) -> MaintenanceCase:
        """Appends an operator review action to the case and updates its active status."""
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise KeyError(f"Maintenance case '{case_id}' not found in case store.")

            # Map operator action to active case status
            action_status_map = {
                HITLAction.ACKNOWLEDGE: CaseStatus.ACKNOWLEDGED,
                HITLAction.INVESTIGATE: CaseStatus.INVESTIGATING,
                HITLAction.ESCALATE: CaseStatus.ESCALATED,
                HITLAction.DISMISS: CaseStatus.DISMISSED,
            }
            new_status = action_status_map.get(decision.action, CaseStatus.ACKNOWLEDGED)

            # Append decision to history (creates new list to ensure clean immutability)
            updated_decisions = list(case.operator_decisions)
            updated_decisions.append(decision)

            # Create updated case preserving all original analytical fields
            updated_case = case.model_copy(
                update={
                    "status": new_status,
                    "operator_decisions": updated_decisions,
                }
            )

            self._cases[case_id] = updated_case
            self.save_to_disk()
            return updated_case

    def count(self) -> int:
        """Returns total number of stored cases."""
        with self._lock:
            return len(self._cases)

    def save_to_disk(self) -> Path:
        """Persists all in-memory cases atomically to disk under a file lock."""
        with self._lock:
            data = {
                case_id: case.model_dump()
                for case_id, case in self._cases.items()
            }
            return self.file_store.write_json_atomic(data, self.store_path)

    def load_from_disk(self) -> int:
        """Restores cases from persistent disk file."""
        with self._lock:
            if not self.store_path.exists():
                return 0

            raw_data = self.file_store.read_json_safe(self.store_path)
            if not isinstance(raw_data, dict):
                raise ValueError(f"Invalid case store format in {self.store_path}")

            loaded_count = 0
            new_cases: Dict[str, MaintenanceCase] = {}
            for cid, cdata in raw_data.items():
                case = MaintenanceCase.model_validate(cdata)
                new_cases[cid] = case
                loaded_count += 1

            self._cases = new_cases
            return loaded_count

    def clear(self) -> None:
        """Clears all in-memory and on-disk cases (used for test teardown)."""
        with self._lock:
            self._cases.clear()
            if self.store_path.exists():
                try:
                    self.file_store.write_json_atomic({}, self.store_path)
                except Exception:
                    try:
                        self.store_path.unlink(missing_ok=True)
                    except Exception:
                        pass
            lock_file = self.store_path.with_suffix(self.store_path.suffix + ".lock")
            if lock_file.exists():
                try:
                    lock_file.unlink(missing_ok=True)
                except Exception:
                    pass


# Global case store singleton
case_store = CaseStore()
