from apiops import (
    build_query,
    error_message,
    extract_items,
    is_success,
    normalize_headers,
    paginate_offset,
    pick_etag,
    rate_limit_remaining,
    retry_delay,
    timeout_budget,
)


def test_is_success():
    assert is_success(204)
    assert not is_success(300)


def test_retry_delay():
    assert retry_delay(3) == 4.0


def test_extract_items():
    assert extract_items({"data": {"items": [{"id": 1}]}}) == [{"id": 1}]


def test_normalize_headers():
    assert normalize_headers({"Content-Type": " application/json "}) == {
        "content-type": "application/json"
    }


def test_build_query():
    assert build_query({"q": "proof patch", "page": 2}) == "page=2&q=proof+patch"


def test_paginate_offset():
    assert paginate_offset(3, 25) == 50


def test_error_message():
    assert error_message({"error": {"message": "Not found"}}) == "Not found"


def test_pick_etag():
    assert pick_etag({"ETag": ' "abc" '}) == '"abc"'


def test_timeout_budget():
    assert timeout_budget(5, 7) == 0.0


def test_rate_limit_remaining():
    assert rate_limit_remaining({"X-RateLimit-Remaining": "12"}) == 12
