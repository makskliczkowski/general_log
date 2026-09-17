"""Tests for print_arguments and log_timing_summary."""

from __future__ import annotations

import argparse
import logging

from general_log import Logger, log_timing_summary, print_arguments


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="demo")
    p.add_argument("--lr", type=float, default=1e-3, help="learning rate")
    p.add_argument("--epochs", type=int, default=10, help="epochs")
    return p


def test_print_arguments_plain(capsys):
    print_arguments(_parser(), title="Config")
    out = capsys.readouterr().out
    assert "Title: Config" in out
    assert "lr" in out
    assert "learning rate" in out
    assert "epochs" in out


def test_print_arguments_with_logger(capsys):
    lg = Logger(name="arg", lvl=logging.INFO)
    print_arguments(_parser(), logger=lg)
    out = capsys.readouterr().out
    assert "lr" in out
    assert "learning rate" in out


def test_timing_summary_table(capsys):
    lg = Logger(name="ts", lvl=logging.INFO)
    log_timing_summary(
        lg,
        {"compile": 1.0, "train": 9.0},
        total_duration=10.0,
        extra_info=["note line", "1000 samples/sec"],
    )
    out = capsys.readouterr().out
    assert "Timing Summary" in out
    assert "compile" in out
    assert "Total" in out
    assert "note line" in out
    # Performance line appears after the table (bottom), not among extras.
    assert out.index("samples/sec") > out.index("Total")


def test_timing_summary_mismatch_warns(capsys):
    lg = Logger(name="tsw", lvl=logging.INFO)
    log_timing_summary(lg, {"a": 1.0}, total_duration=5.0)
    out = capsys.readouterr().out
    assert "differs from sum" in out
    assert "Total" in out


def test_timing_summary_no_phases(capsys):
    lg = Logger(name="tsn", lvl=logging.INFO)
    log_timing_summary(lg, {})
    out = capsys.readouterr().out
    assert "No phases timed" in out
