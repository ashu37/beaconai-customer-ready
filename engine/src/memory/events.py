"""S-3 prep — typed event payload schemas (B-2 surface b + audit L-E).

Status: **NOT YET WIRED.** This module ships the typed payload schemas
for the ``recommendation_emitted`` / ``recommendation_considered``
substrate events that S-3 will write. The substrate writer
(``src.memory.store.append_event``) and lineage helper
(``src.memory.lineage.compute_lineage_id``) live behind ticket S-2 and
do NOT exist on this branch yet. Engineer A is implementing S-2 in
parallel; once it merges to ``post-6b-restructured-roadmap``, S-3 wires
``decide.py`` to call ``append_event(...)`` with these typed payloads.

What this module pins on the engine-B branch:

1. **Typed ``EvidenceSnapshot``** (B-2 surface b) — one snapshot per
   candidate, capturing the internal Measurement diagnostics that the
   merchant-facing ``PlayCard`` does not surface but that the
   calibration consumer / Phase 9 ``compute_realized_outcome`` will
   need to score against the prediction at recall time.

2. **Typed ``ExpectedOutcome``** (audit L-E pre-registered expectation
   block) — three fields the engine MUST commit to before the outcome
   is observed:

   - ``expected_direction``: ``"increase" | "decrease" | "either"``
   - ``min_interesting_effect_size``: float, the smallest absolute
     effect the merchant would care about for this play type
   - ``expected_observation_window_days``: int, the window the realized
     outcome must be measured over to be commensurable

   Pre-registration prevents post-hoc rationalization at calibration
   time. Audit L-E is the requirement; this struct is the surface.

3. **Typed ``RecommendationEmittedPayload`` /
   ``RecommendationConsideredPayload``** — the full event payload
   structure that ``decide.py`` will hand to ``append_event``.

When S-2 lands and S-3 begins wiring, all callsites importing from
this module will move to ``src.memory.events``. The TODO markers in
``src/decide.py`` flag the wire-up sites; until then this is a pure
type-definition module with no runtime callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Pre-registered expectation block (audit L-E)
# ---------------------------------------------------------------------------


ExpectedDirection = Literal["increase", "decrease", "either"]


@dataclass(frozen=True)
class ExpectedOutcome:
    """Pre-registered prediction the engine commits to at recommendation
    emission time.

    Audit reference L-E: every ``recommendation_emitted`` event MUST
    carry these three fields. The calibration consumer (Phase 9
    L-D #1) compares the realized outcome against ``expected_direction``
    and ``min_interesting_effect_size`` to decide whether the realized
    outcome is "as predicted," "below threshold," or "wrong direction."

    The fields are a contract between the engine and the calibration
    consumer; they are NOT merchant-facing copy. ``PlayCard`` rendering
    does not surface these values directly.

    Fields:
      expected_direction:
        Direction of effect the engine predicts. ``"either"`` is allowed
        only for explicitly two-sided hypotheses (e.g. discount hygiene
        where margin can move in either direction); most plays are
        ``"increase"``.
      min_interesting_effect_size:
        Smallest absolute effect the merchant would care about, in the
        unit of the ``would_be_measured_by`` enum. For
        ``REPEAT_PURCHASE_IN_30D`` this is an absolute proportion delta
        (e.g. ``0.02`` = 2 percentage-point lift). The calibration
        consumer treats realized effects below this threshold as "below
        threshold," not "as predicted" — even if direction matches.
      expected_observation_window_days:
        Number of days post-recommendation the realized outcome must be
        measured over. Must match the ``would_be_measured_by`` enum's
        natural window (e.g. 30 for ``REPEAT_PURCHASE_IN_30D``).
    """

    expected_direction: ExpectedDirection
    min_interesting_effect_size: float
    expected_observation_window_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expected_direction": self.expected_direction,
            "min_interesting_effect_size": self.min_interesting_effect_size,
            "expected_observation_window_days": self.expected_observation_window_days,
        }


# ---------------------------------------------------------------------------
# Typed evidence snapshot (B-2 surface b)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Internal Measurement diagnostics carried on each emitted event.

    Captures the measurement state the engine used to make the
    recommendation decision — the inputs Phase 9 ``compute_realized_outcome``
    will compare its realized output against. Nothing in here is merchant
    facing; ``PlayCard`` does not surface these values verbatim.

    The snapshot is intentionally schema-pinned at ``event_version=1``.
    Additive-only future evolution per Risk #1 in the plan: never remove
    a field, only add new ones with safe defaults.

    Fields:
      evidence_class:
        ``"measured" | "directional" | "targeting"`` — which evidence
        class produced this candidate. ``measured`` plays carry full
        statistical diagnostics; ``targeting`` plays carry None for
        ``effect_abs`` / ``p_internal`` (no measurement design wired).
      window_label:
        Which window the measurement was computed over (e.g. ``"L28"``,
        ``"L56"``, ``"multiwindow"``). For multi-window combiner output
        this is ``"multiwindow"`` per the B-6 invariant.
      effect_abs:
        Absolute effect size in the natural unit of the play's
        ``would_be_measured_by`` enum. ``None`` for ``targeting`` plays.
      p_internal:
        Internal-only p-value from the measurement test. Never surfaced
        in merchant-facing copy (Phase 6A forbidden-token sweep). ``None``
        for ``targeting`` plays.
      sample_size:
        Audience N at the time of measurement. Distinct from the
        recommendation-time audience size; this is the sample the
        statistical test ran on.
      multiwindow_agreement:
        Optional — when the multiwindow combiner ran, this is the
        fraction of windows whose effect direction agreed with the
        combined direction. ``None`` when only one window was used.
      data_quality_flags:
        Snapshot of ``EngineRun.data_quality_flags`` at emission time.
        Calibration uses this to skip outcomes that came from
        anomalous-window runs.
      measurement_design_version:
        Integer version of the measurement design used. Bump whenever
        the test logic for a play changes substantively (analogous to
        ``audience_definition_version`` per D-1).
    """

    evidence_class: Literal["measured", "directional", "targeting"]
    window_label: str
    effect_abs: Optional[float]
    p_internal: Optional[float]
    sample_size: Optional[int]
    multiwindow_agreement: Optional[float] = None
    data_quality_flags: List[str] = field(default_factory=list)
    measurement_design_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_class": self.evidence_class,
            "window_label": self.window_label,
            "effect_abs": self.effect_abs,
            "p_internal": self.p_internal,
            "sample_size": self.sample_size,
            "multiwindow_agreement": self.multiwindow_agreement,
            "data_quality_flags": list(self.data_quality_flags),
            "measurement_design_version": self.measurement_design_version,
        }


