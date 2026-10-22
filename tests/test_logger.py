"""Core Logger behavior: console output, levels, titles, timing, file output."""

from __future__ import annotations

import logging

import pytest

from general_log import Logger, default_log_dir


@pytest.fixture(autouse=True)
def _no_colors(monkeypatch):
    monkeypatch.setenv("PYLOGCOLORS", "0")
    yield


def make_logger(name: str = "fxtr", lvl: int = logging.DEBUG, **kwargs):
    """Build a logger inside the test body, after capsys is active."""
    return Logger(name=name, lvl=lvl, use_ts_in_cmd=False, **kwargs)


def _log_methods(lg: Logger, prefix: str):
    """Emit one message per level with the ``info/.../error`` names."""
    lg.debug(f"{prefix}-debug")
    lg.info(f"{prefix}-info")
    lg.warning(f"{prefix}-warn")
    lg.error(f"{prefix}-error")


def test_console_output_contains_messages(capsys):
    logger = make_logger()
    _log_methods(logger, "m")
    out = capsys.readouterr().out
    assert "m-debug" in out
    assert "m-info" in out
    assert "m-warn" in out
    assert "m-error" in out


def test_level_filtering(capsys):
    lg = Logger(name="fil", lvl=logging.WARNING)
    _log_methods(lg, "f")
    out = capsys.readouterr().out
    assert "f-debug" not in out
    assert "f-info" not in out
    assert "f-warn" in out
    assert "f-error" in out


def test_indentation_levels(capsys):
    logger = make_logger()
    logger.info("lvl0")
    logger.info("lvl1", lvl=1)
    out = capsys.readouterr().out
    assert "lvl0" in out
    assert "\t->lvl1" in out


def test_title_creates_filler(capsys):
    logger = make_logger()
    logger.title("TITLE", desired_size=20, fill="#")
    out = capsys.readouterr().out
    # The body (after the level prefix) is centered and never exceeds the
    # requested width while keeping the tail centered.
    line = out.strip().split("]", 1)[-1].strip()
    assert len(line) <= 20
    assert "TITLE" in line
    assert line.startswith("#") and line.endswith("#")
    # Both sides balance: SAME filler count before and after the tail.
    head = line.split("TITLE")[0]
    tail = line.split("TITLE")[1]
    assert head.count("#") == tail.count("#")


def test_timing_decorator_logs_debug(capsys):
    logger = make_logger()
    @logger.timing
    def work():
        return 42

    assert work() == 42
    out = capsys.readouterr().out
    assert "Starting 'work'..." in out
    assert "Finished 'work' in" in out


def test_file_output_and_header(tmp_path, capsys, monkeypatch):
    """A logfile argument writes to ./<dir>/<name>.log with the header."""
    monkeypatch.chdir(tmp_path)
    lg = make_logger(name="f1", logfile="run", append_ts=False)
    lg.info("to-file")
    lg.close()
    path = tmp_path / "log" / "run.log"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "to-file" in text
    assert "[INFO]" in text
    assert "This is the log file" in text
    assert "Log level set to: debug" in text


