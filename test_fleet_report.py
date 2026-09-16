# test_fleet_report.py
from fleet_report import fleet_summary, car_wear
import pytest

SAMPLE = [
    {"id": "VOS-4471", "odometer": 14900, "last_service_km": 0},
    {"id": "VOS-2210", "odometer": 48400, "last_service_km": 45000},
]


def test_summary_counts_due_cars():
    # Only VOS-4471 is nearly worn (~99.3%), so exactly one car is due.
    assert fleet_summary(SAMPLE)["due"] == 1


def test_summary_handles_missing_reading():
    # A fleet that contains a car with no last_service_km must not raise a KeyError.
    # VOS-7788 has no reading; the report should complete and return a valid summary.
    fleet = [
        {"id": "VOS-4471", "odometer": 14900, "last_service_km": 0},
        {"id": "VOS-7788", "odometer": 92000},  # no last_service_km
    ]
    summary = fleet_summary(fleet)
    assert "average_wear" in summary
    assert summary["count"] == 2
    # VOS-7788 has no baseline reading so it must NOT be counted as due.
    assert summary["due"] == 1


def test_summary_raises_on_empty_fleet():
    # Calling fleet_summary with an empty list is a caller bug and must raise.
    with pytest.raises(ValueError, match="empty fleet"):
        fleet_summary([])


def test_car_wear_returns_zero_for_missing_reading():
    # A car with no last_service_km contributes 0.0 % wear, not a crash.
    assert car_wear({"id": "VOS-7788", "odometer": 92000}) == 0.0
