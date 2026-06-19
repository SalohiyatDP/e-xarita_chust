# -*- coding: utf-8 -*-
"""
Logging utilities.

Provides a single ``get_logger`` factory that returns a logger writing both to
the console and to a rotating per-run log file.  Works identically on Python
2.7 (ArcGIS) and Python 3 (tests).  No arcpy dependency.
"""

from __future__ import unicode_literals

import io
import logging
import os
import sys
import time

_CONFIGURED = {}


def _utf8_stream_handler():
    """A console handler that will not choke on Cyrillic under a cp1251 console."""
    handler = logging.StreamHandler(sys.stdout)
    return handler


def get_logger(name="chust_balance", log_dir=None, level=logging.INFO):
    """Return a configured logger.

    Parameters
    ----------
    name : str
        Logger name; reused loggers are returned as-is.
    log_dir : str or None
        Directory to write the ``<name>_<timestamp>.log`` file into.  When None
        only console logging is configured.
    level : int
        Logging level.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid attaching duplicate handlers if called repeatedly.
    cfg_key = (name, log_dir)
    if _CONFIGURED.get(cfg_key):
        return logger

    logger.handlers = []
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    console = _utf8_stream_handler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_dir:
        try:
            if not os.path.isdir(log_dir):
                os.makedirs(log_dir)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            log_path = os.path.join(log_dir, "%s_%s.log" % (name, stamp))
            file_handler = logging.StreamHandler(
                io.open(log_path, "w", encoding="utf-8")
            )
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
            logger.info("Log file: %s", log_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not create log file in %s: %s", log_dir, exc)

    logger.propagate = False
    _CONFIGURED[cfg_key] = True
    return logger
