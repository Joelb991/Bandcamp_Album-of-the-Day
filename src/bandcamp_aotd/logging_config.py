"""One place to configure logging so every stage reports the same way.

The CLI and the notebooks both call :func:`setup_logging`; modules only ever
call ``logging.getLogger(__name__)`` and never ``print``. A two-hour scrape
then produces a readable, timestamped run log instead of anonymous progress
dots, and the same code is quiet when imported as a library.
"""
from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level=logging.INFO) -> None:
    """Attach a stdout handler to the root logger. Idempotent."""
    root = logging.getLogger()
    if root.handlers:                       # re-running a notebook cell is fine
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
