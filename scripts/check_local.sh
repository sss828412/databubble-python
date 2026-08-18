#!/usr/bin/env bash
# scripts/check_local.sh
#
# "Local dev environment is done" gate, mirroring the main app's
# scripts/deploy_test.sh in spirit: one command that builds the package,
# runs the test suite, checks the built artifacts are valid for upload, and
# checks the SDK hasn't silently drifted behind the app's journey routes
# again (see scripts/check_drift.py — this is the class of bug that
# motivated writing these scripts at all).
#
# Run this before scripts/publish_testpypi.sh. Nothing here touches PyPI,
# GitHub, or any remote — pure local build + checks.
#
# Usage:
#   scripts/check_local.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "1) SDK/API drift check (journeys + skills) ..."
python3 scripts/check_drift.py

echo
echo "2) Running test suite ..."
python3 -m pytest tests/ -q --ignore=tests/test_smoke_live.py

echo
echo "3) Building sdist + wheel ..."
rm -rf dist/
python3 -m build

echo
echo "4) Validating built artifacts (twine check) ..."
python3 -m twine check dist/*

echo
echo "All local checks passed. Built artifacts:"
ls -la dist/
echo
echo "Next: dry-run against TestPyPI —"
echo "  scripts/publish_testpypi.sh"
