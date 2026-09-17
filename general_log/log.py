"""Logging helpers with verbosity, indentation, color, and file output.

The :class:`Logger` class wraps the standard :mod:`logging` module behind a
compact, colored API.  Module helpers (``printV``, ``printDictionary``,
``printJust``, ``print_arguments``, ``log_timing_summary``) and the
process-wide :func:`get_global_logger` singleton complete the surface.

Environment variables configure defaults:
``PYLOGCOLORS=1``   forces console colors, ``PYLOGCOLORS=0`` disables them
                    (``NO_COLOR`` is honored; otherwise colors auto-enable on a TTY);
``PYLOGFILE``       sets a default log file (used when no ``logfile`` is passed);
``PYLOGLEVEL``      sets the default level (e.g. ``PYLOGLEVEL=warning``).

Console level fields are colored per level on ANSI-capable terminals; file
output always strips color codes.  The module is re-exported through
``general_log`` and stays importable as ``general_log.log``.
"""

from __future__ import annotations

import functools
import getpass
import logging
import os
import platform
import re
import sys
import threading
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Final, Literal, TextIO, TypeVar

# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

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

T = TypeVar("T")

ENV_LOGGER_FILE: Final   = "PYLOGFILE"
ENV_LOGGER_COLORS: Final = "PYLOGCOLORS"
ENV_LOGGER_LEVEL: Final  = "PYLOGLEVEL"

DEFAULT_LOG_DIRECTORY: Final = "./log"

#: Timestamp format for file names and console/file time fields.
DATE_FMT: Final = "%d_%m_%Y_%H-%M-%S"

_LEVELS: Final[dict[int, str]] = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}
_LEVELS_R: Final[dict[str, int]] = {v: k for k, v in _LEVELS.items()}

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------

