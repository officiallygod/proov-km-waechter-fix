# km_wachter.py
# Core service-scheduling logic for KM-Waechter.
#
# The two rule constants (SERVICE_INTERVAL_KM, WARN_AT_PERCENT) are loaded
# from settings.cfg at import time so there is exactly one place to change
# them.  The module-level names are kept for backward compatibility with any
# caller that imports them directly (e.g. fleet_report, verify.py).

from config_loader import load_settings, get_int
from car_model import CarField

_settings = load_settings()

# Single source of truth: values come from settings.cfg.
# settings.cfg is the authoritative store; these names are kept as
# module-level aliases so existing callers do not need to change.
SERVICE_INTERVAL_KM: int = get_int(_settings, "service_interval_km", 15000)
WARN_AT_PERCENT: int = get_int(_settings, "warn_at_percent", 80)


def wear_percent(km_since_service: float, interval: int) -> float:
    """Return the percentage of the service interval consumed, rounded to 2 dp.

    Example: wear_percent(14900, 15000) → 99.33
    Rounded so that comparisons and display values are stable —
    floating-point drift (e.g. 79.999999…) cannot silently skip the threshold.
    """
    return round((km_since_service / interval) * 100, 2)


def needs_service(car: dict) -> bool:
    """Return True when a car has consumed >= WARN_AT_PERCENT of its service interval.

    Rules:
    - A car with no ``last_service_km`` reading has no reliable baseline and
      is therefore *not* flagged — we must not act on absent data.
    - A car with no ``odometer`` reading is equally unusable and is skipped.
    """
    last = car.get(CarField.LAST_SERVICE_KM)
    odometer = car.get(CarField.ODOMETER)
    if last is None or odometer is None:
        return False
    km_since = odometer - last
    return wear_percent(km_since, SERVICE_INTERVAL_KM) >= WARN_AT_PERCENT


def check_fleet(fleet: list[dict]) -> list[str]:
    """Flag every car that needs a service and return the list of their IDs."""
    flagged = []
    for car in fleet:
        if needs_service(car):
            car_id = car.get(CarField.ID, "<unknown>")
            flagged.append(car_id)
            print(f"SERVICE DUE: {car_id}")
    return flagged
