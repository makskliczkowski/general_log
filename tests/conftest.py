"""Shared pytest fixture: reset module-level logger handler bookkeeping."""

from __future__ import annotations

import logging

import pytest


@pytest.fixture(autouse=True)
def _reset_logger_state():
    """Reset module bookkeeping and detach handlers added to named loggers.

    ``logging.getLogger(name)`` returns the same object across tests, so
    handlers attached in one test keep writing to that test's (stale) console
    stream unless they are detached here.
    """
    yield

    for logger in list(logging.Logger.manager.loggerDict.values()):
        if not isinstance(logger, logging.Logger):
            continue
        for handler in list(logger.handlers):
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
            logger.removeHandler(handler)
