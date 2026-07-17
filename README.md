# DataBubble SDK

Statistical Intelligence as a Service. Current version: **0.2.0**.

**Pre-release:** the package isn't published to PyPI yet — until then, install
from source:

```bash
pip install git+https://github.com/sss828412/databubble-python.git
# or, for local development:
pip install -e .
```

Once released, install will be:

```bash
pip install databubble httpx pandas
```

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
```

## Tiers

| Tier | Price | Analysis calls/month | Knowledge Q&A calls/month | Skills |
|---|---|---|---|---|
| Developer | Free | 100 | 50 | Core analysis skills |
| Pro | $49/month | 2,000 | 1,000 | All skills |
| Business | $299/month | 15,000 | Unlimited (fair use) | All skills + journey endpoints |
| Enterprise | Custom | Unlimited | Unlimited | Everything |

Get a key at [databubble.ai](https://databubble.ai).
