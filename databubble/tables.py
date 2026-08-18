# databubble/tables.py
"""
Tabular rendering helpers for the data-scientist-first result surface.

Everything here is defensive: the API envelope is a moving target, so each
helper reads with .get() chains and returns an empty frame rather than
raising when a field is absent. That means the SDK degrades gracefully
against an older or newer API without a version handshake.

pandas is a hard dependency from 0.5.0 onward, but the import is kept local
so that importing databubble.tables never fails at import time.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

# Canonical column order for a regression estimate table. Keys are the
# envelope's field names (skills/models/linear_regression.py:PredictorEstimate),
# values are the display labels used in summary() and _repr_html_.
ESTIMATE_COLUMNS: dict[str, str] = {
    "name": "predictor",
    "coefficient": "coef",
    "std_error": "std err",
    "t_statistic": "t",
    "p_value": "P>|t|",
    "ci_lower": "[0.025",
    "ci_upper": "0.975]",
    "vif": "VIF",
    "is_significant": "sig",
}

# Fields carried through to .diagnostics, in display order.
DIAGNOSTIC_FIELDS: Sequence[str] = (
    "n_observations",
    "adj_r_squared",
    "assumptions_met",
    "transformation_applied",
    "transformation_validated",
    "significant",
    "ci_lower",
    "ci_upper",
    "icc",
    "group_mode",
    "grouping_column",
)


def _pandas():
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - hard dependency from 0.5.0
        raise ImportError(
            "pandas is required for the DataFrame surface. pip install pandas"
        ) from exc
    return pd


def rows_to_frame(rows: Any, order: Optional[dict[str, str]] = None):
    """
    Turn a list of dicts from the API into a DataFrame.

    Returns an empty DataFrame (not None, not a raise) when rows is missing,
    empty, or not a list of dicts — callers can always chain .empty on it.
    """
    pd = _pandas()
    if not rows or not isinstance(rows, list):
        return pd.DataFrame()
    if not all(isinstance(r, dict) for r in rows):
        return pd.DataFrame({"value": rows})

    frame = pd.DataFrame(rows)
    if order:
        present = [c for c in order if c in frame.columns]
        rest = [c for c in frame.columns if c not in order]
        frame = frame[present + rest]
    return frame


def mapping_to_frame(mapping: Any, key_name: str = "predictor", value_name: str = "value"):
    """Turn {predictor: number} into a two-column DataFrame."""
    pd = _pandas()
    if not isinstance(mapping, dict) or not mapping:
        return pd.DataFrame()
    return pd.DataFrame(
        {key_name: list(mapping.keys()), value_name: list(mapping.values())}
    )


def _fmt(value: Any, width: int = 10, places: int = 4) -> str:
    if value is None:
        return " " * (width - 1) + "-"
    if isinstance(value, bool):
        return f"{'yes' if value else 'no':>{width}}"
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return f"{value:>{width}d}"
    if isinstance(value, float):
        if value != value:  # NaN
            return " " * (width - 3) + "nan"
        return f"{value:>{width}.{places}f}"
    text = str(value)
    return f"{text:>{width}}" if len(text) <= width else text[: width - 1] + "…"


def estimate_table(frame, max_rows: int = 50) -> str:
    """Render an estimates DataFrame as a fixed-width statsmodels-style table."""
    if frame is None or getattr(frame, "empty", True):
        return "  (no per-predictor estimates in this response)"

    cols = [c for c in ESTIMATE_COLUMNS if c in frame.columns]
    if "name" not in cols:
        return "  (estimates present but unrecognised shape — see .estimates)"

    name_width = max([len("predictor")] + [len(str(v)) for v in frame["name"]])
    name_width = min(name_width, 28)

    value_cols = [c for c in cols if c != "name"]
    header = f"{'predictor':<{name_width}}" + "".join(
        f"{ESTIMATE_COLUMNS[c]:>10}" for c in value_cols
    )
    rule = "-" * len(header)

    lines = [header, rule]
    for _, row in frame.head(max_rows).iterrows():
        name = str(row["name"])
        if len(name) > name_width:
            name = name[: name_width - 1] + "…"
        line = f"{name:<{name_width}}"
        for col in value_cols:
            places = 3 if col in ("t_statistic", "p_value", "vif") else 4
            line += _fmt(row.get(col), 10, places)
        lines.append(line)

    if len(frame) > max_rows:
        lines.append(f"... {len(frame) - max_rows} more rows (see .estimates)")
    return "\n".join(lines)


def header_block(title: str, pairs: Sequence[tuple[str, Any]], width: int = 78) -> str:
    """Render the '=====' title bar plus a two-column key/value block."""
    lines = [title, "=" * max(len(title), width)]
    rendered = []
    for label, value in pairs:
        if value is None:
            continue
        if isinstance(value, bool):
            value = "yes" if value else "no"
        elif isinstance(value, float):
            value = f"{value:.4g}"
        rendered.append(f"{label}: {value}")

    for i in range(0, len(rendered), 3):
        lines.append("   ".join(f"{c:<24}" for c in rendered[i : i + 3]).rstrip())
    return "\n".join(lines)


def warnings_block(warnings: Sequence[str], limit: int = 10) -> str:
    if not warnings:
        return ""
    head = f"\nWarnings ({len(warnings)}):"
    body = "\n".join(f"  - {w}" for w in list(warnings)[:limit])
    if len(warnings) > limit:
        body += f"\n  ... {len(warnings) - limit} more (see .warnings)"
    return head + "\n" + body


def frame_to_html(frame, caption: str = "") -> str:
    if frame is None or getattr(frame, "empty", True):
        return ""
    try:
        table = frame.to_html(index=False, border=0, classes="databubble-table")
    except Exception:  # pragma: no cover - defensive
        return ""
    cap = f"<p style='margin:0 0 4px 0;font-weight:600'>{caption}</p>" if caption else ""
    return cap + table


def escape(text: Any) -> str:
    import html

    return html.escape("" if text is None else str(text))
