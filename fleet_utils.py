# fleet_utils.py
# Shared helpers for the KM-Waechter fleet service.

KM_PER_MILE: float = 1.60934
MILES_PER_KM: float = 1.0 / KM_PER_MILE  # ≈ 0.62137 — miles per kilometre


def km_to_miles(km: float) -> float:
    """Convert kilometres to miles.

    Used by the nightly run for the UK partner report.
    """
    return km * MILES_PER_KM


def format_number(value: float) -> str:
    """Format a number to one decimal place."""
    return f"{value:.1f}"


def format_percent(value: float) -> str:
    """Format a number as a whole-number percentage string."""
    return f"{int(value)}%"
