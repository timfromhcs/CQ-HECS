"""Explicit miner state machine; no boolean `connected` flag."""
from __future__ import annotations

from enum import Enum


class MinerState(str, Enum):
    DEMO = "DEMO"
    DISCONNECTED = "DISCONNECTED"
    CONNECTED_READ_ONLY = "CONNECTED_READ_ONLY"
    BACKUP_REQUIRED = "BACKUP_REQUIRED"
    READY = "READY"
    RESEARCH_ARMED = "RESEARCH_ARMED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESTORE_READY = "RESTORE_READY"
    RESTORING = "RESTORING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    FAULT = "FAULT"


S = MinerState

# DEMO may only go to DISCONNECTED (leaving demo); it never reaches a hardware state.
ALLOWED: dict = {
    S.DEMO: {S.DISCONNECTED},
    S.DISCONNECTED: {S.DEMO, S.CONNECTED_READ_ONLY},
    S.CONNECTED_READ_ONLY: {S.DISCONNECTED, S.BACKUP_REQUIRED, S.READY, S.RECOVERY_REQUIRED, S.FAULT},
    S.BACKUP_REQUIRED: {S.DISCONNECTED, S.CONNECTED_READ_ONLY, S.READY, S.RECOVERY_REQUIRED, S.FAULT},
    S.READY: {S.DISCONNECTED, S.BACKUP_REQUIRED, S.RESEARCH_ARMED, S.RESTORE_READY, S.RECOVERY_REQUIRED, S.FAULT},
    S.RESEARCH_ARMED: {S.READY, S.RUNNING, S.PAUSED, S.RECOVERY_REQUIRED, S.FAULT},
    S.RUNNING: {S.PAUSED, S.READY, S.RECOVERY_REQUIRED, S.FAULT},
    S.PAUSED: {S.RUNNING, S.READY, S.RESTORE_READY, S.RECOVERY_REQUIRED, S.FAULT},
    S.RESTORE_READY: {S.RESTORING, S.READY, S.RECOVERY_REQUIRED, S.FAULT},
    S.RESTORING: {S.READY, S.RECOVERY_REQUIRED, S.FAULT},
    # No automatic retry: leaving these needs an explicit disconnect and re-pairing.
    S.RECOVERY_REQUIRED: {S.DISCONNECTED},
    S.FAULT: {S.DISCONNECTED},
}

# Transitions that need an explicit operator confirmation recorded by the caller.
NEEDS_OPERATOR = {
    (S.READY, S.RESEARCH_ARMED),
    (S.RESTORE_READY, S.RESTORING),
}

# States in which a physical flash action may be performed.
FLASH_STATES = {S.RESTORING}


class IllegalTransition(Exception):
    pass


class MinerStateMachine:
    def __init__(self, state: MinerState = MinerState.DEMO):
        self.state = state
        self.history: list = []

    def may_flash(self) -> bool:
        return self.state in FLASH_STATES

    def transition(self, target: MinerState, operator_confirmed: bool = False) -> MinerState:
        if target not in ALLOWED[self.state]:
            raise IllegalTransition(f"{self.state.value} -> {target.value} is not allowed")
        if (self.state, target) in NEEDS_OPERATOR and not operator_confirmed:
            raise IllegalTransition(f"{self.state.value} -> {target.value} needs explicit operator confirmation")
        self.history.append((self.state, target))
        self.state = target
        return self.state
