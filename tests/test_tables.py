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


def test_table_sizes_columns_to_content(capsys):
    lg = Logger(name="tbl", lvl=logging.INFO)
    lg.table([["rbm/ite", "1.5"], ["rbm/iite/pow_1", "22.25"]], header=["arm", "energy"], align=("left", "right"))
    prefix, *lines = capsys.readouterr().out.splitlines()
    assert prefix.endswith("[INFO] ")   # the timestamp and level appear once
    assert lines == ["arm            energy", "-------------- ------", "rbm/ite           1.5", "rbm/iite/pow_1  22.25"]


def test_table_indents_without_arrows(capsys):
    Logger(name="tbl3", lvl=logging.INFO).table([["a", "b"]], header=["x", "y"], lvl=1)
    _, *lines = capsys.readouterr().out.splitlines()
    assert lines == ["\tx y", "\t- -", "\ta b"]


def test_table_rejects_ragged_rows():
    import pytest

    with pytest.raises(ValueError):
        Logger(name="tbl2", lvl=logging.INFO).table([["a", "b"], ["c"]])


def test_ansi_to_html_escapes_and_colors():
    from general_log.log import _ansi_to_html

    assert _ansi_to_html("\x1b[32mINFO\x1b[0m a<b") == '<span style="color:#2e9e4f">INFO</span> a&lt;b'


def test_block_logs_one_prefix_for_all_lines(capsys):
    Logger(name="blk", lvl=logging.INFO).block("first\nsecond", lvl=1)
    prefix, *lines = capsys.readouterr().out.splitlines()
    assert prefix.endswith("[INFO] ")
    assert lines == ["\tfirst", "\tsecond"]


def test_block_follows_level(capsys):
    Logger(name="blkw", lvl=logging.WARNING).block(["hidden"])
    assert capsys.readouterr().out == ""
    Logger(name="blkw2", lvl=logging.WARNING).block(["shown"], log="warning")
    assert "[WARNING]" in capsys.readouterr().out
