"""Append-only audit trail at output/audit_trail.json.

The file is one JSON array. Every agent-loop step adds an entry; nothing is
ever removed or rewritten, so entries from earlier runs are kept. Writes go to
a temporary file first and then replace the original, so a crash mid-write
cannot corrupt the trail. If the existing file can't be read, it is moved
aside (never deleted) and a new trail starts.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import AUDIT_PATH, AUDIT_TEXT_LIMIT
from backend.models import AuditEntry


def clip(value: Any, limit: int = AUDIT_TEXT_LIMIT) -> Any:
    """Shorten very long strings so one tool result can't bloat the trail."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [+{len(value) - limit} chars]"
    if isinstance(value, dict):
        return {k: clip(v, limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clip(v, limit) for v in value]
    return value


class AuditTrail:
    def __init__(self, path: Path = AUDIT_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> list[dict]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        try:
            data = json.loads(self.path.read_text())
            if isinstance(data, list):
                return data
            raise ValueError("audit trail is not a JSON array")
        except (ValueError, json.JSONDecodeError):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            self.path.rename(self.path.with_name(f"{self.path.stem}.unreadable-{stamp}.json"))
            return []

    def append(self, entry: AuditEntry) -> None:
        record = clip(entry.model_dump(mode="json"))
        with self._lock:
            entries = self._load()
            entries.append(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".audit-", suffix=".json")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(entries, f, indent=2, default=str)
                    f.write("\n")
                os.chmod(tmp, 0o644)  # mkstemp makes owner-only files; keep the trail readable
                os.replace(tmp, self.path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise

    def log(self, **fields: Any) -> None:
        self.append(AuditEntry(**fields))
