"""
repair/patcher.py
Safe patch application: validate edits, apply in order, preserve unrelated content.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from compiler.models import RepairCandidate, SourceEdit

log = logging.getLogger(__name__)


class PatchError(Exception):
    """Raised when a patch cannot be applied safely."""


def _validate_edits(source: str, edits: List[SourceEdit]) -> Optional[str]:
    """Return an error string if any edit is invalid, else None."""
    for i, edit in enumerate(edits):
        if edit.start_offset < 0 or edit.end_offset > len(source):
            return (
                f"Edit {i}: offsets [{edit.start_offset}:{edit.end_offset}] "
                f"out of range for source of length {len(source)}"
            )
        actual = source[edit.start_offset: edit.end_offset]
        if actual != edit.original_text:
            return (
                f"Edit {i}: expected original text {edit.original_text!r} "
                f"but found {actual!r} at [{edit.start_offset}:{edit.end_offset}]"
            )
    return None


def _detect_conflicts(edits: List[SourceEdit]) -> Optional[str]:
    """Detect overlapping edits."""
    sorted_edits = sorted(edits, key=lambda e: e.start_offset)
    for i in range(len(sorted_edits) - 1):
        a, b = sorted_edits[i], sorted_edits[i + 1]
        if a.end_offset > b.start_offset:
            return (
                f"Conflicting edits: [{a.start_offset}:{a.end_offset}] "
                f"overlaps [{b.start_offset}:{b.end_offset}]"
            )
    return None


def apply_edits(source: str, edits: List[SourceEdit]) -> Tuple[str, Optional[str]]:
    """
    Apply edits to source (immutable).
    Returns (patched_source, error_message).
    error_message is None on success.
    """
    if not edits:
        return source, None

    # Validate first
    err = _validate_edits(source, edits)
    if err:
        return source, err

    err = _detect_conflicts(edits)
    if err:
        return source, err

    # Apply in reverse order to preserve offsets
    result = source
    for edit in sorted(edits, key=lambda e: e.start_offset, reverse=True):
        result = result[: edit.start_offset] + edit.replacement_text + result[edit.end_offset:]

    return result, None


def apply_candidate(
    source: str, candidate: RepairCandidate
) -> Tuple[Optional[str], Optional[str]]:
    """
    Apply a RepairCandidate to source.
    Returns (patched_source, error_message).
    """
    patched, err = apply_edits(source, candidate.edits)
    if err:
        log.warning(
            "Candidate %s patch failed: %s", candidate.candidate_id, err
        )
        return None, err
    candidate.patched_source = patched
    return patched, None


def diff_lines(original: str, patched: str) -> List[str]:
    """
    Return a simple line-based unified diff between original and patched.
    No external library required.
    """
    orig_lines = original.splitlines(keepends=True)
    patch_lines = patched.splitlines(keepends=True)
    diff: List[str] = []

    max_len = max(len(orig_lines), len(patch_lines))
    i = j = 0

    while i < len(orig_lines) or j < len(patch_lines):
        orig_line = orig_lines[i] if i < len(orig_lines) else None
        patch_line = patch_lines[j] if j < len(patch_lines) else None

        if orig_line == patch_line:
            diff.append(f"  {orig_line.rstrip()}")
            i += 1
            j += 1
        elif orig_line is not None and patch_line is not None:
            diff.append(f"- {orig_line.rstrip()}")
            diff.append(f"+ {patch_line.rstrip()}")
            i += 1
            j += 1
        elif orig_line is not None:
            diff.append(f"- {orig_line.rstrip()}")
            i += 1
        else:
            diff.append(f"+ {patch_line.rstrip()}")
            j += 1

    return diff
