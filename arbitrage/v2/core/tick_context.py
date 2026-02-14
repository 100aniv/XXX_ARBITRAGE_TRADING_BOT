from __future__ import annotations

import contextvars
import threading
from contextlib import contextmanager
from typing import Iterator


_TICK_ACTIVE: contextvars.ContextVar[bool] = contextvars.ContextVar("tick_active", default=False)
_REST_FORBIDDEN: contextvars.ContextVar[bool] = contextvars.ContextVar("rest_forbidden", default=False)

_rest_call_lock = threading.Lock()
_rest_call_count = 0
_tick_state_lock = threading.Lock()
_tick_active_global = 0
_rest_forbidden_global = 0


class RestCallInTickError(AssertionError):
    """Tick 컨텍스트 내 REST 호출 감지 시 발생"""


def is_rest_forbidden_in_tick() -> bool:
    if _TICK_ACTIVE.get() and _REST_FORBIDDEN.get():
        return True
    with _tick_state_lock:
        return _tick_active_global > 0 and _rest_forbidden_global > 0


def is_tick_active() -> bool:
    if _TICK_ACTIVE.get():
        return True
    with _tick_state_lock:
        return _tick_active_global > 0


def record_rest_call() -> int:
    global _rest_call_count
    with _rest_call_lock:
        if not is_tick_active():
            return _rest_call_count
        _rest_call_count += 1
        return _rest_call_count


def get_rest_call_count() -> int:
    with _rest_call_lock:
        return _rest_call_count


def reset_rest_call_count() -> None:
    global _rest_call_count
    with _rest_call_lock:
        _rest_call_count = 0


@contextmanager
def tick_context(rest_forbidden: bool) -> Iterator[None]:
    global _tick_active_global, _rest_forbidden_global
    token_active = _TICK_ACTIVE.set(True)
    token_forbidden = _REST_FORBIDDEN.set(bool(rest_forbidden))
    with _tick_state_lock:
        _tick_active_global += 1
        if rest_forbidden:
            _rest_forbidden_global += 1
    try:
        yield
    finally:
        _TICK_ACTIVE.reset(token_active)
        _REST_FORBIDDEN.reset(token_forbidden)
        with _tick_state_lock:
            _tick_active_global = max(0, _tick_active_global - 1)
            if rest_forbidden:
                _rest_forbidden_global = max(0, _rest_forbidden_global - 1)
