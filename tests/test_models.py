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


def test_insert_rejects_text_match_target():
    # insert is position-only — an occurrence-based target isn't allowed.
    with pytest.raises(ValidationError):
        DocumentChange(
            operation="insert",
            target=ChangeTarget(text="foo", occurrence=1),
            new_text="x",
        )


def test_replace_and_delete_still_allow_text_match_target():
    # the insert-only restriction must not affect replace/delete.
    replace = DocumentChange(
        operation="replace", target=ChangeTarget(text="foo", occurrence=1), new_text="x"
    )
    delete = DocumentChange(
        operation="delete", target=ChangeTarget(text="foo", occurrence=2), new_text=""
    )
    assert replace.target.occurrence == 1
    assert delete.target.occurrence == 2


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


def test_occurrence_all_is_accepted_for_replace_and_delete():
    r = DocumentChange(
        operation="replace", target=ChangeTarget(text="x", occurrence="all"), new_text="y"
    )
    d = DocumentChange(
        operation="delete", target=ChangeTarget(text="x", occurrence="all"), new_text=""
    )
    assert r.target.occurrence == "all"
    assert d.target.occurrence == "all"


def test_occurrence_rejects_arbitrary_strings():
    with pytest.raises(ValidationError):
        ChangeTarget(text="x", occurrence="first")