# ---------------------------------------------------------------------------
# Recommendation event payloads
# ---------------------------------------------------------------------------


#: Pinned schema version for recommendation_* event payloads. Bumping
#: this is a frozen-contract change requiring Swarm-team coordination
#: per the plan §1 "Stop-Coding-Line guarantee."
RECOMMENDATION_EVENT_VERSION: int = 1


@dataclass(frozen=True)
class RecommendationEmittedPayload:
    """Payload for a ``recommendation_emitted`` substrate event.

    Written by ``decide.py`` (single writer per the S-3 grep test) once
    per ``PlayCard`` in ``recommendations`` and ``recommended_experiments``.

    Fields:
      event_version:
        Schema version. Pinned at ``1`` for the Sprint 2 freeze.
      run_id:
        UUID of the engine run. Distinct per run so the same lineage_id
        can have many emissions over time.
      lineage_id:
        SHA1 hex of (store_id, play_id, audience_definition_id,
        audience_definition_version) per S-2 ``compute_lineage_id``.
        Stable across runs that produce the same audience definition.
      store_id:
        Per-merchant scope from B-4/S-1 resolver.
      play_id:
        Play registry key (e.g. ``"discount_hygiene"``).
      audience_definition_id:
        Stable identifier for the audience-builder output.
      audience_definition_version:
        Integer per founder decision D-1; bumped whenever audience
        builder logic changes substantively.
      role:
        ``"recommendation"`` for ``recommendations[]`` cards or
        ``"experiment"`` for ``recommended_experiments[]`` cards.
      evidence_snapshot:
        Typed measurement diagnostics — see :class:`EvidenceSnapshot`.
      expected_outcome:
        Pre-registered prediction — see :class:`ExpectedOutcome`.
      snapshot_path:
        Relative path (under ``data/<store_id>/runs/``) to the immutable
        ``engine_run.json`` snapshot for this run. Set by S-4. Until
        S-4 lands, S-3 emits the receipts-relative path and a
        placeholder ``snapshot_sha256``.
      snapshot_sha256:
        SHA256 of the snapshot file at write time. Set by S-4.
    """

    event_version: int
    run_id: str
    lineage_id: str
    store_id: str
    play_id: str
    audience_definition_id: str
    audience_definition_version: int
    role: Literal["recommendation", "experiment"]
    evidence_snapshot: EvidenceSnapshot
    expected_outcome: ExpectedOutcome
    snapshot_path: Optional[str] = None
    snapshot_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_version": self.event_version,
            "run_id": self.run_id,
            "lineage_id": self.lineage_id,
            "store_id": self.store_id,
            "play_id": self.play_id,
            "audience_definition_id": self.audience_definition_id,
            "audience_definition_version": self.audience_definition_version,
            "role": self.role,
            "evidence_snapshot": self.evidence_snapshot.to_dict(),
            "expected_outcome": self.expected_outcome.to_dict(),
            "snapshot_path": self.snapshot_path,
            "snapshot_sha256": self.snapshot_sha256,
        }


