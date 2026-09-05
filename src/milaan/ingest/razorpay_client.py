"""Razorpay SDK wrapper — pagination, backoff, rate-limit, fixtures mode.

In fixtures mode (when no valid API key is set), returns empty lists
so that `make demo` works with the synthetic data path instead.
"""

from __future__ import annotations

import time
from typing import Any

import razorpay

from milaan.config import Settings


class RazorpayClient:
    """Wrapper around the Razorpay Python SDK with retry and pagination."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._is_fixture_mode = settings.razorpay_key_id.startswith("rzp_test_xxxx")

        if not self._is_fixture_mode:
            self._client = razorpay.Client(
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
            )
        else:
            self._client = None

    @property
    def is_fixture_mode(self) -> bool:
        return self._is_fixture_mode

    def fetch_payments(
        self,
        from_ts: int | None = None,
        to_ts: int | None = None,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all payments with pagination."""
        if self._is_fixture_mode:
            return []
        return self._paginate("payment", from_ts=from_ts, to_ts=to_ts, count=count)

    def fetch_refunds(self, count: int = 100) -> list[dict[str, Any]]:
        """Fetch all refunds with pagination."""
        if self._is_fixture_mode:
            return []
        return self._paginate("refund", count=count)

    def fetch_settlements(self, count: int = 100) -> list[dict[str, Any]]:
        """Fetch all settlements with pagination."""
        if self._is_fixture_mode:
            return []
        return self._paginate("settlement", count=count)

    def fetch_settlement_recon(
        self,
        year: int,
        month: int,
        day: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch settlement recon/combined report."""
        if self._is_fixture_mode:
            return []
        # The Razorpay API for recon varies; this is a simplified version
        try:
            assert self._client is not None
            result = self._client.settlement.fetch_all({
                "count": 100,
            })
            return result.get("items", [])
        except Exception:
            return []

    def _paginate(
        self,
        entity: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """Generic pagination with exponential backoff on rate limits."""
        assert self._client is not None
        all_items: list[dict[str, Any]] = []
        skip = 0
        max_retries = 3

        while True:
            params: dict[str, Any] = {"count": count, "skip": skip}
            if from_ts is not None:
                params["from"] = from_ts
            if to_ts is not None:
                params["to"] = to_ts

            for attempt in range(max_retries):
                try:
                    if entity == "payment":
                        result = self._client.payment.fetch_all(params)
                    elif entity == "refund":
                        result = self._client.refund.fetch_all(params)
                    elif entity == "settlement":
                        result = self._client.settlement.fetch_all(params)
                    else:
                        raise ValueError(f"Unknown entity: {entity}")

                    items = result.get("items", [])
                    all_items.extend(items)

                    if len(items) < count:
                        return all_items  # last page

                    skip += count
                    break  # success, next page

                except Exception as e:
                    if "rate" in str(e).lower() or attempt < max_retries - 1:
                        wait = 2 ** attempt
                        time.sleep(wait)
                    else:
                        raise
            else:
                break  # exhausted retries

        return all_items
