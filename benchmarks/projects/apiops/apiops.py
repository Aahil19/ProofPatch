from urllib.parse import urlencode


def is_success(status: int) -> bool:
    return 200 <= status < 300


def retry_delay(attempt: int, base: float = 0.5) -> float:
    return base * (2**attempt)


def extract_items(payload: dict) -> list[dict]:
    return payload.get("data", {}).get("items", [])


def normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value.strip() for key, value in headers.items()}


def build_query(params: dict[str, object]) -> str:
    return urlencode(sorted(params.items()))


def paginate_offset(page: int, per_page: int) -> int:
    return (page - 1) * per_page


def error_message(payload: dict) -> str:
    error = payload.get("error", {})
    return error.get("message") or "Unknown API error"


def pick_etag(headers: dict[str, str]) -> str | None:
    return normalize_headers(headers).get("etag")


def timeout_budget(total: float, elapsed: float) -> float:
    return max(0.0, total - elapsed)


def rate_limit_remaining(headers: dict[str, str]) -> int | None:
    value = normalize_headers(headers).get("x-ratelimit-remaining")
    return int(value) if value is not None else None
