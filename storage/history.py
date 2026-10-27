"""
storage/history.py
Optional SQLite persistence for analysis sessions.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import List, Optional

from compiler.models import AnalysisResult, RepairCandidate

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "history.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with _get_connection() as conn:
            conn.executescript(schema)
    except Exception as exc:
        log.warning("Could not initialize history DB: %s", exc)


def save_analysis(
    result: AnalysisResult,
    candidates: Optional[List[RepairCandidate]] = None,
) -> Optional[int]:
    """Save an analysis result. Returns the row ID or None on failure."""
    try:
        with _get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO analyses (source, status, error_count, stages)
                VALUES (?, ?, ?, ?)
                """,
                (
                    result.source[:5000],  # cap length
                    result.status.value,
                    len(result.errors),
                    ",".join(result.completed_stages),
                ),
            )
            analysis_id = cur.lastrowid

            for d in result.diagnostics:
                conn.execute(
                    """
                    INSERT INTO diagnostics (analysis_id, code, category, message, severity, line, col)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_id,
                        d.code,
                        d.category.value,
                        d.message,
                        d.severity.value,
                        d.span.start.line,
                        d.span.start.column,
                    ),
                )

            if candidates:
                for c in candidates:
                    conn.execute(
                        """
                        INSERT INTO repair_candidates
                            (analysis_id, candidate_id, description, method, rank_score, verification_status)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            analysis_id,
                            c.candidate_id,
                            c.description,
                            c.method.value,
                            c.rank_score,
                            c.verification_status.value,
                        ),
                    )

            conn.commit()
            return analysis_id
    except Exception as exc:
        log.warning("Could not save analysis: %s", exc)
        return None


def get_recent_analyses(limit: int = 20) -> List[dict]:
    """Fetch recent analyses for the history view."""
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, status, error_count, stages,
                       substr(source, 1, 80) as source_preview
                FROM analyses
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("Could not fetch history: %s", exc)
        return []


def get_analysis_diagnostics(analysis_id: int) -> List[dict]:
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM diagnostics WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []
