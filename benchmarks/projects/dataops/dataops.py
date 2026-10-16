def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 0:
        return (ordered[middle - 1] + ordered[middle]) / 2
    return ordered[middle]


def clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def moving_average(values: list[float], width: int) -> list[float]:
    return [sum(values[index : index + width]) / width for index in range(len(values) - width + 1)]


def unique_preserving(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))


def chunk(values: list[int], size: int) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def flatten(values: list[list[int]]) -> list[int]:
    return [item for group in values for item in group]


def normalize_minmax(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    if low == high:
        return [0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def sum_by_key(rows: list[dict], key: str) -> float:
    return sum(row[key] for row in rows if key in row)


def transpose(matrix: list[list[int]]) -> list[list[int]]:
    return [list(column) for column in zip(*matrix, strict=True)]
