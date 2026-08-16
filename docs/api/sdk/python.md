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

# Classification — binary outcome (churn, fraud, default, response)
result = db.journeys.classification(
    df, outcome_col="churned", candidate_cols=["tenure", "usage"],
)

# A/B test — randomised experiment, two groups
result = db.journeys.ab_test(df, group_col="variant", metric_col="converted")

# Customer lifetime value / survival analysis
result = db.journeys.clv(
    df, duration_col="tenure_months", event_col="churned", margin_per_period=42.0,
)

# Predictive model — classifier built for prediction accuracy over interpretation
result = db.journeys.predictive_model(
    df, target_col="default", feature_cols=["income", "credit_score"],
)

# Latent factors — PCA (compression) or EFA (latent constructs)
result = db.journeys.latent_factors(
    df, indicator_cols=["q1", "q2", "q3", "q4", "q5"], intent="efa",
)

# Causal inference — design-based effect from observational data
result = db.journeys.causal_inference(
    df, treatment_col="treated", outcome_col="revenue",
    design="did", unit_col="store_id", time_col="week", treat_period=12,
)

# SPC monitoring — is this process stable, or has it shifted?
result = db.journeys.spc_monitoring(df, date_col="day", value_col="defect_rate", baseline_n=60)

# Forecast to inventory — reorder point + safety stock from a demand forecast
result = db.journeys.forecast_inventory(
    df, date_col="week", value_col="units_sold", lead_time_periods=3,
)

# Churn -> CLV at risk — expected revenue at risk from churn probability x CLV
result = db.journeys.churn_clv_at_risk(
    df, duration_col="tenure_months", event_col="churned", margin_per_period=42.0,
)

# Marketing mix model — per-channel response curves, ROI, contribution share
result = db.journeys.mmm(
    df, date_col="week", outcome_col="revenue", channel_cols=["tv_spend", "search_spend"],
)

# Pay equity audit — adjusted pay-gap with raw/adjusted/explained breakdown
result = db.journeys.pay_equity(
    df, compensation_col="salary", protected_col="gender", factor_cols=["level"],
)

# Cross-price elasticity & cannibalization
result = db.journeys.cross_price(
    df, quantity_col="units", own_price_col="price_a", other_price_cols=["price_b"],
)

# Intervention lift — did this promo/price change/policy actually move the metric?
result = db.journeys.intervention_lift(
    df, date_col="day", value_col="conversions", intervention_date="2026-06-01",
)
```

17 journey methods total as of SDK 0.4.0. Column-by-column argument reference
lives in each method's docstring (`databubble/journeys.py`) — this page shows
call shape, not the full parameter list.

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
