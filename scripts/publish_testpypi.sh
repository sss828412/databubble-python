#!/usr/bin/env bash
# scripts/publish_testpypi.sh
#
# "test.databubble.ai" equivalent for the SDK: builds the CURRENT local tree
# (no git push required — same as the main app's deploy_test.sh, which
# builds straight from the working directory rather than from whatever is
# already on a remote) and uploads it to test.pypi.org, then verifies the
# upload actually installs and imports cleanly from a throwaway venv.
#
# Deliberately does NOT use the GitHub Actions workflow's testpypi dry-run
# path (workflow_dispatch with confirm=testpypi) as the primary route here —
# that path builds from whatever is already pushed to GitHub, not your local
# uncommitted changes, which breaks the "test what I actually just wrote"
# guarantee this script exists to give you. Uses `twine upload` directly
# instead, same as any local package publish.
#
# One-time setup: a TestPyPI account + API token
# (https://test.pypi.org/manage/account/#api-tokens), configured either via
# env vars or ~/.pypirc:
#   export TWINE_USERNAME=__token__
#   export TWINE_PASSWORD=pypi-<your TestPyPI token>
# This is separate from and does not touch the real PyPI Trusted Publishing
# setup in RELEASING.md — no token for the real index is ever needed
# locally.
#
# Usage:
#   scripts/publish_testpypi.sh [--skip-build]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_BUILD=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build) SKIP_BUILD="1"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

VERSION="$(python3 -c "import databubble; print(databubble.__version__)")"
echo "Publishing databubble $VERSION to TestPyPI ..."

if [[ -z "$SKIP_BUILD" ]]; then
  echo
  echo "1) Local checks + build (scripts/check_local.sh) ..."
  ./scripts/check_local.sh
else
  echo "Skipping build (--skip-build) — using existing dist/*"
fi

echo
echo "2) Uploading to TestPyPI ..."
python3 -m twine upload --repository testpypi dist/databubble-"$VERSION"* --skip-existing

echo
echo "3) Verifying install from TestPyPI in a throwaway venv ..."
VERIFY_DIR="$(mktemp -d)"
python3 -m venv "$VERIFY_DIR/venv"
# --extra-index-url so pandas/httpx resolve from real PyPI — TestPyPI only
# carries whatever's been manually uploaded there, i.e. just this package.
"$VERIFY_DIR/venv/bin/pip" install -q \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  "databubble==$VERSION"

INSTALLED_VERSION="$("$VERIFY_DIR/venv/bin/python" -c "import databubble; print(databubble.__version__)")"
"$VERIFY_DIR/venv/bin/python" -c "
from databubble import DataBubble, JourneyResult
db = DataBubble(api_key='dbk_smoketest')
assert hasattr(db.journeys, 'intervention_lift'), 'newest journey wrapper missing from installed package'
print('import + attribute check OK')
"
rm -rf "$VERIFY_DIR"

if [[ "$INSTALLED_VERSION" != "$VERSION" ]]; then
  echo "FAIL: installed $INSTALLED_VERSION, expected $VERSION" >&2
  exit 1
fi

echo
echo "TestPyPI dry-run verified: databubble $VERSION installs and imports cleanly."
echo "  https://test.pypi.org/project/databubble/$VERSION/"
echo
echo "Once you're happy with this, cut the real release:"
echo "  scripts/publish_release.sh"
