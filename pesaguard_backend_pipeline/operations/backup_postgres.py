"""DEPRECATED — this file has been superseded.

The canonical backup module is ``pesaguard_backend_pipeline/backup_postgres.py``.
This copy at ``operations/backup_postgres.py`` was an earlier standalone
implementation and is kept only as a redirect so that any stray references
do not silently fail.

Migration guide
---------------
* Imports:  ``from pesaguard_backend_pipeline import backup_postgres``
* CLI:      ``python -m pesaguard_backend_pipeline.backup_postgres --backup``
* Tests:    ``tests/test_phase8_backup_dr.py``, ``tests/test_backup_integrity.py``

This redirect shim will be removed after the next deployment cycle.
"""

from __future__ import annotations

import sys
from pathlib import Path

_CANONICAL = Path(__file__).resolve().parents[1] / "backup_postgres.py"


def _redirect() -> None:
    if len(sys.argv) <= 1 or sys.argv[1] in {"--help", "-h"}:
        print(
            "This script is DEPRECATED. Use the canonical module instead:\n"
            "  python " + str(_CANONICAL) + " --backup\n"
            "  python " + str(_CANONICAL) + " --restore /path/to/backup\n"
            "  python " + str(_CANONICAL) + " --pitr-restore /path/to/base/backup --target-time 'YYYY-MM-DD HH:MM:SS'\n",
            file=sys.stderr,
        )
        sys.exit(0)

    print(
        "operations/backup_postgres.py is DEPRECATED.\n"
        "Use the canonical module instead: python " + str(_CANONICAL) + " <args>",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    _redirect()
