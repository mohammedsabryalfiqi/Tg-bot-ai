"""Message batching: customers often send several short messages in a row
("hi" / "how much" / "for 2 people?"). Answering each one wastes tokens and
produces choppy replies, so messages from the same chat are collected for a
short window (``reply_debounce_seconds``, default 1 s) and answered once.

Concurrency model
-----------------
* One small critical section per ``(business connection, chat)`` keeps the state
  consistent; different customers are handled in parallel.
* The first message of a burst becomes the *flusher*: it waits out the window and
  then drains everything that arrived meanwhile into a single batch.
* Follow-up messages are added to the open batch and return ``None`` immediately
  (their text will be answered by the batch in flight) — which also makes
  duplicate/redelivered updates harmless.
"""

from __future__ import annotations

import logging
import threading
import time

import database

log = logging.getLogger("smartel.batching")

MAX_WINDOW_SECONDS = 8.0
DEFAULT_WINDOW_SECONDS = 1.0
MAX_TRACKED_IDS = 64          # remembered message ids per chat (dup guard)
MAX_TRACKED_CHATS = 512       # bounded memory: idle chats are evicted


def _window_from_settings() -> float:
    try:
        window = float(database.get_float("reply_debounce_seconds"))
    except Exception:
        return DEFAULT_WINDOW_SECONDS
    return max(0.0, min(MAX_WINDOW_SECONDS, window))


class _ChatState:
    __slots__ = ("lock", "buffer", "seen", "handled")

    def __init__(self):
        self.lock = threading.Lock()
        self.buffer: list[tuple[int, str]] = []
        self.seen: list[int] = []
        self.handled = False          # a flusher is currently waiting/draining

    def idle(self) -> bool:
        return not self.handled and not self.buffer


class ChatBatcher:
    """Collects rapid-fire messages per chat and hands back one batch."""

    def __init__(self, window_getter=_window_from_settings, sleeper=time.sleep):
        self._window_getter = window_getter
        self._sleeper = sleeper
        self._guard = threading.Lock()
        self._states: dict[tuple, _ChatState] = {}

    # -- state helpers -------------------------------------------------------
    def _state_for(self, key: tuple) -> _ChatState:
        with self._guard:
            state = self._states.get(key)
            if state is None:
                if len(self._states) >= MAX_TRACKED_CHATS:
                    for idle_key in [k for k, s in self._states.items() if s.idle()]:
                        del self._states[idle_key]
                        if len(self._states) < MAX_TRACKED_CHATS:
                            break
                state = _ChatState()
                self._states[key] = state
            return state

    def window(self) -> float:
        try:
            return max(0.0, min(MAX_WINDOW_SECONDS, float(self._window_getter())))
        except Exception:
            log.warning("could not read the debounce window; using default", exc_info=True)
            return DEFAULT_WINDOW_SECONDS

    def _remember(self, state: _ChatState, message_ids: list[int]) -> None:
        state.seen.extend(mid for mid in message_ids if mid is not None)
        if len(state.seen) > MAX_TRACKED_IDS:
            del state.seen[:-MAX_TRACKED_IDS]

    # -- public API ----------------------------------------------------------
    def process(self, key: tuple, message_id, text: str) -> list[tuple[int, str]] | None:
        """Add a message to its chat's batch.

        Returns the batch to answer when this call owns the flush, or ``None``
        when the message was (or will be) covered by another flush.
        """
        state = self._state_for(key)
        with state.lock:
            if message_id is not None and message_id in state.seen:
                log.debug("message %s already answered in an earlier batch", message_id)
                return None
            state.buffer.append((message_id, text))
            if state.handled:
                return None          # an in-flight batch will answer it
            state.handled = True     # we own the flush

        window = self.window()
        if window > 0:
            self._sleeper(window)

        with state.lock:
            batch = state.buffer
            state.buffer = []
            self._remember(state, [mid for mid, _ in batch])
            state.handled = False
        return batch

    def reset(self) -> None:
        """Drop all buffers/state (used by tests and by /reset)."""
        with self._guard:
            self._states.clear()


# Module-level instance used by the business pipeline.
batcher = ChatBatcher()
