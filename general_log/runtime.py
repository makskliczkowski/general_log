r"""
Runtime memory and Slurm job monitoring helpers.

Zero-dependency utilities for reading process resident memory (RSS and peak RSS) and inspecting Slurm job memory
limits and remaining wall time.

-----------------------------------------------
Author            : Maks Kliczkowski
File              : runtime.py
-----------------------------------------------
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib    import Path
from typing     import TYPE_CHECKING, Any, Callable, Iterator

try:
    import resource as _resource
except ImportError:                                                 # pragma: no cover - non-POSIX
    _resource = None                                                # type: ignore[assignment]

# -------------------------------------------

if TYPE_CHECKING:
    from .log   import Logger

# -------------------------------------------

_BYTES_PER_GIB  = float(1024**3)
_TIME_FIELD_RE  = re.compile(r"(?:^|\s)(TimeLimit|RunTime)=([^\s]+)")

# -------------------------------------------


def memory_usage_gb() -> float | None:
    r"""
    Current process resident memory (RSS) in GiB.

    Uses ``psutil`` when installed, then ``/proc/self/status`` (``VmRSS``), and falls back to ``peak_memory_gb``.

    Returns
    -------
    float or None
        Resident memory in GiB, or ``None`` when unavailable.
    """
    try:
        import psutil                                               # type: ignore[import-not-found]

        return float(psutil.Process().memory_info().rss) / _BYTES_PER_GIB
    except Exception:
        pass

    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text().splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return float(int(parts[1]) * 1024) / _BYTES_PER_GIB
    return peak_memory_gb()


def peak_memory_gb() -> float | None:
    r"""
    Peak process resident memory (high-water mark) in GiB.

    Returns
    -------
    float or None
        Peak RSS in GiB from ``resource.getrusage``, or ``None`` when unavailable.
    """
    if _resource is None:
        return None
    rss = float(_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss)
    if rss <= 0.0:
        return None
    # macOS reports bytes; Linux and BSD report KiB.
    divisor = _BYTES_PER_GIB if sys.platform == "darwin" else float(1024**2)
    return rss / divisor


def _parse_slurm_time(time_str: str) -> int:
    r"""Parse Slurm duration strings (``DD-HH:MM:SS``, ``DD-HH:MM``, ``HH:MM:SS``, ``MM:SS``) to seconds."""
    text = time_str.strip()
    if not text or text in ("UNLIMITED", "NOT_SET", "N/A"):
        return -1
    days = 0
    if "-" in text:
        day_part, text = text.split("-", 1)
        if not day_part.isdigit():
            return 0
        days = int(day_part)
    parts = text.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        hours, minutes, seconds = nums
    elif len(nums) == 2:
        hours, minutes, seconds = (0, nums[0], nums[1]) if days == 0 else (nums[0], nums[1], 0)
    else:
        return 0
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


# -------------------------------------------


class SlurmMonitor:
    r"""Slurm job and process memory monitoring utilities."""

    @staticmethod
    def is_slurm() -> bool:
        r"""True when running inside a Slurm allocation."""
        return os.getenv("SLURM_JOB_ID") is not None

    @staticmethod
    def get_memory_used(logger: Logger | None = None, *, lvl: int = 3) -> float | None:
        r"""
        Current RSS in GiB, logged when ``logger`` is given.

        Parameters
        ----------
        logger : Logger, optional
            Logger that receives the memory line.
        lvl : int, default 3
            Indentation level passed to ``logger``.

        Returns
        -------
        float or None
            Resident memory in GiB, or ``None`` when unavailable.
        """
        mem_gb = memory_usage_gb()
        if logger is not None:
            if mem_gb is not None:
                logger.info(f"Memory: {mem_gb:.2f} GB", lvl=lvl)
            else:
                logger.warning("Failed to get memory info", lvl=lvl)
        return mem_gb

    @staticmethod
    def get_slurm_memory(logger: Logger | None = None, *, lvl: int = 3) -> float | None:
        r"""
        Slurm memory limit in GiB from ``SLURM_MEM_PER_NODE`` or ``SLURM_MEM_PER_CPU``.

        Parameters
        ----------
        logger : Logger, optional
            Logger that receives the memory limit or parse warning.
        lvl : int, default 3
            Indentation level passed to ``logger``.

        Returns
        -------
        float or None
            Memory limit in GiB, or ``None`` outside Slurm or when unset.
        """
        if not SlurmMonitor.is_slurm():
            return None
        mem_limit_str = os.getenv("SLURM_MEM_PER_NODE") or os.getenv("SLURM_MEM_PER_CPU")
        if not mem_limit_str:
            return None
        try:
            mem_limit_gb = int(mem_limit_str) / 1024.0
        except ValueError as exc:
            if logger is not None:
                logger.warning(f"Failed to parse SLURM memory limit {mem_limit_str!r}: {exc}", lvl=lvl)
            return None
        if logger is not None:
            logger.info(f"SLURM memory limit: {mem_limit_gb:.2f} GB", lvl=lvl)
        return mem_limit_gb

    @staticmethod
    def get_remaining_time(logger: Logger | None = None) -> int:
        r"""
        Remaining Slurm wall time in seconds, or ``-1`` when unavailable.

        Parameters
        ----------
        logger : Logger, optional
            Logger that receives the remaining time or failure warning.

        Returns
        -------
        int
            Remaining seconds, or ``-1`` outside Slurm or on ``scontrol`` failure.
        """
        job_id = os.getenv("SLURM_JOB_ID")
        if not job_id:
            return -1
        try:
            result = subprocess.run(
                ["scontrol", "show", "job", job_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return -1
            fields = dict(_TIME_FIELD_RE.findall(result.stdout))
            if "TimeLimit" not in fields or "RunTime" not in fields:
                return -1
            total_limit = _parse_slurm_time(fields["TimeLimit"])
            total_run   = _parse_slurm_time(fields["RunTime"])
            if total_limit <= 0 or total_run < 0:
                return -1
            remaining   = max(0, total_limit - total_run)
            if logger is not None:
                logger.info(f"SLURM remaining time: {remaining} s", lvl=3)
            return remaining
        except Exception as exc:
            if logger is not None:
                logger.warning(f"Failed to get SLURM time info: {exc}")
            return -1

    @staticmethod
    def get_remaining_and_current_time(default: int = 60 * 60 * 24 * 4) -> tuple[int, float]:
        r"""
        Remaining Slurm wall time in seconds and ``time.perf_counter()``.

        Parameters
        ----------
        default : int, default 345600
            Fallback remaining time in seconds outside Slurm.

        Returns
        -------
        tuple of (int, float)
            ``(remaining_seconds, perf_counter)``.
        """
        remaining = SlurmMonitor.get_remaining_time() if SlurmMonitor.is_slurm() else -1
        return (remaining if remaining != -1 else default), time.perf_counter()

    @staticmethod
    def is_overtime(
        limit       : float         = 1000.0,
        start_time  : float | None  = None,
        job_time    : float | None  = None,
        logger      : Logger | None = None,
        verbose     : bool          = False,
        **kwargs    : Any,
    ) -> bool:
        r"""
        True when remaining wall time is below ``limit`` seconds.

        Uses ``start_time`` and ``job_time`` when both are given; otherwise queries Slurm.
        """
        if not SlurmMonitor.is_slurm() and (start_time is None or job_time is None):
            return False
        if start_time is not None and job_time is not None:
            elapsed     = time.perf_counter() - start_time
            remaining   = job_time - elapsed
            if verbose and logger is not None:
                logger.info(f"Elapsed={elapsed:.1f}s, remaining={remaining:.1f}s, limit={limit:.1f}s", lvl=3, **kwargs)
            if remaining < limit:
                if logger is not None:
                    logger.warning(f"Remaining time {remaining:.1f}s is below limit {limit:.1f}s", lvl=3, **kwargs)
                return True
            return False

        rem = SlurmMonitor.get_remaining_time(logger=logger)
        if rem == -1:
            if logger is not None:
                logger.warning("Failed to get remaining time from SLURM", lvl=3, **kwargs)
            return False
        if verbose and logger is not None:
            logger.info(f"Remaining time in SLURM job: {rem:.1f}s", lvl=3, **kwargs)
        if rem < limit:
            if logger is not None:
                logger.warning(f"Remaining time {rem:.1f}s is below limit {limit:.1f}s", lvl=3, **kwargs)
            return True
        return False

    @staticmethod
    @contextmanager
    def is_overtime_scope(
        limit               : float                 = 1000.0,
        start_time          : float | None          = None,
        job_time            : float | None          = None,
        *,
        slurm_poll_interval : float                 = 30.0,
        on_trigger          : Callable[[], Any] | None = None,
        raise_on_trigger    : bool                  = False,
        logger              : Logger | None         = None,
        **kwargs            : Any,
    ) -> Iterator[Callable[[], bool]]:
        r"""
        Context manager yielding a cached ``should_stop()`` predicate for loops.

        Caches ``scontrol`` queries for ``slurm_poll_interval`` seconds. Checks again on exit.
        """
        last_slurm_check                = -1e30
        cached_remaining: int | None    = None

        def _check_once() -> bool:
            nonlocal last_slurm_check, cached_remaining
            now = time.perf_counter()
            if start_time is not None and job_time is not None:
                remaining: float = job_time - (now - start_time)
            else:
                if not SlurmMonitor.is_slurm():
                    return False
                if cached_remaining is None or (now - last_slurm_check) >= slurm_poll_interval:
                    cached_remaining = SlurmMonitor.get_remaining_time(logger=logger)
                    last_slurm_check = now
                if cached_remaining == -1:
                    if logger is not None:
                        logger.warning("Failed to get remaining time from SLURM", lvl=3, **kwargs)
                    return False
                remaining = float(cached_remaining)

            if remaining < limit:
                if logger is not None:
                    logger.warning(f"Remaining time {remaining:.1f}s < limit {limit:.1f}s", lvl=3, **kwargs)
                if on_trigger is not None:
                    try:
                        on_trigger()
                    except Exception as exc:
                        if logger is not None:
                            logger.error(f"on_trigger() failed: {exc}", lvl=2, **kwargs)
                if raise_on_trigger:
                    raise SystemExit(0)
                return True
            return False

        try:
            yield _check_once
        finally:
            _check_once()


# -------------------------------------------
#! EOF
# -------------------------------------------
