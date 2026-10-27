"""
compiler/lexer.py
PLY-based lexer for the supported C subset.
Produces Token objects with accurate line/column/offset tracking.
"""
from __future__ import annotations

import re
from typing import List, Tuple
import ply.lex as lex  # type: ignore[import-not-found]

from compiler.models import (
    Diagnostic, DiagnosticCategory, Severity, SourcePosition, SourceSpan, Token
)


# ---------------------------------------------------------------------------
# Token type catalog
# ---------------------------------------------------------------------------

KEYWORDS = {
    "int", "float", "char", "void",
    "if", "else", "while", "for", "return",
}

# All token names PLY must know about
tokens = (
    # Literals
    "INT_LITERAL",
    "FLOAT_LITERAL",
    "CHAR_LITERAL",
    "STRING_LITERAL",
    # Identifiers / keywords (keywords matched via identifier rule)
    "ID",
    # Keywords (returned as separate types)
    "INT", "FLOAT_TYPE", "CHAR_TYPE", "VOID",
    "IF", "ELSE", "WHILE", "FOR", "RETURN",
    # Operators
    "PLUS", "MINUS", "TIMES", "DIVIDE", "MODULO",
    "ASSIGN",
    "EQ", "NEQ", "LT", "LE", "GT", "GE",
    "AND", "OR", "NOT",
    # Delimiters
    "LPAREN", "RPAREN",
    "LBRACE", "RBRACE",
    "SEMICOLON", "COMMA",
)


class CSubsetLexer:
    """
    Stateful wrapper around PLY Lex for the C subset.
    Reconstructed on each call to tokenize() so sessions don't contaminate.
    """

    tokens = tokens

    # ------------------------------------------------------------------ rules

    # Whitespace (ignored, but updates position tracking)
    def t_NEWLINE(self, t: lex.LexToken) -> None:
        r"\n+"
        t.lexer.lineno += t.value.count("\n")

    t_ignore = " \t\r"

    # Comments — consume entirely
    def t_BLOCK_COMMENT(self, t: lex.LexToken) -> None:
        r"/\*(.|\n)*?\*/"
        t.lexer.lineno += t.value.count("\n")

    def t_LINE_COMMENT(self, t: lex.LexToken) -> None:
        r"//[^\n]*"

    # ---- Literals --------------------------------------------------------

    def t_FLOAT_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r"\d+\.\d*([eE][+-]?\d+)?|\d+[eE][+-]?\d+"
        t.value = float(t.value)
        return t

    def t_INT_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r"\d+"
        t.value = int(t.value)
        return t

    def t_CHAR_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r"'(\\.|[^\\'\n])'"
        t.value = t.value[1:-1]  # strip quotes
        return t

    def t_STRING_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r'"(\\.|[^\\"\n])*"'
        t.value = t.value[1:-1]  # strip quotes
        return t

    # Unterminated string
    def t_UNTERMINATED_STRING(self, t: lex.LexToken) -> None:
        r'"[^"\n]*'
        col = self._col(t)
        self._diag(
            "LEX003",
            "Unterminated string literal",
            t.lexer.lineno, col, t.lexpos, t.lexpos + len(t.value)
        )

    # Unterminated char literal
    def t_UNTERMINATED_CHAR(self, t: lex.LexToken) -> None:
        r"'[^'\n]*"
        col = self._col(t)
        self._diag(
            "LEX004",
            "Unterminated character literal",
            t.lexer.lineno, col, t.lexpos, t.lexpos + len(t.value)
        )

    # ---- Identifiers / keywords ------------------------------------------

    def t_ID(self, t: lex.LexToken) -> lex.LexToken:
        r"[A-Za-z_][A-Za-z0-9_]*"
        kw_map = {
            "int": "INT", "float": "FLOAT_TYPE", "char": "CHAR_TYPE", "void": "VOID",
            "if": "IF", "else": "ELSE", "while": "WHILE", "for": "FOR",
            "return": "RETURN",
        }
        t.type = kw_map.get(t.value, "ID")
        return t

    # ---- Operators -------------------------------------------------------

    t_PLUS = r"\+"
    t_MINUS = r"-"
    t_TIMES = r"\*"
    t_DIVIDE = r"/"
    t_MODULO = r"%"
    t_EQ = r"=="
    t_NEQ = r"!="
    t_LE = r"<="
    t_GE = r">="
    t_LT = r"<"
    t_GT = r">"
    t_AND = r"&&"
    t_OR = r"\|\|"
    t_NOT = r"!"
    t_ASSIGN = r"="

    # ---- Delimiters ------------------------------------------------------

    t_LPAREN = r"\("
    t_RPAREN = r"\)"
    t_LBRACE = r"\{"
    t_RBRACE = r"\}"
    t_SEMICOLON = r";"
    t_COMMA = r","

    # ---- Error handler ---------------------------------------------------

    def t_error(self, t: lex.LexToken) -> None:
        col = self._col(t)
        self._diag(
            "LEX001",
            f"Illegal character {t.value[0]!r}",
            t.lexer.lineno, col, t.lexpos, t.lexpos + 1
        )
        t.lexer.skip(1)

    # ---------------------------------------------------------------- helpers

    def _col(self, t: lex.LexToken) -> int:
        last_nl = self._source.rfind("\n", 0, t.lexpos)
        return t.lexpos - last_nl  # 1-based

    def _diag(
        self,
        code: str,
        msg: str,
        line: int,
        col: int,
        start_off: int,
        end_off: int,
    ) -> None:
        span = SourceSpan(
            SourcePosition(start_off, line, col),
            SourcePosition(end_off, line, col + (end_off - start_off)),
        )
        self._diagnostics.append(
            Diagnostic(
                code=code,
                category=DiagnosticCategory.LEXICAL,
                message=msg,
                severity=Severity.ERROR,
                span=span,
                source="lexer",
            )
        )

    # ---------------------------------------------------------------- public

    def __init__(self) -> None:
        self._source = ""
        self._diagnostics: List[Diagnostic] = []
        self._lexer = lex.lex(module=self, debug=False, errorlog=lex.NullLogger())

    def tokenize(self, source: str) -> Tuple[List[Token], List[Diagnostic]]:
        """Lex *source* and return (tokens, diagnostics)."""
        self._source = source
        self._diagnostics = []
        self._lexer.input(source)
        self._lexer.lineno = 1

        result: List[Token] = []
        while True:
            tok = self._lexer.token()
            if tok is None:
                break

            # Compute column from source offsets
            last_nl = source.rfind("\n", 0, tok.lexpos)
            col = tok.lexpos - last_nl  # 1-based
            end_off = tok.lexpos + len(str(tok.value) if not isinstance(tok.value, str) else tok.value)
            # For numeric tokens the lexeme length differs from value length
            raw_len = _raw_lexeme_length(tok, source)
            end_off = tok.lexpos + raw_len

            span = SourceSpan(
                SourcePosition(tok.lexpos, tok.lineno, col),
                SourcePosition(end_off, tok.lineno, col + raw_len),
            )
            # Reconstruct original lexeme from source
            lexeme = source[tok.lexpos: tok.lexpos + raw_len]
            result.append(Token(type=tok.type, lexeme=lexeme, span=span))

        return result, self._diagnostics


