# log_util.py
# Lightweight in-process logger for KM-Waechter.
#
# LOG_LINES accumulates entries for the current run and is flushed to disk
# by flush_log() at the end of print_report(). It is intentionally module-level
# so that every caller in the same process shares one buffer.

import time

LOG_LINES: list[str] = []


def log(message: str) -> None:
    """Append a timestamped entry to the in-memory log and print it."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    LOG_LINES.append(line)
    print(line)


def flush_log(path: str) -> None:
    """Write buffered log lines to *path* (append mode) and clear the buffer."""
    with open(path, "a") as f:
        for line in LOG_LINES:
            f.write(line + "\n")
    LOG_LINES.clear()
