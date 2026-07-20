"""Validation tests for the DocumentChange model."""

import pytest
from pydantic import ValidationError

from app.models import ChangeRange, ChangeTarget, DocumentChange


def test_range_has_no_occurrence_field():
    assert "occurrence" not in ChangeRange.model_fields


def test_range_only_change_ignores_stray_occurrence():
    change = DocumentChange.model_validate(
        {
            "operation": "replace",
            "range": {"start": 0, "end": 3, "occurrence": 5},
            "new_text": "x",
        }
    )
    assert change.target is None
    assert not hasattr(change.range, "occurrence")


def test_requires_exactly_one_locator_neither_set():
    with pytest.raises(ValidationError):
        DocumentChange(operation="delete", new_text="")


def test_requires_exactly_one_locator_both_set():
    with pytest.raises(ValidationError):
        DocumentChange(
            operation="replace",
            target=ChangeTarget(text="a", occurrence=1),
            range=ChangeRange(start=0, end=1),
            new_text="x",
        )


def test_insert_requires_start_equals_end():
    with pytest.raises(ValidationError):
        DocumentChange(
            operation="insert", range=ChangeRange(start=0, end=1), new_text="x"
        )


def test_insert_allows_start_equals_end():
    change = DocumentChange(
        operation="insert", range=ChangeRange(start=3, end=3), new_text="x"
    )
    assert change.range.start == change.range.end == 3


def test_delete_requires_empty_new_text():
    with pytest.raises(ValidationError):
        DocumentChange(
            operation="delete", range=ChangeRange(start=0, end=1), new_text="oops"
        )


def test_delete_allows_empty_new_text():
    change = DocumentChange(
        operation="delete", range=ChangeRange(start=0, end=1), new_text=""
    )
    assert change.new_text == ""


def test_replace_rejects_empty_new_text():
    with pytest.raises(ValidationError):
        DocumentChange(
            operation="replace", range=ChangeRange(start=0, end=1), new_text=""
        )


def test_replace_requires_nonempty_new_text():
    change = DocumentChange(
        operation="replace", range=ChangeRange(start=0, end=1), new_text="hi"
    )
    assert change.new_text == "hi"
