"""Subset-sum solver with DP + amount-bound pruning + timeout.

Used by T2 composition matching: given a target settlement amount and a
list of candidate amounts (payments - fees - refunds - disputes), find
the subset that sums exactly to the target.

Returns the proof set (indices) or None if no solution within bounds.
"""

from __future__ import annotations

import time
from typing import Optional, Sequence, Union

from milaan.domain.money import Paise


def subset_sum(
    candidates: Sequence[Union[Paise, int]],
    target: Union[Paise, int],
    *,
    max_candidates: int = 60,
    timeout_ms: int = 500,
) -> Optional[list[int]]:
    """Find a subset of candidates that sums exactly to target.

    Uses dynamic programming with pruning.
    """
    target_int = int(target)
    if target_int <= 0:
        return None
    if not candidates:
        return None
    if len(candidates) > max_candidates:
        return None

    valid: list[tuple[int, int]] = [
        (i, int(c)) for i, c in enumerate(candidates) if 0 < int(c) <= target_int
    ]

    if not valid:
        return None

    deadline = time.monotonic() + timeout_ms / 1000.0
    dp: dict[int, list[int]] = {0: []}

    for idx, amount in valid:
        if time.monotonic() > deadline:
            return None

        new_entries: dict[int, list[int]] = {}
        for current_sum, indices in dp.items():
            new_sum = current_sum + amount
            if new_sum > target_int:
                continue
            if new_sum not in dp and new_sum not in new_entries:
                new_entries[new_sum] = indices + [idx]
                if new_sum == target_int:
                    return new_entries[new_sum]

        dp.update(new_entries)

    return dp.get(target_int)


# Alias
solve_subset_sum = subset_sum


def subset_sum_with_tolerance(
    candidates: Sequence[Union[Paise, int]],
    target: Union[Paise, int],
    tolerance_paise: int = 0,
    *,
    max_candidates: int = 60,
    timeout_ms: int = 500,
) -> Optional[tuple[list[int], Paise]]:
    """Find a subset that sums to within ±tolerance of target."""
    target_int = int(target)
    exact = subset_sum(
        candidates, target_int,
        max_candidates=max_candidates, timeout_ms=timeout_ms,
    )
    if exact is not None:
        return (exact, Paise(target_int))

    if tolerance_paise <= 0:
        return None

    for delta in range(1, tolerance_paise + 1):
        for sign in (1, -1):
            adjusted = target_int + sign * delta
            if adjusted <= 0:
                continue
            result = subset_sum(
                candidates, adjusted,
                max_candidates=max_candidates,
                timeout_ms=max(50, timeout_ms // (tolerance_paise + 1)),
            )
            if result is not None:
                return (result, Paise(adjusted))

    return None
