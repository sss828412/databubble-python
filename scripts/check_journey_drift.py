#!/usr/bin/env python3
"""
scripts/check_journey_drift.py

Diffs the main app's /v1/journeys/* routes against the SDK's JourneysClient
wrapper methods. Exists because the SDK drifted 7 journeys behind the app
for over a week (2026-08-05 -> 2026-08-16) with nothing catching it —
see CHANGELOG.md's 2026-08-16 entry.

Assumes the sibling layout this was written against:
  databubble/
    code/   <- the main app (api/routes/journeys.py)
    sdk/    <- this repo
Override with DATABUBBLE_CODE_REPO if your layout differs.

Local-only tool — the app repo isn't checked out anywhere this could run in
CI, so this is meant to be run by hand (via check_local.sh) before cutting a
release, not wired into GitHub Actions.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SDK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CODE_REPO = SDK_ROOT.parent / "code"
CODE_REPO = Path(os.environ.get("DATABUBBLE_CODE_REPO", DEFAULT_CODE_REPO))

ROUTE_FILE = CODE_REPO / "api" / "routes" / "journeys.py"
SDK_FILE = SDK_ROOT / "databubble" / "journeys.py"

ROUTE_RE = re.compile(r'@journeys_router\.post\("/journeys/([a-z_]+)"\)')
WRAPPED_RE = re.compile(r'self\._call\("([a-z_]+)"')


def main() -> int:
    if not ROUTE_FILE.exists():
        print(
            f"SKIP: can't find {ROUTE_FILE} — set DATABUBBLE_CODE_REPO to the "
            "main app repo's path if it isn't checked out as a sibling of sdk/."
        )
        return 0

    routes = set(ROUTE_RE.findall(ROUTE_FILE.read_text()))
    wrapped = set(WRAPPED_RE.findall(SDK_FILE.read_text()))

    missing = sorted(routes - wrapped)
    extra = sorted(wrapped - routes)

    if not missing and not extra:
        print(f"OK: JourneysClient wraps all {len(routes)} /v1/journeys/* routes.")
        return 0

    if missing:
        print(f"MISSING from SDK ({len(missing)}): {', '.join(missing)}")
        print("  -> add a wrapper method in databubble/journeys.py for each.")
    if extra:
        print(f"WRAPPED but no longer a live route ({len(extra)}): {', '.join(extra)}")
        print("  -> route was renamed/removed on the app side; update or remove the wrapper.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
