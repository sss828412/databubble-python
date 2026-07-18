# Contributing to databubble-python

The external Python SDK for DataBubble — a thin, typed client over the
`/v1/*` HTTP API. If you're changing the API itself, see the `databubble`
repo instead; this repo should only ever describe the public, documented
surface of that API.

## Setup

```bash
pip install -e ".[dev]"
```

This installs the package in editable mode plus `httpx`, `pandas`, `pytest`,
and `pytest-mock`. `httpx` is the only optional runtime dependency — a raw
`urllib` fallback covers `post_json` if it's absent, so keep that fallback
working if you touch `client.py`.

## Running tests

```bash
pytest tests/
```

`tests/test_sdk.py` and `tests/test_sdk_journeys.py` are the main unit
suites (mocked HTTP). `tests/test_smoke_live.py` hits a real running API —
only run it with a live server and a valid key; don't add it to routine CI
expectations.

## Conventions

- The root client class is `DataBubble` (`from databubble import DataBubble`)
  — not `Client`. Check `databubble/__init__.py`'s `__all__` before adding or
  renaming any public export.
- Every public method should raise the typed exceptions in `exceptions.py`
  (`AuthError`, `ForbiddenError`, `RateLimitError`, `SkillError`,
  `ServerError`, `SDKUsageError`) rather than leaking raw `httpx`/`urllib`
  exceptions.
- Keep `pyproject.toml`'s `version` and `databubble/__init__.py`'s
  `__version__` in sync — `RELEASING.md` depends on this.
- This SDK does not (and should not silently start to) expose the
  knowledge-base/`/ask` surface — that's deliberately left as a REST-only
  surface for now. If that changes, it's a scoped decision, not a drive-by
  addition.

## Releasing

See `RELEASING.md` for the full cut-a-release process (PyPI Trusted
Publishing via `.github/workflows/publish.yml`, gated on a published GitHub
Release — nothing fires on a plain push).

## Changelog

Add a `CHANGELOG.md` entry for every PR, in the same PR — what changed and
why, not a commit list.

## Before this is publishable

- No `LICENSE` file exists yet, even though `pyproject.toml` already
  declares `license = {text = "MIT"}`. Adding the file is an owner decision
  (which license text) — see the SDK README's release checklist.
