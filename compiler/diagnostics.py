"""
compiler/diagnostics.py
Diagnostic normalization and root-cause grouping pipeline.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from compiler.models import Diagnostic, DiagnosticCategory, Severity, SourceSpan


@dataclass
class DiagnosticGroup:
    """A cluster of related diagnostics with an inferred root cause."""
    group_id: str
    root_cause_id: str          # diagnostic_id of the likely initiating error
    member_ids: List[str] = field(default_factory=list)
    cascade_ids: List[str] = field(default_factory=list)  # likely cascades
    relationship: str = "inferred"   # "certain" | "inferred" | "speculative"
    explanation: str = ""


class DiagnosticPipeline:
    """
    Normalizes, deduplicates, and groups compiler diagnostics.

    Heuristic grouping algorithm:
    1. Sort by (line, column).
    2. Mark the first error in each syntactic region as a root-cause candidate.
    3. If subsequent errors are within CASCADE_LINE_RADIUS lines and share
       a similar token, mark them as likely cascades of the candidate.
    4. Assign stable group IDs and uncertainty labels.
    """

    CASCADE_LINE_RADIUS = 5

    def __init__(self) -> None:
        self._groups: List[DiagnosticGroup] = []

    def process(self, diagnostics: List[Diagnostic]) -> List[Diagnostic]:
        """
        Assign diagnostic_ids, group_ids, and related_ids.
        Returns the enriched list (sorted by location).
        """
        # Assign stable IDs
        for i, d in enumerate(diagnostics):
            if not d.diagnostic_id:
                d.diagnostic_id = f"D{i:04d}"

        # Sort by source location
        def _sort_key(d: Diagnostic) -> Tuple[int, int]:
            p = d.span.start
            return (p.line if p.line > 0 else 9999, p.column)

        sorted_diags = sorted(diagnostics, key=_sort_key)
        errors = [d for d in sorted_diags if d.severity == Severity.ERROR]

        # Group: sliding window heuristic
        self._groups = []
        visited: Set[str] = set()

        for i, root in enumerate(errors):
            if root.diagnostic_id in visited:
                continue
            visited.add(root.diagnostic_id)

            group_id = f"G{i:03d}"
            root.group_id = group_id
            cascades: List[str] = []

            root_line = root.span.start.line

            for j in range(i + 1, len(errors)):
                candidate = errors[j]
                if candidate.diagnostic_id in visited:
                    continue
                cand_line = candidate.span.start.line
                if abs((cand_line - root_line) <= self.CASCADE_LINE_RADIUS and candidate.category == root.category
    and candidate.code == root.code):
                    # Speculative: same region
                    candidate.group_id = group_id
                    cascade_explanation = (
                        f"This error may be a cascade of '{root.message}' "
                        f"at line {root_line}. Fixing that first may resolve it."
                    )
                    if not candidate.explanation:
                        candidate.explanation = cascade_explanation
                    cascades.append(candidate.diagnostic_id)
                    visited.add(candidate.diagnostic_id)

            group = DiagnosticGroup(
                group_id=group_id,
                root_cause_id=root.diagnostic_id,
                member_ids=[root.diagnostic_id] + cascades,
                cascade_ids=cascades,
                relationship="inferred" if cascades else "certain",
                explanation=(
                    f"Root cause: {root.message} at {root.short_location()}. "
                    f"{len(cascades)} likely cascade(s) identified."
                    if cascades
                    else f"Isolated error: {root.message}."
                ),
            )
            self._groups.append(group)

        # Wire related_ids
        id_to_diag: Dict[str, Diagnostic] = {d.diagnostic_id: d for d in sorted_diags}
        for grp in self._groups:
            for did in grp.member_ids:
                if did in id_to_diag:
                    related = [m for m in grp.member_ids if m != did]
                    id_to_diag[did].related_ids = related

        return sorted_diags

    @property
    def groups(self) -> List[DiagnosticGroup]:
        return self._groups

    def summary(self) -> str:
        lines = [f"Diagnostic groups: {len(self._groups)}"]
        for g in self._groups:
            lines.append(
                f"  [{g.group_id}] root={g.root_cause_id} "
                f"cascades={len(g.cascade_ids)} ({g.relationship})"
            )
        return "\n".join(lines)
