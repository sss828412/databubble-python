#!/usr/bin/env bash
# scripts/publish_release.sh
#
# "demo.databubble.ai" equivalent for the SDK — the real, public release:
# pushes main, tags the version, and publishes a GitHub Release, which is
# what actually triggers the real PyPI upload (via OIDC Trusted Publishing —
# see RELEASING.md; no token involved, here or in CI). This repo is public,
# so pushing main and creating the release are both immediately visible —
# same "manually gated, never scripted around" posture as the main app's
# scripts/promote_demo.sh, and for the same reason: a real human decision
# has to happen before something prospect/user-facing goes out.
#
# Run scripts/check_local.sh and scripts/publish_testpypi.sh first. This
# script doesn't re-verify the TestPyPI dry-run passed — it trusts you did
# that already, same as promote_demo.sh trusts test.databubble.ai was
# smoke-tested before you type PROMOTE.
#
# Usage:
#   scripts/publish_release.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYPROJECT_VERSION="$(grep -m1 '^version = ' pyproject.toml | sed -E 's/version = "(.*)"/\1/')"
INIT_VERSION="$(python3 -c "import databubble; print(databubble.__version__)")"

if [[ "$PYPROJECT_VERSION" != "$INIT_VERSION" ]]; then
  echo "FAIL: pyproject.toml says $PYPROJECT_VERSION but databubble/__init__.py says $INIT_VERSION — fix before releasing." >&2
  exit 1
fi

TAG="v$PYPROJECT_VERSION"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree has uncommitted changes — commit them first (they won't be released otherwise)." >&2
  git status --porcelain >&2
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "FAIL: tag $TAG already exists locally. Bump the version if this release already went out." >&2
  exit 1
fi

if git ls-remote --tags origin "refs/tags/$TAG" | grep -q "$TAG"; then
  echo "FAIL: tag $TAG already exists on origin. Bump the version if this release already went out." >&2
  exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "FAIL: on branch '$CURRENT_BRANCH', not main. Releases are cut from main." >&2
  exit 1
fi

echo "About to publish databubble $PYPROJECT_VERSION:"
echo "  branch:        main ($(git rev-parse --short HEAD))"
echo "  tag:           $TAG (new)"
echo "  repo:          $(git remote get-url origin)"
echo "  will push:     main, then the $TAG tag"
echo "  will create:   a published GitHub Release from $TAG"
echo "                 (this is what triggers the real PyPI upload — see RELEASING.md)"
echo
echo "Preconditions (confirm before typing PROMOTE):"
echo "  [ ] scripts/check_local.sh passed"
echo "  [ ] scripts/publish_testpypi.sh passed and you spot-checked the install"
echo "  [ ] CHANGELOG.md has an entry for this release"
echo

read -r -p "Type PROMOTE to publish databubble $PYPROJECT_VERSION to the real PyPI: " confirm
if [[ "$confirm" != "PROMOTE" ]]; then
  echo "Aborted."
  exit 1
fi

echo
echo "Pushing main ..."
git push origin main

echo "Tagging and pushing $TAG ..."
git tag -a "$TAG" -m "databubble $PYPROJECT_VERSION"
git push origin "$TAG"

echo "Creating GitHub Release (this triggers the PyPI publish workflow) ..."
gh release create "$TAG" \
  --title "$TAG" \
  --generate-notes

echo
echo "Release published. Watch the publish workflow:"
echo "  gh run list --workflow=publish.yml --limit 3"
echo
echo "Verify once it completes:"
echo "  https://pypi.org/project/databubble/$PYPROJECT_VERSION/"
echo "  pip install databubble==$PYPROJECT_VERSION"
