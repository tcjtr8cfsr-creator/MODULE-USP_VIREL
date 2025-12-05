#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Literal
import sys

State = Literal["OPERATIONAL", "SAFE_ON"]


# ============================================================
#  CONFIG (corresponding to CONSTANTS in TLA)
# ============================================================

@dataclass(frozen=True)
class USPVirelConfig:
    domains: List[str]
    tokens: List[str]
    epoch_max: int
    lamport_max: int
    hold_ms: int


# ============================================================
#  STATE MACHINE IMPLEMENTATION
# ============================================================

@dataclass
class USPVirel:
    cfg: USPVirelConfig
    state: State = "OPERATIONAL"
    epoch: int = 0
    lamport: int = 0
    quorum_votes: Dict[str, List[str]] = field(default_factory=dict)
    provisional_timer: int = 0

    def __post_init__(self):
        if not self.quorum_votes:
            self.quorum_votes = {d: [] for d in self.cfg.domains}
        self._check_type_ok()

    # ---------------------- helpers ------------------------------------

    def _has_halt(self, d: str) -> bool:
        return "HALT" in self.quorum_votes[d]

    def _check_type_ok(self):
        assert self.state in {"OPERATIONAL", "SAFE_ON"}
        assert 0 <= self.epoch <= self.cfg.epoch_max
        assert 0 <= self.lamport <= self.cfg.lamport_max
        assert isinstance(self.provisional_timer, int)

        for d, seq in self.quorum_votes.items():
            for t in seq:
                assert t in self.cfg.tokens

    def _check_safe_state(self):
        if self.state == "SAFE_ON":
            if not any(self._has_halt(d) for d in self.cfg.domains):
                raise AssertionError(
                    "Invariant violation: SAFE_ON without HALT quorum."
                )

    def assert_invariants(self):
        self._check_type_ok()
        self._check_safe_state()

    # ---------------------- actions ------------------------------------

    def cast_vote(self, d: str, token: str) -> bool:
        if self.state != "OPERATIONAL":
            print("❌ Cannot cast vote: state is SAFE_ON.")
            return False

        if d not in self.cfg.domains:
            print(f"❌ Unknown domain: {d}")
            return False

        if token not in self.cfg.tokens:
            print(f"❌ Unknown token: {token}")
            return False

        if len(self.quorum_votes[d]) >= 2:
            print(f"❌ Domain {d} already has 2 votes.")
            return False

        self.quorum_votes[d].append(token)
        print(f"📥 CAST {token} IN {d}")
        self.assert_invariants()
        return True

    def halt_precedence(self) -> bool:
        if self.state != "OPERATIONAL":
            return False

        for d in self.cfg.domains:
            if len(self.quorum_votes[d]) >= 2 and self._has_halt(d):
                self.state = "SAFE_ON"
                self.lamport += 1
                print(f"⚠️  HALT QUORUM FOR {d} → SAFE_ON")
                self.assert_invariants()
                return True

        return False

    def safe_on_stays_safe(self):
        if self.state == "SAFE_ON":
            self.assert_invariants()
            return True
        return False

    def idle(self):
        self.assert_invariants()
        return True

    def step(self):
        """
        Next =
            CastVote  (not auto here)
            OR HaltPrecedence
            OR SafeOnStaysSafe
            OR Idle
        """
        if self.halt_precedence():
            return "halt_precedence"

        if self.state == "SAFE_ON":
            self.safe_on_stays_safe()
            return "safe_on"

        self.idle()
        return "idle"

    # ---------------------- display ------------------------------------

    def show(self):
        print("\n🔎 CURRENT STATE")
        print("------------------------")
        print(f" state          = {self.state}")
        print(f" epoch          = {self.epoch}")
        print(f" lamport        = {self.lamport}")
        print(f" provisional_ms = {self.provisional_timer}")
        print(f" votes:")
        for d,v in self.quorum_votes.items():
            print(f"   {d}: {v}")
        print("------------------------\n")