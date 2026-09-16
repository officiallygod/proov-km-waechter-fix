# config_loader.py
# Reads settings.cfg for KM-Waechter runtime configuration.

SETTINGS_FILE = "settings.cfg"

KNOWN_KEYS = [
    "service_interval_km",
    "warn_at_percent",
    "report_title",
    "history_file",
    "log_file",
    "mileage_unit",
]


def load_settings(path: str | None = None) -> dict[str, str]:
    """Parse settings.cfg and return a dict of known keys.

    Unknown keys are silently ignored so that stale or mistyped entries
    in the file do not surface as errors at runtime — but a warning is
    printed so typos in the config are at least visible.
    """
    if path is None:
        path = SETTINGS_FILE
    settings: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key in KNOWN_KEYS:
                settings[key] = value
    return settings


def get_int(settings: dict[str, str], key: str, fallback: int) -> int:
    """Return an integer setting value, or *fallback* if the key is absent or non-numeric."""
    try:
        return int(settings[key])
    except (KeyError, ValueError):
        return fallback


def get_setting(settings: dict[str, str], key: str, fallback: str = "") -> str:
    """Return a string setting value, or *fallback* if the key is absent."""
    return settings.get(key, fallback)
