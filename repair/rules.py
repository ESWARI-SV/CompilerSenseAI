"""
repair/rules.py
Deterministic repair rules for selected error patterns.
Each rule targets a specific Diagnostic pattern and proposes a minimal safe patch.
"""
from __future__ import annotations

import re
from typing import List, Optional

from compiler.models import (
    AnalysisResult, Diagnostic, DiagnosticCategory, RepairCandidate,
    RepairMethod, SourceEdit, Severity,
)


# ---------------------------------------------------------------------------
# Base rule
# ---------------------------------------------------------------------------

class RepairRule:
    """Abstract base for a deterministic repair rule."""

    rule_id: str = "RULE000"
    description: str = "Base rule"

    def applies_to(self, diag: Diagnostic, result: AnalysisResult) -> bool:
        """Return True if this rule can attempt a repair for *diag*."""
        raise NotImplementedError

    def generate(
        self, diag: Diagnostic, result: AnalysisResult
    ) -> Optional[RepairCandidate]:
        """Generate a RepairCandidate or None if no safe fix can be produced."""
        raise NotImplementedError

    def _candidate(
        self,
        diag: Diagnostic,
        description: str,
        edits: List[SourceEdit],
        explanation: str,
        rank_score: float = 0.7,
        rank_reason: str = "",
    ) -> RepairCandidate:
        import uuid
        return RepairCandidate(
            candidate_id=str(uuid.uuid4())[:8],
            description=description,
            edits=edits,
            method=RepairMethod.DETERMINISTIC,
            explanation=explanation,
            target_diagnostic_ids=[diag.diagnostic_id],
            rank_score=rank_score,
            rank_reason=rank_reason or f"Deterministic rule {self.rule_id}",
        )


# ---------------------------------------------------------------------------
# Rule: missing semicolon
# ---------------------------------------------------------------------------

class MissingSemicolonRule(RepairRule):
    """
    Detects 'Syntax error at X' where the preceding statement is missing ';'.
    Inserts ';' just before the error token position.
    Only applies when the insertion point can be uniquely identified.
    """

    rule_id = "RULE001"
    description = "Insert missing semicolon"

    def applies_to(self, diag: Diagnostic, result: AnalysisResult) -> bool:
        if diag.category != DiagnosticCategory.SYNTAX:
            return False
        return "syntax error" in diag.message.lower() or "SYN001" == diag.code

    def generate(
        self, diag: Diagnostic, result: AnalysisResult
    ) -> Optional[RepairCandidate]:
        source = result.source
        err_offset = diag.span.start.offset

        if err_offset <= 0 or err_offset > len(source):
            return None

        # Scan backwards past whitespace to find last non-whitespace char
        pos = err_offset - 1
        while pos >= 0 and source[pos] in (" ", "\t", "\r", "\n"):
            pos -= 1

        if pos < 0:
            return None

        insert_pos = pos + 1
        preceding_char = source[pos]

        # Only insert if the preceding character is a word char, closing paren, or literal
        if not (preceding_char.isalnum() or preceding_char in (")", "'", '"', "_")):
            return None

        # Verify no existing semicolon very close by (within 2 chars)
        nearby = source[insert_pos: insert_pos + 2]
        if ";" in nearby:
            return None

        edit = SourceEdit(
            start_offset=insert_pos,
            end_offset=insert_pos,
            original_text="",
            replacement_text=";",
            explanation=f"Insert ';' after position {insert_pos}",
        )

        candidate = self._candidate(
            diag,
            description="Insert missing semicolon",
            edits=[edit],
            explanation=(
                f"A semicolon appears to be missing before '{diag.message}'. "
                f"Inserting ';' at line {diag.span.start.line}, "
                f"column {diag.span.start.column}."
            ),
            rank_score=0.75,
            rank_reason="High-confidence deterministic fix: semicolons are unambiguous at statement boundaries.",
        )
        candidate.intent = "safe_fix"
        return candidate


# ---------------------------------------------------------------------------
# Rule: missing closing brace
# ---------------------------------------------------------------------------

