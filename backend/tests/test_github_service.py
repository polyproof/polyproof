"""Tests for github_service helper functions."""

from app.services.github_service import count_sorries_in_declaration

SAMPLE_FILE = """\
import Mathlib

namespace Foo

lemma single_sorry : True := by sorry

lemma two_sorries {a : Nat} (h : a > 0) : a > 0 := by
  cases a with
  | zero => sorry
  | succ n => sorry

theorem no_sorry : True := trivial

end Foo
"""


def test_count_sorries_single():
    assert count_sorries_in_declaration(SAMPLE_FILE, "Foo.single_sorry") == 1


def test_count_sorries_two():
    assert count_sorries_in_declaration(SAMPLE_FILE, "Foo.two_sorries") == 2


def test_count_sorries_none():
    assert count_sorries_in_declaration(SAMPLE_FILE, "Foo.no_sorry") == 0


def test_count_sorries_not_found():
    assert count_sorries_in_declaration(SAMPLE_FILE, "Foo.nonexistent") == 0


def test_count_sorries_short_name():
    """The function uses the short name (after last dot)."""
    assert count_sorries_in_declaration(SAMPLE_FILE, "single_sorry") == 1
