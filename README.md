# general_log

Colored, verbosity-aware console and file logging helpers for Python projects.

`general_log` wraps the standard `logging` module behind a compact API with
indentation, per-level colors, optional file output, and a few print/table
helpers. It is designed both as a git submodule/subtree for embedded use and as
a pip-installable package.

## Features

- `Logger` class with `info` / `debug` / `warning` / `error` / `say`, indentation
  (`lvl`), colored output (auto on TTY), `title`, and `timing` decorator.
- Runtime level control: `set_level()`, `.level`, `.verbose`.
- Process-wide `get_global_logger()` singleton, fork- and thread-safe.
- Optional file logging with a session header; ANSI codes stripped from file
  output.
- Notebook/IPython detection; a shared console handler prevents duplicate output.
- Env-configurable defaults: `PYLOGCOLORS`, `PYLOGFILE`, `PYLOGLEVEL`; honors the
  standard `NO_COLOR`.
- Module helpers: `printV`, `printJust`, `printDictionary`, `print_arguments`,
  `log_timing_summary`.
- Zero required dependencies. Python 3.10+. PEP 561 typed (`py.typed`).

## Install

```bash
pip install -e .            # editable, local
pip install git+https://github.com/your-org/general_log   # from git
```

Or embed as a submodule/subtree and import from the vendored path:

```bash
git submodule add https://github.com/your-org/general_log vendor/general_log
```

## Quick start

```python
from general_log import get_global_logger

logger = get_global_logger()
logger.info("Hello, world!")
logger.warning("Careful.")
logger.error("Boom.")
logger.say("Line one", "Line two", log="info", lvl=1)
logger.title("Section title", desired_size=60, fill="=")
```

With file output:

```python
from general_log import Logger

logger = Logger(name="app", logfile="run", append_ts=True)
logger.info("Hello from a file.")
```

The log file is written to `./log/run_<timestamp>.log` (with `append_ts=True`)
or `./log/run.log` (without).  `get_logger` and `get_global_logger` default to
`append_ts=True`.

## Environment variables

| Variable | Effect |
| --- | --- |
| `PYLOGCOLORS=1` | Force console colors on (even for non-TTY output). |
| `PYLOGCOLORS=0` | Disable console colors. |
| `NO_COLOR` (any value) | Disable console colors (https://no-color.org). |
| `PYLOGFILE=<path>` | Default log file used when no `logfile` is passed. |
| `PYLOGLEVEL=<level>` | Default level used when `lvl` is not passed (`warning`, etc.). |

Without `PYLOGCOLORS`, `NO_COLOR` disables colors (https://no-color.org) and
color auto-enables only on a TTY.  `PYLOGCOLORS` always wins: `=0` forces
off, `=1` forces on regardless of TTY or `NO_COLOR`.  On Windows, ANSI
processing is enabled through `colorama` when installed
(`pip install general-log[color]`); without it colors stay off.

## Colors

The level field of each console line is colored per level (debug cyan, info
green, warning yellow, error red, critical magenta).  Message colors are
applied per call:

```python
logger.info("plain")                       # green level, plain message
logger.info("hello", color="cyan")         # cyan message
logger.warning("careful")                  # yellow by default
logger.error("boom")                       # red by default
```

File output always strips ANSI codes, regardless of console colors.

## Runtime level control

```python
logger.set_level("debug")     # name, letter, or logging int
logger.level                  # current level as an int
logger.verbose                # True when DEBUG+ is recorded
```

`set_level` reconfigures the wrapped logger and every attached handler
immediately.

## Logging levels

Levels accept `logging` ints, names, or first-letter shorthands:

```python
logger.say("msg", log="warning")     # WARNING
logger.say("msg", log="w")           # WARNING
logger.say("msg", log=logging.INFO)  # INFO
```

The wrapped `logging` logger is available as `logger.logger`, so the full
`logging` API (filters, custom handlers, `logger.exception`) remains usable on
the same name.

## Timing

```python
@logger.timing
def train():
    ...
```

`logger.timing` logs a debug message before and after the call with the elapsed
time.

`log_timing_summary` renders a phase map as a table:

```python
log_timing_summary(logger, {"compile": 1.2, "train": 9.8}, total_duration=11.2)
```

## Import paths

Both entry points expose the same objects:

```python
from general_log import Logger          # canonical
from general_log.log import Logger      # direct module path
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy general_log
```

## License

MIT. See [LICENSE](LICENSE).
