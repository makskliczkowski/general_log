"""Tests for the reference README quick-start snippets."""

from __future__ import annotations

import logging

from general_log import get_global_logger


def test_readme_quickstart(capsys):
    logger = get_global_logger()
    logger.info("This is an informational message.")
    out = capsys.readouterr().out
    assert "This is an informational message." in out


def test_debug_shows_when_requested(capsys):
    """Debug output is visible only when the logger level permits it."""
    import general_log.log as mod

    # Other tests may have already constructed the singleton at INFO level, so
    # the cached instance must be dropped to observe the DEBUG logger here.
    mod._G_LOGGER = None
    mod._G_LOGGER_PID = None
    old = mod.os.environ.get("GEN_PYTHON_LOGGER_INIT_DONE")
    mod.os.environ["GEN_PYTHON_LOGGER_INIT_DONE"] = "0"
    try:
        logger = get_global_logger(lvl=logging.DEBUG)
        logger.debug("This is a debug message.")
        out = capsys.readouterr().out
        assert "This is a debug message." in out
    finally:
        if old is None:
            mod.os.environ.pop("GEN_PYTHON_LOGGER_INIT_DONE")
        else:
            mod.os.environ["GEN_PYTHON_LOGGER_INIT_DONE"] = old


def test_readme_banner_only_once(capsys):
    """The banner must appear at most once across construction."""
    import general_log.log as mod

    old = mod.os.environ.get("GEN_PYTHON_LOGGER_INIT_DONE")
    mod.os.environ["GEN_PYTHON_LOGGER_INIT_DONE"] = "0"
    try:
        get_global_logger()
        get_global_logger()
    finally:
        if old is None:
            mod.os.environ.pop("GEN_PYTHON_LOGGER_INIT_DONE")
        else:
            mod.os.environ["GEN_PYTHON_LOGGER_INIT_DONE"] = old
    out = capsys.readouterr().out
    assert out.count("Global Logger initialized!") <= 1
