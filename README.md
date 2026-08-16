# DataBubble SDK

Statistical Intelligence as a Service. Current version: **0.4.0**.

A thin, typed client over the DataBubble HTTP API (`/v1/*`) — handles
authentication (`X-API-Key`), request/response shaping, and session memory.
It does **not** expose the knowledge-base / `/ask` surface (no `knowledge` or
`ask` module) — that's a REST-only surface for now.

> **Status:** published on PyPI. MIT licensed — `LICENSE` file added
> 2026-08-01, matching the `license = {text = "MIT"}` declared in
> `pyproject.toml`.

```bash
pip install databubble httpx pandas
```

(Installing straight from GitHub also still works, if you want an
unreleased commit: `pip install git+https://github.com/sss828412/databubble-python.git`,
or `pip install -e .` for local development.)

## Quick start

```python
from databubble import DataBubble
import pandas as pd

db = DataBubble(api_key="dbk_...")

# Univariate analysis
result = db.skills.univariate(df["price"])
print(result.summary)
print(result.warnings)

# Missing value profiling
result = db.skills.missing_values(df)

# Export session memory for next session
mem = db.memory.export(df, label="POS data June 2026")
mem.save("pos_memory.json")
```

## Available skills

| Skill | Input | What it does |
|---|---|---|
| `univariate` | Series or DataFrame + column= | Distribution analysis, skewness, bounded ordinal detection, MNAR flags |
| `outliers` | Series or DataFrame + column= | IQR + Z-score outlier detection |
| `missing_values` | DataFrame | MCAR/MAR/MNAR profiling, treatment recommendations |
| `leakage` | DataFrame + outcome= | Post-outcome timing detection, correlation proxy check |
| `bivariate` | DataFrame + x= + y= | Relationship analysis, linearity check |
| `correlation` | DataFrame + x= + y= | Pearson + Spearman, non-linearity flag |

## Journeys

Single-call, end-to-end analyses — `db.journeys.*` — available on **Business and
Enterprise tiers only**. Each returns a `JourneyResult` (`primary_estimate`,
`plain_english_summary`, `warnings`, `assumptions_met`, `is_reliable()`) rather
than a raw `SkillOutput`. Full reference: `docs/api/sdk/python.md`.

```python
# Price elasticity of demand
result = db.journeys.elasticity(
    df, price_col="price", sales_col="revenue", confounder_cols=["region"],
)
if result.is_reliable():
    print(result.revenue_implication)

# Driver analysis — which variables drive the outcome?
result = db.journeys.driver(
    df, outcome_col="sales", candidate_cols=["price", "promotion", "region"],
)
print(result.recommended)

# Segmentation — discovery (no label_col) or classification (with label_col)
result = db.journeys.segmentation(df, feature_cols=["recency", "frequency", "spend"])

# Time series — forecast or decompose
result = db.journeys.time_series(df, date_col="week", value_col="sales", objective="forecast")

# Binary classification — churn, fraud, default, response
result = db.journeys.classification(df, outcome_col="churned", candidate_cols=["tenure", "usage"])

# A/B test — randomised experiment, two groups
result = db.journeys.ab_test(df, group_col="variant", metric_col="converted")

# Customer lifetime value / survival analysis
result = db.journeys.clv(df, duration_col="tenure_months", event_col="churned", margin_per_period=42.0)

# Predictive model — classifier built for prediction accuracy
result = db.journeys.predictive_model(df, target_col="default", feature_cols=["income", "credit_score"])

# Latent factors — PCA (compression) or EFA (latent constructs)
result = db.journeys.latent_factors(df, indicator_cols=["q1", "q2", "q3", "q4", "q5"], intent="efa")

# Causal inference — design-based effect from observational data (not a randomised test)
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
    df, date_col="week", outcome_col="revenue",
    channel_cols=["tv_spend", "search_spend", "social_spend"],
)

# Pay equity audit — adjusted pay-gap with raw/adjusted/explained breakdown
result = db.journeys.pay_equity(
    df, compensation_col="salary", protected_col="gender", factor_cols=["level", "tenure_years"],
)

# Cross-price elasticity & cannibalization
result = db.journeys.cross_price(
    df, quantity_col="units", own_price_col="price_a", other_price_cols=["price_b", "price_c"],
)

# Intervention lift — did this promo/price change/policy actually move the metric?
result = db.journeys.intervention_lift(
    df, date_col="day", value_col="conversions", intervention_date="2026-06-01",
)
```

## Tiers

| Tier | Price | Analysis calls/month | Knowledge Q&A calls/month | Skills |
|---|---|---|---|---|
| Developer | Free | 100 | 50 | Core analysis skills |
| Pro | $49/month | 2,000 | 1,000 | All skills |
| Business | $299/month | 15,000 | Unlimited (fair use) | All skills + journey endpoints |
| Enterprise | Custom | Unlimited | Unlimited | Everything |

Get a key at [databubble.ai](https://databubble.ai).

## Related repositories

- **databubble** — the main platform (API + skills + journeys + front-end).
- **databubble-knowledge** — the knowledge / Obsidian vault.

## Releasing a new version

See `RELEASING.md` for the full flow. Short version:
`scripts/check_local.sh` (build + test + drift check) -> `scripts/publish_testpypi.sh`
(dry run) -> `scripts/publish_release.sh` (real PyPI, manually gated).
