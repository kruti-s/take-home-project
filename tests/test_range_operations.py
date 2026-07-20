"""Unit tests for the pure apply_range_operation function and change resolution."""

import pytest

from app.models import ChangeRange, ChangeTarget, DocumentChange
from app.services.document_service import (
    _resolve_change_location,
    apply_range_operation,
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
    change = DocumentChange(operation="replace", range=ChangeRange(start=1, end=3))
    assert _resolve_change_location("abcdef", change) == (1, 3)


def test_resolve_change_location_finds_first_occurrence():
    change = DocumentChange(
        operation="replace", target=ChangeTarget(text="cat", occurrence=1)
    )
    assert _resolve_change_location("the cat sat on the cat mat", change) == (4, 7)


def test_resolve_change_location_finds_second_occurrence():
    change = DocumentChange(
        operation="replace", target=ChangeTarget(text="cat", occurrence=2)
    )
    assert _resolve_change_location("the cat sat on the cat mat", change) == (19, 22)


def test_resolve_change_location_missing_occurrence_raises():
    change = DocumentChange(
        operation="replace", target=ChangeTarget(text="dog", occurrence=1)
    )
    with pytest.raises(ValueError):
        _resolve_change_location("the cat sat", change)
