"""Tests for the public API surface and level coercion."""

from __future__ import annotations

import logging

from general_log import (
    Colors,
    coerce_level,
    colorize,
    printDictionary,
    printJust,
    printV,
)


def test_both_import_paths_expose_same_objects():
    """The package and module entry points must share identity."""
    import general_log as pkg
    import general_log.log as mod

    for name in ("Logger", "Colors", "get_global_logger", "colorize"):
        assert getattr(pkg, name) is getattr(mod, name)
    assert pkg.Logger.__module__ == "general_log.log"


def test_coerce_level_cases():
    assert coerce_level(None) == logging.INFO
    assert coerce_level(logging.ERROR) == logging.ERROR
    assert coerce_level("warning") == logging.WARNING
    assert coerce_level("W") == logging.WARNING
    assert coerce_level("d") == logging.DEBUG
    assert coerce_level("c") == logging.CRITICAL
    # Unknown strings fall back to INFO.
    assert coerce_level("bogus") == logging.INFO


def test_colorize_roundtrip():
    out = colorize("text", "red")
    assert out == "\x1b[31mtext\x1b[0m"
    # Falsy / white colors leave the text unchanged; unknown names resolve to
    # the reset code (matching the legacy behavior).
    assert colorize("text", None) == "text"
    assert colorize("text", "") == "text"
    assert colorize("text", "white") == "text"
    assert colorize("text", "nope") == "\x1b[0mtext\x1b[0m"


def test_colors_wrapper():
    c = Colors("red")
    assert c("x") == "\x1b[31mx\x1b[0m"
    assert str(c) == "\x1b[31m"
    assert Colors("yELLow")("y") == "\x1b[33my\x1b[0m"
    assert Colors("nope")("z") == "\x1b[0mz\x1b[0m"


def test_printV_verbosity_gate(capsys):
    printV("shown", v=True)
    printV("hidden", v=False)
    out = capsys.readouterr().out
    assert "shown" in out
    assert "hidden" not in out


def test_printDictionary_empty_handling():
    assert printDictionary(None) == ""
    assert printDictionary({}) == ""
    assert printDictionary({"a": 1, "b": 2}) == "a: 1, b: 2"


def test_printJust_columns_and_scientific():
    from io import StringIO

    buf = StringIO()
    printJust(buf, elements=[1, 2, 3], width=8)
    assert buf.getvalue() == "1\t      2\t      3\t      \n"
    assert not buf.getvalue().endswith("\n\n")
