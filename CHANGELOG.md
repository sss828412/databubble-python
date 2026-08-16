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

## 2026-08-01 — MIT LICENSE file added

`pyproject.toml` already declared `license = {text = "MIT"}` but no `LICENSE`
file existed — the last blocker before a PyPI publish. Owner picked MIT
(recommended in `LICENSE_DECISION.md`) over Apache-2.0/copyleft alternatives;
README release checklist updated to match.

## 2026-08-05 — item 5: 6 new journey wrappers (classification, ab_test, clv,
predictive_model, latent_factors, causal_inference)

`JourneysClient` goes from 4 to 10 methods, matching the 2 new `/v1/journeys/*`
routes added the same day (`api/routes/journeys.py`) for the two graph-only
journeys (latent_factors, causal_inference — neither has a classic
`journey_*.py` driver; both run via `graph_runner.run_graph`). `column_map`
keys verified directly against each route body, not assumed from the review
docs that specced this — `predictive_model`'s server-side key is
`outcome_col`/`candidate_cols` even though the SDK kwarg is `target_col`
(matches `classification`'s shape; the route reuses it). `latent_factors` and
`causal_inference` results carry their domain payload under
`result.raw["result"]["handoffs"]` rather than dedicated `JourneyResult`
fields — deliberately not extending `models.py`/`_parse_journey_result` for
these two to match the SDK's existing scope (only `driver`'s
recommended/caution/excluded gets bespoke parsing; everything else already
leans on `.raw`). Added `README.md` examples for all 6. Version bump to
0.3.0 and PyPI publish are deferred to the (owner-run) publish step, per the
review's own item 5/6 split.

## 2026-08-16 — 7 more journey wrappers, closing the API/SDK gap

`JourneysClient` goes from 10 to 17 methods, catching up to every
`/v1/journeys/*` route the API has: `spc_monitoring`, `forecast_inventory`,
`churn_clv_at_risk`, `mmm`, `pay_equity`, `cross_price`, `intervention_lift`.
These 7 routes shipped in the main app on 2026-08-12/13 (`api/routes/
journeys.py`, all graph-only journeys run via `_run_graph_journey_sync`) but
were never wrapped here — found by diffing the API's route list against
`JourneysClient`'s method list while investigating an unrelated support
question, not by a planned audit. `column_map`/`options` keys verified
directly against each route's docstring and body, not assumed. All 7 return
their domain payload under `result.raw["result"]["handoffs"]`, matching
`latent_factors`/`causal_inference`'s existing convention rather than adding
bespoke `JourneyResult` fields. 21 new tests in `tests/test_sdk_journeys.py`
(payload-shape + validation-error cases per journey, mocked HTTP, no live
server). Version bump to 0.4.0.

Also added `scripts/check_local.sh` (build+test+twine-check+the drift check
that would have caught this gap earlier), `scripts/publish_testpypi.sh`, and
`scripts/publish_release.sh` — a manual-trigger, staged release flow mirroring
`code/scripts/deploy_test.sh`/`promote_demo.sh`'s local-dev -> test -> demo
pattern. See `RELEASING.md` for the updated flow.
