import pytest
from textops import (
    common_prefix,
    initials,
    is_palindrome,
    mask_email,
    normalize_space,
    parse_bool,
    slugify,
    truncate,
    word_count,
    wrap_words,
)


def test_normalize_space():
    assert normalize_space("  proof\tpatch  ") == "proof patch"


def test_slugify():
    assert slugify(" Evidence, First! ") == "evidence-first"


def test_truncate():
    assert truncate("evidence", 5) == "evid…"


def test_initials():
    assert initials("grace brewster murray hopper") == "GBMH"


def test_word_count():
    assert word_count("  one  two\nthree ") == 3


def test_is_palindrome():
    assert is_palindrome("Never odd or even")


def test_common_prefix():
    assert common_prefix(["repair", "repeat", "report"]) == "rep"


def test_mask_email():
    assert mask_email("alex@example.com") == "a***@example.com"


def test_wrap_words():
    assert wrap_words(["a", "b", "c", "d", "e"], 2) == [["a", "b"], ["c", "d"], ["e"]]


def test_parse_bool():
    assert parse_bool(" YES ") is True
    with pytest.raises(ValueError):
        parse_bool("maybe")