class MissingClosingBraceRule(RepairRule):
    """
    Detects unmatched '{' and proposes inserting '}' at end of file.
    Conservative: only when exactly one more '{' than '}' exists.
    """

    rule_id = "RULE002"
    description = "Insert missing closing brace"

    def applies_to(self, diag: Diagnostic, result: AnalysisResult) -> bool:
        if diag.category != DiagnosticCategory.SYNTAX:
            return False
        return "syntax error" in diag.message.lower() or "end of file" in diag.message.lower()

    def generate(
        self, diag: Diagnostic, result: AnalysisResult
    ) -> Optional[RepairCandidate]:
        source = result.source
        opens = source.count("{")
        closes = source.count("}")
        if opens - closes != 1:
            return None  # Ambiguous; do not apply

        insert_pos = len(source)
        # Insert newline + closing brace at EOF
        edit = SourceEdit(
            start_offset=insert_pos,
            end_offset=insert_pos,
            original_text="",
            replacement_text="\n}",
            explanation="Insert missing closing brace at end of file",
        )
        return self._candidate(
            diag,
            description="Insert missing closing brace '}'",
            edits=[edit],
            explanation=(
                "The source has one more opening brace '{' than closing brace '}'. "
                "Inserting '}' at the end of the file to balance them."
            ),
            rank_score=0.65,
            rank_reason="Deterministic: exactly one unmatched '{' found.",
        )


# ---------------------------------------------------------------------------
# Rule: missing closing parenthesis
# ---------------------------------------------------------------------------

class MissingClosingParenRule(RepairRule):
    """Inserts ')' when exactly one paren pair is unbalanced."""

    rule_id = "RULE003"
    description = "Insert missing closing parenthesis"

    def applies_to(self, diag: Diagnostic, result: AnalysisResult) -> bool:
        return diag.category == DiagnosticCategory.SYNTAX

    def generate(
        self, diag: Diagnostic, result: AnalysisResult
    ) -> Optional[RepairCandidate]:
        source = result.source
        opens = source.count("(")
        closes = source.count(")")
        if opens - closes != 1:
            return None

        insert_pos = diag.span.start.offset
        if insert_pos <= 0 or insert_pos > len(source):
            return None

        edit = SourceEdit(
            start_offset=insert_pos,
            end_offset=insert_pos,
            original_text="",
            replacement_text=")",
            explanation="Insert missing closing parenthesis",
        )
        return self._candidate(
            diag,
            description="Insert missing closing parenthesis ')'",
            edits=[edit],
            explanation=(
                "The source has one more opening '(' than closing ')'. "
                "Inserting ')' at the error location."
            ),
            rank_score=0.60,
            rank_reason="Deterministic: exactly one unmatched '(' found.",
        )


# ---------------------------------------------------------------------------
# Rule: keyword spelling (conservative)
# ---------------------------------------------------------------------------

_KEYWORD_CORRECTIONS = {
    "retrun": "return",
    "retrn": "return",
    "retur": "return",
    "whiel": "while",
    "whlie": "while",
    "wihle": "while",
    "fr": "for",
    "fo": "for",
    "iff": "if",
    "esle": "else",
    "flota": "float",
    "folat": "float",
    "cahar": "char",
    "vodi": "void",
    "iny": "int",
    "itn": "int",
}


class KeywordTypoRule(RepairRule):
    """Replace a close misspelling of a keyword with the correct spelling."""

    rule_id = "RULE004"
    description = "Correct keyword misspelling"

    def applies_to(self, diag: Diagnostic, result: AnalysisResult) -> bool:
        if diag.category != DiagnosticCategory.SYNTAX:
            return False
        # Check if a token near the error location matches a known typo
        err_line = diag.span.start.line
        for tok in result.tokens:
            if tok.span.start.line == err_line and tok.lexeme in _KEYWORD_CORRECTIONS:
                return True
        return False

    def generate(
        self, diag: Diagnostic, result: AnalysisResult
    ) -> Optional[RepairCandidate]:
        err_line = diag.span.start.line
        for tok in result.tokens:
            if tok.span.start.line == err_line and tok.lexeme in _KEYWORD_CORRECTIONS:
                correct = _KEYWORD_CORRECTIONS[tok.lexeme]
                edit = SourceEdit(
                    start_offset=tok.span.start.offset,
                    end_offset=tok.span.end.offset,
                    original_text=tok.lexeme,
                    replacement_text=correct,
                    explanation=f"Replace '{tok.lexeme}' with '{correct}'",
                )
                return self._candidate(
                    diag,
                    description=f"Replace '{tok.lexeme}' with '{correct}'",
                    edits=[edit],
                    explanation=(
                        f"'{tok.lexeme}' looks like a misspelling of the keyword '{correct}'. "
                        "Only applying because the correction is unambiguous."
                    ),
                    rank_score=0.80,
                    rank_reason="Keyword lookup: deterministic correction from known typo table.",
                )
        return None

