"""Progress bars retain console messages, file output, and notebook backend selection."""

from io import StringIO
from types import SimpleNamespace
import sys

import pytest

from general_log import Logger


def test_progress_logs_preserve_the_bar_and_file_output(tmp_path, monkeypatch):
    """Logs pass through tqdm once; the real bar closes and file output retains indentation."""
    tqdm = pytest.importorskip("tqdm").tqdm
    stream = StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    logger = Logger(name="progress-file", logfile=str(tmp_path / "run.log"), use_ts_in_cmd=False)
    writes = []
    original = tqdm.write

    def write(message, **kwargs):
        writes.append(message)
        return original(message, **kwargs)

    monkeypatch.setattr(tqdm, "write", write)
    with logger.progress(range(2), backend="terminal", desc="Training", file=stream, mininterval=0) as bar:
        for step in bar:
            bar.set_postfix(loss=1.0 / (step + 1))
            logger.info([f"step {step}", "saved"], column_width=(8, 6), lvl=1)
    logger.close()
    assert bar.n == 2 and bar.disable
    assert len(writes) == 2 and all("\t->step" in message for message in writes)
    assert "Training" in stream.getvalue() and "loss=" in stream.getvalue()
    saved = (tmp_path / "run.log").read_text()
    assert saved.count("\t->step 0") == 1 and saved.count("\t->step 1") == 1
    assert "\t->step 0   saved \n" in saved
    assert "Training" not in saved


@pytest.mark.parametrize("backend, module", [("auto", "tqdm.auto"), ("notebook", "tqdm.notebook")])
def test_progress_selects_the_requested_backend(monkeypatch, backend, module):
    """Backend selection forwards native nesting and display options without requiring a kernel."""
    calls    = []
    sentinel = object()

    def factory(iterable, **kwargs):
        calls.append((iterable, kwargs))
        return sentinel

    monkeypatch.setitem(sys.modules, module, SimpleNamespace(tqdm=factory))
    logger = Logger(name=f"progress-{backend}")
    items = range(3)
    assert logger.progress(items, backend=backend, position=1, leave=False) is sentinel
    assert calls == [(items, {"position": 1, "leave": False})]
    logger.close()


def test_notebook_widget_supports_updates_and_logging(capsys):
    """A real widget bar accepts manual updates and postfixes while logs remain visible."""
    pytest.importorskip("ipywidgets")
    pytest.importorskip("tqdm.notebook")
    logger = Logger(name="progress-widget", use_ts_in_cmd=False)
    with logger.progress(total=2, backend="notebook", display=False, mininterval=0) as bar:
        bar.set_postfix(energy=-1.0)
        bar.update(1)
        logger.info("saved checkpoint", lvl=1)
        bar.update(1)
    assert bar.n == 2
    assert bar.container.children[1].value == 2
    assert "\t->saved checkpoint" in capsys.readouterr().out
    logger.close()
