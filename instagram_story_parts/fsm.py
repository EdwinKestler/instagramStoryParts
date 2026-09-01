"""Explicit finite-state machine for a single split job."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Callable


class SplitState(str, Enum):
    CREATED = "created"
    VALIDATING = "validating"
    PROBING = "probing"
    PLANNING = "planning"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StateTransition:
    previous: SplitState
    current: SplitState
    occurred_at: float


class InvalidStateTransition(RuntimeError):
    """Raised when a job attempts a transition not present in its graph."""


TransitionListener = Callable[[StateTransition], None]


class SplitStateMachine:
    """Thread-safe, observable state machine with an immutable history."""

    _ALLOWED: dict[SplitState, frozenset[SplitState]] = {
        SplitState.CREATED: frozenset({SplitState.VALIDATING, SplitState.FAILED}),
        SplitState.VALIDATING: frozenset({SplitState.PROBING, SplitState.FAILED}),
        SplitState.PROBING: frozenset({SplitState.PLANNING, SplitState.FAILED}),
        SplitState.PLANNING: frozenset({SplitState.EXPORTING, SplitState.FAILED}),
        SplitState.EXPORTING: frozenset({SplitState.COMPLETED, SplitState.FAILED}),
        SplitState.COMPLETED: frozenset(),
        SplitState.FAILED: frozenset(),
    }

    def __init__(self, listener: TransitionListener | None = None) -> None:
        self._state = SplitState.CREATED
        self._history: list[StateTransition] = []
        self._listener = listener
        self._lock = RLock()

    @property
    def state(self) -> SplitState:
        with self._lock:
            return self._state

    @property
    def history(self) -> tuple[StateTransition, ...]:
        with self._lock:
            return tuple(self._history)

    def transition_to(self, target: SplitState) -> StateTransition:
        with self._lock:
            if target not in self._ALLOWED[self._state]:
                raise InvalidStateTransition(
                    f"Cannot transition split job from {self._state.value} "
                    f"to {target.value}."
                )
            event = StateTransition(self._state, target, monotonic())
            self._state = target
            self._history.append(event)

        if self._listener is not None:
            self._listener(event)
        return event

    def fail(self) -> StateTransition | None:
        """Move an active machine to FAILED; terminal states remain unchanged."""
        with self._lock:
            if self._state in {SplitState.COMPLETED, SplitState.FAILED}:
                return None
        return self.transition_to(SplitState.FAILED)
