# databubble/charts.py
"""
Chart access for notebook users.

Two sources, in preference order:

1. Inline SVG carried in the response (`charts` / `chart_svg` keys). This is
   what Track B adds to /v1/journeys/*, and what POST /v1/eda already does
   today. No second request, no shared directory, nothing orphaned on disk.

2. A server-side file path (`{"svg": "/abs/path/x_9f3a.svg", "png": ...}`),
   which several /v1/skills/* responses already return inside
   `result.findings`. Only the basename is usable: it is fetched from
   GET /v1/charts/{filename}, which is public and unauthenticated by design
   so the web app can load charts in an <img> tag.

ChartSet is lazy — nothing is fetched until you ask for bytes.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional


class Chart:
    """One chart. Either inline SVG text, or a name to fetch on demand."""

    def __init__(
        self,
        key: str,
        svg: Optional[str] = None,
        name: Optional[str] = None,
        png_name: Optional[str] = None,
        http=None,
    ):
        self.key = key
        self._svg = svg
        self.name = name
        self.png_name = png_name
        self._http = http

    # -- content ----------------------------------------------------------
    @property
    def svg(self) -> Optional[str]:
        """SVG source, fetching from /v1/charts/{name} if it is not inline."""
        if self._svg is None and self.name and self._http is not None:
            self._svg = self._http.get_text(f"/v1/charts/{self.name}")
        return self._svg

    def png(self) -> Optional[bytes]:
        if not self.png_name or self._http is None:
            return None
        return self._http.get_bytes(f"/v1/charts/{self.png_name}")

    # -- notebook ---------------------------------------------------------
    def show(self):
        """Render inline in a Jupyter notebook."""
        try:
            from IPython.display import SVG, display
        except ImportError:  # pragma: no cover
            print(f"Chart '{self.key}' — install ipython to render, or use .svg / .save()")
            return
        source = self.svg
        if source:
            display(SVG(source))

    def _repr_html_(self) -> str:
        source = self._svg
        if source:
            return source
        return f"<em>Chart '{self.key}' (not yet fetched — call .svg or .show())</em>"

    def save(self, path: str) -> str:
        source = self.svg
        if source is None:
            raise ValueError(f"Chart '{self.key}' has no retrievable content.")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source)
        return path

    def __repr__(self) -> str:
        where = "inline" if self._svg is not None else (self.name or "unavailable")
        return f"Chart({self.key}, {where})"


class ChartSet:
    """Dict-like collection of Chart objects."""

    def __init__(self, charts: Optional[dict[str, Chart]] = None):
        self._charts: dict[str, Chart] = charts or {}

    def __len__(self) -> int:
        return len(self._charts)

    def __bool__(self) -> bool:
        return bool(self._charts)

    def __iter__(self) -> Iterator[str]:
        return iter(self._charts)

    def __getitem__(self, key: str) -> Chart:
        return self._charts[key]

    def keys(self):
        return self._charts.keys()

    def values(self):
        return self._charts.values()

    def items(self):
        return self._charts.items()

    def get(self, key: str, default=None):
        return self._charts.get(key, default)

    def show(self, key: Optional[str] = None):
        """Render one chart, or all of them."""
        targets = [self._charts[key]] if key else list(self._charts.values())
        for chart in targets:
            chart.show()

    def save_all(self, directory: str) -> list[str]:
        import os

        os.makedirs(directory, exist_ok=True)
        written = []
        for key, chart in self._charts.items():
            written.append(chart.save(os.path.join(directory, f"{key}.svg")))
        return written

    def _repr_html_(self) -> str:
        if not self._charts:
            return (
                "<em>No charts in this response. Journeys return charts only when the "
                "server supports <code>include_charts</code> (Track B); skills return "
                "them via <code>result.charts</code>.</em>"
            )
        return "".join(
            f"<div style='margin-bottom:12px'><strong>{key}</strong>{chart._repr_html_()}</div>"
            for key, chart in self._charts.items()
        )

    def __repr__(self) -> str:
        return f"ChartSet({list(self._charts)})"


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _basename(path: Any) -> Optional[str]:
    if not isinstance(path, str) or not path:
        return None
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def from_response(payload: Any, http=None) -> ChartSet:
    """
    Build a ChartSet from any nested response fragment.

    Handles all shapes seen in the wild:
      {"charts": {"histogram": "<svg .../>"}}          inline (Track B, /v1/eda)
      {"all_charts": {"histogram": {"svg": "/path"}}}  file paths (/v1/analyse)
      {"chart_histogram": {"svg": "/p.svg", "png": "/p.png"}}   skills findings
      {"chart_svg": "<svg .../>"}                      eda relationship
    """
    charts: dict[str, Chart] = {}
    if not isinstance(payload, dict):
        return ChartSet()

    def add(key: str, value: Any):
        if key in charts:
            return
        if isinstance(value, str) and value.lstrip().startswith("<svg"):
            charts[key] = Chart(key, svg=value, http=http)
        elif isinstance(value, str) and value.endswith((".svg", ".png")):
            name = _basename(value)
            charts[key] = Chart(key, name=name, http=http)
        elif isinstance(value, dict):
            svg_name = _basename(value.get("svg"))
            png_name = _basename(value.get("png"))
            inline = value.get("svg") if isinstance(value.get("svg"), str) and value["svg"].lstrip().startswith("<svg") else None
            if inline:
                charts[key] = Chart(key, svg=inline, png_name=png_name, http=http)
            elif svg_name or png_name:
                charts[key] = Chart(key, name=svg_name or png_name, png_name=png_name, http=http)

    for container_key in ("charts", "all_charts", "chart_paths"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            for key, value in container.items():
                add(str(key), value)

    for key, value in payload.items():
        if key == "chart_svg" and isinstance(value, str):
            add("relationship", value)
        elif key.startswith("chart_"):
            add(key[len("chart_"):], value)

    return ChartSet(charts)
