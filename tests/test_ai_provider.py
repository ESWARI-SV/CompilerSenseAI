
from compiler.models import (
    AnalysisResult,
    Diagnostic,
    DiagnosticCategory,
    SourcePosition,
    SourceSpan,
)
import repair.ai_provider as ai


def make_result():
    source = "int main() {\n    return 0;\n}\n"
    diagnostic = Diagnostic(
        code="SYN001",
        category=DiagnosticCategory.SYNTAX,
        message="Test diagnostic",
        span=SourceSpan(
            start=SourcePosition(offset=13, line=2, column=5),
            end=SourcePosition(offset=19, line=2, column=11),
        ),
    )
    return AnalysisResult(source=source, diagnostics=[diagnostic])


def fake_response(intent=None):
    response = {
        "description": "Test suggestion",
        "explanation": "Testing candidate generation",
        "assumptions": "",
        "edits": [
            {
                "line": 2,
                "original_line_text": "    return 0;",
                "replacement_line_text": "    return 1;",
                "explanation": "Test edit",
            }
        ],
    }
    if intent is not None:
        response["intent"] = intent
    return response


def setup_fake_ai(monkeypatch, response):
    monkeypatch.setattr(ai, "_is_available", lambda: True)
    monkeypatch.setattr(ai, "_get_provider", lambda: "openai")
    monkeypatch.setattr(
        ai, "_call_openai", lambda *args, **kwargs: response
    )


def test_safe_fix_intent_is_preserved(monkeypatch):
    setup_fake_ai(monkeypatch, fake_response("safe_fix"))

    candidates = ai.generate_ai_candidates(make_result())

    assert len(candidates) == 1
    assert candidates[0].intent == "safe_fix"


def test_ambiguous_intent_is_preserved(monkeypatch):
    setup_fake_ai(monkeypatch, fake_response("ambiguous"))

    candidates = ai.generate_ai_candidates(make_result())

    assert len(candidates) == 1
    assert candidates[0].intent == "ambiguous"


def test_missing_intent_defaults_to_ambiguous(monkeypatch):
    setup_fake_ai(monkeypatch, fake_response())

    candidates = ai.generate_ai_candidates(make_result())

    assert len(candidates) == 1
    assert candidates[0].intent == "ambiguous"


def test_invalid_intent_is_rejected():
    response = fake_response("guess")
    assert ai._validate_response(response) == "Invalid 'intent' value"



def test_non_dictionary_response_is_rejected():
    assert (
        ai._validate_response(["intent"])
        == "Response is not a JSON object"
    )


def test_empty_edits_are_valid():
    response = fake_response()
    response["edits"] = []
    assert ai._validate_response(response) is None

def test_noop_ai_edit_is_rejected():
    source = "int main() {\n    return 0;\n}\n"
    raw_edits = [
        {
            "line": 2,
            "original_line_text": "    return 0;",
            "replacement_line_text": "    return 0;",
        }
    ]

    assert ai._parse_line_edits(source, raw_edits) is None