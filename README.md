# General Log

A colored, verbosity-aware console and file logging library for Python. It wraps the standard `logging` module behind a compact API with indentation, colors, optional file output, and a few table and timing helpers. Zero required dependencies, optional tqdm progress bars and notebook widgets, Python 3.10+, and usable both as a pip package and as a vendored git submodule.

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

## Column widths

Message methods accept optional `column_width` and `align` arguments. Pass a list or tuple of values as the message. An integer gives every column the same minimum width; a sequence gives one width per column. Adjacent columns have one separating space.

```python
logger.info(["arm", "energy", "variance"], column_width=(20, 14, 12))
logger.info(["rbm/iite", "-1.234567", "2.30e-06"], column_width=(20, 14, 12), align=("left", "right", "right"), lvl=1)
logger.warning(["status", "stalled"], column_width=16)
logger.say("rbm", "saved", column_width=(20, 12))
```

`align` accepts `"left"` (default), `"right"`, or `"center"`, either shared or per column. Widths are non-negative minimum character counts. ANSI color codes do not count toward the width. Long values are retained without truncation. Numeric formatting remains explicit, for example `f"{energy:.6f}"`.

The options work with `info`, `debug`, `warning`, `error`, `exception`, `say`, and `title`. A scalar message becomes one column. With widths specified, `say` formats its arguments as one row and ignores `end`; `title` pads its generated title as one column. Column layout is preserved in console output and log files, including when tqdm bars are active. Without `column_width`, existing message formatting is unchanged.

## Progress bars

`logger.progress(...)` returns a native `tqdm` bar. The default `backend="auto"` selects notebook widgets when available and a terminal bar otherwise. Install `general-log[progress]` for tqdm or `general-log[notebook]` for tqdm and ipywidgets.

```python
with logger.progress(range(100), desc="Training", unit="step") as steps:
    for step in steps:
        loss = train_step(step)
        steps.set_postfix(loss=f"{loss:.3e}")
        if step % 20 == 0:
            logger.info(f"Checkpoint at step {step}", lvl=1)
```

Console messages use `tqdm.write` while tqdm is loaded, preserving active bars. Indentation, severity, colors, and file logging still apply. Progress refreshes are not written to the log file.

Use `backend="notebook"` to request widgets explicitly, or `backend="terminal"` to request text output. Keyword arguments such as `total`, `position`, `leave`, and `disable` pass directly to tqdm. For manual updates, call `logger.progress(total=100)` and use its `update()` method inside a context manager. Nested bars use tqdm's usual position handling.

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
