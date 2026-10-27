"""tests/test_integration.py — End-to-end integration tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.orchestrator import Orchestrator
from compiler.models import AnalysisStatus, DiagnosticCategory, Severity
from repair.rules import generate_deterministic_candidates
from repair.verifier import verify_candidate
from repair.ranking import rank_candidates


def full_pipeline(src):
    orch = Orchestrator()
    result = orch.analyze(src)
    candidates = generate_deterministic_candidates(result)
    for c in candidates:
        verify_candidate(c, result)
    candidates = rank_candidates(candidates)
    return result, candidates


# ---- Demo A: valid code ----

def test_demo_a_valid():
    src = "int main() {\n    int x = 10;\n    int y = x + 5;\n    return y;\n}\n"
    result, candidates = full_pipeline(src)
    assert result.status == AnalysisStatus.SUCCESS
    assert not result.errors
    assert not candidates
    assert result.ast is not None


# ---- Demo B: missing semicolon ----

def test_demo_b_missing_semicolon():
    src = "int main() {\n    int x = 10\n    return x;\n}\n"
    result, candidates = full_pipeline(src)
    assert result.has_errors
    syntax_errs = result.syntax_diagnostics
    assert len(syntax_errs) >= 1
    # Should have a semicolon repair candidate
    sem_cands = [c for c in candidates if "semicolon" in c.description.lower()]
    assert len(sem_cands) >= 1


# ---- Demo C: undeclared identifier ----

def test_demo_c_undeclared():
    src = "int main() {\n    int x = 10;\n    return y;\n}\n"
    result, candidates = full_pipeline(src)
    assert result.has_errors
    sem_errs = result.semantic_diagnostics
    assert any(e.code == "SEM001" for e in sem_errs)
    # An undeclared identifier may produce an ambiguous suggestion,
    # but it must never be treated as an automatic safe fix.
    assert all(c.intent != "safe_fix" for c in candidates)
    assert all(c.intent == "ambiguous" for c in candidates)


# ---- Demo D: type mismatch ----

def test_demo_d_type_mismatch():
    src = 'int main() {\n    int x = "hello";\n    return x;\n}\n'
    result, candidates = full_pipeline(src)
    assert result.has_errors
    sem_errs = result.semantic_diagnostics
    assert any(e.code == "SEM003" for e in sem_errs)


# ---- Demo E: multiple errors ----

def test_demo_e_multiple_errors():
    src = "int main() {\n    int x = 10;\n    float y = \"bad\"\n    return z;\n}\n"
    result, _ = full_pipeline(src)
    # Parser fails due to missing semicolon before semantic analysis runs,
    # so we get at least 1 syntax error. Semantic errors are cascade.
    assert result.has_errors
    assert len(result.errors) >= 1


# ---- Demo F: repair regression (patch that fails) ----

def test_demo_f_regression_reported():
    """Verify that a deliberately bad patch is NOT marked as verified."""
    from compiler.models import RepairCandidate, RepairMethod, SourceEdit, VerificationStatus
    src = "int main() { int x = 5; return x; }"
    result, _ = full_pipeline(src)
    # Construct a bad patch
    from repair.patcher import apply_candidate
    cand = RepairCandidate(
        candidate_id="reg01",
        description="Bad patch",
        edits=[SourceEdit(source.index("int") if (source := src) else 0,
                          src.index("int") + 3, "int", "BROKEN")],
        method=RepairMethod.DETERMINISTIC,
        explanation="deliberate regression",
    )
    verify_candidate(cand, result)
    assert cand.verification_status not in (
        VerificationStatus.VERIFIED, VerificationStatus.TARGET_RESOLVED
    )


# ---- Symbol table populated ----

def test_symbol_table_populated():
    src = "int main() { int x = 5; return x; }"
    result, _ = full_pipeline(src)
    assert result.symbol_table_snapshot is not None
    snap = result.symbol_table_snapshot
    # main should be defined
    all_syms = {}
    for scope in snap.get("scopes", []):
        all_syms.update(scope.get("symbols", {}))
    assert "main" in all_syms


# ---- Multiple independent analyses don't contaminate ----

def test_no_cross_session_contamination():
    src1 = "int main() { int x = 5; return x; }"
    src2 = "int main() { return y; }"
    r1, _ = full_pipeline(src1)
    r2, _ = full_pipeline(src2)
    assert not r1.has_errors
    assert r2.has_errors
    # r1 should not have accumulated r2's errors
    assert not r1.errors


# ---- AST printer works ----

def test_ast_printer():
    from compiler.ast_nodes import ASTPrinter
    src = "int main() { int x = 5; return x; }"
    result, _ = full_pipeline(src)
    assert result.ast is not None
    printer = ASTPrinter()
    text = printer.render(result.ast)
    assert "FuncDecl" in text
    assert "main" in text
    assert "VarDecl" in text



def test_ast_printer_covers_control_flow_and_expressions():
    from compiler.ast_nodes import ASTPrinter

    src = """
    int square(int x) {
        return x * x;
    }

    int main() {
        int x = 2;
        if (x > 0) {
            x = -x;
        } else {
            x = square(x);
        }
        while (x < 0) {
            x = x + 1;
        }
        for (int i = 0; i < 2; i = i + 1) {
            x = x + i;
        }
        return x;
    }
    """
    result, _ = full_pipeline(src)
    assert result.ast is not None

    text = ASTPrinter().render(result.ast)

    for expected in (
        "FuncDecl",
        "Param",
        "ReturnStmt",
        "BinaryExpr",
        "IfStmt",
        "WhileStmt",
        "ForStmt",
        "UnaryExpr",
        "FuncCall",
        "Assign",
    ):
        assert expected in text, f"AST printer output is missing {expected}"


# ---- Diagnostic grouping: independent semantic errors ----

def test_independent_semantic_errors_are_not_grouped_as_cascades():
    from compiler.diagnostics import DiagnosticPipeline
    from compiler.models import (
        Diagnostic,
        DiagnosticCategory,
        Severity,
        SourcePosition,
        SourceSpan,
    )

    def make_diag(code, message, line):
        return Diagnostic(
            code=code,
            category=DiagnosticCategory.SEMANTIC,
            message=message,
            severity=Severity.ERROR,
            span=SourceSpan(
                SourcePosition(0, line, 1),
                SourcePosition(1, line, 2),
            ),
        )

    diagnostics = [
        make_diag(
            "SEM003",
            "Type mismatch: cannot initialize 'float y' with value of type 'char*'",
            3,
        ),
        make_diag(
            "SEM001",
            "Use of undeclared identifier 'z'",
            4,
        ),
    ]

    pipeline = DiagnosticPipeline()
    pipeline.process(diagnostics)

    assert len(pipeline.groups) == 2
    assert all(not group.cascade_ids for group in pipeline.groups)
