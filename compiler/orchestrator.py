"""
compiler/orchestrator.py
Coordinates lexer → parser → semantic analysis → diagnostic pipeline.
Returns AnalysisResult; never raises for user-facing errors.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from compiler.diagnostics import DiagnosticPipeline
from compiler.lexer import CSubsetLexer
from compiler.models import AnalysisResult, AnalysisStatus, Severity
from compiler.parser import CSubsetParser
from compiler.semantic import SemanticAnalyzer

log = logging.getLogger(__name__)


class Orchestrator:
    """
    Run the full compiler pipeline on a source string.
    Re-create lexer/parser each call to avoid cross-session contamination.
    """

    def analyze(self, source: str) -> AnalysisResult:
        result = AnalysisResult(source=source)
        t0 = time.monotonic()

        # ------------------------------------------------------------------
        # Stage 1: Lexical analysis
        # ------------------------------------------------------------------
        try:
            lexer = CSubsetLexer()
            tokens, lex_diags = lexer.tokenize(source)
            result.tokens = tokens
            result.diagnostics.extend(lex_diags)
            result.completed_stages.append("lexer")
        except Exception as exc:
            log.exception("Lexer crashed: %s", exc)
            result.status = AnalysisStatus.LEXER_FAILED
            return result

        has_lex_errors = any(d.severity == Severity.ERROR for d in lex_diags)
        if has_lex_errors:
            # Still attempt parsing; the lexer may have recovered partially
            result.status = AnalysisStatus.PARTIAL

        # ------------------------------------------------------------------
        # Stage 2: Parsing
        # ------------------------------------------------------------------
        try:
            parser = CSubsetParser()
            ast, parse_diags = parser.parse(source, tokens, lex_diags)
            # parse_diags already contains lex_diags (from parser constructor)
            # Replace diagnostics with merged set
            result.diagnostics = parse_diags
            result.ast = ast
            result.completed_stages.append("parser")
        except Exception as exc:
            log.exception("Parser crashed: %s", exc)
            result.status = AnalysisStatus.PARSER_FAILED
            return result

        has_parse_errors = any(
            d.severity == Severity.ERROR and d.source in ("parser",)
            for d in result.diagnostics
        )

        # ------------------------------------------------------------------
        # Stage 3: Semantic analysis (proceed even with parser errors if AST exists)
        # ------------------------------------------------------------------
        if result.ast is not None:
            try:
                sem = SemanticAnalyzer()
                sem_diags, st_snapshot = sem.analyze(result.ast)
                result.diagnostics.extend(sem_diags)
                result.symbol_table_snapshot = st_snapshot
                result.completed_stages.append("semantic")
            except Exception as exc:
                log.exception("Semantic analysis crashed: %s", exc)
                # Non-fatal; continue to pipeline

        # ------------------------------------------------------------------
        # Stage 4: Diagnostic pipeline (grouping / root-cause analysis)
        # ------------------------------------------------------------------
        try:
            pipeline = DiagnosticPipeline()
            result.diagnostics = pipeline.process(result.diagnostics)
        except Exception as exc:
            log.warning("Diagnostic pipeline error: %s", exc)

        # ------------------------------------------------------------------
        # Determine final status
        # ------------------------------------------------------------------
        total_errors = sum(
            1 for d in result.diagnostics if d.severity == Severity.ERROR
        )
        if total_errors == 0:
            result.status = AnalysisStatus.SUCCESS
        elif result.ast is not None and "semantic" in result.completed_stages:
            result.status = AnalysisStatus.PARTIAL
        elif has_parse_errors:
            result.status = AnalysisStatus.PARSER_FAILED
        elif has_lex_errors:
            result.status = AnalysisStatus.LEXER_FAILED
        else:
            result.status = AnalysisStatus.PARTIAL

        elapsed = time.monotonic() - t0
        log.info(
            "Analysis complete in %.3fs: status=%s errors=%d",
            elapsed, result.status.value, total_errors,
        )
        return result
