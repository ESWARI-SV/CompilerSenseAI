"""tests/test_patcher.py — Patch application tests."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.models import SourceEdit, RepairCandidate, RepairMethod, VerificationStatus
from repair.patcher import apply_edits, apply_candidate, diff_lines


def test_simple_insertion():
    source = "int x = 5"
    edit = SourceEdit(start_offset=9, end_offset=9, original_text="", replacement_text=";")
    patched, err = apply_edits(source, [edit])
    assert err is None
    assert patched == "int x = 5;"


def test_simple_replacement():
    source = "retrun x;"
    edit = SourceEdit(start_offset=0, end_offset=6, original_text="retrun", replacement_text="return")
    patched, err = apply_edits(source, [edit])
    assert err is None
    assert patched == "return x;"


def test_wrong_original_text_rejected():
    source = "int x = 5;"
    edit = SourceEdit(start_offset=0, end_offset=3, original_text="INT", replacement_text="float")
    patched, err = apply_edits(source, [edit])
    assert err is not None
    assert patched == source  # unchanged


def test_out_of_range_rejected():
    source = "abc"
    edit = SourceEdit(start_offset=0, end_offset=100, original_text="abc", replacement_text="xyz")
    patched, err = apply_edits(source, [edit])
    assert err is not None


def test_conflicting_edits_rejected():
    source = "hello world"
    edit1 = SourceEdit(0, 5, "hello", "greet")
    edit2 = SourceEdit(3, 8, "lo wo", "XX")
    patched, err = apply_edits(source, [edit1, edit2])
    assert err is not None


def test_multiple_non_overlapping_edits():
    source = "aXbYc"
    edit1 = SourceEdit(1, 2, "X", "1")
    edit2 = SourceEdit(3, 4, "Y", "2")
    patched, err = apply_edits(source, [edit1, edit2])
    assert err is None
    assert patched == "a1b2c"


def test_empty_edit_list():
    source = "unchanged"
    patched, err = apply_edits(source, [])
    assert err is None
    assert patched == source


def test_candidate_apply():
    source = "int x = 5"
    cand = RepairCandidate(
        candidate_id="test01",
        description="test",
        edits=[SourceEdit(9, 9, "", ";")],
        method=RepairMethod.DETERMINISTIC,
        explanation="add semi",
    )
    patched, err = apply_candidate(source, cand)
    assert err is None
    assert patched == "int x = 5;"
    assert cand.patched_source == "int x = 5;"


def test_diff_lines_shows_changes():
    original = "line1\nline2\nline3\n"
    patched = "line1\nLINE2\nline3\n"
    diff = diff_lines(original, patched)
    assert any("- line2" in l for l in diff)
    assert any("+ LINE2" in l for l in diff)


def test_diff_lines_identical():
    source = "line1\nline2\n"
    diff = diff_lines(source, source)
    assert all(l.startswith("  ") for l in diff)
