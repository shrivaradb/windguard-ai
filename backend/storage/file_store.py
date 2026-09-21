"""Thread-Safe and Process-Safe Atomic File Persistence Helper.

Implements ADR-006 (Thread-Safe Atomic File-Locked Persistence) using
filelock and atomic file replacement primitives (write to .tmp and os.replace).

Source:
- docs/08_system_architecture.md ADR-006
- docs/13_technology_stack.md §3.5
"""

import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict, List, Union
from filelock import FileLock
import pandas as pd


class AtomicFileStore:
    """Provides atomic, thread-safe, and process-safe read/write operations for JSON and CSV files."""

    def __init__(self):
        self._thread_lock = threading.Lock()

    def _atomic_replace(self, temp_name: str, target_path: str) -> None:
        """Atomically replaces target file with retry logic for Windows file locks."""
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                os.replace(temp_name, target_path)
                return
            except (PermissionError, OSError):
                if attempt == max_attempts - 1:
                    raise
                time.sleep(0.02)

    def write_json_atomic(self, data: Union[Dict[str, Any], List[Any]], target_path: Union[str, Path]) -> Path:
        """Writes JSON data atomically using a temporary file and atomic replace under a file lock."""
        path = Path(target_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")

        with self._thread_lock:
            with FileLock(str(lock_path), timeout=10.0):
                # Write to temp file in same directory to guarantee same filesystem for atomic rename
                temp_dir = path.parent
                with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
                    json.dump(data, tf, indent=2, ensure_ascii=False)
                    temp_name = tf.name

                # Atomic replacement with Windows retry protection
                self._atomic_replace(temp_name, str(path))

        return path

    def read_json_safe(self, target_path: Union[str, Path]) -> Union[Dict[str, Any], List[Any]]:
        """Reads JSON data safely under a shared file lock."""
        path = Path(target_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        lock_path = path.with_suffix(path.suffix + ".lock")

        with self._thread_lock:
            with FileLock(str(lock_path), timeout=10.0):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)

    def write_csv_atomic(self, df: pd.DataFrame, target_path: Union[str, Path]) -> Path:
        """Writes DataFrame to CSV atomically under a file lock."""
        path = Path(target_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")

        with self._thread_lock:
            with FileLock(str(lock_path), timeout=10.0):
                temp_dir = path.parent
                with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8", suffix=".csv") as tf:
                    temp_name = tf.name

                df.to_csv(temp_name, index=False)
                self._atomic_replace(temp_name, str(path))

        return path

    def read_csv_safe(self, target_path: Union[str, Path]) -> pd.DataFrame:
        """Reads CSV safely under a file lock."""
        path = Path(target_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        lock_path = path.with_suffix(path.suffix + ".lock")

        with self._thread_lock:
            with FileLock(str(lock_path), timeout=10.0):
                return pd.read_csv(path)