#: ANSI reset code; doubles as the ``white`` entry for the legacy ``Colors`` API.
_RESET: Final = "\x1b[0m"
_CODES: Final[dict[str, str]] = {
    "black": "\x1b[30m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "blue": "\x1b[34m",
    "white": _RESET,
}

#: Regex for ANSI CSI sequences (ESC [ ... m).
_ansi_escape: Final = re.compile(r"\x1b\[[0-9;]*m")

#: Per-level ANSI color for the console levelname field.
_LEVEL_COLORS: Final[dict[int, str]] = {
    logging.DEBUG: "\x1b[36m",     # cyan
    logging.INFO: "\x1b[32m",      # green
    logging.WARNING: "\x1b[33m",   # yellow
    logging.ERROR: "\x1b[31m",     # red
    logging.CRITICAL: "\x1b[35m",  # magenta
}


class Colors:
    """ANSI color wrapper.

    ``Colors("red")("text")`` wraps ``text`` in red escape codes.  Legacy
    attribute access (``Colors.red``) returns the raw code; ``str(Colors(name))``
    resolves a name (case-insensitive) to its code.  Unknown names resolve to
    the reset code.
    """

    black: Final  = _CODES["black"]
    red: Final    = _CODES["red"]
    green: Final  = _CODES["green"]
    yellow: Final = _CODES["yellow"]
    blue: Final   = _CODES["blue"]
    white: Final  = _RESET

    def __init__(self, color: str) -> None:
        self.color = color

    def __str__(self) -> str:
        return _CODES.get(str(self.color).lower(), _RESET)

    def __repr__(self) -> str:
        return str(self)

    def __call__(self, text: object) -> str:
        """Wrap ``text`` in this color followed by a reset code."""
        return f"{self}{text}{_RESET}"

    def __len__(self) -> int:
        return len(str(self))


class StripAnsiFormatter(logging.Formatter):
    """Formatter that removes ANSI color sequences from log records."""

    def format(self, record: logging.LogRecord) -> str:
        return _ansi_escape.sub("", super().format(record))


def colorize(text: object, color: str | None) -> str:
    """Wrap ``text`` in the named color.

    ``None``, the empty string, ``"white"``, and unknown names return
    ``str(text)`` unchanged.
    """
    if not color or color.lower() == "white":
        return str(text)
    return f"{Colors(color)}{text}{_RESET}"


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------

def coerce_level(level: int | str | None) -> int:
    """Resolve a level: ``logging`` int, name/letter shorthand, or ``None``.

    String values match by name (``"warning"``) or first letter (``"w"``,
    ``"WARN"``) against ``debug/info/warning/error/critical``.  Unknown
    strings and ``None`` default to ``logging.INFO``; ints pass through.
    """
    if level is None:
        return logging.INFO
    if not isinstance(level, str):
        return int(level)
    key = level.strip().lower()
    if key in _LEVELS_R:
        return _LEVELS_R[key]
    for name, num in _LEVELS_R.items():
        if name[:1] == key[:1]:
            return num
    return logging.INFO


# ---------------------------------------------------------------------------
# Console detection
# ---------------------------------------------------------------------------

def _console_stream() -> TextIO:
    """Return stdout, or stderr when stdout is unavailable."""
    if sys.stdout is not None:
        return sys.stdout
    assert sys.stderr is not None
    return sys.stderr


def _stdout_supports_color() -> bool:
    """Whether the console stream is an ANSI-capable TTY.

    ``NO_COLOR`` (https://no-color.org) disables colors regardless of the
    stream; non-TTY streams disable them too.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    isatty = getattr(_console_stream(), "isatty", None)
    if isatty is None:
        return False
    try:
        return bool(isatty())
    except (ValueError, OSError):
        return False


def _enable_windows_ansi() -> bool:
    """Enable Windows ANSI processing via colorama when installed.

    No-op (returns True) on other platforms.  Without colorama, Windows keeps
    colors off because ANSI codes would render as garbage.
    """
    if os.name != "nt":
        return True
    try:
        import colorama  # type: ignore[import-untyped]
    except ImportError:
        return False
    colorama.just_fix_windows_console()
    return True


def _colors_enabled() -> bool:
    """Whether colored console output is requested and supported.

    ``PYLOGCOLORS`` overrides detection: falsy values (``0``, ``false``, ...)
    disable colors; any other value forces them on.  Without it, ``NO_COLOR``
    and a non-TTY stream disable colors.
    """
    force = os.environ.get(ENV_LOGGER_COLORS)
    if force is not None:
        return force.strip().lower() not in {"0", "false", "no", "off"} and _enable_windows_ansi()
    if not _stdout_supports_color():
        return False
    return _enable_windows_ansi()


def _is_interactive_notebook() -> bool:
    """Whether running inside a Jupyter notebook or IPython shell.

    Notebooks attach duplicate handlers to the root logger, repeating console
    output; detection lets the console handler be shared instead.
    """
    try:
        from IPython.core.getipython import get_ipython  # type: ignore[import-not-found]
    except ImportError:
        return False
    try:
        shell = get_ipython()
    except (RuntimeError, AttributeError):
        return False
    if shell is None:
        return False
    return shell.__class__.__name__ in ("ZMQInteractiveShell", "TerminalInteractiveShell")


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def print_tab(lvl: int = 0) -> str:
    """Indentation prefix: ``lvl`` tabs plus ``->`` for positive levels."""
    return "\t" * lvl + ("->" if lvl > 0 else "")


def printV(what: object, v: bool = True, tabulators: int = 0) -> None:
    """Print ``what`` to stdout only when verbosity ``v`` is enabled."""
    if v:
        print("\t" * tabulators + "->" + str(what))


def printDictionary(d: Mapping[Any, Any] | None) -> str:
    """Comma-separated ``key: value`` string of ``d``; empty string for falsy input."""
    if not d:
        return ""
    return ", ".join(f"{key}: {value}" for key, value in d.items())


def printJust(
    file: TextIO,
    sep: str = "\t",
    elements: Sequence[Any] | None = None,
    width: int = 8,
    endline: bool = True,
    scientific: bool = False,
) -> None:
    """Write ``elements`` to ``file`` as fixed-width, left-justified columns.

    Each element is padded with ``sep`` to ``width`` characters; the row ends
    with a newline when ``endline`` is True.  With ``scientific``, elements
    are formatted in scientific notation (``"{:e}"``).
    """
    if not elements:
        return
    for item in elements:
        token = f"{item:e}" if scientific else str(item)
        file.write((token + sep).ljust(max(1, width)))
    if endline:
        file.write("\n")


# ---------------------------------------------------------------------------
# Log file plumbing
# ---------------------------------------------------------------------------

def _write_header(logfile: str, levelname: str) -> None:
    """Write the session header block into a freshly created log file."""
    stamp = datetime.now().strftime(DATE_FMT)
    lines = [
        "--------------------------------------------------",
        "This is the log file for the current session.",
        f"Log file created on {stamp}.",
        f"Log level set to: {levelname}.",
        f"Author: {getpass.getuser() or 'unknown'}",
        f"Machine: {platform.node() or 'unknown'}",
        f"OS: {platform.system()} {platform.release()} {platform.version()}",
        f"Python version: {sys.version}",
        f"Python executable: {sys.executable}",
        f"Current working directory: {os.getcwd()}",
        f"Log file: {logfile}",
        f"Log level: {levelname}",
        f"Log file created on {stamp}",
        f"Log level set to: {levelname}",
        "--------------------------------------------------",
    ]
    with open(logfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class Logger:
    """Console and file logger with verbosity, indentation, and color.

    Wraps a standard :mod:`logging` logger behind a compact API (``info`` /
    ``debug`` / ``warning`` / ``error`` / ``say``, ``title``, ``timing``).  A
    console handler attaches once per logger name; notebook environments share
    a single console handler so output is not duplicated.
    """

    LEVELS: Final[dict[int, str]] = _LEVELS
    LEVELS_R: Final[dict[str, int]] = _LEVELS_R

    #: Shared console handler across all Logger instances in notebook mode.
    _shared_console_handler: logging.StreamHandler[TextIO] | None = None

    class _ColoredLevelFormatter(logging.Formatter):
        """Formatter wrapping the levelname field in a per-level ANSI color."""

        def format(self, record: logging.LogRecord) -> str:
            original = record.levelname
            try:
                code = _LEVEL_COLORS.get(record.levelno, _RESET)
                record.levelname = f"{code}{original}{_RESET}"
                return super().format(record)
            finally:
                record.levelname = original

    def __init__(
        self,
        name: str = "Global",
        logfile: str | None = None,
        lvl: int | str | None = None,
        append_ts: bool = False,
        use_ts_in_cmd: bool = False,
    ) -> None:
        """Initialize the logger.

        Args:
            name: Logger name (default ``"Global"``).
            logfile: Optional log file.  A bare file name is placed in
                ``./log``; a directory component is honored as the location.
                When ``None``, the ``PYLOGFILE`` environment variable is used
                if set.
            lvl: Minimum level to record: ``logging`` int, name/letter
                shorthand, or ``None``.  ``None`` resolves to the
                ``PYLOGLEVEL`` environment variable, then to INFO.
            append_ts: Append the timestamp to the log file name.
            use_ts_in_cmd: Include the timestamp in console output.
        """
        self.now      = datetime.now()
        self.now_str  = self.now.strftime(DATE_FMT)
        if lvl is None:
            lvl = os.environ.get(ENV_LOGGER_LEVEL)
        self.lvl            = coerce_level(lvl)
        self.handler_added  = False
        self.has_colors     = _colors_enabled()

        self.logger           = logging.getLogger(name or __name__)
        self.logger.setLevel(self.lvl)
        self.logger.propagate = False

        self._attach_console_handler(use_ts_in_cmd)

        # Log file selection: explicit ``logfile`` wins, then PYLOGFILE.
        path = logfile or os.environ.get(ENV_LOGGER_FILE)
        self.working = True
        if path:
            directory, base = os.path.split(path)
            if base.endswith(".log"):
                base = base[:-4]
            base = base or self.now_str
            if append_ts:
                base = f"{base}_{self.now_str}"
            self._logfile_base = base
            self.logfile       = base  # provisional; configure() sets the full path
            self.configure(directory or DEFAULT_LOG_DIRECTORY)
        else:
            self._logfile_base = self.now_str
            self.logfile       = self._logfile_base

    # ------------------------------------------------------------- core setup

    def set_level(self, level: int | str | None) -> None:
        """Change the minimum logging level at runtime.

        Accepts the same values as the ``lvl`` constructor argument.  Applies
        to the wrapped logger and all attached handlers.
        """
        self.lvl = coerce_level(level)
        self.logger.setLevel(self.lvl)
        for handler in self.logger.handlers:
            handler.setLevel(self.lvl)

    @property
    def level(self) -> int:
        """The current minimum logging level as a ``logging`` int."""
        return self.lvl

    @property
    def verbose(self) -> bool:
        """True when DEBUG and above are recorded."""
        return self.lvl <= logging.DEBUG

    def _console_formatter(self, use_timestamp: bool) -> logging.Formatter:
        """Console formatter; with colors on, the level field is colored."""
        fmt = "%(asctime)s [%(levelname)s] %(message)s" if use_timestamp else "[%(levelname)s] %(message)s"
        formatter_cls = self._ColoredLevelFormatter if self.has_colors else logging.Formatter
        return formatter_cls(fmt, datefmt=DATE_FMT if use_timestamp else None)

    def _attach_console_handler(self, use_timestamp: bool) -> None:
        """Attach exactly one console handler to the wrapped logger.

        In notebook mode a single shared handler serves all loggers.  In
        normal mode exactly one ``StreamHandler`` per logger name is kept; it
        is recreated whenever it binds to a stream different from the current
        console stream (e.g. pytest swaps ``sys.stdout`` between tests), so
        stale handlers on discarded capture buffers never accumulate.
        """
        stream = _console_stream()

        def make_handler() -> logging.StreamHandler[TextIO]:
            formatter = self._console_formatter(use_timestamp)
            handler: logging.StreamHandler[TextIO] = logging.StreamHandler(stream)
            handler.setLevel(self.lvl)
            handler.setFormatter(formatter)
            return handler

        if _is_interactive_notebook():
            if Logger._shared_console_handler is None:
                Logger._shared_console_handler = make_handler()
            self.logger.addHandler(Logger._shared_console_handler)
            return

        bound_to_current = [
            h for h in self.logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is stream
        ]
        for handler in list(self.logger.handlers):
            if isinstance(handler, logging.StreamHandler) and handler.stream is not stream:
                self.logger.removeHandler(handler)
        if not bound_to_current:
            self.logger.addHandler(make_handler())

    # ------------------------------------------------------------- file setup

    def configure(self, directory: str) -> None:
        """Move the log file into ``directory`` and (re)attach the file handler.

        The base file name (from ``logfile``/``append_ts`` or the timestamp)
        is preserved.  When the directory differs from the current one, any
        existing file handler is closed and re-created at the new path.
        """
        directory    = directory or DEFAULT_LOG_DIRECTORY
        new_path     = os.path.join(directory, f"{self._logfile_base}.log")
        moved        = new_path != self.logfile
        self.logfile = new_path
        self.working = False
        os.makedirs(directory, exist_ok=True)

        if moved:
            for handler in list(self.logger.handlers):
                if isinstance(handler, logging.FileHandler):
                    try:
                        handler.flush()
                        handler.close()
                    finally:
                        self.logger.removeHandler(handler)
            self.handler_added = False

        _write_header(self.logfile, self.LEVELS.get(self.lvl, "info"))

        if not self.handler_added:
            fh = logging.FileHandler(self.logfile, encoding="utf-8")
            fh.setLevel(self.lvl)
            fh.setFormatter(StripAnsiFormatter("%(asctime)s [%(levelname)s] %(message)s", datefmt=DATE_FMT))
            self.logger.addHandler(fh)
            self.handler_added = True
            self._log_message(logging.INFO, f"Log file created: {self.logfile}")
            self._log_message(logging.INFO, f"Log level set to: {self.LEVELS.get(self.lvl, 'info')}")
        self.working = True

    # ------------------------------------------------------------- formatting

    @staticmethod
    def colorize(txt: object, color: str | None) -> str:
        """Wrap ``txt`` in the ANSI code for ``color`` (see :func:`colorize`)."""
        return colorize(txt, color)

    @staticmethod
    def print(msg: str, lvl: int = 0) -> str:
        """Prefix ``msg`` with the indentation for ``lvl``."""
        return print_tab(lvl) + str(msg)

    # ``print_tab`` is exposed as both a module function and a static method.
    print_tab = staticmethod(print_tab)

    # ------------------------------------------------------------- emit

    def _log_message(self, log_level: int, msg: str, lvl: int = 0) -> None:
        """Route ``msg`` to the wrapped logger at ``log_level`` with indentation."""
        method = getattr(self.logger, self.LEVELS.get(log_level, "info"))
        method(self.print(msg, lvl))

    def say(
        self,
        *args: object,
        end: bool = True,
        log: int | str | None = logging.INFO,
        lvl: int = 0,
        verbose: bool = True,
        color: str | None = None,
    ) -> None:
        """Log multiple messages joined into one record if verbosity is enabled.

        Args:
            *args: Messages to log; each is ``str()``-coerced.
            end: Join messages with newlines (True) or spaces (False).
            log: Log level: ``logging`` int, name/letter shorthand, or None
                (INFO).
            lvl: Indentation level.
            verbose: Whether to log at all (default True).
            color: Optional color name applied when console colors are on.
        """
        level = coerce_level(log)
        if not verbose or level < self.lvl:
            return
        messages = [str(arg) for arg in args]
        combined = "\n".join(messages) if end else " ".join(messages)
        if color is not None and self.has_colors:
            combined = self.colorize(combined, color)
        self._log_message(level, combined, lvl)

    def info(self, msg: object, lvl: int = 0, verbose: bool = True, color: str | None = None) -> None:
        """Log an informational message if verbosity is enabled."""
        if not verbose:
            return
        if color is not None and self.has_colors:
            msg = self.colorize(msg, color)
        self.logger.info(self.print(str(msg), lvl))

    def debug(self, msg: object, lvl: int = 0, verbose: bool = True, color: str | None = None) -> None:
        """Log a debug message if verbosity is enabled."""
        if not verbose:
            return
        if color is not None and self.has_colors:
            msg = self.colorize(msg, color)
        self.logger.debug(self.print(str(msg), lvl))

    def warning(self, msg: object, lvl: int = 0, verbose: bool = True, color: str = "yellow") -> None:
        """Log a warning message if verbosity is enabled."""
        if not verbose:
            return
        if self.has_colors:
            msg = self.colorize(msg, color)
        self.logger.warning(self.print(str(msg), lvl))

    def error(self, msg: object, lvl: int = 0, verbose: bool = True, color: str = "red") -> None:
        """Log an error message if verbosity is enabled."""
        if not verbose:
            return
        if self.has_colors:
            msg = self.colorize(msg, color)
        self.logger.error(self.print(str(msg), lvl))

    def exception(self, msg: object = "", lvl: int = 0, **kwargs: Any) -> None:
        """Log an error with the current exception traceback.

        Call inside an ``except`` block; outside one it behaves like
        :meth:`error`.  The traceback is passed via ``exc_info=True`` so the
        file handler records it too.
        """
        try:
            self.logger.error(self.print(str(msg), lvl), exc_info=True, **kwargs)
        except Exception:
            traceback.print_exc()

    # ------------------------------------------------------------- utilities

    @staticmethod
    def breakline(n: int) -> None:
        """Print ``n`` blank lines to stdout."""
        for _ in range(n):
            print()

    def title(
        self,
        tail: str,
        desired_size: int = 50,
        fill: str = "=",
        lvl: int = 0,
        verbose: bool = True,
        color: str | None = None,
    ) -> None:
        """Log a title centered with ``fill`` characters.

        Args:
            tail: Text centered within the title.
            desired_size: Target total width of the title.
            fill: Filler character(s) repeated either side of ``tail``.
            lvl: Indentation level.
            verbose: Whether to log (default True).
            color: Optional color name applied when console colors are on.
        """
        if not verbose:
            return
        tail_length = len(tail)
        lvl_len     = 2 + lvl * 3 * 2
        if tail_length + lvl_len > desired_size:
            self.info(tail, lvl, verbose)
            return
        fill_len  = max(1, len(fill))
        fill_size = (desired_size - tail_length) // (2 * fill_len)
        out       = (fill * fill_size) + tail + (fill * fill_size)
        if len(out) < desired_size:
            out += fill[0] * max(0, desired_size - len(out) - 1)
        elif len(out) > desired_size:
            out = out[:desired_size]
        self.info(out, lvl, verbose, color)

    def timing(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorate ``func`` to log its execution time at debug level.

        Emits ``Starting 'name'...`` before the call and
        ``Finished 'name' in X seconds.`` after it.  Use as ``@logger.timing``.
        """
        name = getattr(func, "__name__", type(func).__name__)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            self.debug(f"Starting '{name}'...")
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                self.debug(f"Finished '{name}' in {elapsed:.4f} seconds.")

        return wrapper

    # ------------------------------------------------------------- lifecycle

    def close(self) -> None:
        """Flush, close, and detach every handler attached to this logger."""
        for handler in list(self.logger.handlers):
            try:
                handler.flush()
                handler.close()
            finally:
                self.logger.removeHandler(handler)

    def __enter__(self) -> Logger:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
        self.close()
        return False


# ---------------------------------------------------------------------------
# Argument table
# ---------------------------------------------------------------------------

def print_arguments(
    parser: Any,
    logger: Any | None = None,
    title: str = "Options for the script",
    columnsize: int = 30,
) -> None:
    """Print ``parser``'s options in a formatted table.

    Args:
        parser: An ``argparse.ArgumentParser`` (or anything with ``_actions``).
        logger: Optional ``Logger``; when None the table is printed to stdout.
        title: Title displayed above the options table.
        columnsize: Width of the "Option" column.
    """
    default_size      = 15
    description_size  = 70
    border            = f"|{'-' * (columnsize + 2)}|{'-' * (default_size + 2)}|{'-' * (description_size + 2)}|"
    header            = (
        f"| {'Option':<{columnsize}} | {'Default':<{default_size}} "
        f"| {'Description':<{description_size}} |"
    )
    rows = [
        f"| {a.dest:<{columnsize}} | {str(a.default):<{default_size}} |"
        f" {str(a.help):<{description_size}} |"
        for a in parser._actions
    ]

    if logger is None:
        print("\n")
        print(f"Title: {title}")
        for line in [border, header, border, *rows, border]:
            print(line)
    else:
        logger.breakline(1)
        logger.title(title, 50, "#", 0)
        for line in [border, header, border, *rows, border]:
            logger.info(line, lvl=0)
        logger.breakline(1)


# ---------------------------------------------------------------------------
# Timing summary
# ---------------------------------------------------------------------------

def _isclose(a: float, b: float, rtol: float = 1e-3, atol: float = 1e-4) -> bool:
    """Sameness check within relative/absolute tolerance (no numpy)."""
    return abs(a - b) <= max(rtol * max(abs(a), abs(b)), atol)


def log_timing_summary(
    logger: Logger,
    phase_durations: dict[str, float] | None = None,
    total_duration: float | None = None,
    title: str = "Timing Summary",
    phase_col_width: int = 18,
    duration_col_width: int = 14,
    duration_precision: int = 4,
    lvl: int = 0,
    add_total_row: bool = True,
    extra_info: Iterable[str] | None = None,
) -> None:
    """Log a timing summary in a tabular format using ``logger``.

    Args:
        logger: Logger instance used to emit the table.
        phase_durations: Mapping of phase name (str) to duration (float).
        total_duration: Overall duration (optional).  With ``add_total_row``, a
            "Total" row is appended; if the value differs from the phase sum
            beyond tolerance, a warning is logged.
        title: Title displayed above the table.
        phase_col_width: Width of the "Phase" column.
        duration_col_width: Width of the "Duration (s)" column.
        duration_precision: Decimal places for durations.
        lvl: Base indentation level.
        add_total_row: Include a Total row (the computed sum when
            ``total_duration`` is None).
        extra_info: Optional extra lines logged below the table; lines
            mentioning "samples/sec" or "performance" are moved after the
            table.
    """
    if logger is None:
        print("Error: Logger instance is required for log_timing_summary.")
        return

    phase_durations = phase_durations or {}

    phase_header       = "Phase"
    duration_header    = "Duration (s)"
    phase_col_width    = max(phase_col_width, len(phase_header))
    duration_col_width = max(duration_col_width, len(duration_header))

    separator = f"|{'-' * (phase_col_width + 2)}|{'-' * (duration_col_width + 2)}|"
    header_fmt = f"| {phase_header:<{phase_col_width}} | {duration_header:>{duration_col_width}} |"
    row_fmt = (
        f"| {{phase_name:<{phase_col_width}}} "
        f"| {{duration:>{duration_col_width}.{duration_precision}f}} |"
    )
    empty_row_fmt = f"| {{msg:<{phase_col_width + duration_col_width + 3}}} |"

    logger.title(f"{title}", 50, "#", lvl)

    # Split extra info: performance lines are held for below the table.
    perf_string = None
    filtered    = []
    for info in extra_info or ():
        lowered = info.lower()
        if "samples/sec" in lowered or "performance" in lowered:
            perf_string = info
        else:
            filtered.append(info)
    for info in filtered:
        logger.info(info, lvl=lvl + 1)

    # Table header, then phase durations, then the total row.
    logger.info(separator, lvl=lvl + 1)
    logger.info(header_fmt, lvl=lvl + 1)
    logger.info(separator, lvl=lvl + 1)

    calculated_sum = 0.0
    if phase_durations:
        for name, duration in phase_durations.items():
            logger.info(row_fmt.format(phase_name=name, duration=duration), lvl=lvl + 1)
            calculated_sum += duration
    else:
        logger.info(empty_row_fmt.format(msg="No phases timed"), lvl=lvl + 1)

    if add_total_row:
        logger.info(separator, lvl=lvl + 1)
        if total_duration is not None and not _isclose(total_duration, calculated_sum):
            logger.warning(
                f"Provided total duration ({total_duration:.4f}s) differs from sum of "
                f"phases ({calculated_sum:.4f}s). Using provided total.",
                lvl=lvl + 2,
            )
        actual_total = total_duration if total_duration is not None else calculated_sum
        if actual_total is not None:
            logger.info(row_fmt.format(phase_name="Total", duration=actual_total), lvl=lvl + 1)
        else:
            logger.info(empty_row_fmt.format(msg="Total duration not available"), lvl=lvl + 1)

    logger.info(separator, lvl=lvl + 1)
    if perf_string:
        logger.info(perf_string, lvl=lvl + 1)


# ---------------------------------------------------------------------------
# Global logger singleton
# ---------------------------------------------------------------------------

_G_LOGGER: Logger | None = None
_G_LOGGER_PID: int | None = None
_G_LOCK = threading.Lock()


def get_global_logger(**kwargs: Any) -> Logger:
    """Return one ``Logger`` per process (PID), safe across threads and forks.

    The first call in a process constructs the logger; later calls return the
    cached instance.  The initialization banner is emitted at most once per
    program, guarded by an inherited environment sentinel so forked workers do
    not repeat it.

    Args:
        **kwargs: Forwarded to :class:`Logger`; supports ``name``, ``lvl``,
            ``append_ts``, ``use_ts_in_cmd``, ``logfile``.

    Returns:
        Logger: The process-wide logger instance.
    """
    global _G_LOGGER, _G_LOGGER_PID
    pid = os.getpid()

    if _G_LOGGER is not None and _G_LOGGER_PID == pid:
        return _G_LOGGER

    with _G_LOCK:
        if _G_LOGGER is not None and _G_LOGGER_PID == pid:
            return _G_LOGGER

        logger = Logger(
            name=kwargs.get("name", "Global"),
            lvl=kwargs.get("lvl"),
            append_ts=kwargs.get("append_ts", True),
            use_ts_in_cmd=kwargs.get("use_ts_in_cmd", True),
            logfile=kwargs.get("logfile"),
        )

        # Banner once per program; the sentinel survives fork() so workers
        # (which inherit it) stay quiet.
        if os.environ.get("GEN_PYTHON_LOGGER_INIT_DONE", "0") != "1":
            os.environ["GEN_PYTHON_LOGGER_INIT_DONE"] = "1"
            if os.environ.get("PY_BACKEND_INFO", "0") != "0":
                logger.title("Global Logger initialized!", 50, "#", 0)

        _G_LOGGER     = logger
        _G_LOGGER_PID = pid
        return _G_LOGGER


def get_logger(**kwargs: Any) -> Logger:
    """Create a new ``Logger`` instance (no caching).

    Args:
        **kwargs: Forwarded to :class:`Logger`; supports ``name``, ``lvl``,
            ``append_ts``, ``use_ts_in_cmd``, ``logfile``.

    Returns:
        Logger: A new Logger instance.
    """
    return Logger(
        name=kwargs.get("name", "Global"),
        lvl=kwargs.get("lvl"),
        append_ts=kwargs.get("append_ts", True),
        use_ts_in_cmd=kwargs.get("use_ts_in_cmd", True),
        logfile=kwargs.get("logfile"),
    )
