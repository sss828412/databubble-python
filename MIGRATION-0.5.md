# Migrating to 0.5.0

0.5.0 inverts the default output. The quantitative surface is now primary; the
business narrative is opt-in. Nothing is removed — three attributes are
deprecated, and they now return correct data for the first time.

## What changes when you upgrade without touching your code

| Before (0.4.0) | After (0.5.0) |
|---|---|
| `print(r)` → `JourneyResult(driver, estimate=-8.2, reliable=True)` | `print(r)` → full regression table |
| `r.recommended` → `[]` (silently wrong) | `[...]` + `DeprecationWarning` pointing at `.selected_predictors` |
| `r.caution` / `r.excluded` → `[]` | correct values + `DeprecationWarning` |
| journey call times out at 60s | 300s (`journey_timeout=`) |
| 503 from the compute pool → exception | retried up to 3× honouring `Retry-After` |
| `pip install databubble` → runtime ImportError on pandas | pandas + httpx installed as dependencies |

Existing scripts keep working. If you assert on `repr()` output, that changed.

## What's new

```python
r = db.journeys.driver(df, outcome_col="sales", candidate_cols=[...])

r.estimates            # DataFrame: name, coefficient, std_error, t, p, CI, VIF
r.coefficients         # Series: predictor -> coefficient
r.effects              # DataFrame: std coef, partial R², dominance
r.diagnostics          # Series: n, adj R², assumptions_met, transformation...
r.selected_predictors  # what was actually fitted
r.excluded_predictors
r.confidence_interval  # (lower, upper) on the primary estimate
r.significant
r.n_observations
r.handoffs             # domain payload for the 9 graph-based journeys
r.charts               # ChartSet — empty until the platform ships Track B
r.summary()            # the text table repr() shows
r.explain()            # the business narrative
r.to_frame()           # alias for .estimates
r.raw                  # unchanged: everything the API returned
```

Skills gained the same treatment:

```python
s = db.skills.univariate(df["price"])
s.charts.show()        # fetches from GET /v1/charts/{name} and renders inline
s.to_frame()           # metric/value DataFrame
db.skills.transformations(df["price"], transform="log")   # new — 7th skill, was unwrapped
```

## Deprecations (removed in 1.0)

`.recommended`, `.caution`, `.excluded`. They parsed `result["selection_output"]`,
a key the live API has never returned — the real envelope names these
`selected_predictors` / `excluded_predictors`, and puts the selection reasoning
in a `selection` key that is a *sibling* of `result`. The properties now read
all three shapes, so they return real data while warning.

To silence the warnings during migration:

```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="databubble")
```

## Why the old tests did not catch this

`tests/test_sdk_journeys.py:MOCK_DRIVER_RESPONSE` contains a
`result.selection_output` block that the platform does not produce. The fixture
was written from the intended shape rather than a captured response, so the
test passed and production returned `[]`. `tests/test_ds_surface.py` uses
fixtures built from `api/envelope.py`. **Capture real responses for fixtures.**
