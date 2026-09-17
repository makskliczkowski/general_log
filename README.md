# general_log

A colored, verbosity-aware console and file logging library for Python. It wraps the standard `logging` module behind a compact API with indentation, colors, optional file output, and a few table and timing helpers. Zero required dependencies, Python 3.10+, and usable both as a pip package and as a vendored git submodule.

## Install

```bash
pip install -e .
```

To keep it inside one of your repositories as a submodule:

```bash
git submodule add https://github.com/your-org/general_log vendor/general_log
```

## Quick start

`get_global_logger()` returns a process-wide singleton. The first call builds the logger; later calls return the same instance, so you can create it once and share it across modules.

```python
from general_log import get_global_logger

logger = get_global_logger()
logger.info("Hello, world!")
```

Console output includes a timestamp by default and a colored level name:

```
17_09_2026_17-19-34 [INFO] Hello, world!
```

Pass `use_ts_in_cmd=False` to drop the timestamp. To create a standalone instance instead, use `Logger` directly:

```python
from general_log import Logger

logger = Logger(name="app")
```

## Levels and verbosity

A logger has a severity level. Debug output is invisible unless requested; the default level is INFO.

```python
logger.debug("Entering the loop")
logger.info("Started training")
logger.warning("GPU memory is low")
logger.error("Model file not found")
```

Set the level at construction, at runtime, or from the environment:

```python
logger = get_global_logger(lvl="debug")     # logging int, name, or letter
logger.set_level("debug")                   # runtime change
logger.level                                # current level as an int
logger.verbose                              # True when DEBUG+ is recorded
```

`PYLOGLEVEL=warning python train.py` silences everything below warning without touching the code.

## Conveniences

`say` logs several messages in one call. They become separate lines, or are joined with spaces when `end=False`:

```python
logger.say("Loading data", "Preprocessing")
logger.say("Dev", "Test", end=False)
```

`title` centers text with a filler character:

```python
logger.title("Training", desired_size=50, fill="=")
```

```
[INFO] =====================Training=====================
```

`timing` logs a function's execution time as debug messages:

```python
@logger.timing
def train():
    ...
```

It emits `Starting 'train'...` before the call and `Finished 'train' in 3.2 seconds.` after.

## Indentation

Logging methods accept an `lvl` argument that indents the line:

```python
logger.info("Outer step")
logger.info("Inner detail", lvl=1)
logger.info("Deeper still", lvl=2)
```

```
[INFO] Outer step
[INFO] 	->Inner detail
[INFO] 		->Deeper still
```

The arrow deepens with each nesting level, so the structure of a run stays visible at a glance.

## File output

Pass a `logfile` name and the logger writes to disk in addition to the console. The file lands in `./log/` by default:

```python
logger = Logger(name="app", logfile="run")          # ./log/run.log
logger = Logger(name="app", logfile="run", append_ts=True)  # ./log/run_17_09_2026_17-19-34.log
```

The file starts with a header recording the creation time, user, machine, and Python version. ANSI codes are stripped from file output. `configure(directory)` relocates the file at runtime; `close()` flushes and detaches the handlers.

## Colors

The level field is colored per level: debug cyan, info green, warning yellow, error red, critical magenta. Message text can be colored per call:

```python
logger.info("hello", color="cyan")
logger.warning("careful")            # yellow by default
logger.error("boom")                 # red by default
```

Colors auto-enable only on a TTY. `NO_COLOR` disables them; `PYLOGCOLORS=1` and `PYLOGCOLORS=0` force the decision on or off and take precedence over both. On Windows, ANSI processing uses `colorama` when installed (`pip install general-log[color]`); otherwise colors stay off.

## Helpers

A few module-level helpers cover common patterns:

```python
printV("detail", v=verbose)                          # print gated on a flag
printJust(sys.stdout, elements=[1.0, 2.5], width=10) # fixed-width columns
printDictionary({"lr": 1e-3, "epochs": 10})          # "lr: 1e-3, epochs: 10"
```

`print_arguments` renders an `argparse` parser's options as a table, optionally through a logger. `log_timing_summary` logs a phase-duration table with a Total row, and warns when a provided total disagrees with the phase sum:

```python
log_timing_summary(logger, {"compile": 1.2, "train": 9.8}, total_duration=11.2)
```

## Environment variables

| Variable | Effect |
| --- | --- |
| `PYLOGCOLORS=1` | Force console colors on, even for non-TTY output. |
| `PYLOGCOLORS=0` | Force console colors off. |
| `NO_COLOR` | Disable console colors (https://no-color.org). |
| `PYLOGFILE=<path>` | Default log file when no `logfile` is passed. |
| `PYLOGLEVEL=<level>` | Default level when `lvl` is not passed. |

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
