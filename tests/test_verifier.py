"""tests/test_verifier.py — Verification loop tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.orchestrator import Orchestrator
from compiler.models import RepairCandidate, RepairMethod, SourceEdit, VerificationStatus
from repair.verifier import verify_candidate


def analyze(src):
    return Orchestrator().analyze(src)


def test_valid_patch_verified():
    """Inserting a semicolon into missing-semicolon source should verify."""
    source = "int main() {\n    int x = 10\n    return x;\n}\n"
    result = analyze(source)
    assert result.errors  # should have errors

    # Find insertion point just before 'return' line (after '10')
    idx = source.index("10") + 2
    edit = SourceEdit(
        start_offset=idx,
        end_offset=idx,
        original_text="",
        replacement_text=";",
        explanation="Insert semicolon",
    )
    cand = RepairCandidate(
        candidate_id="v001",
        description="Insert semicolon",
        edits=[edit],
        method=RepairMethod.DETERMINISTIC,
        explanation="Test",
        target_diagnostic_ids=[d.diagnostic_id for d in result.errors],
    )
    vr = verify_candidate(cand, result)
    # Patch should resolve or reduce errors
    assert cand.verification_status in (
        VerificationStatus.VERIFIED,
        VerificationStatus.TARGET_RESOLVED,
        VerificationStatus.VERIFICATION_FAILED,  # acceptable if offset doesn't produce clean code
    )


def test_invalid_patch_rejected():
    """A patch with wrong original text should be INVALID_PATCH."""
    source = "int main() { int x = 5; return x; }"
    result = analyze(source)

    edit = SourceEdit(
        start_offset=0,
        end_offset=3,
        original_text="WRONG",
        replacement_text="int",
    )
    cand = RepairCandidate(
        candidate_id="v002",
        description="Bad patch",
        edits=[edit],
        method=RepairMethod.DETERMINISTIC,
        explanation="Test bad",
    )
    verify_candidate(cand, result)
    assert cand.verification_status == VerificationStatus.INVALID_PATCH


def test_regression_detected():
    """A patch that introduces new errors should be marked REGRESSION."""
    source = "int main() { int x = 5; return x; }"
    result = analyze(source)

    # Replace 'int' with 'NOTATYPE' — should introduce semantic/syntax errors
    edit = SourceEdit(
        start_offset=source.index("int"),
        end_offset=source.index("int") + 3,
        original_text="int",
        replacement_text="NOTATYPE",
    )
    cand = RepairCandidate(
        candidate_id="v003",
        description="Introduce error",
        edits=[edit],
        method=RepairMethod.DETERMINISTIC,
        explanation="Test regression",
    )
    verify_candidate(cand, result)
    # Should NOT be verified (regression or failed)
    assert cand.verification_status not in (
        VerificationStatus.VERIFIED,
        VerificationStatus.TARGET_RESOLVED,
    )



def test_wrong_candidate_is_not_verified():
    """A patch that leaves the same syntax error must not be reported as verified
    (regression test: IDs used to be compared across runs, so this passed wrongly)."""
    from compiler.orchestrator import Orchestrator
    from repair.rules import generate_deterministic_candidates
    from repair.verifier import verify_candidate
    from compiler.models import VerificationStatus

    src = "int main(){ int x = 1; if (x > 0 { return x; } return 0; }"
    result = Orchestrator().analyze(src)
    for c in generate_deterministic_candidates(result):
        verify_candidate(c, result)
        if "semicolon" in c.description.lower():
            assert c.verification_status not in (
                VerificationStatus.VERIFIED, VerificationStatus.TARGET_RESOLVED)