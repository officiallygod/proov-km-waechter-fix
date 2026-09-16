# fleet_report.py
# Nightly fleet-health report for Vossberg Mobility.
#
# Reads runtime configuration from settings.cfg via config_loader so that
# the report title, log path, and mileage unit can be changed without
# touching this file.

from km_wachter import wear_percent, needs_service, SERVICE_INTERVAL_KM
from config_loader import load_settings, get_setting
from log_util import log, flush_log
from car_model import CarField
import fleet_utils


def car_wear(car: dict) -> float:
    """Return the service-interval wear percentage for one car.

    Returns 0.0 for any car that has no ``last_service_km`` baseline so
    that a missing reading never raises a KeyError or skews the average.
    """
    last = car.get(CarField.LAST_SERVICE_KM)
    odometer = car.get(CarField.ODOMETER, 0)
    if last is None:
        return 0.0
    return wear_percent(odometer - last, SERVICE_INTERVAL_KM)


def fleet_summary(fleet: list[dict]) -> dict:
    """Return a summary dict for the whole fleet.

    Keys: ``count`` (int), ``due`` (int), ``average_wear`` (float, %).

    ``average_wear`` is the mean of each car's individual wear percentage.
    Cars with no last_service_km reading contribute 0 % to the accumulator
    so they pull the average down rather than crash the report.

    Raises ``ValueError`` if *fleet* is empty — a report over zero cars is
    meaningless and most likely a caller bug.
    """
    if not fleet:
        raise ValueError("fleet_summary called with an empty fleet")

    total_wear_pct = 0.0  # accumulates per-car wear percentages; divided by count below
    due = 0
    for car in fleet:
        total_wear_pct += car_wear(car)
        if needs_service(car):
            due += 1

    average_wear = total_wear_pct / len(fleet)
    return {"count": len(fleet), "due": due, "average_wear": average_wear}


def print_report(fleet: list[dict]) -> None:
    """Print the nightly fleet-health report and append a timestamped log entry.

    Distance is displayed in the unit specified by ``mileage_unit`` in
    settings.cfg.  Supported values: ``km`` (default) and ``miles``.
    Using ``km`` keeps the displayed figure in the same unit as the
    odometer readings stored in the database; ``miles`` is used for the
    UK partner garage report.
    """
    settings = load_settings()
    log(get_setting(settings, "report_title", "Nightly fleet report"))

    s = fleet_summary(fleet)
    print(f"Fleet: {s['count']} cars")
    print(f"Due for service: {s['due']}")
    # format_percent rounds to the nearest whole number, matching the
    # original report format (e.g. "Average wear: 59%").
    print(f"Average wear: {fleet_utils.format_percent(s['average_wear'])}")

    total_km = sum(car.get(CarField.ODOMETER, 0) for car in fleet)

    mileage_unit = get_setting(settings, "mileage_unit", "km")
    if mileage_unit == "miles":
        # UK partner garage requests distance in imperial miles.
        distance_str = f"{fleet_utils.format_number(fleet_utils.km_to_miles(total_km))} miles"
    else:
        # Default: show kilometres — the same unit used in the odometer readings.
        distance_str = f"{fleet_utils.format_number(total_km)} km"

    print(f"Fleet distance: {distance_str}")
    flush_log(get_setting(settings, "log_file", "km_wachter.log"))
