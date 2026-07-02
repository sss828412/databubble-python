# Python SDK Reference

## Memory

<!-- existing memory section stub -->

## Journeys

Journey methods require **business or enterprise tier**.

```python
# Elasticity — price elasticity of demand
result = db.journeys.elasticity(
    df,
    price_col="price",
    sales_col="revenue",
    confounder_cols=["region", "promo_flag"],  # optional
)

# Driver — which variables drive the outcome?
result = db.journeys.driver(
    df,
    outcome_col="sales",
    candidate_cols=["price", "promotion", "region", "advertising"],
)

# Segmentation — discovery mode (find natural groups)
result = db.journeys.segmentation(
    df, feature_cols=["recency", "frequency", "spend"]
)

# Segmentation — classification mode (predict pre-defined segments)
result = db.journeys.segmentation(
    df,
    feature_cols=["recency", "frequency", "spend"],
    label_col="segment",
)

# Time series — forecast or decompose
result = db.journeys.time_series(
    df, date_col="week", value_col="sales", objective="forecast"
)
```

## JourneyResult fields

```python
result.journey_type          # str — which journey ran
result.halted                # bool — True when platform stopped early
result.halt_reason           # str or None — why it halted
result.primary_estimate      # float or None — main numerical result
result.plain_english_summary # str — full non-technical narrative
result.warnings              # list[str] — assumption violations, caveats
result.assumptions_met       # bool or None
result.revenue_implication   # str or None — elasticity only
result.recommended           # list[str] — driver only
result.caution               # list[str] — driver only
result.excluded              # list[str] — driver only
result.is_reliable()         # bool — not halted AND assumptions_met is not False
result.raw                   # dict — full API response
```

## Halt handling

A halted journey is not an error — the platform stopped to protect you
from a misleading result. Always check `result.halted` before using
`result.primary_estimate`.

```python
result = db.journeys.elasticity(df, price_col="price", sales_col="revenue")

if result.halted:
    print(f"Journey stopped: {result.halt_reason}")
    print("Resolve the issue and re-run.")
elif not result.is_reliable():
    print("Completed with caveats:")
    for w in result.warnings:
        print(f"  ⚠ {w}")
    print(result.plain_english_summary)
else:
    print(result.plain_english_summary)
    print(f"Estimate: {result.primary_estimate}")
```
