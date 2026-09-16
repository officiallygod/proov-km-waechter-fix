# car_model.py
# Canonical field names for a car record dict.
#
# Every module that reads car dicts must import these constants instead of
# using raw string literals.  Changing a field name here propagates
# automatically to every caller — no scattered find-and-replace needed.
#
# Uses the (str, Enum) mixin pattern for Python 3.10 compatibility.
# Members compare equal to plain strings, so dict.get(CarField.ODOMETER)
# works exactly like dict.get("odometer").

from enum import Enum


class CarField(str, Enum):
    """Keys present in a car record dict."""

    ID = "id"
    ODOMETER = "odometer"
    LAST_SERVICE_KM = "last_service_km"