@dataclass(frozen=True)
class RecommendationConsideredPayload:
    """Payload for a ``recommendation_considered`` substrate event.

    Written by ``decide.py`` once per ``RejectedPlay`` (the merchant-
    facing "Considered" list). Mirrors the emitted payload shape but
    carries the typed ``ReasonCode`` instead of a role, and the
    ``evidence_snapshot`` is optional (a play that was held for
    ``AUDIENCE_TOO_SMALL`` may not have run a measurement at all).

    Fields:
      reason_code:
        Stringified :class:`src.engine_run.ReasonCode` per the S-3
        fan-out. One of:
          - ``audience_too_small``
          - ``cold_start_insufficient_data``
          - ``inventory_blocked``
          - ``materiality_below_floor``
          - ``data_quality_flag``
          - ``no_measured_signal`` (default fallback)
        Plus the existing legacy codes that already map (cap_exceeded,
        anomalous_window, etc.).
    """

    event_version: int
    run_id: str
    lineage_id: str
    store_id: str
    play_id: str
    audience_definition_id: str
    audience_definition_version: int
    reason_code: str
    evidence_snapshot: Optional[EvidenceSnapshot]
    expected_outcome: Optional[ExpectedOutcome]
    snapshot_path: Optional[str] = None
    snapshot_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_version": self.event_version,
            "run_id": self.run_id,
            "lineage_id": self.lineage_id,
            "store_id": self.store_id,
            "play_id": self.play_id,
            "audience_definition_id": self.audience_definition_id,
            "audience_definition_version": self.audience_definition_version,
            "reason_code": self.reason_code,
            "evidence_snapshot": (
                self.evidence_snapshot.to_dict()
                if self.evidence_snapshot is not None
                else None
            ),
            "expected_outcome": (
                self.expected_outcome.to_dict()
                if self.expected_outcome is not None
                else None
            ),
            "snapshot_path": self.snapshot_path,
            "snapshot_sha256": self.snapshot_sha256,
        }


# ---------------------------------------------------------------------------
# Campaign sent event payload (S-6)
# ---------------------------------------------------------------------------


#: Pinned schema version for ``campaign_sent`` event payloads. Bumping
#: this is a frozen-contract change requiring Swarm-team coordination
#: per the plan §1 "Stop-Coding-Line guarantee." Future evolution is
#: ADDITIVE-ONLY — never remove a field, never change a field's type;
#: only add new ``Optional`` fields with safe defaults.
CAMPAIGN_SENT_EVENT_VERSION: int = 1


#: Channels accepted in the v1 schema. Sourced from the merchant
#: marketing surfaces Beacon currently scopes (Klaviyo / Postscript /
#: Shopify Email send paths). New values land via additive enum growth
#: behind founder sign-off — adding here forks the v1 contract.
CAMPAIGN_SENT_ALLOWED_CHANNELS: frozenset[str] = frozenset(
    {"email", "sms", "push", "other"}
)


