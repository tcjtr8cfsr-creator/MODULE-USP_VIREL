from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Literal


State = Literal["OPERATIONAL", "SAFE_ON"]


@dataclass(frozen=True)
class USPVirelConfig:
    """
    Configuration corresponding to the CONSTANTS in the TLA+ spec.
    """
    domains: List[str]          # Domains = {"A","B"}
    tokens: List[str]           # Tokens  = {"HALT","RES"}
    epoch_max: int              # EpochMax
    lamport_max: int            # LamportMax
    hold_ms: int                # HoldMs (not used yet, but kept for completeness)


@dataclass
class USPVirel:
    """
    Python state machine for the USP_VIREL protocol.

    Mirrors the TLA+ spec:

      - VARIABLES: state, epoch, lamport, quorum_votes, provisional_timer
      - ACTIONS:   CastVote, HaltPrecedence, SafeOnStaysSafe, Idle
      - INVARIANTS: TypeOK, SafeState
    """
    cfg: USPVirelConfig
    state: State = "OPERATIONAL"
    epoch: int = 0
    lamport: int = 0
    quorum_votes: Dict[str, List[str]] = field(default_factory=dict)
    provisional_timer: int = 0

    def __post_init__(self) -> None:
        # Initialize quorum_votes to empty sequences for each domain
        if not self.quorum_votes:
            self.quorum_votes = {d: [] for d in self.cfg.domains}
        self._check_type_ok()

    # ------------------------------------------------------------------
    # Helpers (HasHALT, invariants)
    # ------------------------------------------------------------------

    def _has_halt(self, domain: str) -> bool:
        """
        HasHALT(d) == ∃ i : quorum_votes[d][i] = "HALT"
        """
        return "HALT" in self.quorum_votes[domain]

    def _check_type_ok(self) -> None:
        """
        TypeOK invariant from the TLA+ spec.
        Raises AssertionError if violated.
        """
        assert self.state in {"OPERATIONAL", "SAFE_ON"}, "Invalid state"
        assert 0 <= self.epoch <= self.cfg.epoch_max, "Epoch out of bounds"
        assert 0 <= self.lamport <= self.cfg.lamport_max, "Lamport out of bounds"

        # quorum_votes ∈ [Domains -> Seq(Tokens)]
        assert set(self.quorum_votes.keys()) == set(self.cfg.domains), \
            "quorum_votes must have exactly one entry per domain"

        for d, seq in self.quorum_votes.items():
            assert isinstance(seq, list), "Votes must be lists"
            for t in seq:
                assert t in self.cfg.tokens, "Unknown token in quorum_votes"

        assert isinstance(self.provisional_timer, int) and self.provisional_timer >= 0, \
            "provisional_timer must be a natural number"

    def _check_safe_state(self) -> None:
        """
        SafeState invariant:

          state = "SAFE_ON" => ∃ d ∈ Domains : HasHALT(d)
        """
        if self.state == "SAFE_ON":
            if not any(self._has_halt(d) for d in self.cfg.domains):
                raise AssertionError("SafeState violated: SAFE_ON without HALT quorum")

    def assert_invariants(self) -> None:
        """
        Public helper to assert all invariants.
        Call this after any series of operations if you want.
        """
        self._check_type_ok()
        self._check_safe_state()

    # ------------------------------------------------------------------
    # Actions (CastVote, HaltPrecedence, SafeOnStaysSafe, Idle)
    # ------------------------------------------------------------------

    def cast_vote(self, domain: str, token: str) -> bool:
        """
        CastVote action.

        Guard:
          - domain ∈ Domains
          - token ∈ Tokens
          - state = "OPERATIONAL"
          - Len(quorum_votes[domain]) < 2   (bounded for finite state)

        Returns True if the vote was accepted, False if guard not satisfied.
        """
        if domain not in self.cfg.domains:
            raise ValueError(f"Unknown domain: {domain}")
        if token not in self.cfg.tokens:
            raise ValueError(f"Unknown token: {token}")

        if self.state != "OPERATIONAL":
            return False
        if len(self.quorum_votes[domain]) >= 2:
            return False

        # Effect:
        #   state' = state
        #   epoch' = epoch
        #   lamport' = lamport
        #   quorum_votes'[domain] = Append(.., token)
        #   provisional_timer' = provisional_timer
        self.quorum_votes[domain].append(token)
        print(("CAST", token, "IN", domain))

        self._check_type_ok()
        self._check_safe_state()
        return True

    def halt_precedence(self) -> bool:
        """
        HaltPrecedence action.

        Guard:
          ∃ d ∈ Domains :
            state = "OPERATIONAL" ∧
            Len(quorum_votes[d]) ≥ 2 ∧
            HasHALT(d)

        Effect:
          state'   = "SAFE_ON"
          epoch'   = epoch
          lamport' = lamport + 1
        """
        if self.state != "OPERATIONAL":
            return False

        for d in self.cfg.domains:
            if len(self.quorum_votes[d]) >= 2 and self._has_halt(d):
                if self.lamport >= self.cfg.lamport_max:
                    raise AssertionError("LamportMax would be exceeded")
                self.state = "SAFE_ON"
                self.lamport += 1
                print(("HALT QUORUM FOR", d, "→ SAFE_ON"))
                self._check_type_ok()
                self._check_safe_state()
                return True

        return False

    def safe_on_stays_safe(self) -> bool:
        """
        SafeOnStaysSafe action.

        Guard:
          state = "SAFE_ON"

        Effect:
          state' = "SAFE_ON"
          (everything else unchanged)
        """
        if self.state != "SAFE_ON":
            return False
        # No state change; we just check invariants.
        self._check_type_ok()
        self._check_safe_state()
        return True

    def idle(self) -> None:
        """
        Idle action: leaves all variables unchanged.
        Always enabled.
        """
        # UNCHANGED vars
        self._check_type_ok()
        self._check_safe_state()

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def auto_step(self) -> None:
        """
        A helper that approximates the TLA+ Next relation:

          Next == CastVote \/ HaltPrecedence \/ SafeOnStaysSafe \/ Idle

        For real systems you’d call the actions directly; this is just for
        quick simulations.
        """
        # Prioritize HaltPrecedence if it's enabled.
        if self.halt_precedence():
            return
        if self.state == "SAFE_ON":
            self.safe_on_stays_safe()
        else:
            # In TLA+, CastVote is nondeterministic; here we do nothing.
            self.idle()

    def __repr__(self) -> str:
        return (
            f"USP_VIREL(state={self.state}, epoch={self.epoch}, "
            f"lamport={self.lamport}, votes={self.quorum_votes}, "
            f"timer={self.provisional_timer})"
        )