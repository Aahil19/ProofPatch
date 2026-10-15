import pytest
from stats import clamp_nonnegative, mean, median


@pytest.mark.parametrize("values, expected", [([2, 4, 6], 4), ([5], 5)])
def test_mean(values, expected):
    assert mean(values) == expected


def test_empty_mean():
    with pytest.raises(ValueError):
        mean([])


def test_even_median():
    assert median([9, 1, 3, 7]) == 5


def test_odd_median():
    assert median([9, 1, 3]) == 3


def test_empty_median():
    with pytest.raises(ValueError):
        median([])


@pytest.mark.parametrize("value, expected", [(-4, 0), (0, 0), (3, 3)])
def test_clamp(value, expected):
    assert clamp_nonnegative(value) == expected