def test_pylogfile_env_used_as_default(tmp_path, monkeypatch, capsys):
    """Without logfile, the PYLOGFILE env var selects the file base."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYLOGFILE", "envrun")
    lg = make_logger(name="f2", lvl=logging.INFO)
    lg.info("env-file")
    lg.close()
    assert (tmp_path / "log" / "envrun.log").exists()


def test_configure_relocates_file(tmp_path, monkeypatch, capsys):
    """Calling ``configure`` with a new directory moves the log file."""
    monkeypatch.chdir(tmp_path)
    lg = make_logger(name="relo", logfile="run")
    assert (tmp_path / "log" / "run.log").exists()
    lg.configure(str(tmp_path / "other"))
    lg.info("after-move")
    lg.close()
    moved = tmp_path / "other" / "run.log"
    assert moved.exists()
    assert "after-move" in moved.read_text(encoding="utf-8")


def test_say_joins_and_colorizes(capsys):
    logger = make_logger()
    logger.say("a", "b", end=False)
    logger.say("c", "d", end=True, log="w")
    out = capsys.readouterr().out
    assert "a b" in out
    assert "c\nd" in out


def test_exception_logs_traceback(capsys):
    logger = make_logger()
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("context")
    out = capsys.readouterr().out
    assert "context" in out
    assert "Traceback" in out
    assert "ValueError: boom" in out


def test_set_level_changes_behavior(capsys):
    logger = make_logger()
    logger.info("before-set")
    logger.set_level("warning")
    logger.info("after-set-hidden")
    logger.warning("after-set-shown")
    assert logger.level == logging.WARNING
    out = capsys.readouterr().out
    assert "before-set" in out
    assert "after-set-hidden" not in out
    assert "after-set-shown" in out


def test_verbose_property(capsys):
    assert make_logger(lvl=logging.DEBUG).verbose is True
    assert make_logger(lvl=logging.WARNING).verbose is False


def test_no_color_env_disables_color(monkeypatch, capsys):
    from general_log import Logger as _L

    monkeypatch.delenv("PYLOGCOLORS", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    lg = _L(name="nocolor", lvl=logging.INFO, use_ts_in_cmd=False)
    assert lg.has_colors is False  # NO_COLOR respected when PYLOGCOLORS unset


def test_pylogcolors_forces_color_even_with_no_color(monkeypatch, capsys):
    from general_log import Logger as _L

    monkeypatch.setenv("PYLOGCOLORS", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    lg = _L(name="forcedcolor", lvl=logging.INFO, use_ts_in_cmd=False)
    assert lg.has_colors is True  # explicit override wins


def test_default_log_dir_per_platform(monkeypatch, tmp_path):
    """Each platform resolves its conventional per-user log directory."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    assert default_log_dir("app") == str(tmp_path / ".local" / "state" / "app" / "logs")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert default_log_dir("app") == str(tmp_path / "state" / "app" / "logs")
    monkeypatch.setattr("sys.platform", "darwin")
    assert default_log_dir("app") == str(tmp_path / "Library" / "Logs" / "app")
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert default_log_dir("app") == str(tmp_path / "Local" / "app" / "logs")


def test_max_bytes_appends_sessions(tmp_path, capsys):
    """With ``max_bytes`` a second session appends instead of truncating."""
    path = str(tmp_path / "keep.log")
    for index, name in enumerate(("keep1", "keep2")):
        lg = make_logger(name=name, logfile=path, max_bytes=100_000)
        lg.info(f"session-{index}")
        lg.close()
    text = (tmp_path / "keep.log").read_text(encoding="utf-8")
    assert text.count("Session started") == 2
    assert "session-0" in text and "session-1" in text


def test_max_bytes_rotates(tmp_path, capsys):
    """The log rotates once it exceeds ``max_bytes``."""
    lg = make_logger(name="rot", logfile=str(tmp_path / "rot.log"), max_bytes=1000)
    for index in range(40):
        lg.info(f"filler-{index:03d} " + "x" * 40)
    lg.close()
    assert (tmp_path / "rot.log.1").exists()
    assert (tmp_path / "rot.log").stat().st_size <= 1000


def test_unwritable_log_dir_degrades_to_console(tmp_path, capsys):
    """A log directory that cannot be created is reported, not raised."""
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", encoding="utf-8")
    lg = make_logger(name="deny", logfile=str(blocker / "sub" / "run.log"))
    lg.info("still-works")
    out = capsys.readouterr().out
    assert not lg.handler_added
    assert "Log file unavailable" in out
    assert "still-works" in out


def test_console_false_is_file_only(tmp_path, capsys):
    """``console=False`` keeps the console silent and the file complete."""
    lg = make_logger(name="quiet", logfile=str(tmp_path / "q.log"), console=False)
    lg.info("only-in-file")
    lg.close()
    assert "only-in-file" not in capsys.readouterr().out
    assert "only-in-file" in (tmp_path / "q.log").read_text(encoding="utf-8")


def test_log_file_is_private(tmp_path, capsys):
    """The log file is created owner-only."""
    lg = make_logger(name="perm", logfile=str(tmp_path / "p.log"))
    lg.close()
    assert (tmp_path / "p.log").stat().st_mode & 0o077 == 0


def test_html_notebook_enables_color_without_tty(monkeypatch):
    """A Jupyter kernel stream is not a TTY, but the HTML handler renders ANSI colors."""
    from general_log import log as _log

    monkeypatch.delenv("PYLOGCOLORS", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(_log, "_is_html_notebook", lambda: True)
    assert _log.Logger(name="htmlcolor", lvl=logging.INFO, use_ts_in_cmd=False).has_colors is True
    monkeypatch.setenv("NO_COLOR", "1")
    assert _log.Logger(name="htmlnocolor", lvl=logging.INFO, use_ts_in_cmd=False).has_colors is False
