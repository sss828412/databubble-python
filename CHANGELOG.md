# Changelog

Tracks what each merged PR/branch did — not a commit-by-commit log (`git log`
is authoritative for that), but a short, human-readable note per change so
anyone (including future you) can see what shipped and why without reading
every diff. Add an entry here as part of each PR, in the same PR.

Format: date, branch/PR, one or two lines on what changed and why.

## 2026-07-18 — `docs/platform-docs-2026-07-18`

Corrected a code-sample bug in `README.md` (draft had `from databubble import
Client`; the real class is `DataBubble`), and added a pre-PyPI/license-status
note, a "does not expose the knowledge base" clarification, and a related-
repositories section. Added `CONTRIBUTING.md`, `SECURITY.md`, and
`LICENSE_DECISION.md` (license choice is still an open owner decision — MIT
recommended, not yet finalized). Merged directly to `main` (fast-forward, no
conflicts).
