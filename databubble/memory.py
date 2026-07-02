# databubble/memory.py
"""
MemoryClient — export, load, and reconcile AnalyticalMemory files.
"""

from __future__ import annotations

import json
from typing import Optional

from databubble.models import (
    MemoryResult, ReconciliationResult,
    ColumnReconciliation, TreatmentRecord, ColumnMemory,
)
from databubble.exceptions import SDKUsageError


class MemoryClient:
    def __init__(self, http_client):
        self._http = http_client

    def export(
        self,
        df,
        label: str,
        eda_result: Optional[dict] = None,
        journey_results: Optional[list] = None,
    ) -> MemoryResult:
        """
        Export current session analysis as a portable AnalyticalMemory file.

        Args:
            df:              The DataFrame that was analysed this session.
            label:           Human-readable label e.g. "POS data — June 2026".
            eda_result:      EDA report dict if EDA was run (optional).
            journey_results: List of journey output dicts if journeys ran (optional).

        Returns:
            MemoryResult with .save() and .save_markdown() convenience methods.

        Example:
            mem = db.memory.export(df, label="POS data June 2026")
            mem.save("pos_memory.json")
            mem.save_markdown("pos_memory.md")
        """
        try:
            import pandas as pd
        except ImportError:
            raise SDKUsageError("pandas is required.")

        if not isinstance(df, pd.DataFrame):
            raise SDKUsageError("export() requires a pd.DataFrame.")
        if not label or not label.strip():
            raise SDKUsageError("label is required and cannot be empty.")

        response = self._http.post_multipart(
            "/v1/memory/export",
            fields={
                "label": label,
                "eda_result": json.dumps(eda_result) if eda_result else None,
                "journey_results": json.dumps(journey_results) if journey_results else None,
            },
            files={"file": ("data.csv", df.to_csv(index=False), "text/csv")},
        )

        return MemoryResult(
            memory_id=response["memory_id"],
            label=label,
            memory_json=response["memory_json"],
            memory_markdown=response["memory_markdown"],
            open_count=response.get("open_count", 0),
            blocking_count=response.get("blocking_count", 0),
            columns_covered=response.get("columns_with_univariate", 0),
            raw=response,
        )

    def load_file(self, path: str) -> dict:
        """
        Load a memory file from disk.
        Returns the raw memory dict for use with reconcile().

        Example:
            mem1 = db.memory.load_file("pos_memory.json")
            mem2 = db.memory.load_file("customer_memory.json")
            reconciliation = db.memory.reconcile(
                memories=[mem1, mem2], df=joined_df,
                note="joined on customer_id"
            )
        """
        with open(path) as f:
            return json.load(f)

    def reconcile(
        self,
        memories: list,
        df,
        note: str = "",
        treatments_applied: Optional[list[str]] = None,
        treatments_deferred: Optional[list[str]] = None,
    ) -> ReconciliationResult:
        """
        Load memory files alongside a new DataFrame.
        Returns a ReconciliationResult describing what was inherited,
        what's still open, and what to do next.

        Args:
            memories:             List of memory dicts (from load_file() or
                                  MemoryResult.memory_json).
            df:                   The new combined DataFrame.
            note:                 Free text — what you did between sessions.
                                  e.g. "joined POS and customer on customer_id,
                                        log transform applied to price"
            treatments_applied:   Column names where you applied a treatment.
            treatments_deferred:  Column names where you skipped a treatment.

        Returns:
            ReconciliationResult — .ready_to_advance tells you if all columns
            have univariate coverage (Option A). .new_columns lists columns
            that need analysis. .suggested_next recommends the next step.
        """
        try:
            import pandas as pd
        except ImportError:
            raise SDKUsageError("pandas is required.")

        if not isinstance(df, pd.DataFrame):
            raise SDKUsageError("reconcile() requires a pd.DataFrame.")
        if not memories:
            raise SDKUsageError("reconcile() requires at least one memory dict.")

        import tempfile, os
        tmp_files = []
        try:
            file_tuples = []
            for i, mem in enumerate(memories):
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".json", delete=False, mode="w"
                )
                json.dump(mem, tmp)
                tmp.close()
                tmp_files.append(tmp.name)
                file_tuples.append(
                    ("memory_files", (f"memory_{i}.json",
                     open(tmp.name, "rb"), "application/json"))
                )

            session_note = {
                "what_was_done": note,
                "treatments_applied": treatments_applied or [],
                "treatments_deferred": treatments_deferred or [],
                "other_notes": None,
            }

            response = self._http.post_multipart(
                "/v1/memory/load",
                fields={"session_note": json.dumps(session_note)},
                files={
                    **{f"memory_file_{i}": t[1] for i, t in enumerate(file_tuples)},
                    "new_csv": ("data.csv", df.to_csv(index=False), "text/csv"),
                },
            )
        finally:
            for path in tmp_files:
                try:
                    os.unlink(path)
                except Exception:
                    pass

        rec = response.get("reconciliation", {})
        columns_matched = [
            ColumnReconciliation(
                name=c["name"],
                status=c["status"],
                memory_source=c.get("memory_source"),
                shift_note=c.get("shift_note"),
            )
            for c in rec.get("columns_matched", [])
        ]

        return ReconciliationResult(
            memories_loaded=rec.get("memories_loaded", []),
            columns_matched=columns_matched,
            open_items=rec.get("open_items", []),
            verified_treatments=rec.get("verified_treatments", []),
            unverifiable_treatments=rec.get("unverifiable_treatments", []),
            ready_to_advance=rec.get("ready_to_advance", False),
            suggested_next=rec.get("suggested_next", ""),
            inherited_column_memories=response.get("inherited_column_memories", {}),
            raw=response,
        )
