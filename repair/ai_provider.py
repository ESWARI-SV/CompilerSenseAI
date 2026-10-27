"""
repair/ai_provider.py
Optional AI provider abstraction.
Falls back gracefully when no API key is configured or any error occurs.
"""
from __future__ import annotations

import json
import importlib
import logging
import os
from typing import Any, Dict, List, Optional

from compiler.models import (
    AnalysisResult, Diagnostic, RepairCandidate, RepairMethod, SourceEdit,
    Severity, VerificationStatus
)
from repair.prompts import SYSTEM_PROMPT, build_repair_prompt

log = logging.getLogger(__name__)

# Load .env if present
try:
    importlib.import_module("dotenv").load_dotenv()
except ImportError:
    pass


def _get_provider() -> str:
    return os.getenv("AI_PROVIDER", "none").lower().strip()


def _is_available() -> bool:
    provider = _get_provider()
    if provider == "none":
        return False
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    return False


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def _validate_response(data: Any) -> Optional[str]:
    """Return error string if schema invalid, else None."""
    if not isinstance(data, dict):
        return "Response is not a JSON object"
    if "intent" in data and data["intent"] not in ("safe_fix", "ambiguous"):
        return "Invalid 'intent' value"
    if "edits" not in data:
        return "Missing 'edits' field"
    if not isinstance(data["edits"], list):
        return "'edits' must be a list"
    for i, edit in enumerate(data["edits"]):
        for key in ("line", "original_line_text", "replacement_line_text"):
            if key not in edit:
                return f"Edit {i} missing field '{key}'"
    return None


def _parse_line_edits(
    source: str,
    raw_edits: List[Dict],
) -> Optional[List[SourceEdit]]:
    """Convert line-based AI edits to offset-based SourceEdits."""
    lines = source.splitlines(keepends=True)
    source_edits: List[SourceEdit] = []

    for raw in raw_edits:
        line_no = int(raw["line"]) - 1   # 0-based
        if line_no < 0 or line_no >= len(lines):
            log.warning("AI edit references out-of-range line %d", raw["line"])
            return None

        original = raw["original_line_text"]
        replacement = raw["replacement_line_text"]
        if replacement.strip() == original.strip():
            log.warning(
                "AI edit on line %d is a no-op; rejecting candidate",
                raw["line"],
            )
            return None

        # Locate offset
        actual_line = lines[line_no].rstrip("\r\n")
        if actual_line.strip() != original.strip():
            log.warning(
                "AI edit line %d: expected %r, found %r",
                raw["line"], original, actual_line,
            )
            return None

        start_off = sum(len(l) for l in lines[:line_no])
        end_off = start_off + len(lines[line_no])
        # Preserve line ending from original
        ending = lines[line_no][len(actual_line):]
        new_text = replacement + ending

        source_edits.append(SourceEdit(
            start_offset=start_off,
            end_offset=end_off,
            original_text=lines[line_no],
            replacement_text=new_text,
            explanation=raw.get("explanation", ""),
        ))

    return source_edits


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_openai(
    user_prompt: str,
    model: str,
    timeout: int,
) -> Dict:
    """Call OpenAI API and return parsed JSON."""
    try:
        openai = importlib.import_module("openai")
    except ImportError:
        raise RuntimeError("openai package not installed")

    client = openai.OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=timeout,
    )
    # Use new-style client.chat.completions
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    content = response.choices[0].message.content
    return json.loads(content)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def ai_available() -> bool:
    return _is_available()


def generate_ai_candidates(
    result: AnalysisResult,
    max_candidates: int = 2,
) -> List[RepairCandidate]:
    """
    Generate AI-assisted repair candidates.
    Returns an empty list with no exception if AI is unavailable or fails.
    """
    if not _is_available():
        log.info("AI provider not configured; skipping AI suggestions.")
        return []

    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    if not errors:
        return []

    # Build prompt
    user_prompt = build_repair_prompt(
        source=result.source,
        diagnostics=errors[:5],   # limit context
        symbol_snapshot=result.symbol_table_snapshot or {},
    )

    provider = _get_provider()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    timeout = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))

    try:
        if provider == "openai":
            data = _call_openai(user_prompt, model, timeout)
        else:
            log.warning("Unknown provider '%s'", provider)
            return []
    except json.JSONDecodeError as exc:
        log.warning("AI returned invalid JSON: %s", exc)
        return []
    except Exception as exc:
        log.warning("AI call failed: %s", exc)
        return []

    # Validate schema
    err = _validate_response(data)
    if err:
        log.warning("AI response schema invalid: %s", err)
        return []

    if not data.get("edits"):
        log.info("AI returned no edits.")
        return []

    # Parse line edits → offset edits
    source_edits = _parse_line_edits(result.source, data["edits"])
    if source_edits is None:
        log.warning("Could not parse AI line edits into source offsets.")
        return []

    import uuid
    candidate = RepairCandidate(
        candidate_id=str(uuid.uuid4())[:8],
        description=data.get("description", "AI suggestion"),
        edits=source_edits,
        method=RepairMethod.AI,
        intent=data.get("intent", "ambiguous"),
        explanation=data.get("explanation", ""),
        target_diagnostic_ids=[d.diagnostic_id for d in errors[:5]],
        rank_score=0.5,
        rank_reason="AI-generated; pending verification",
        verification_status=VerificationStatus.NOT_CHECKED,
    )
    log.info("AI generated candidate %s", candidate.candidate_id)
    return [candidate]