class UndeclaredAssignmentRule(RepairRule):
    """Declare an undeclared variable in a simple integer assignment."""

    rule_id = "RULE005"
    description = "Declare an undeclared integer variable"

    def applies_to(self, diag: Diagnostic, result: AnalysisResult) -> bool:
        return (
            diag.category == DiagnosticCategory.SEMANTIC
            and diag.code == "SEM001"
            and "undeclared identifier" in diag.message.lower()
        )

    def generate(
        self, diag: Diagnostic, result: AnalysisResult
    ) -> Optional[RepairCandidate]:
        source = result.source
        lines = source.splitlines(keepends=True)
        line_no = diag.span.start.line

        if line_no < 1 or line_no > len(lines):
            return None

        line = lines[line_no - 1]
        match = re.match(
            r"^(\s*)([A-Za-z_]\w*)\s*=\s*(.+?)\s*;\s*(?:\r?\n)?$",
            line,
        )
        if not match:
            return None

        indent, name, rhs = match.groups()

        if not re.search(
            rf"undeclared identifier\s+['\"]{re.escape(name)}['\"]",
            diag.message,
            re.IGNORECASE,
        ):
            return None

        # Do not redeclare an identifier already declared in the source.
        if re.search(
            rf"\b(?:int|float|char|void)\s+{re.escape(name)}\b",
            source,
        ):
            return None

        # Only accept simple integer arithmetic involving previously
        # declared integer variables.
        if not re.fullmatch(r"[\w\s+\-*/%()]+", rhs):
            return None

        identifiers = re.findall(r"\b[A-Za-z_]\w*\b", rhs)
        if any(
            not re.search(
                rf"\bint\s+{re.escape(identifier)}\b",
                source[:source.find(line)],
            )
            for identifier in identifiers
        ):
            return None

        if not re.search(r"\d", rhs) and not identifiers:
            return None

        insert_pos = sum(len(item) for item in lines[:line_no - 1])

        edit = SourceEdit(
            start_offset=insert_pos,
            end_offset=insert_pos,
            original_text="",
            replacement_text=f"{indent}int {name};\n",
            explanation=f"Declare integer variable '{name}' before its assignment",
        )

        return self._candidate(
            diag,
            description=f"Declare integer variable '{name}'",
            edits=[edit],
            explanation=(
                f"'{name}' is assigned before being declared. "
                "The expression appears compatible with integer arithmetic; "
                "verify that int is the intended type."
            ),
            rank_score=0.65,
            rank_reason="Conservative declaration proposal for a simple assignment.",
        )


# ---------------------------------------------------------------------------
# Rule: suggest a similar declared identifier
# ---------------------------------------------------------------------------

