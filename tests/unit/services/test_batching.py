"""Tests for services/batching.py: burst coalescing, per-chat isolation and the
duplicate-message guard."""

from __future__ import annotations

import threading
import time

from services.batching import ChatBatcher


class FakeClock:
    """Deterministic sleeper that records how long a batch waited."""

    def __init__(self):
        self.slept: list[float] = []

    def __call__(self, seconds):
        self.slept.append(seconds)


def test_zero_window_returns_the_message_immediately():
    batcher = ChatBatcher(window_getter=lambda: 0, sleeper=FakeClock())
    batch = batcher.process(("bc", 1), 10, "hello")
    assert batch == [(10, "hello")]


def test_window_is_passed_to_the_sleeper():
    clock = FakeClock()
    batcher = ChatBatcher(window_getter=lambda: 2.5, sleeper=clock)
    batcher.process(("bc", 1), 10, "hello")
    assert clock.slept == [2.5]


def test_window_is_clamped_to_the_maximum():
    clock = FakeClock()
    batcher = ChatBatcher(window_getter=lambda: 999, sleeper=clock)
    batcher.process(("bc", 1), 10, "hello")
    assert clock.slept == [batcher.window()]
    assert clock.slept[0] <= 8.0


def test_window_getter_failure_falls_back_to_default():
    def boom():
        raise RuntimeError("db down")

    batcher = ChatBatcher(window_getter=boom, sleeper=FakeClock())
    assert batcher.window() == 1.0


def test_rapid_follow_ups_are_coalesced_into_one_batch():
    """Follow-ups that arrive inside the window join the batch in flight."""
    window_open = threading.Event()
    release = threading.Event()
    batches: list = []

    def sleeper(_seconds):
        window_open.set()
        release.wait(5)

    batcher = ChatBatcher(window_getter=lambda: 1, sleeper=sleeper)

    def first():
        batches.append(batcher.process(("bc", 1), 1, "hi"))

    thread = threading.Thread(target=first)
    thread.start()
    assert window_open.wait(2)

    # These arrive while the first message is still inside its window, so they
    # are queued and return immediately.
    assert batcher.process(("bc", 1), 2, "how much?") is None
    assert batcher.process(("bc", 1), 3, "for two people") is None
    release.set()
    thread.join(5)

    assert batches == [[(1, "hi"), (2, "how much?"), (3, "for two people")]]


def test_message_after_the_flush_starts_a_new_batch():
    window_open = threading.Event()
    release = threading.Event()
    batcher = ChatBatcher(window_getter=lambda: 1,
                          sleeper=lambda _s: (window_open.set(), release.wait(5)))

    thread = threading.Thread(target=lambda: batcher.process(("bc", 1), 1, "hi"))
    thread.start()
    assert window_open.wait(2)
    release.set()
    thread.join(5)

    # A later message (not part of that burst) is answered on its own.
    assert batcher.process(("bc", 1), 2, "second question") == [(2, "second question")]


def test_duplicate_message_id_is_ignored_after_a_batch():
    batcher = ChatBatcher(window_getter=lambda: 0, sleeper=FakeClock())
    assert batcher.process(("bc", 1), 7, "hello") == [(7, "hello")]
    assert batcher.process(("bc", 1), 7, "hello") is None


def test_different_chats_do_not_block_each_other():
    batcher = ChatBatcher(window_getter=lambda: 0, sleeper=FakeClock())
    assert batcher.process(("bc", 1), 1, "a") == [(1, "a")]
    assert batcher.process(("bc", 2), 2, "b") == [(2, "b")]


def test_duplicate_guard_is_bounded():
    batcher = ChatBatcher(window_getter=lambda: 0, sleeper=FakeClock())
    for index in range(100):
        batcher.process(("bc", 1), index, f"m{index}")
    # Oldest ids are dropped, newest are remembered.
    assert batcher.process(("bc", 1), 99, "again") is None
    assert batcher.process(("bc", 1), 0, "again") == [(0, "again")]


def test_reset_clears_state():
    batcher = ChatBatcher(window_getter=lambda: 0, sleeper=FakeClock())
    batcher.process(("bc", 1), 1, "a")
    batcher.reset()
    assert batcher.process(("bc", 1), 1, "a") == [(1, "a")]


def test_thread_safety_smoke():
    """Many chats pushing concurrently: every message is answered exactly once."""
    batcher = ChatBatcher(window_getter=lambda: 0.001, sleeper=time.sleep)
    answered: list[tuple] = []  # (chat_id, message_id) pairs
    lock = threading.Lock()

    def worker(chat_id):
        for message_id in range(5):
            batch = batcher.process(("bc", chat_id), message_id, f"msg{message_id}")
            if batch is not None:
                with lock:
                    answered.extend((chat_id, mid) for mid, _ in batch)

    threads = [threading.Thread(target=worker, args=(chat,)) for chat in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert len(answered) == 40
    assert len(set(answered)) == 40
