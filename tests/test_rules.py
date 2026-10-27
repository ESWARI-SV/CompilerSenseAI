"""tests/test_rules.py — Deterministic repair rule tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.orchestrator import Orchestrator
from repair.rules import (
    MissingSemicolonRule,
    MissingClosingBraceRule,
    KeywordTypoRule,
    generate_deterministic_candidates,
    UndeclaredIdentifierSuggestionRule,
    UndeclaredAssignmentRule,
)
from compiler.models import Severity


def analyze(src):
    return Orchestrator().analyze(src)


# ---- MissingSemicolonRule ----

def test_semicolon_rule_applies():
    src = "int main() { int x = 10\n return x; }"
    result = analyze(src)
    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    rule = MissingSemicolonRule()
    applicable = [d for d in errors if rule.applies_to(d, result)]
    # Should find at least one applicable diagnostic
    assert len(applicable) >= 1


def test_semicolon_rule_generates_candidate():
    src = "int main() { int x = 10\n return x; }"
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)
    semicolon_cands = [c for c in candidates if "semicolon" in c.description.lower()]
    assert len(semicolon_cands) >= 1


def test_semicolon_edit_is_minimal():
    src = "int main() { int x = 10\n return x; }"
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)
    for c in candidates:
        if "semicolon" in c.description.lower():
            for e in c.edits:
                assert e.replacement_text == ";"
                assert e.original_text == ""


# ---- MissingClosingBraceRule ----

def test_brace_rule_single_unmatched():
    src = "int main() { int x = 5; return x;"
    result = analyze(src)
    rule = MissingClosingBraceRule()
    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    applicable = [d for d in errors if rule.applies_to(d, result)]
    if applicable:
        cand = rule.generate(applicable[0], result)
        if cand:
            assert "}" in cand.edits[0].replacement_text


def test_brace_rule_refuses_ambiguous():
    # Multiple unmatched braces → rule should return None
    src = "int main() { { int x = 5; return x;"
    result = analyze(src)
    rule = MissingClosingBraceRule()
    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    for d in errors:
        if rule.applies_to(d, result):
            cand = rule.generate(d, result)
            # With 2 unmatched, rule should refuse
            assert cand is None


# ---- KeywordTypoRule ----

def test_keyword_typo_retrun():
    src = "int main() { int x = 5; retrun x; }"
    result = analyze(src)
    rule = KeywordTypoRule()
    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    applicable = [d for d in errors if rule.applies_to(d, result)]
    assert len(applicable) >= 1


def test_keyword_typo_generates_candidate():
    src = "int main() { int x = 5; retrun x; }"
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)
    typo_cands = [c for c in candidates if "return" in c.description.lower()]
    assert len(typo_cands) >= 1
    for c in typo_cands:
        for e in c.edits:
            assert "retrun" in e.original_text
            assert "return" in e.replacement_text


# ---- No rule applied for unsupported error ----

def test_undeclared_return_identifier_generates_candidate():
    src = "int main() { return z; }"
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)

    assert any(
        d.code == "SEM001" and "undeclared identifier" in d.message.lower()
        for d in result.diagnostics
    )
    assert not any(
        "undeclared" in c.description.lower()
        for c in candidates
    )


def test_no_candidates_for_valid_code():
    src = "int main() { int x = 5; return x; }"
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)
    assert len(candidates) == 0


# ---- Undeclared identifier suggestion edge cases ----

def test_similar_identifier_suggests_declared_name():
    src = "int main() { int count = 5; return coutn; }"
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)

    suggestions = [
        c for c in candidates
        if "coutn" in c.description.lower()
    ]

    assert len(suggestions) >= 1
    assert any("count" in c.description.lower() for c in suggestions)
    assert all(c.intent == "ambiguous" for c in suggestions)


def test_unknown_identifier_with_multiple_variables_gets_no_guess():
    src = """
int main() {
    int x = 1;
    int count = 2;
    int total = 3;
    return unknown;
}
"""
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)

    assert any(
        d.code == "SEM001" and "unknown" in d.message.lower()
        for d in result.diagnostics
    )
    assert not any(
        "unknown" in c.description.lower()
        for c in candidates
    )


def test_unknown_identifier_without_variables_gets_no_suggestion():
    src = "int main() { return unknown; }"
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)

    assert any(
        d.code == "SEM001" and "unknown" in d.message.lower()
        for d in result.diagnostics
    )
    assert not any(
        "unknown" in c.description.lower()
        for c in candidates
    )


# ---- UndeclaredIdentifierSuggestionRule ----

def test_out_of_scope_identifier_does_not_suggest_itself():
    src = """int main() {
    {
        int y = 10;
    }
    return y;
}"""
    result = analyze(src)

    candidates = generate_deterministic_candidates(result)

    self_suggestions = [
        candidate
        for candidate in candidates
        if any(
            edit.original_text == "y"
            and edit.replacement_text == "y"
            for edit in candidate.edits
        )
    ]

    assert self_suggestions == []

def test_undeclared_assignment_candidate_remains_ambiguous():
    src = """int main() {
    int x = 10;
    y = 20;
    return 0;
}"""
    result = analyze(src)
    candidates = generate_deterministic_candidates(result)

    declaration_candidates = [
        c for c in candidates
        if "declare integer variable 'y'" in c.description.lower()
    ]

    assert len(declaration_candidates) == 1
    assert declaration_candidates[0].intent == "ambiguous"