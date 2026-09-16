# test_km_wachter.py
from km_wachter import needs_service, wear_percent
import pytest


def test_almost_due_car_is_flagged():
    # A car at 14,900 of its 15,000 km window is about 99% worn and MUST be flagged.
    assert needs_service({"id": "VOS-4471", "odometer": 14900, "last_service_km": 0}) is True


def test_missing_reading_is_not_treated_as_zero():
    # A car with NO last-service reading must not be treated as fully worn.
    assert needs_service({"id": "VOS-7788", "odometer": 92000}) is False


def test_missing_odometer_is_not_flagged():
    # A car with no odometer reading cannot be evaluated — must not be flagged.
    assert needs_service({"id": "VOS-0001", "last_service_km": 5000}) is False


def test_wear_percent_rounds_to_two_decimal_places():
    # 14900 / 15000 * 100 = 99.333... — must come back as 99.33, not a long float.
    assert wear_percent(14900, 15000) == 99.33


def test_wear_percent_exact_interval_is_100():
    # A car exactly at its interval boundary is 100 % worn.
    assert wear_percent(15000, 15000) == 100.0


def test_wear_percent_fresh_car_is_zero():
    # A car with 0 km since service is 0 % worn.
    assert wear_percent(0, 15000) == 0.0
