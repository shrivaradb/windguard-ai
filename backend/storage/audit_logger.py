"""Thread-Safe Append-Only Audit Logger for WindGuard AI (Layer 6).

Implements persistent audit trail logging for diagnostic evaluations,
operator human-in-the-loop (HITL) review actions, and tariff configuration mutations.

Source:
- docs/08_system_architecture.md Principle 6 & ADR-006
- docs/10_data_architecture.md §6 & §7
- docs/PHASE_6_OWNER_DECISION_RESOLUTION.md §4 (OD-P6-11)
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union
from filelock import FileLock

from backend.config import settings


class AuditLogger:
    """Thread-safe and process-safe append-only JSONL audit logger."""

    def __init__(self, log_path: Optional[Union[str, Path]] = None):
        self.log_path = Path(log_path).resolve() if log_path else settings.PATHS.STORAGE_DIR / "audit_log.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.log_path.with_suffix(self.log_path.suffix + ".lock")
        self._thread_lock = threading.Lock()

    def log_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        actor: str = "SYSTEM",
        case_id: Optional[str] = None,
        turbine_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Appends a structured event entry to the immutable audit trail log."""
        iso_timestamp = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        entry = {
            "timestamp": iso_timestamp,
            "event_type": event_type,
            "actor": actor,
            "case_id": case_id,
            "turbine_id": turbine_id,
            "payload": payload,
        }

        serialized = json.dumps(entry, ensure_ascii=False) + "\n"

        with self._thread_lock:
            with FileLock(str(self.lock_path), timeout=10.0):
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(serialized)

        return entry

    def read_events(
        self,
        event_type: Optional[str] = None,
        case_id: Optional[str] = None,
        turbine_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Reads and filters audit log entries."""
        if not self.log_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        with self._thread_lock:
            with FileLock(str(self.lock_path), timeout=10.0):
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            item = json.loads(line_str)
                            if event_type and item.get("event_type") != event_type:
                                continue
                            if case_id and item.get("case_id") != case_id:
                                continue
                            if turbine_id and item.get("turbine_id") != turbine_id:
                                continue
                            entries.append(item)
                        except json.JSONDecodeError:
                            continue

        if limit and limit > 0:
            return entries[-limit:]
        return entries

    def clear(self) -> None:
        """Clears audit log (used exclusively for isolated test teardown)."""
        with self._thread_lock:
            with FileLock(str(self.lock_path), timeout=10.0):
                if self.log_path.exists():
                    self.log_path.unlink()


# Global audit logger singleton
audit_logger = AuditLogger()