#: Required top-level keys in the inbox JSON. Strict: any missing key
#: causes the importer to refuse the file.
CAMPAIGN_SENT_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "lineage_id",
        "recommendation_event_id",
        "campaign_id",
        "sent_at",
        "audience_size",
        "channel",
    }
)


#: Optional top-level keys allowed in the inbox JSON. Strict: any key
#: outside the union of required + optional causes the importer to
#: refuse the file (v1 strict-mode contract). Add new keys only via the
#: additive-only evolution rule documented in
#: ``docs/memory_substrate.md``.
CAMPAIGN_SENT_OPTIONAL_FIELDS: frozenset[str] = frozenset(
    {
        # Operator-supplied free-text label for the campaign creative.
        "campaign_name",
        # Reserved typed slot for the Swarm Deploy Agent / manual
        # operator to record the upstream provider message id.
        "provider_message_id",
        # Reserved typed slot for the Swarm Deploy Agent to record the
        # provider name (e.g. "klaviyo", "postscript"). Free-text in v1.
        "provider",
        # Operator-supplied notes; surfaces in inspect_memory output.
        "notes",
    }
)


@dataclass(frozen=True)
class CampaignSentPayload:
    """Payload for a ``campaign_sent`` substrate event.

    Written by ``tools/import_campaign_sent.py`` (single writer per the
    S-6 grep test) once per validated JSON file dropped under
    ``data/<store_id>/inbox/campaigns/``. The engine NEVER writes this
    event type — file boundary is the discipline (D-5 manual JSON
    import only).

    Pinned at ``event_version=1`` for the Sprint 3 Swarm-integration
    contract. Additive-only future evolution: new ``Optional`` fields
    may be added with safe defaults; no field may be removed or
    re-typed.

    Required fields:
      lineage_id:
        SHA1 hex of the recommendation lineage tuple per S-2
        ``compute_lineage_id``. Must match a ``lineage_id`` carried by
        an existing ``recommendation_emitted`` event in the same store
        (importer enforces this; orphan ``campaign_sent`` events are
        refused).
      recommendation_event_id:
        ``event_id`` of the originating ``recommendation_emitted``
        event. Must exist in the same store's ``events`` table.
      campaign_id:
        Operator-chosen identifier for the send. Unique within a store
        — duplicate ``campaign_id`` causes the importer to refuse the
        file. v1 is strict because de-dup logic upstream is the
        operator's responsibility, not the engine's.
      sent_at:
        ISO-8601 UTC timestamp the campaign was dispatched. Stored as
        a string; consumers parse on read.
      audience_size:
        Integer audience N at send time. Must be ``>= 0``.
      channel:
        One of ``CAMPAIGN_SENT_ALLOWED_CHANNELS``.

    Optional fields:
      campaign_name, provider, provider_message_id, notes — see
      ``CAMPAIGN_SENT_OPTIONAL_FIELDS``.
    """

    event_version: int
    lineage_id: str
    recommendation_event_id: str
    campaign_id: str
    sent_at: str
    audience_size: int
    channel: str
    campaign_name: Optional[str] = None
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "event_version": self.event_version,
            "lineage_id": self.lineage_id,
            "recommendation_event_id": self.recommendation_event_id,
            "campaign_id": self.campaign_id,
            "sent_at": self.sent_at,
            "audience_size": self.audience_size,
            "channel": self.channel,
        }
        if self.campaign_name is not None:
            out["campaign_name"] = self.campaign_name
        if self.provider is not None:
            out["provider"] = self.provider
        if self.provider_message_id is not None:
            out["provider_message_id"] = self.provider_message_id
        if self.notes is not None:
            out["notes"] = self.notes
        return out


__all__ = [
    "ExpectedDirection",
    "ExpectedOutcome",
    "EvidenceSnapshot",
    "RecommendationEmittedPayload",
    "RecommendationConsideredPayload",
    "RECOMMENDATION_EVENT_VERSION",
    "CampaignSentPayload",
    "CAMPAIGN_SENT_EVENT_VERSION",
    "CAMPAIGN_SENT_ALLOWED_CHANNELS",
    "CAMPAIGN_SENT_REQUIRED_FIELDS",
    "CAMPAIGN_SENT_OPTIONAL_FIELDS",
]
