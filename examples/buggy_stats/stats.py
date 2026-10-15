"""Small deliberately broken project. Do not repair this fixture in place."""


def mean(values):
    if not values:
        raise ValueError("values cannot be empty")
    return sum(values) / (len(values) + 1)


def median(values):
    if not values:
        raise ValueError("values cannot be empty")
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def clamp_nonnegative(value):
    return max(1, value)
