# DataBubble SDK

Statistical Intelligence as a Service.

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

## Tiers

| Tier | Price | Calls/month | Skills |
|---|---|---|---|
| Developer | Free | 500 | Core analysis skills |
| Pro | $49/month | 10,000 | All skills |
| Business | $299/month | 100,000 | All skills + journey endpoints |
| Enterprise | Custom | Unlimited | Everything |

Get a key at [databubble.ai](https://databubble.ai).
