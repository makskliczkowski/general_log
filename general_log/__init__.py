"""general_log: colored, verbosity-aware console/file logging for Python projects.

The package re-exports the :mod:`general_log.log` surface, so both import
paths work:

    from general_log import Logger          # canonical
    from general_log.log import Logger      # direct module path

Example
-------
    >>> from general_log import get_global_logger
    >>> logger = get_global_logger()
    >>> logger.info("This is an informational message.")
    >>> logger.debug("This is a debug message.", color="blue")
"""

from __future__ import annotations

__version__ = "2.1.0"
__author__ = "Maksymilian Kliczkowski"
__email__ = "maksymilian.kliczkowski@pwr.edu.pl"
__license__ = "MIT"

from .log import (
    ENV_LOGGER_COLORS,
    ENV_LOGGER_FILE,
    ENV_LOGGER_LEVEL,
    Colors,
    Logger,
    StripAnsiFormatter,
    coerce_level,
    colorize,
    get_global_logger,
    get_logger,
    log_timing_summary,
    print_arguments,
    print_tab,
    printDictionary,
    printJust,
    printV,
)

__all__ = [
    "Logger",
    "Colors",
    "StripAnsiFormatter",
    "colorize",
    "coerce_level",
    "print_tab",
    "printV",
    "printJust",
    "printDictionary",
    "print_arguments",
    "log_timing_summary",
    "get_global_logger",
    "get_logger",
    "ENV_LOGGER_FILE",
    "ENV_LOGGER_COLORS",
    "ENV_LOGGER_LEVEL",
]
