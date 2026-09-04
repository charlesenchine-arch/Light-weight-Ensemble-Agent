import threading
import time

from agentflow.cancel import clear, requested
from agentflow.turn_queue import TurnQueue


def test_queue_drains_in_order():
    order: list[str] = []
    gate = threading.Event()

    def run_fn(text: str) -> None:
        order.append("start:" + text)
        if text == "a":
            gate.wait(timeout=1)
        order.append("end:" + text)

    q = TurnQueue(run_fn)
    assert q.submit("a") == "started"
    assert q.submit("b") == "queued"
    assert q.queued == 1
    gate.set()
    q.join(timeout=2)
    time.sleep(0.2)
    q.join(timeout=2)
    assert order[0] == "start:a"
    assert "end:a" in order
    assert "start:b" in order
    assert "end:b" in order


def test_interrupt_sets_cancel_flag():
    clear()
    started = threading.Event()

    def run_fn(text: str) -> None:
        started.set()
        time.sleep(0.4)

    q = TurnQueue(run_fn)
    q.submit("a")
    assert started.wait(timeout=1)
    q.interrupt()
    assert requested()
    q.join(timeout=2)
    clear()


def test_steer_interrupts_and_prioritizes_message():
    clear()
    order: list[str] = []
    started = threading.Event()

    def run_fn(text: str) -> None:
        order.append("start:" + text)
        if text == "a":
            started.set()
            deadline = time.time() + 2
            while not requested() and time.time() < deadline:
                time.sleep(0.01)
        order.append("end:" + text)

    q = TurnQueue(run_fn)
    q.submit("a")
    assert started.wait(timeout=1)
    q.submit("later")
    assert q.steer("urgent") == "interrupting"
    q.join(timeout=2)
    time.sleep(0.1)
    q.join(timeout=2)
    time.sleep(0.1)
    q.join(timeout=2)

    assert order.index("start:urgent") < order.index("start:later")
    clear()
