"""Tests for runtime memory and Slurm monitoring helpers."""

from __future__ import annotations

import subprocess
import time

from general_log import Logger, SlurmMonitor, memory_usage_gb, peak_memory_gb
from general_log.runtime import _parse_slurm_time


def test_memory_helpers_return_positive_gb():
    mem = memory_usage_gb()
    peak = peak_memory_gb()
    assert mem is None or mem > 0.0
    assert peak is None or peak > 0.0


def test_parse_slurm_time_formats():
    assert _parse_slurm_time("1-02:03:04") == 86400 + 2 * 3600 + 3 * 60 + 4
    assert _parse_slurm_time("2-05:30") == 2 * 86400 + 5 * 3600 + 30 * 60
    assert _parse_slurm_time("01:02:03") == 3600 + 2 * 60 + 3
    assert _parse_slurm_time("05:10") == 5 * 60 + 10
    assert _parse_slurm_time("UNLIMITED") == -1


def test_slurm_monitor_env_and_overtime(monkeypatch):
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    assert not SlurmMonitor.is_slurm()
    assert SlurmMonitor.get_slurm_memory() is None
    assert SlurmMonitor.get_remaining_time() == -1

    monkeypatch.setenv("SLURM_JOB_ID", "12345")
    monkeypatch.setenv("SLURM_MEM_PER_NODE", "4096")
    assert SlurmMonitor.is_slurm()
    assert SlurmMonitor.get_slurm_memory() == 4.0

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="JobId=12345 TimeLimit=01:00:00 RunTime=00:50:00\n", stderr=""
        ),
    )
    assert SlurmMonitor.get_remaining_time() == 600
    assert SlurmMonitor.is_overtime(limit=700)
    assert not SlurmMonitor.is_overtime(limit=500)

    # Local stopwatch scope
    triggered = []
    with Logger(name="test_runtime", console=False) as logger:
        with SlurmMonitor.is_overtime_scope(
            limit=10.0,
            start_time=time.perf_counter() - 5.0,
            job_time=8.0,
            on_trigger=lambda: triggered.append(True),
            logger=logger,
        ) as should_stop:
            assert should_stop() is True
    assert triggered == [True, True]