def _raw_lexeme_length(tok: lex.LexToken, source: str) -> int:
    """Determine the length of the raw token in the source string."""
    # For string/char values we cannot use len(tok.value) because quotes were stripped.
    # Walk forward from lexpos until we find the end boundary.
    pos = tok.lexpos
    if tok.type == "STRING_LITERAL":
        # Find closing quote
        i = pos + 1
        while i < len(source):
            if source[i] == '"' and source[i - 1] != "\\":
                return i - pos + 1
            i += 1
        return len(source) - pos
    if tok.type == "CHAR_LITERAL":
        i = pos + 1
        while i < len(source):
            if source[i] == "'" and source[i - 1] != "\\":
                return i - pos + 1
            i += 1
        return len(source) - pos
    if tok.type in ("INT_LITERAL", "FLOAT_LITERAL"):
        # Scan numeric characters
        i = pos
        has_dot = False
        has_exp = False
        while i < len(source):
            c = source[i]
            if c.isdigit():
                i += 1
            elif c == "." and not has_dot and not has_exp:
                has_dot = True
                i += 1
            elif c in ("e", "E") and not has_exp:
                has_exp = True
                i += 1
                if i < len(source) and source[i] in ("+", "-"):
                    i += 1
            else:
                break
        return max(1, i - pos)
    # For identifiers / keywords: scan alphanumeric+underscore
    if tok.type in ("ID",) or tok.type in (
        "INT", "FLOAT_TYPE", "CHAR_TYPE", "VOID",
        "IF", "ELSE", "WHILE", "FOR", "RETURN",
    ):
        i = pos
        while i < len(source) and (source[i].isalnum() or source[i] == "_"):
            i += 1
        return max(1, i - pos)
    # Multi-char operators
    two_char = {"EQ": "==", "NEQ": "!=", "LE": "<=", "GE": ">=", "AND": "&&", "OR": "||"}
    if tok.type in two_char:
        return 2
    return 1
