"""Column formatting preserves logging levels, colors, file output, and tracebacks."""

import pytest

from general_log import Logger, colorize


@pytest.mark.parametrize("method", ["info", "debug", "warning", "error"])
def test_message_methods_align_columns_with_indentation(method, capsys, monkeypatch):
    """All message levels accept per-column widths and alignments."""
    monkeypatch.setenv("PYLOGCOLORS", "0")
    logger = Logger(name=f"columns-{method}", lvl="debug", use_ts_in_cmd=False)
    getattr(logger, method)(["E", "-1.250", "ok"], column_width=(4, 8, 4), align=("left", "right", "center"), lvl=1)
    assert "\t->E      -1.250  ok \n" in capsys.readouterr().out
    logger.close()


def test_columns_ignore_ansi_codes_and_preserve_long_values_in_files(tmp_path, capsys, monkeypatch):
    """Color escapes consume no column width, and values wider than their minimum are retained."""
    monkeypatch.setenv("PYLOGCOLORS", "1")
    logger = Logger(name="columns-color", logfile=str(tmp_path / "columns.log"), use_ts_in_cmd=False)
    logger.info([colorize("E", "cyan"), "-1.250"], column_width=(4, 8), align=("left", "right"), color="green", lvl=1)
    logger.warning(["long label", "ok"], column_width=4)
    logger.close()
    saved = (tmp_path / "columns.log").read_text()
    assert "\t->E      -1.250\n" in saved
    assert "long label ok  \n" in saved
    assert "\x1b[" not in saved
    assert "\x1b[" in capsys.readouterr().out


def test_say_title_and_exception_support_columns(capsys, monkeypatch):
    """Convenience methods retain their severity, title formatting, and exception traceback."""
    monkeypatch.setenv("PYLOGCOLORS", "0")
    logger = Logger(name="columns-helpers", use_ts_in_cmd=False)
    logger.say("E", "-1.25", column_width=(4, 8), align=("left", "right"), log="critical")
    logger.title("Run", desired_size=7, fill="=", column_width=11, align="right")
    try:
        raise ValueError("trial failed")
    except ValueError:
        logger.exception(["arm", "iite"], column_width=6, lvl=1)
    output = capsys.readouterr().out
    assert "[CRITICAL] E       -1.25\n" in output
    assert "[INFO]     ==Run==\n" in output
    assert "\t->arm    iite  \n" in output
    assert "ValueError: trial failed" in output
    logger.close()


def test_invalid_column_layouts_are_reported():
    """Malformed column dimensions and alignments fail without silently losing values."""
    logger = Logger(name="columns-invalid")
    for widths, alignment in [((4,), "left"), ((4, -1), "left"), ((4, 4), ("left",)), ((4, 4), "diagonal")]:
        with pytest.raises(ValueError):
            logger.info(["a", "b"], column_width=widths, align=alignment)
    logger.close()
