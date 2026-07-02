"""
DataBubble SDK — Quickstart
===========================
Five minutes from key to first result.

Prerequisites:
    pip install databubble httpx pandas

Get a key at databubble.ai (free developer tier: 500 calls/month).
"""

import pandas as pd
from databubble import DataBubble

# ---------------------------------------------------------------------------
# 1. Initialise the client
# ---------------------------------------------------------------------------
db = DataBubble(api_key="dbk_your_key_here")
# Or set DATABUBBLE_API_KEY env var and call DataBubble() with no args.

# ---------------------------------------------------------------------------
# 2. Load some data
# ---------------------------------------------------------------------------
df = pd.DataFrame({
    "price": [8.5, 9.0, 10.0, 10.5, 11.0, 12.0, 13.5, 14.0, 15.0,
              8.0, 9.5, 11.5, 12.5, 10.0, 9.0, 13.0, 14.5, 8.5,
              10.5, 11.0, 12.0, 9.5, 10.0, 11.5, 13.0, 14.0, 8.0,
              9.0, 10.5, 12.5],
    "sales": [120, 115, 100, 98, 90, 82, 71, 68, 60,
              125, 110, 88, 75, 100, 115, 73, 65, 122,
              96, 92, 84, 111, 102, 87, 74, 67, 127,
              118, 95, 78],
})

# ---------------------------------------------------------------------------
# 3. Analyse price distribution
# ---------------------------------------------------------------------------
result = db.skills.univariate(df["price"])

print("=== Univariate Analysis: Price ===")
print(f"Summary:  {result.summary}")
print(f"Skewness: {result.findings.get('skewness', 'n/a'):.3f}")
if result.warnings:
    print("Warnings:")
    for w in result.warnings:
        print(f"  ⚠  {w}")
if result.recommendations:
    print("Recommendations:")
    for r in result.recommendations:
        print(f"  →  {r}")
print(f"Learn more: {result.chapter_ref}")

# ---------------------------------------------------------------------------
# 4. Profile missing values across all columns
# ---------------------------------------------------------------------------
result_mv = db.skills.missing_values(df)

print("\n=== Missing Value Profile ===")
print(f"Summary: {result_mv.summary}")

# ---------------------------------------------------------------------------
# 5. Export a memory file for next session
# ---------------------------------------------------------------------------
mem = db.memory.export(df, label="Price-sales data — quickstart")
mem.save("quickstart_memory.json")
mem.save_markdown("quickstart_memory.md")

print(f"\n=== Memory Exported ===")
print(f"Columns covered: {mem.columns_covered}")
print(f"Open items:      {mem.open_count}")
print(f"Saved to:        quickstart_memory.json + quickstart_memory.md")

# ---------------------------------------------------------------------------
# 6. Next session — load the memory
# ---------------------------------------------------------------------------
# mem_loaded = db.memory.load_file("quickstart_memory.json")
# reconciliation = db.memory.reconcile(
#     memories=[mem_loaded],
#     df=new_df,
#     note="applied log transform to price as recommended"
# )
# print(reconciliation.suggested_next)
