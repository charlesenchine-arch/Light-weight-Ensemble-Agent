"""Background turn + follow-up queue (Grok-style: dialog stays, Enter queues)."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable

from agentflow.cancel import clear as clear_cancel
from agentflow.cancel import request as request_cancel


class TurnQueue:
    def __init__(self, run_fn: Callable[[str], None], *, on_change: Callable[[], None] | None = None):
        self._run_fn = run_fn
        self._on_change = on_change
        self._lock = threading.Lock()
        self._pending: deque[str] = deque()
        self._busy = False
        self._thread: threading.Thread | None = None
        self.current: str | None = None

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def queued(self) -> int:
        with self._lock:
            return len(self._pending)

    def peek_queue(self) -> list[str]:
        with self._lock:
            return list(self._pending)

    def submit(self, text: str) -> str:
        """'started' if a worker began now, 'queued' if the current turn is still running."""
        text = (text or "").strip()
        if not text:
            return "empty"
        with self._lock:
            if self._busy:
                self._pending.append(text)
                self._notify()
                return "queued"
            self._busy = True
            self.current = text
        self._spawn(text)
        self._notify()
        return "started"

    def steer(self, text: str) -> str:
        """Interrupt the active turn and run this message before queued follow-ups."""
        text = (text or "").strip()
        if not text:
            return "empty"
        with self._lock:
            if self._busy:
                self._pending.appendleft(text)
                # Keep the lock while signalling so the current worker cannot
                # start the next turn and clear this cancellation first.
                request_cancel()
                status = "interrupting"
            else:
                self._busy = True
                self.current = text
                status = "started"
        if status == "started":
            self._spawn(text)
        self._notify()
        return status

    def interrupt(self) -> None:
        request_cancel()
        self._notify()

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()

    def _spawn(self, text: str) -> None:
        clear_cancel()
        self._thread = threading.Thread(target=self._worker, args=(text,), daemon=True, name="lea-turn")
        self._thread.start()

    def _worker(self, text: str) -> None:
        try:
            self._run_fn(text)
        finally:
            nxt: str | None = None
            with self._lock:
                if self._pending:
                    nxt = self._pending.popleft()
                    self.current = nxt
                    self._busy = True
                else:
                    self.current = None
                    self._busy = False
            self._notify()
            if nxt:
                self._spawn(nxt)
