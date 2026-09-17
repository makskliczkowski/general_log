"""Tests for get_global_logger and get_logger."""

from __future__ import annotations

from general_log import Logger, get_global_logger, get_logger


def test_get_global_logger_is_singleton(monkeypatch):
    # Reset module state so the test is hermetic.
    import general_log.log as mod

    monkeypatch.setattr(mod, "_G_LOGGER", None)
    monkeypatch.setattr(mod, "_G_LOGGER_PID", None)
    monkeypatch.setenv("GEN_PYTHON_LOGGER_INIT_DONE", "0")

    a = get_global_logger()
    b = get_global_logger()
    assert a is b
    assert isinstance(a, Logger)


def test_get_logger_creates_new_instances():
    a = get_logger(name="n1")
    b = get_logger(name="n1")
    assert a is not b
