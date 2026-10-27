"""
repair/ranking.py
Candidate ranking using compiler-verified evidence.
"""
from __future__ import annotations

from typing import List

from compiler.models import RepairCandidate, Severity, VerificationStatus


def rank_candidates(candidates: List[RepairCandidate]) -> List[RepairCandidate]:
    """
    Score and sort candidates using explicit criteria:

    1. Verification status (VERIFIED > TARGET_RESOLVED > NOT_CHECKED > FAILED > REGRESSION)
    2. Whether the patch is syntactically minimal (fewer edits preferred)
    3. Initial rule-assigned rank_score
    4. AI vs deterministic (deterministic slightly preferred for same score)
    """
    from compiler.models import RepairMethod

    STATUS_WEIGHT = {
        VerificationStatus.VERIFIED: 1.0,
        VerificationStatus.TARGET_RESOLVED: 0.8,
        VerificationStatus.NOT_CHECKED: 0.5,
        VerificationStatus.VERIFICATION_FAILED: 0.2,
        VerificationStatus.INVALID_PATCH: 0.0,
        VerificationStatus.REGRESSION: -0.5,
    }

    for c in candidates:
        status_score = STATUS_WEIGHT.get(c.verification_status, 0.3)
        minimal_score = 1.0 / (1 + len(c.edits))   # fewer edits → higher
        method_score = 0.05 if c.method == RepairMethod.DETERMINISTIC else 0.0

        # Check regression: did new errors appear?
        before_errors = {d.diagnostic_id for d in c.diagnostics_before if d.severity == Severity.ERROR}
        after_errors = {d.diagnostic_id for d in c.diagnostics_after if d.severity == Severity.ERROR}
        regression_penalty = 0.0
        if c.diagnostics_after:
            new_count = len(after_errors - before_errors)
            regression_penalty = min(0.5, new_count * 0.1)

        c.rank_score = (
            status_score * 0.50
            + c.rank_score * 0.30
            + minimal_score * 0.15
            + method_score * 0.05
            - regression_penalty
        )

        reasons = []
        reasons.append(f"Verification: {c.verification_status.value}")
        reasons.append(f"Edits: {len(c.edits)}")
        if regression_penalty:
            reasons.append(f"Regression penalty: -{regression_penalty:.2f}")
        c.rank_reason = " | ".join(reasons)

    return sorted(candidates, key=lambda c: c.rank_score, reverse=True)
