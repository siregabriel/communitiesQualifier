"""
JsonFileBacked mixin
Shared persistence helpers so services stay in sync with their JSON file on
disk instead of trusting a stale in-memory copy:

  * _ensure_fresh() — reloads from disk if the file changed since last load
    (cheap mtime check). Call this at the start of every read AND before every
    read-modify-write, so concurrent writers / external edits aren't clobbered.
  * _atomic_write() — writes via a temp file + os.replace so a crash mid-write
    can't corrupt the file, and readers never see a half-written file.
  * _lock — a re-entrant lock to serialize read-modify-write within a process.

Each service must:
  - set self.storage_path
  - call self._init_store() in __init__ (before its initial load)
  - implement load_from_file() (which _ensure_fresh calls)
"""

import os
import json
import tempfile
import threading


class JsonFileBacked:
    def _init_store(self) -> None:
        self._mtime = None
        self._lock = threading.RLock()

    def _file_mtime(self):
        try:
            return os.path.getmtime(self.storage_path) if os.path.exists(self.storage_path) else None
        except OSError:
            return None

    def _ensure_fresh(self) -> None:
        """Reload from disk if the file changed since we last read it."""
        if not hasattr(self, '_mtime'):
            self._init_store()
        if self._file_mtime() != self._mtime:
            self.load_from_file()
            self._mtime = self._file_mtime()

    def _mark_loaded(self) -> None:
        """Record the current file mtime as the loaded version."""
        self._mtime = self._file_mtime()

    def _atomic_write(self, data, indent: int = 2) -> None:
        """Atomically write JSON to storage_path (temp file + os.replace)."""
        directory = os.path.dirname(self.storage_path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            os.replace(tmp, self.storage_path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
        self._mark_loaded()
