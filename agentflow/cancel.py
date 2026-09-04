"""Cooperative cancel so Ctrl+C stops the current turn without killing LEA."""

from __future__ import annotations

import threading
from collections.abc import Callable

_flag = threading.Event()
_closer_lock = threading.Lock()
_closers: set[Callable[[], None]] = set()


class Cancelled(Exception):
    """The user interrupted the current turn."""


def request() -> None:
    _flag.set()
    with _closer_lock:
        closers = list(_closers)
    for close in closers:
        try:
            close()
        except Exception:
            pass


def clear() -> None:
    _flag.clear()


def requested() -> bool:
    return _flag.is_set()


def check() -> None:
    if _flag.is_set():
        raise Cancelled("interrupted")


def register_closer(close: Callable[[], None]) -> None:
    """Register an in-flight resource that should be closed on interruption."""
    with _closer_lock:
        _closers.add(close)
        already_cancelled = _flag.is_set()
    if already_cancelled:
        try:
            close()
        except Exception:
            pass


def unregister_closer(close: Callable[[], None]) -> None:
    with _closer_lock:
        _closers.discard(close)


def wait(seconds: float) -> None:
    """Sleep until the timeout, but wake immediately when cancellation is requested."""
    if _flag.wait(timeout=max(seconds, 0.0)):
        raise Cancelled("interrupted")
