from dataops import (
    chunk,
    clamp,
    flatten,
    mean,
    median,
    moving_average,
    normalize_minmax,
    sum_by_key,
    transpose,
    unique_preserving,
)


def test_mean():
    assert mean([2, 4, 9]) == 5


def test_median():
    assert median([9, 1, 3, 7]) == 5


def test_clamp():
    assert clamp(-4, 0, 10) == 0


def test_moving_average():
    assert moving_average([1, 3, 5, 7], 2) == [2, 4, 6]


def test_unique_preserving():
    assert unique_preserving([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_chunk():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_flatten():
    assert flatten([[1, 2], [], [3]]) == [1, 2, 3]


def test_normalize_minmax():
    assert normalize_minmax([10, 20, 30]) == [0.0, 0.5, 1.0]


def test_sum_by_key():
    assert sum_by_key([{"cost": 2}, {}, {"cost": 5}], "cost") == 7


def test_transpose():
    assert transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]