class UndeclaredIdentifierSuggestionRule(RepairRule):
    """Suggest a similar declared identifier without assuming user intent."""

    rule_id = "RULE006"
    description = "Suggest a declared identifier for an undeclared name"

    def applies_to(self, diag: Diagnostic, result: AnalysisResult) -> bool:
        return (
            diag.category == DiagnosticCategory.SEMANTIC
            and diag.code == "SEM001"
            and "undeclared identifier" in diag.message.lower()
        )

    def generate(
        self, diag: Diagnostic, result: AnalysisResult
    ) -> Optional[RepairCandidate]:
        match = re.search(
            r"undeclared identifier\s+['\"]([A-Za-z_]\w*)['\"]",
            diag.message,
            re.IGNORECASE,
        )
        if not match:
            return None

        unknown_name = match.group(1)

        # Gather names from the symbol table, if available.
        snapshot = result.symbol_table_snapshot or {}
        scopes = snapshot.get("scopes", [])

        declared_variables = []
        declared_names = set()

        for scope in scopes:
            symbols = scope.get("symbols", {})
            if isinstance(symbols, dict):
                for name, details in symbols.items():
                    declared_names.add(name)
                    if details.get("kind") == "variable":
                        declared_variables.append(name)

        if not declared_names:
            return None

        from difflib import get_close_matches

        matches = get_close_matches(
            unknown_name, sorted(declared_names), n=1, cutoff=0.6
        )

        if matches:
            suggested_name = matches[0]
        elif len(set(declared_variables)) == 1:
            # Offer a clearly ambiguous alternative when there is
            # exactly one declared variable, even if spelling differs.
            suggested_name = declared_variables[0]
        else:
            return None
        # Never suggest replacing an identifier with itself.
        if suggested_name == unknown_name:
            return None

        source = result.source

        # Replace only the undeclared identifier at the diagnostic location.
        offset = diag.span.start.offset
        if offset < 0 or offset >= len(source):
            return None

        identifier_match = re.match(
            r"[A-Za-z_]\w*",
            source[offset:],
        )

        if not identifier_match or identifier_match.group(0) != unknown_name:
            # Some diagnostics point to a nearby token rather than its start.
            line_start = source.rfind("\n", 0, offset) + 1
            line_end = source.find("\n", offset)
            if line_end == -1:
                line_end = len(source)

            line = source[line_start:line_end]
            matches_on_line = list(
                re.finditer(r"\b" + re.escape(unknown_name) + r"\b", line)
            )
            if len(matches_on_line) != 1:
                return None

            start_offset = line_start + matches_on_line[0].start()
            end_offset = line_start + matches_on_line[0].end()
        else:
            start_offset = offset
            end_offset = offset + len(unknown_name)

        edit = SourceEdit(
            start_offset=start_offset,
            end_offset=end_offset,
            original_text=unknown_name,
            replacement_text=suggested_name,
            explanation=(
                f"Suggest '{suggested_name}' as a possible replacement "
                f"for undeclared identifier '{unknown_name}'"
            ),
        )

        candidate = self._candidate(
            diag,
            description=f"Possible alternative: '{suggested_name}' for '{unknown_name}'",
            edits=[edit],
            explanation=(
             f"'{unknown_name}' is undeclared. '{suggested_name}' is an "
             "existing declared name, but the intended identifier is uncertain. "
             "Review this suggestion carefully before applying it."
            ),
            rank_score=0.55,
            rank_reason=(
                "Ambiguous identifier suggestion based on spelling similarity; "
                "requires user confirmation."
            ),
        )

        candidate.intent = "ambiguous"
        return candidate


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

ALL_RULES: List[RepairRule] = [
    KeywordTypoRule(),
    MissingSemicolonRule(),
    MissingClosingBraceRule(),
    MissingClosingParenRule(),
    UndeclaredAssignmentRule(),
    UndeclaredIdentifierSuggestionRule(),
]


def generate_deterministic_candidates(
    result: AnalysisResult,
) -> List[RepairCandidate]:
    """Apply all rules to all diagnostics and collect candidates."""
    candidates: List[RepairCandidate] = []
    seen_edits: set = set()

    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    for diag in errors:
        for rule in ALL_RULES:
            try:
                if rule.applies_to(diag, result):
                    cand = rule.generate(diag, result)
                    if cand is None:
                        continue
                    # Deduplicate by edit fingerprint
                    fp = tuple(
                        (e.start_offset, e.end_offset, e.replacement_text)
                        for e in cand.edits
                    )
                    if fp in seen_edits:
                        continue
                    seen_edits.add(fp)
                    candidates.append(cand)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Rule %s failed on diag %s: %s", rule.rule_id, diag.diagnostic_id, exc
                )
    return candidates
