"""Thirty deterministic bugs used to exercise the repair reliability layer.

The candidate patches are fixtures, not model outputs. Seven cases per project repair on
the first proposal, two require verification feedback and a second proposal, and one is
deliberately unrepairable within the two-attempt policy.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    project: str
    category: str
    description: str
    file: str
    test: str
    correct: str
    buggy: str
    candidates: tuple[str, ...]
    expected: str

    def as_dict(self) -> dict:
        value = asdict(self)
        value["candidates"] = list(self.candidates)
        return value


def _scenario(
    project: str,
    number: int,
    name: str,
    category: str,
    description: str,
    correct: str,
    buggy: str,
    *candidates: str,
) -> Scenario:
    expected = "escalated" if number == 10 else "verified"
    return Scenario(
        id=f"{project}-{number:02d}-{name}",
        project=project,
        category=category,
        description=description,
        file=f"{project}.py",
        test=f"tests/test_{project}.py::test_{name}",
        correct=correct,
        buggy=buggy,
        candidates=tuple(candidates or (correct,)),
        expected=expected,
    )


SCENARIOS = (
    _scenario(
        "textops",
        1,
        "normalize_space",
        "normalization",
        "Collapses mixed whitespace.",
        'return " ".join(value.split())',
        'return "  ".join(value.split())',
    ),
    _scenario(
        "textops",
        2,
        "slugify",
        "parsing",
        "Removes both boundary separators.",
        'return cleaned.strip("-")',
        'return cleaned.lstrip("-")',
    ),
    _scenario(
        "textops",
        3,
        "truncate",
        "boundary",
        "Reserves one character for the ellipsis.",
        'return value[: max(0, limit - 1)] + "…"',
        'return value[:limit] + "…"',
    ),
    _scenario(
        "textops",
        4,
        "initials",
        "formatting",
        "Uppercases generated initials.",
        'return "".join(part[0].upper() for part in name.split() if part)',
        'return "".join(part[0].lower() for part in name.split() if part)',
    ),
    _scenario(
        "textops",
        5,
        "word_count",
        "parsing",
        "Counts words across arbitrary whitespace.",
        "return len(value.split())",
        'return len(value.split(" "))',
    ),
    _scenario(
        "textops",
        6,
        "is_palindrome",
        "comparison",
        "Compares normalized text with its reverse.",
        "return normalized == normalized[::-1]",
        "return normalized == value",
    ),
    _scenario(
        "textops",
        7,
        "common_prefix",
        "iteration",
        "Shrinks a prefix from its right edge.",
        "prefix = prefix[:-1]",
        "prefix = prefix[1:]",
    ),
    _scenario(
        "textops",
        8,
        "mask_email",
        "privacy",
        "Masks every local-part character after the first.",
        "return f\"{visible}{'*' * max(1, len(local) - 1)}@{domain}\"",
        "return f\"{visible}{'*' * max(1, len(local) - 2)}@{domain}\"",
        "return f\"{visible}{'*' * len(local)}@{domain}\"",
        "return f\"{visible}{'*' * max(1, len(local) - 1)}@{domain}\"",
    ),
    _scenario(
        "textops",
        9,
        "wrap_words",
        "slicing",
        "Starts chunking at the first word.",
        "return [words[index : index + width] for index in range(0, len(words), width)]",
        "return [words[index : index + width] for index in range(1, len(words), width)]",
        "return [words[index : index + width] for index in range(2, len(words), width)]",
        "return [words[index : index + width] for index in range(0, len(words), width)]",
    ),
    _scenario(
        "textops",
        10,
        "parse_bool",
        "input validation",
        "Recognizes the documented true literals.",
        'if normalized in {"true", "1", "yes", "on"}:',
        'if normalized in {"true", "1", "on"}:',
        'if normalized in {"true", "1", "y", "on"}:',
        'if normalized in {"true", "1", "enabled", "on"}:',
    ),
    _scenario(
        "dataops",
        1,
        "mean",
        "arithmetic",
        "Uses the number of values as the denominator.",
        "return sum(values) / len(values)",
        "return sum(values) / (len(values) + 1)",
    ),
    _scenario(
        "dataops",
        2,
        "median",
        "statistics",
        "Averages the two middle values for even input.",
        "if len(ordered) % 2 == 0:\n        return (ordered[middle - 1] + ordered[middle]) / 2",
        "if len(ordered) % 2 == 0:\n        return ordered[middle]",
    ),
    _scenario(
        "dataops",
        3,
        "clamp",
        "boundary",
        "Clamps low values to the lower bound.",
        "return min(upper, max(lower, value))",
        "return max(upper, min(lower, value))",
    ),
    _scenario(
        "dataops",
        4,
        "moving_average",
        "statistics",
        "Divides each window by its width.",
        "return [sum(values[index : index + width]) / width for index in range(len(values) - width + 1)]",
        "return [sum(values[index : index + width]) / (width + 1) for index in range(len(values) - width + 1)]",
    ),
    _scenario(
        "dataops",
        5,
        "unique_preserving",
        "ordering",
        "Deduplicates without sorting the input.",
        "return list(dict.fromkeys(values))",
        "return sorted(set(values))",
    ),
    _scenario(
        "dataops",
        6,
        "chunk",
        "slicing",
        "Advances by exactly one chunk size.",
        "return [values[index : index + size] for index in range(0, len(values), size)]",
        "return [values[index : index + size] for index in range(0, len(values), size + 1)]",
    ),
    _scenario(
        "dataops",
        7,
        "flatten",
        "iteration",
        "Preserves group order while flattening.",
        "return [item for group in values for item in group]",
        "return [item for group in reversed(values) for item in group]",
    ),
    _scenario(
        "dataops",
        8,
        "normalize_minmax",
        "normalization",
        "Uses the data range as the scale.",
        "return [(value - low) / (high - low) for value in values]",
        "return [(value - low) / high for value in values]",
        "return [(value - low) / (high + low) for value in values]",
        "return [(value - low) / (high - low) for value in values]",
    ),
    _scenario(
        "dataops",
        9,
        "sum_by_key",
        "aggregation",
        "Ignores rows that do not contain the key.",
        "return sum(row[key] for row in rows if key in row)",
        "return sum(row[key] for row in rows if key not in row)",
        "return sum(row.get(key, 1) for row in rows)",
        "return sum(row[key] for row in rows if key in row)",
    ),
    _scenario(
        "dataops",
        10,
        "transpose",
        "matrix",
        "Transposes rows into columns in source order.",
        "return [list(column) for column in zip(*matrix, strict=True)]",
        "return [list(column) for column in zip(matrix, strict=True)]",
        "return [list(column) for column in zip(*matrix[::-1], strict=True)]",
        "return [list(column) for column in zip(*reversed(matrix), strict=True)]",
    ),
    _scenario(
        "apiops",
        1,
        "is_success",
        "HTTP semantics",
        "Treats only 2xx status codes as success.",
        "return 200 <= status < 300",
        "return 200 <= status <= 300",
    ),
    _scenario(
        "apiops",
        2,
        "retry_delay",
        "backoff",
        "Uses the configured zero-based retry exponent.",
        "return base * (2**attempt)",
        "return base * (2 ** (attempt - 1))",
    ),
    _scenario(
        "apiops",
        3,
        "extract_items",
        "response parsing",
        "Reads items from the nested data envelope.",
        'return payload.get("data", {}).get("items", [])',
        'return payload.get("items", [])',
    ),
    _scenario(
        "apiops",
        4,
        "normalize_headers",
        "HTTP semantics",
        "Normalizes header names case-insensitively.",
        "return {key.lower(): value.strip() for key, value in headers.items()}",
        "return {key: value.strip() for key, value in headers.items()}",
    ),
    _scenario(
        "apiops",
        5,
        "build_query",
        "encoding",
        "Sorts query parameters for stable output.",
        "return urlencode(sorted(params.items()))",
        "return urlencode(params)",
    ),
    _scenario(
        "apiops",
        6,
        "paginate_offset",
        "pagination",
        "Converts one-based pages to a zero-based offset.",
        "return (page - 1) * per_page",
        "return page * per_page",
    ),
    _scenario(
        "apiops",
        7,
        "error_message",
        "response parsing",
        "Reads the nested API error message.",
        'return error.get("message") or "Unknown API error"',
        'return payload.get("message") or "Unknown API error"',
    ),
    _scenario(
        "apiops",
        8,
        "pick_etag",
        "HTTP semantics",
        "Finds ETag after header normalization.",
        'return normalize_headers(headers).get("etag")',
        'return normalize_headers(headers).get("ETag")',
        'return normalize_headers(headers).get("e-tag")',
        'return normalize_headers(headers).get("etag")',
    ),
    _scenario(
        "apiops",
        9,
        "timeout_budget",
        "boundary",
        "Never returns a negative timeout budget.",
        "return max(0.0, total - elapsed)",
        "return max(0.0, total + elapsed)",
        "return min(total, elapsed)",
        "return max(0.0, total - elapsed)",
    ),
    _scenario(
        "apiops",
        10,
        "rate_limit_remaining",
        "HTTP semantics",
        "Reads the conventional rate-limit header.",
        'value = normalize_headers(headers).get("x-ratelimit-remaining")',
        'value = normalize_headers(headers).get("x-rate-limit-remaining")',
        'value = normalize_headers(headers).get("ratelimit-remaining")',
        'value = normalize_headers(headers).get("x-rate-limit")',
    ),
)


assert len(SCENARIOS) == 30
assert {scenario.project for scenario in SCENARIOS} == {"textops", "dataops", "apiops"}
