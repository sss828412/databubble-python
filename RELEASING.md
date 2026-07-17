# Releasing the DataBubble SDK

The publish workflow (`.github/workflows/publish.yml`) is inert until the
one-time account-level setup below is done. It uses **PyPI Trusted
Publishing (OIDC)** — no API token is ever stored in this repo.

## One-time setup (do this once, before the first release)

1. **Create the PyPI project.** Reserve the `databubble` name on
   [pypi.org](https://pypi.org) if not already done. If the name is taken,
   pick a different distribution name and update `pyproject.toml`'s
   `[project].name` before continuing — the workflow publishes whatever
   `python -m build` produces from that field.
2. **Configure the Trusted Publisher.** On the PyPI project's
   "Publishing" settings, add a new trusted publisher:
   - Owner: `sss828412`
   - Repository: `databubble-python`
   - Workflow filename: `publish.yml`
   - Environment name: `pypi`
3. **Repeat for TestPyPI** (optional, only needed for dry-runs), using
   environment name `testpypi` on [test.pypi.org](https://test.pypi.org).
4. **Create the GitHub environments.** In the repo's Settings → Environments,
   create `pypi` and (optionally) `testpypi`. No secrets need to be added to
   either — Trusted Publishing authenticates via OIDC, not a stored value.
   Adding required reviewers on the `pypi` environment is recommended so a
   real publish needs explicit approval.

## Cutting a release

1. Bump `version` in `pyproject.toml` and `__version__` in
   `databubble/__init__.py` together — keep them in sync.
2. Update `README.md`'s version reference and any changed install
   instructions (drop the "Pre-release" note once the package is actually
   on PyPI).
3. Commit, tag (`git tag v0.X.0`), and push the tag.
4. Create a GitHub Release from that tag. **Publishing the release is what
   triggers the workflow** — nothing fires on a plain tag push or on `git
   push` to `main`.
5. Watch the Actions run: `build` job produces the sdist+wheel, then
   `publish-pypi` runs (gated on the `pypi` environment, using OIDC — no
   token needed) and uploads to PyPI.

## Verifying a release

- Check the workflow run in the Actions tab completed successfully.
- Check [pypi.org/project/databubble](https://pypi.org/project/databubble)
  shows the new version.
- In a clean environment: `pip install databubble==<version>` and run a
  quick smoke check (`from databubble import DataBubble`).

## Dry-running against TestPyPI

Run the workflow manually (Actions tab → "Publish to PyPI" → "Run workflow"),
typing `testpypi` into the confirmation field. This builds and publishes to
test.pypi.org only — it never touches the real PyPI index, and requires the
explicit confirmation string so it can't fire by accident from a blank
manual trigger.

## What the workflow deliberately does NOT do

- Does not run on `push` to any branch — only on a published release, or an
  explicitly-confirmed manual TestPyPI dry-run.
- Does not store or reference any PyPI API token — Trusted Publishing (OIDC)
  is the only auth mechanism.
- Does not make the GitHub repository public, or decide the release
  version — those are your calls, made before tagging.
