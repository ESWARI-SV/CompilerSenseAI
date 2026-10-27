"""
repair/prompts.py
Prompt templates for the AI provider.
Kept separate from compiler and provider logic.
"""
from __future__ import annotations

from typing import List

from compiler.models import AnalysisResult, Diagnostic


SYSTEM_PROMPT = """You are a compiler assistant for a C subset language.
You receive structured diagnostic information from a real compiler and propose minimal source code corrections.

The supported language includes:
- Types: int, float, char, void
- Variables, assignments, arithmetic, relational and logical expressions
- if/else, while, for, return
- Function definitions and calls
- Single-line and block comments
- NO pointers, arrays, structs, macros, or preprocessing

You MUST respond with ONLY a JSON object matching this schema (no markdown, no prose outside):
{
  "description": "one-line description of the fix or suggestion",
  "explanation": "detailed explanation of why and what changed",
  "assumptions": "any ambiguities or assumptions made",
  "intent": "safe_fix or ambiguous",
  "edits": [
    {
      "line": <1-based line number>,
      "original_line_text": "<exact text of the original line>",
      "replacement_line_text": "<replacement text for that line>",
      "explanation": "why this edit"
    }
  ]
}

If you cannot propose a safe fix, respond with:
{"description": "no fix", "explanation": "reason", "assumptions": "", "intent": "ambiguous", "edits": []}

IMPORTANT:
- Only propose changes that address the listed diagnostics.
- Do not change any code unrelated to the error.
- Do not invent variables or types not present in the source.
- Do not execute code, access files, or call external services.
REPAIR INTENT RULES:
- Use "safe_fix" only for a minimal, directly supported correction
  that does not require guessing the programmer's intended meaning.
- Use "ambiguous" when multiple plausible corrections exist or when
  a change could alter the program's intended behavior.
- Never silently invent a variable, rename an identifier, or change
  a value's meaning to make an error disappear.
- For ambiguous errors, explain the uncertainty in "assumptions".
  If there is no safe correction, return no edits.
- A missing semicolon or an unambiguous missing closing delimiter
  can usually be a "safe_fix" when the surrounding syntax supports it.
- An undeclared identifier is not automatically a typo. Offer a
  correction only when the source and known symbols support it.
- The "intent" label is a classification, not proof that a patch is safe.
- Return valid JSON only. Include the "intent" field in every response.
"""


def build_repair_prompt(
    source: str,
    diagnostics: List[Diagnostic],
    symbol_snapshot: dict,
    context_lines: int = 5,
) -> str:
    """Build a user-turn prompt for the AI provider."""
    lines = source.splitlines()

    # Collect relevant line numbers
    relevant = set()
    for d in diagnostics:
        ln = d.span.start.line
        for offset in range(-context_lines, context_lines + 1):
            idx = ln + offset - 1
            if 0 <= idx < len(lines):
                relevant.add(idx)

    numbered_lines = []
    for i, line in enumerate(lines):
        marker = ">>>" if i in relevant else "   "
        numbered_lines.append(f"{marker} {i+1:4d}: {line}")

    diag_summaries = []
    for d in diagnostics:
        diag_summaries.append(
            f"  [{d.code}] {d.category.value.upper()} at line "
            f"{d.span.start.line}, col {d.span.start.column}: {d.message}"
        )

    symbols_text = ""
    if symbol_snapshot:
        scopes = symbol_snapshot.get("scopes", [])
        for scope in scopes:
            symbols_text += f"\n  Scope '{scope['name']}':"
            for name, info in scope.get("symbols", {}).items():
                symbols_text += f"\n    {name}: {info['type']} ({info['kind']})"

    return f"""SOURCE CODE (relevant lines marked with >>>):
{chr(10).join(numbered_lines)}

COMPILER DIAGNOSTICS:
{chr(10).join(diag_summaries) if diag_summaries else "  (none)"}

KNOWN SYMBOLS:{symbols_text if symbols_text else " (none)"}

Propose a minimal correction for the listed diagnostics. Respond with the JSON schema only."""
