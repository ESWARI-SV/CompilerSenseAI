"""
compiler/models.py
Shared data-model dataclasses used by every compiler stage and the repair pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DiagnosticCategory(str, Enum):
    LEXICAL = "lexical"
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    INTERNAL = "internal"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AnalysisStatus(str, Enum):
    NOT_STARTED = "not_started"
    LEXER_FAILED = "lexer_failed"
    PARSER_FAILED = "parser_failed"
    SEMANTIC_FAILED = "semantic_failed"
    SUCCESS = "success"
    PARTIAL = "partial"


class RepairMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    AI = "ai"


class VerificationStatus(str, Enum):
    NOT_CHECKED = "not_checked"
    INVALID_PATCH = "invalid_patch"
    VERIFICATION_FAILED = "verification_failed"
    TARGET_RESOLVED = "target_resolved"
    VERIFIED = "verified"
    REGRESSION = "regression"


# ---------------------------------------------------------------------------
# Source-position helpers
# ---------------------------------------------------------------------------

@dataclass
class SourcePosition:
    """Zero-based character offset, 1-based line/column (editor convention)."""
    offset: int = 0
    line: int = 1
    column: int = 1

    def __repr__(self) -> str:
        return f"L{self.line}C{self.column}"


@dataclass
class SourceSpan:
    start: SourcePosition = field(default_factory=SourcePosition)
    end: SourcePosition = field(default_factory=SourcePosition)

    def __repr__(self) -> str:
        return f"{self.start}–{self.end}"

    @staticmethod
    def unknown() -> "SourceSpan":
        return SourceSpan(SourcePosition(0, 0, 0), SourcePosition(0, 0, 0))


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

@dataclass
class Token:
    type: str
    lexeme: str
    span: SourceSpan

    def __repr__(self) -> str:
        return f"Token({self.type!r}, {self.lexeme!r}, {self.span})"


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------

@dataclass
class Diagnostic:
    code: str                                     # e.g. "LEX001"
    category: DiagnosticCategory
    message: str
    severity: Severity = Severity.ERROR
    span: SourceSpan = field(default_factory=SourceSpan.unknown)
    source: str = "compiler"                       # "lexer" | "parser" | "semantic" | …
    group_id: Optional[str] = None                # root-cause group
    related_ids: List[str] = field(default_factory=list)
    explanation: Optional[str] = None
    repair_eligible: bool = True
    diagnostic_id: str = ""                        # populated by DiagnosticPipeline

    def __post_init__(self) -> None:
        if not self.diagnostic_id:
            import uuid
            self.diagnostic_id = str(uuid.uuid4())[:8]

    def short_location(self) -> str:
        p = self.span.start
        if p.line == 0:
            return "unknown location"
        return f"line {p.line}, col {p.column}"

    def __repr__(self) -> str:
        return (
            f"[{self.code}] {self.category.value.upper()}: "
            f"{self.message} @ {self.short_location()}"
        )


# ---------------------------------------------------------------------------
# AnalysisResult
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    tokens: List[Token] = field(default_factory=list)
    ast: Optional[Any] = None           # AST root node or None
    diagnostics: List[Diagnostic] = field(default_factory=list)
    symbol_table_snapshot: Optional[Any] = None
    completed_stages: List[str] = field(default_factory=list)
    status: AnalysisStatus = AnalysisStatus.NOT_STARTED
    source: str = ""

    @property
    def errors(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == Severity.ERROR]

    @property
    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self.diagnostics)

    @property
    def lexical_diagnostics(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.category == DiagnosticCategory.LEXICAL]

    @property
    def syntax_diagnostics(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.category == DiagnosticCategory.SYNTAX]

    @property
    def semantic_diagnostics(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.category == DiagnosticCategory.SEMANTIC]


# ---------------------------------------------------------------------------
# Patch and RepairCandidate
# ---------------------------------------------------------------------------

@dataclass
class SourceEdit:
    """A single text-replace operation."""
    start_offset: int
    end_offset: int                # exclusive
    original_text: str             # must match source[start:end] exactly
    replacement_text: str
    explanation: str = ""

    def validate(self, source: str) -> bool:
        actual = source[self.start_offset:self.end_offset]
        return actual == self.original_text


@dataclass
class RepairCandidate:
    candidate_id: str
    description: str
    edits: List[SourceEdit]
    method: RepairMethod
    explanation: str
    target_diagnostic_ids: List[str] = field(default_factory=list)
    rank_score: float = 0.0
    rank_reason: str = ""
    verification_status: VerificationStatus = VerificationStatus.NOT_CHECKED
    verification_detail: str = ""
    diagnostics_before: List[Diagnostic] = field(default_factory=list)
    diagnostics_after: List[Diagnostic] = field(default_factory=list)
    patched_source: Optional[str] = None
    intent: str = "ambiguous"  # "safe_fix" | "ambiguous"

    def __post_init__(self) -> None:
        if not self.candidate_id:
            import uuid
            self.candidate_id = str(uuid.uuid4())[:8]
