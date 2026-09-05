"""Time normalization — UTC epoch → IST date, settlement day bucketing.

Razorpay created_at is UTC epoch seconds. Settlement dates are IST.
The classic off-by-one-day bug lives here: a payment at 23:30 UTC is
05:00 IST the *next* day.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# IST is UTC+05:30, fixed (India does not observe DST)
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


def epoch_to_utc_datetime(epoch_seconds: int) -> datetime:
    """Convert UTC epoch seconds to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(epoch_seconds, tz=UTC)


def epoch_to_ist_datetime(epoch_seconds: int) -> datetime:
    """Convert UTC epoch seconds to IST datetime."""
    return datetime.fromtimestamp(epoch_seconds, tz=IST)


def epoch_to_ist_date(epoch_seconds: int) -> date:
    """Convert UTC epoch seconds to IST date.

    This is the correct function for settlement day bucketing.
    A payment at 2024-03-12 23:30 UTC is 2024-03-13 in IST.
    """
    return epoch_to_ist_datetime(epoch_seconds).date()


def date_to_epoch_ist_start(d: date) -> int:
    """Return epoch seconds for start of day (00:00:00) in IST."""
    dt = datetime(d.year, d.month, d.day, tzinfo=IST)
    return int(dt.timestamp())


def date_to_epoch_ist_end(d: date) -> int:
    """Return epoch seconds for end of day (23:59:59) in IST."""
    dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=IST)
    return int(dt.timestamp())


def settlement_day(epoch_seconds: int, t_plus_days: int = 2) -> date:
    """Compute expected settlement day: IST date of capture + T+n business days.

    Simplified: does not account for bank holidays. In production you'd
    use an RBI holiday calendar.
    """
    capture_date = epoch_to_ist_date(epoch_seconds)
    # Simple T+n (skipping weekends)
    days_added = 0
    current = capture_date
    while days_added < t_plus_days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            days_added += 1
    return current


def dates_within_window(d1: date, d2: date, window_days: int) -> bool:
    """Check if two dates are within ±window_days of each other."""
    return abs((d1 - d2).days) <= window_days
