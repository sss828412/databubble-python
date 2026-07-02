# databubble/models.py
"""
Typed return objects for the DataBubble SDK.

Deliberately lightweight — plain dataclasses, no Pydantic dependency.
Every object exposes `.raw` for full API response access.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillResult:
    """
    Return type for all skill calls.

    Attributes:
        summary         Plain-English summary of the finding (token-efficient).
        findings        Dict of structured findings — skewness, mean, mechanism etc.
        warnings        List of warning strings — assumption violations, data issues.
        recommendations List of recommendation strings — what to do next.
        chapter_ref     Knowledge chapter reference e.g. "Chapter 04".
        skill_name      Which skill was called.
        column          Column analysed (None for whole-dataset skills).
        n_rows          Row count of the input data.
        tier            API tier used for this call.
        key_prefix      Key prefix for audit trail.
        raw             Full API response dict — access anything not surfaced above.
    """
    summary: str
    findings: dict[str, Any]
    warnings: list[str]
    recommendations: list[str]
    chapter_ref: str
    skill_name: str
    column: Optional[str] = None
    n_rows: Optional[int] = None
    tier: Optional[str] = None
    key_prefix: Optional[str] = None
    raw: dict = field(default_factory=dict)

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def has_blocking_issues(self) -> bool:
        """True if any warning uses the word 'blocking' or 'halt'."""
        lower = [w.lower() for w in self.warnings]
        return any("blocking" in w or "halt" in w for w in lower)

    def __repr__(self) -> str:
        warn_str = f", {len(self.warnings)} warnings" if self.warnings else ""
        col_str = f" on '{self.column}'" if self.column else ""
        return f"SkillResult({self.skill_name}{col_str}{warn_str})"


@dataclass
class TreatmentRecord:
    """One platform recommendation on one column."""
    column: str
    issue: str
    recommendation: str
    severity: str          # "blocking" / "warning" / "informational"
    status: str            # "open" / "applied" / "deferred" / "overridden"


@dataclass
class ColumnMemory:
    """Analytical record for one column from a memory file."""
    name: str
    skewness: Optional[float]
    mean: Optional[float]
    median: Optional[float]
    missing_pct: float
    missing_mechanism: Optional[str]
    variable_type: Optional[str]
    is_bounded_ordinal: bool
    blocking_issues: list[str]
    treatments: list[TreatmentRecord]

    @property
    def has_blocking_issues(self) -> bool:
        return len(self.blocking_issues) > 0

    @property
    def open_treatments(self) -> list[TreatmentRecord]:
        return [t for t in self.treatments if t.status == "open"]


@dataclass
class MemoryResult:
    """
    Return type for db.memory.export().

    Attributes:
        memory_id       UUID for this memory file.
        label           User-given label.
        memory_json     Full memory dict — pass to save() or load back later.
        memory_markdown Human-readable narrative string.
        open_count      Number of unresolved recommendations.
        blocking_count  Number of columns with blocking issues.
        columns_covered Number of columns with univariate coverage.
        raw             Full API response.
    """
    memory_id: str
    label: str
    memory_json: dict
    memory_markdown: str
    open_count: int
    blocking_count: int
    columns_covered: int
    raw: dict = field(default_factory=dict)

    def save(self, path: str) -> None:
        """Write memory_json to disk as a .json file."""
        import json
        with open(path, "w") as f:
            json.dump(self.memory_json, f, indent=2)
        print(f"Memory saved to {path}")

    def save_markdown(self, path: str) -> None:
        """Write human-readable narrative to disk as a .md file."""
        with open(path, "w") as f:
            f.write(self.memory_markdown)
        print(f"Markdown summary saved to {path}")

    def __repr__(self) -> str:
        return (
            f"MemoryResult('{self.label}', "
            f"{self.columns_covered} columns covered, "
            f"{self.open_count} open items)"
        )


@dataclass
class ColumnReconciliation:
    name: str
    status: str            # matched / missing_in_new / new_column / stats_shifted
    memory_source: Optional[str]
    shift_note: Optional[str]


@dataclass
class ReconciliationResult:
    """
    Return type for db.memory.reconcile().

    Attributes:
        memories_loaded         Labels of loaded memory files.
        columns_matched         Per-column reconciliation status.
        open_items              Unresolved recommendations from all memories.
        verified_treatments     Treatments user claimed that platform could verify.
        unverifiable_treatments Treatments platform could not confirm from data.
        ready_to_advance        True when all columns have univariate coverage (Option A).
        suggested_next          Plain-English suggestion for next analysis step.
        inherited_column_memories  Dict of col_name → column facts for EDA orchestrator.
        raw                     Full API response.
    """
    memories_loaded: list[str]
    columns_matched: list[ColumnReconciliation]
    open_items: list[str]
    verified_treatments: list[str]
    unverifiable_treatments: list[str]
    ready_to_advance: bool
    suggested_next: str
    inherited_column_memories: dict
    raw: dict = field(default_factory=dict)

    @property
    def new_columns(self) -> list[str]:
        return [c.name for c in self.columns_matched if c.status == "new_column"]

    @property
    def shifted_columns(self) -> list[str]:
        return [c.name for c in self.columns_matched if c.status == "stats_shifted"]

    def __repr__(self) -> str:
        return (
            f"ReconciliationResult("
            f"{len(self.memories_loaded)} memories, "
            f"ready={self.ready_to_advance}, "
            f"open={len(self.open_items)})"
        )
