"""Unit tests for the pure apply_range_operation function and change resolution."""

import pytest

from app.models import ChangeRange, ChangeTarget, DocumentChange
from app.services.document_service import (
    _resolve_change_location,
    apply_changes,
    apply_range_operation,
    diff_text,
)


def test_replace_range():
    assert apply_range_operation("hello world", "replace", 6, 11, "there") == "hello there"


def test_delete_range():
    assert apply_range_operation("hello world", "delete", 5, 11) == "hello"


def test_insert_at_position():
    assert apply_range_operation("hello world", "insert", 5, 5, " there") == "hello there world"


def test_insert_ignores_end():
    assert apply_range_operation("hello world", "insert", 5, 999, "!") == "hello! world"


def test_replace_at_start():
    assert apply_range_operation("hello world", "replace", 0, 5, "goodbye") == "goodbye world"


def test_replace_full_text():
    assert apply_range_operation("hello", "replace", 0, 5, "bye") == "bye"


def test_start_out_of_bounds_raises():
    with pytest.raises(ValueError):
        apply_range_operation("hello", "replace", 10, 12, "x")


def test_end_out_of_bounds_raises():
    with pytest.raises(ValueError):
        apply_range_operation("hello", "replace", 0, 12, "x")


def test_end_before_start_raises():
    with pytest.raises(ValueError):
        apply_range_operation("hello", "delete", 3, 1)


def test_unknown_operation_raises():
    with pytest.raises(ValueError):
        apply_range_operation("hello", "frobnicate", 0, 1, "x")


def test_resolve_change_location_uses_range_directly():
    change = DocumentChange(
        operation="replace", range=ChangeRange(start=1, end=3), new_text="x"
    )
    assert _resolve_change_location("abcdef", change) == (1, 3)


def test_resolve_change_location_finds_first_occurrence():
    change = DocumentChange(
        operation="replace", target=ChangeTarget(text="cat", occurrence=1), new_text="x"
    )
    assert _resolve_change_location("the cat sat on the cat mat", change) == (4, 7)


def test_resolve_change_location_finds_second_occurrence():
    change = DocumentChange(
        operation="replace", target=ChangeTarget(text="cat", occurrence=2), new_text="x"
    )
    assert _resolve_change_location("the cat sat on the cat mat", change) == (19, 22)


def test_resolve_change_location_missing_occurrence_raises():
    change = DocumentChange(
        operation="replace", target=ChangeTarget(text="dog", occurrence=1), new_text="x"
    )
    with pytest.raises(ValueError):
        _resolve_change_location("the cat sat", change)


def test_apply_changes_applies_multiple_changes_in_order():
    changes = [
        DocumentChange(
            operation="replace", target=ChangeTarget(text="quick", occurrence=1), new_text="slow"
        ),
        DocumentChange(
            operation="delete", target=ChangeTarget(text="brown ", occurrence=1), new_text=""
        ),
    ]
    assert apply_changes("the quick brown fox", changes) == "the slow fox"


def test_apply_changes_empty_list_returns_text_unchanged():
    assert apply_changes("hello", []) == "hello"


def test_apply_changes_raises_on_bad_target():
    changes = [
        DocumentChange(
            operation="replace", target=ChangeTarget(text="nope", occurrence=1), new_text="x"
        )
    ]
    with pytest.raises(ValueError):
        apply_changes("hello", changes)


def test_diff_text_shows_changed_lines():
    diff = diff_text("the quick brown fox", "the slow brown fox")
    assert "-the quick brown fox" in diff
    assert "+the slow brown fox" in diff


def test_diff_text_identical_texts_produces_empty_diff():
    assert diff_text("same", "same") == ""
