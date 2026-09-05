"""Unit tests for subset-sum composition matcher."""

from milaan.matching.subset_sum import solve_subset_sum


def test_subset_sum_exact_match():
    candidates = [10000, 20000, 30000, 40000]
    target = 50000
    indices = solve_subset_sum(candidates, target)
    assert indices is not None
    assert sum(candidates[i] for i in indices) == target


def test_subset_sum_no_match():
    candidates = [10000, 20000]
    target = 35000
    indices = solve_subset_sum(candidates, target)
    assert indices is None


def test_subset_sum_empty():
    assert solve_subset_sum([], 10000) is None
