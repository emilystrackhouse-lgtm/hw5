"""Reset the working database to the original shop data.

Copies data/campus_customs.db over data/campus_customs_new.db. Run this before
every full run of the agent team:

    python -m backend.reset_db

The original file is never modified. The audit trail is kept (it is append-only);
pass --clear-audit to start a fresh output/audit_trail.json as well.
"""

from __future__ import annotations

import shutil
import sqlite3
import stat
import sys

from backend.config import AUDIT_PATH, ORIGINAL_DB_PATH, WORKING_DB_PATH


def reset(clear_audit: bool = False) -> None:
    if not ORIGINAL_DB_PATH.exists():
        sys.exit(f"Original database not found at {ORIGINAL_DB_PATH}.")
    for suffix in ("-wal", "-shm", "-journal"):
        WORKING_DB_PATH.with_name(WORKING_DB_PATH.name + suffix).unlink(missing_ok=True)
    shutil.copyfile(ORIGINAL_DB_PATH, WORKING_DB_PATH)
    WORKING_DB_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    with sqlite3.connect(WORKING_DB_PATH) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    print(f"Reset {WORKING_DB_PATH.name} from {ORIGINAL_DB_PATH.name}.")
    if clear_audit and AUDIT_PATH.exists():
        AUDIT_PATH.write_text("[]\n")
        print(f"Cleared {AUDIT_PATH.name}.")


if __name__ == "__main__":
    reset(clear_audit="--clear-audit" in sys.argv)
