"""Priors loader (Milestone 6, T6.1).

Lazy-load ``config/priors.yaml`` once per process and expose a single
function, :func:`get_prior`, used by :mod:`src.sizing` to look up the
typed prior entry for a ``(play_id, prior_key)`` pair under a given
vertical / subvertical scope.

This module is the FIRST runtime consumer of ``config/priors.yaml``.
Through M2-M5 the file was config-only and intentionally not loaded.
Tests in ``tests/test_priors_yaml.py::test_yaml_not_loaded_at_runtime``
explicitly allow ``priors_loader.py`` to be the loader (it is the
exception listed there).

Design choices:

- **Cached** at module level (``_PRIORS_CACHE``). One load per process.
  The cache is keyed by file path so callers in tests can reset by
  invalidating the cache (see :func:`clear_cache`).
- **Pure read.** Never writes. Never mutates the YAML.
- **Conservative defaults.** If the file is missing, malformed, or a
  prior key is unknown, :func:`get_prior` returns ``None`` rather than
  raising. The caller (sizing) treats this as "no prior available" and
  marks the resulting ``revenue_range`` accordingly.
- **Resolution preference**: subvertical > vertical > "*" wildcard.
  When two entries match the same ``(play_id, name)`` slot, the more
  specific scope wins. Ties (e.g., two vertical-level entries for the
  same vertical) prefer the FIRST entry as authored in the YAML, which
  matches the lookup semantics encoded in ``test_priors_yaml.py``.

The loader does NOT validate cross-references against
``src.play_registry.PLAYS``. The registry tests already cover that
relationship; the loader is intentionally permissive.

Casing invariant (S7 priors-wiring, 2026-05-20)
-----------------------------------------------

**Casing follows authoring-source provenance.** Enum string values in
this module are NOT normalized to a single house style; each value
preserves the casing of the document that authored it. This is a
deliberate departure from a single-convention regime, adopted at S7
after the founder-spec memos added new archetypes whose authoring
source uses UPPER_SNAKE while the prior contract-Q3 archetypes use
lowercase.

The rule, verbatim:

    Contract-Q3 archetypes lowercase; founder-spec S7 archetypes
    UPPER_SNAKE; future additions cite source and follow its casing.

This applies to :class:`AudienceArchetype` specifically. A future
agent extending the enum MUST cite the authoring document in a
comment and match its casing. Do NOT migrate existing values to a
unified case; mixed-regime is the intended end state.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .engine_run import WouldBeMeasuredBy


# ---------------------------------------------------------------------------
# Path to the priors YAML.
# ---------------------------------------------------------------------------

# Default lookup path: ``<repo_root>/config/priors.yaml``. Computed once at
# import time; tests may pass an explicit ``path`` to :func:`get_prior` to
# load a fixture.
_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "priors.yaml"


# ---------------------------------------------------------------------------
# Cache + lock
# ---------------------------------------------------------------------------

_PRIORS_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Typed return shape
# ---------------------------------------------------------------------------


class PriorValidationStatus(str, Enum):
    """Sprint 7.5 Ticket T1: closed enum of per-prior validation provenance.

    Replaces the unsafe ``source_class``-only signal as the load-bearing
    contract that ``sizing.size_play`` (Sprint 7.5 T3) will read to decide
    whether to permit blending. Five values, exactly, per
    ARCHITECTURE_PLAN.md Part III-1 §III-1 Step 1:

    - ``validated_external``: backed by a public benchmark with a memo in
      ``config/priors_sources/`` (T2).
    - ``validated_internal``: backed by an internal reproducible CSV /
      script artifact in the repo (T1.5 / T2).
    - ``elicited_expert``: formally elicited from a domain expert with the
      elicitation captured in ``config/priors_sources/``.
    - ``heuristic_unvalidated``: engineer-typed YAML constant with no
      reproducible source. Default for every existing entry post-T1; the
      T3 flag refuses to blend on this value.
    - ``placeholder``: known-incomplete docstring / scaffold value (e.g.,
      ``first_to_second_purchase.second_purchase_lift``). T3 also
      refuses to blend on this value.

    Casing: lowercase values, matching the existing ``source_class``
    convention in ``config/priors.yaml``. The enum is closed; the loader
    raises :class:`PriorsValidationError` on any unknown string at parse
    time (closed-enum contract).
    """

    VALIDATED_EXTERNAL = "validated_external"
    VALIDATED_INTERNAL = "validated_internal"
    ELICITED_EXPERT = "elicited_expert"
    HEURISTIC_UNVALIDATED = "heuristic_unvalidated"
    PLACEHOLDER = "placeholder"


class PriorsValidationError(ValueError):
    """Raised when a prior entry's ``validation_status`` is not in the closed enum.

    Inherits from :class:`ValueError` so existing broad ``ValueError``
    catches in upstream callers continue to trip; named class lets new
    callers discriminate validation-status errors from other YAML
    failures (e.g., :class:`PriorsMetadataError`).
    """


@dataclass(frozen=True)
class PriorEntry:
    """One resolved prior. Returned by :func:`get_prior`.

    Mirrors the YAML keys but is typed for downstream consumers (sizing,
    tests). All numeric fields are floats; ``source_class`` is one of
    ``{"observational", "causal", "expert"}`` per the M2 schema.

    Sprint 7.5 Ticket T1 additive fields (all default to safe values so
    every existing YAML entry parses unchanged):

    - ``validation_status``: closed-enum provenance tag. Defaults to
      :attr:`PriorValidationStatus.HEURISTIC_UNVALIDATED` when the YAML
      entry omits the field (every pre-T1 entry).
    - ``source_artifact``: optional relative path (e.g.,
      ``config/priors_sources/<file>.md``) attesting the validation
      claim. Required by T2 invariant tests when ``validation_status in
      {validated_external, validated_internal}``.
    - ``effective_n``: optional underlying sample size for validated
      entries. Overrides the default per-status ``pseudo_N`` (added as a
      module constant in T3).
    """

    name: str
    value: float
    range_p10: float
    range_p90: float
    source_class: str
    last_updated: Optional[str] = None
    applies_to: Optional[Mapping[str, Any]] = None
    notes: Optional[str] = None
    play_id: Optional[str] = None
    validation_status: PriorValidationStatus = PriorValidationStatus.HEURISTIC_UNVALIDATED
    source_artifact: Optional[str] = None
    effective_n: Optional[int] = None


# ---------------------------------------------------------------------------
# Phase 6A Ticket A3: Per-play eligibility metadata.
#
# A play in ``config/priors.yaml`` may carry a ``metadata:`` block that
# encodes the small set of eligibility / mechanism fields needed by the
# Recommended Experiment slate (Ticket A4 onward). The metadata is loaded
# by :func:`get_play_metadata` and is typed via :class:`PlayMetadata`.
#
# Plays that DO NOT carry a metadata block continue to load through the
# legacy list form; :func:`get_play_metadata` returns ``None`` for them.
# This is intentional: A3 is purely additive and must not break loading
# of any play in the existing file.
# ---------------------------------------------------------------------------


class AudienceArchetype(str, Enum):
    """Loader-side enum of audience archetypes.

    Locked initial set, per the campaign-slate contract (Q3 of
    ``agent_outputs/implementation-manager-campaign-slate-plan.md``):
    ``{first_time_buyer, lapsed_buyer, discount_buyer, hero_sku_buyer,
    replenishment_buyer, full_price_buyer, vip_loyalist, no_archetype}``.

    Casing for the Contract-Q3 archetypes above is **lowercase** to
    match the campaign-slate contract spec (the contract consistently
    lists archetypes as lowercase strings: e.g. ``hero_sku_buyer``,
    ``discount_buyer``). This deviates from the A2
    ``WouldBeMeasuredBy`` UPPER_SNAKE_CASE convention because the
    contract pins the casing for archetypes specifically.

    Per the module-level casing invariant (S7 priors-wiring),
    casing now follows authoring-source provenance, not a unified
    house style: **Contract-Q3 archetypes lowercase; founder-spec S7
    archetypes UPPER_SNAKE; future additions cite source and follow
    its casing.** A future agent extending the enum must cite the
    authoring document and match its casing; do NOT migrate existing
    values.
    """

    FIRST_TIME_BUYER = "first_time_buyer"
    LAPSED_BUYER = "lapsed_buyer"
    DISCOUNT_BUYER = "discount_buyer"
    HERO_SKU_BUYER = "hero_sku_buyer"
    REPLENISHMENT_BUYER = "replenishment_buyer"
    # S6-T3.5 Prereq 1: ``cadence_due_repeat_buyer`` was authored in
    # ``config/priors.yaml`` at S6-T3.x for the ``replenishment_due``
    # metadata block but the enum was not extended at the same time —
    # latent until any caller asked for ``get_play_metadata("replenishment_due")``.
    # Storytelling_v2 + decide.py both lazy-import + swallow the
    # PriorsMetadataError silently, so the symptom is "mechanism line
    # never renders for replenishment_due" — defeats T3.z + T3.5
    # merchant-facing copy on the activation moment. Additive enum value
    # is schema-additive within ``event_version=1`` per A2 precedent.
    CADENCE_DUE_REPEAT_BUYER = "cadence_due_repeat_buyer"
    FULL_PRICE_BUYER = "full_price_buyer"
    VIP_LOYALIST = "vip_loyalist"
    NO_ARCHETYPE = "no_archetype"
    # Sprint 7 priors-wiring (2026-05-20) — additive within event_version=1
    # per A2 precedent. Authored alongside the priors.yaml metadata blocks
    # for ``discount_dependency_hygiene`` and ``aov_lift_via_threshold_bundle``
    # (cross-pinned via tests/test_s7_priors_enum_cross_pin.py). Casing is
    # UPPER_SNAKE_CASE to match the YAML-side authored strings; this
    # deviates from the rest of this enum's lowercase convention because
    # the founder spec for the S7 priors-wiring ticket explicitly mandates
    # UPPER_SNAKE_CASE on the YAML metadata side (do NOT normalize).
    DISCOUNT_CONDITIONED_REPEAT_BUYER = "DISCOUNT_CONDITIONED_REPEAT_BUYER"
    THRESHOLD_NEAR_BUYER = "THRESHOLD_NEAR_BUYER"


class PriorsMetadataError(ValueError):
    """Raised when a ``metadata:`` block in ``config/priors.yaml`` is malformed.

    Inherits from :class:`ValueError` so callers using the broader
    ``ValueError`` catch (e.g. existing schema-validation tests) still
    catch us. Carries a clear, named class for new callers that want to
    discriminate metadata-specific errors from other YAML failures.
    """


class ConfigError(ValueError):
    """Raised when ``config/priors.yaml`` carries a structurally invalid block.

    Sprint 1 Ticket B-7 (post-6B restructured plan): the engine's vertical
    scope is hard-locked at ``{beauty, supplements, mixed}``. The priors
    loader refuses to silently accept dead config: any top-level YAML key
    that is being interpreted as a ``vertical_mode`` (i.e. it sits in
    vertical-mode position alongside ``plays``, with a mapping value) but
    is NOT in the supported set raises :class:`ConfigError` with the
    offending key named in the message.

    Inherits from :class:`ValueError` so existing ``ValueError`` catches
    in upstream callers and tests will still trip.
    """


# ---------------------------------------------------------------------------
# Sprint 1 Ticket B-7: structural validation of top-level YAML keys.
# ---------------------------------------------------------------------------

# Top-level keys that are STRUCTURAL (i.e. not interpreted as a vertical_mode
# block). Any other top-level key whose value is a mapping is treated as
# being in vertical-mode position and must be in the supported set.
_STRUCTURAL_TOP_LEVEL_KEYS: frozenset = frozenset(
    {
        "schema_version",
        "last_reviewed",
        "plays",
    }
)

# Mirrors ``src.play_registry._ALL_VERTICALS``. Inlined here to avoid
# importing the play registry at loader-import time (the loader is
# called early; the play registry pulls in unrelated modules).
_SUPPORTED_VERTICALS_FOR_LOADER: frozenset = frozenset(
    {"beauty", "supplements", "mixed"}
)


def _validate_top_level_verticals(doc: Mapping[str, Any]) -> None:
    """Raise :class:`ConfigError` on any non-supported vertical block.

    A top-level key is interpreted as a ``vertical_mode`` block when:
      1. it is NOT in :data:`_STRUCTURAL_TOP_LEVEL_KEYS`, AND
      2. its value is a mapping (i.e. it looks like a config block,
         not a scalar metadata field).

    Such a key must be one of ``{beauty, supplements, mixed}`` (the
    vertical scope hard-lock per B-7). Any other key (e.g. ``apparel``,
    ``food_bev``, ``home``, ``wellness``) raises :class:`ConfigError`
    naming the offending key.

    Scalar non-structural keys (e.g. a future ``notes:`` string at the
    top level) are tolerated; they are not vertical_mode blocks.
    """

    if not isinstance(doc, dict):
        return
    for key, value in doc.items():
        if key in _STRUCTURAL_TOP_LEVEL_KEYS:
            continue
        if not isinstance(value, dict):
            # Scalar top-level keys are not interpreted as vertical_mode
            # blocks; they're either future structural fields or stray
            # scalar metadata. The caller may catch this elsewhere; we
            # don't refuse here.
            continue
        if str(key).lower() not in _SUPPORTED_VERTICALS_FOR_LOADER:
            raise ConfigError(
                f"config/priors.yaml: top-level vertical_mode block {key!r} "
                f"is not in the supported set "
                f"{sorted(_SUPPORTED_VERTICALS_FOR_LOADER)}. "
                f"Beacon's engine scope is hard-locked at "
                f"{{beauty, supplements, mixed}} (Sprint 1 Ticket B-7). "
                f"Remove the {key!r} block or escalate for a founder-level "
                f"scope decision."
            )


@dataclass(frozen=True)
class PlayMetadata:
    """Per-play eligibility metadata for the Recommended Experiment slate.

    Field semantics:

    - ``audience_floor``: minimum eligible-audience count for the play
      to surface as a Recommended Experiment. Strictly positive integer
      OR ``None`` for plays whose floor grid has not yet been founder-
      locked (e.g. S7 priors-wiring entries `discount_dependency_hygiene`
      and `aov_lift_via_threshold_bundle`, which land their floor cells
      in a separate founder-lock commit before the S7-T1 / S7-T3 builder
      ships).
    - ``mechanism``: human-readable description of what the play does
      and what it tracks. Non-empty string.
    - ``vertical_applicability``: list of vertical-name strings the play
      applies to (e.g. ``["beauty", "mixed"]``). Validated as a list of
      strings; canonical-set validation happens at the consume layer
      (Ticket A4+).
    - ``would_be_measured_by``: enum-backed outcome metric pinning what
      the experiment would measure. Reuses
      :class:`src.engine_run.WouldBeMeasuredBy` (Ticket A2).
    - ``audience_archetype``: enum-backed archetype label used by the
      slate-diversity rule (Ticket B5). Reuses
      :class:`AudienceArchetype` above.
    """

    audience_floor: Optional[int]
    mechanism: str
    vertical_applicability: List[str]
    would_be_measured_by: WouldBeMeasuredBy
    audience_archetype: AudienceArchetype
    # Sprint 4 Ticket G-3: optional per-vertical floor override.
    # ``audience_floor_by_vertical`` is a mapping from a vertical name in
    # ``{beauty, supplements, mixed}`` (D-8) to a positive int floor. When
    # absent or when a specific vertical key is missing, callers should
    # fall back to the scalar :attr:`audience_floor`. Adding the field is
    # purely additive — plays that never authored a per-vertical block
    # continue to load with ``audience_floor_by_vertical=None``.
    audience_floor_by_vertical: Optional[Dict[str, int]] = None


def _coerce_metadata_enum(enum_cls, value, *, play_id: str, field_name: str):
    """Coerce ``value`` into ``enum_cls`` or raise :class:`PriorsMetadataError`.

    Mirrors the ``_coerce_enum`` helper in :mod:`src.engine_run` but
    raises a metadata-named error class so test failures point at the
    YAML file rather than the engine schema.
    """

    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except (ValueError, TypeError) as exc:
        valid = sorted(m.value for m in enum_cls)
        raise PriorsMetadataError(
            f"plays[{play_id!r}].metadata.{field_name}={value!r} is not a valid "
            f"{enum_cls.__name__}; expected one of {valid}"
        ) from exc


# ---------------------------------------------------------------------------
# Loader internals
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load and parse the YAML file. Returns ``{}`` on any failure.

    The conservative-fallback policy is documented at the module level:
    a missing or malformed file should NOT crash the engine. The sizing
    module will treat an empty dict as "no priors available" and set
    ``revenue_range.suppressed = True`` for any play that needed a prior.
    """

    try:
        import yaml  # type: ignore[import-not-found]
    except Exception:
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if not isinstance(doc, dict):
            return {}
        return doc
    except Exception:
        return {}


def _key(path: Path) -> str:
    return str(path.resolve())


def load_priors(path: Optional[Path] = None) -> Dict[str, Any]:
    """Return the cached parsed YAML document (or ``{}`` on failure).

    Subsequent calls within a process re-use the cached document. To
    force a re-read from disk (tests), call :func:`clear_cache`.
    """

    p = Path(path) if path is not None else _DEFAULT_PATH
    cache_key = _key(p)
    with _LOCK:
        cached = _PRIORS_CACHE.get(cache_key)
        if cached is None:
            cached = _load_yaml(p)
            # Sprint 1 Ticket B-7: structural validation of top-level keys.
            # Raises ConfigError on any non-supported vertical block (e.g.
            # an ``apparel:`` block in vertical_mode position). Runs BEFORE
            # caching so a malformed YAML never gets cached as the parsed
            # document; clear_cache() in tests will let a fixed YAML re-load.
            _validate_top_level_verticals(cached)
            _PRIORS_CACHE[cache_key] = cached
    return cached


def clear_cache() -> None:
    """Clear the in-process cache. Tests use this to re-read the YAML."""

    with _LOCK:
        _PRIORS_CACHE.clear()


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _scope_specificity(applies_to: Optional[Mapping[str, Any]]) -> int:
    """Return a small integer rank: more-specific scope wins.

    Specificity ordering (higher number = more specific):
        3 = subvertical match
        2 = vertical match (non-wildcard)
        1 = vertical "*" wildcard
        0 = no applies_to provided / unmatched
    """

    if not applies_to:
        return 0
    if applies_to.get("subvertical"):
        return 3
    v = applies_to.get("vertical")
    if v and v != "*":
        return 2
    if v == "*":
        return 1
    return 0


def _matches_scope(
    applies_to: Optional[Mapping[str, Any]],
    *,
    vertical: Optional[str],
    subvertical: Optional[str],
) -> bool:
    """Return True if the prior's scope is compatible with the lookup."""

    if not applies_to:
        return True
    a_vert = applies_to.get("vertical")
    a_sub = applies_to.get("subvertical")
    # vertical match (or wildcard).
    if a_vert and a_vert != "*":
        if not vertical or str(vertical).lower() != str(a_vert).lower():
            return False
    # subvertical, when present in the prior, must match the lookup.
    if a_sub:
        if not subvertical or str(subvertical).lower() != str(a_sub).lower():
            return False
    return True


def _extract_play_block(
    doc: Mapping[str, Any], play_id: str
) -> Tuple[Optional[List[Any]], Optional[Mapping[str, Any]]]:
    """Return ``(priors_list, metadata_dict)`` for a play_id.

    A play in ``config/priors.yaml`` has one of two shapes:

    1. **Legacy list form** (every play prior to Phase 6A):
       ``plays.<play_id>: [ <prior_dict>, ... ]``. The metadata dict is
       ``None``.
    2. **Dict form** (Phase 6A Ticket A3 onward, opt-in per play):
       ``plays.<play_id>: { metadata: {...}, priors: [ <prior_dict>, ... ] }``.

    Either ``priors_list`` or ``metadata_dict`` may be ``None`` if the
    play is missing or malformed, but both being non-``None`` is the
    typical Ticket A3 case.
    """

    plays = doc.get("plays") if isinstance(doc, dict) else None
    if not isinstance(plays, dict):
        return None, None
    raw = plays.get(play_id)
    if raw is None:
        return None, None
    if isinstance(raw, list):
        return raw, None
    if isinstance(raw, dict):
        priors = raw.get("priors")
        if not isinstance(priors, list):
            priors = None
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = None
        return priors, metadata
    return None, None


def _coerce_validation_status(
    raw_value: Any, *, play_id: str, prior_name: str
) -> PriorValidationStatus:
    """Coerce a YAML ``validation_status`` string into the closed enum.

    - Missing / ``None`` → :attr:`PriorValidationStatus.HEURISTIC_UNVALIDATED`
      (additive default; every existing pre-T1 entry parses unchanged).
    - Valid enum string → matching enum member.
    - Unknown string → :class:`PriorsValidationError` naming the offending
      ``(play_id, prior_name, value)`` triple and the closed set. The
      closed-enum contract is load-bearing for the T3 refusal rule:
      silently coercing an unknown string would defeat the contract.
    """

    if raw_value is None:
        return PriorValidationStatus.HEURISTIC_UNVALIDATED
    if isinstance(raw_value, PriorValidationStatus):
        return raw_value
    try:
        return PriorValidationStatus(raw_value)
    except (ValueError, TypeError) as exc:
        valid = sorted(m.value for m in PriorValidationStatus)
        raise PriorsValidationError(
            f"plays[{play_id!r}] prior {prior_name!r}: validation_status="
            f"{raw_value!r} is not in the closed set {valid}"
        ) from exc


def _coerce_effective_n(raw_value: Any) -> Optional[int]:
    """Coerce ``effective_n`` to a positive ``int`` or ``None``.

    Tolerant policy: any value that does not cleanly coerce to a positive
    int (None, missing, bool, non-numeric, ``<= 0``) yields ``None``.
    Closed-enum strictness applies to ``validation_status`` only; the
    sample size is metadata for the T3 ``pseudo_N`` override and the
    safe default is "no override".
    """

    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        return None
    try:
        n = int(raw_value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return n


def _coerce_source_artifact(raw_value: Any) -> Optional[str]:
    """Coerce ``source_artifact`` to a stripped non-empty string or ``None``."""

    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        return None
    stripped = raw_value.strip()
    if not stripped:
        return None
    return stripped


def _coerce_entry(play_id: str, raw: Mapping[str, Any]) -> Optional[PriorEntry]:
    """Convert a raw prior dict into a typed :class:`PriorEntry`. Lossy on bad rows.

    Sprint 7.5 T1: closed-enum violations on ``validation_status`` are
    NOT lossy — they raise :class:`PriorsValidationError`. The
    closed-enum contract is the whole point of T1; silent coercion to
    the default would defeat the T3 refusal rule.
    """

    try:
        name = str(raw["name"])
        value = float(raw["value"])
        range_p10 = float(raw["range_p10"])
        range_p90 = float(raw["range_p90"])
    except (KeyError, TypeError, ValueError):
        return None

    # Closed-enum coercion happens outside the broad-catch so unknown
    # strings raise rather than getting swallowed as "malformed row".
    validation_status = _coerce_validation_status(
        raw.get("validation_status"), play_id=play_id, prior_name=name
    )

    return PriorEntry(
        name=name,
        value=value,
        range_p10=range_p10,
        range_p90=range_p90,
        source_class=str(raw.get("source_class", "expert")),
        last_updated=raw.get("last_updated"),
        applies_to=raw.get("applies_to") or {},
        notes=raw.get("notes"),
        play_id=play_id,
        validation_status=validation_status,
        source_artifact=_coerce_source_artifact(raw.get("source_artifact")),
        effective_n=_coerce_effective_n(raw.get("effective_n")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_prior(
    play_id: str,
    *,
    vertical: Optional[str] = None,
    subvertical: Optional[str] = None,
    key: str,
    path: Optional[Path] = None,
) -> Optional[PriorEntry]:
    """Look up the most-specific prior for ``(play_id, key)``.

    Returns the matching :class:`PriorEntry`, or ``None`` if no prior is
    registered for that pair (or the YAML failed to load). Resolution
    preference: subvertical > vertical > wildcard. Ties prefer the
    earlier entry as authored in the YAML.

    The lookup is intentionally tolerant. A malformed entry is skipped
    rather than raising. This is the conservative-fallback policy
    described in the module docstring.
    """

    doc = load_priors(path)
    rows, _ = _extract_play_block(doc, play_id)
    if not isinstance(rows, list):
        return None

    best: Optional[PriorEntry] = None
    best_rank = -1
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("name") or "") != str(key):
            continue
        if not _matches_scope(raw.get("applies_to"), vertical=vertical, subvertical=subvertical):
            continue
        rank = _scope_specificity(raw.get("applies_to"))
        if rank > best_rank:
            entry = _coerce_entry(play_id, raw)
            if entry is None:
                continue
            best = entry
            best_rank = rank
    return best


def list_priors_for_play(
    play_id: str,
    *,
    path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return the raw list of prior dicts for a play_id (or [])."""

    doc = load_priors(path)
    rows, _ = _extract_play_block(doc, play_id)
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


_REQUIRED_METADATA_KEYS = (
    "audience_floor",
    "mechanism",
    "vertical_applicability",
    "would_be_measured_by",
    "audience_archetype",
)


def _coerce_metadata(play_id: str, raw: Mapping[str, Any]) -> PlayMetadata:
    """Convert a raw ``metadata:`` dict into a typed :class:`PlayMetadata`.

    Raises :class:`PriorsMetadataError` (a :class:`ValueError` subclass)
    on missing keys, invalid types, or invalid enum strings.

    Required keys: ``audience_floor`` (positive int), ``mechanism``
    (non-empty string), ``vertical_applicability`` (list of strings),
    ``would_be_measured_by`` (:class:`WouldBeMeasuredBy` enum string),
    ``audience_archetype`` (:class:`AudienceArchetype` enum string).
    """

    missing = [k for k in _REQUIRED_METADATA_KEYS if k not in raw]
    if missing:
        raise PriorsMetadataError(
            f"plays[{play_id!r}].metadata missing required keys: {sorted(missing)}"
        )

    audience_floor = raw["audience_floor"]
    # S7 priors-wiring (2026-05-20): `None` is a legal authored value for
    # plays whose floor grid has not yet been founder-locked. Consumers
    # of `get_audience_floor` already handle `None` by falling back to the
    # caller's legacy default. The positive-int validation remains in
    # force when a value is actually authored.
    if audience_floor is not None:
        if isinstance(audience_floor, bool) or not isinstance(audience_floor, int):
            raise PriorsMetadataError(
                f"plays[{play_id!r}].metadata.audience_floor must be a positive int or null; "
                f"got {audience_floor!r} ({type(audience_floor).__name__})"
            )
        if audience_floor <= 0:
            raise PriorsMetadataError(
                f"plays[{play_id!r}].metadata.audience_floor must be > 0; "
                f"got {audience_floor}"
            )

    mechanism = raw["mechanism"]
    if not isinstance(mechanism, str) or not mechanism.strip():
        raise PriorsMetadataError(
            f"plays[{play_id!r}].metadata.mechanism must be a non-empty string; "
            f"got {mechanism!r}"
        )

    vertical_applicability = raw["vertical_applicability"]
    if not isinstance(vertical_applicability, list) or not all(
        isinstance(v, str) and v.strip() for v in vertical_applicability
    ):
        raise PriorsMetadataError(
            f"plays[{play_id!r}].metadata.vertical_applicability must be a list "
            f"of non-empty strings; got {vertical_applicability!r}"
        )

    would_be = _coerce_metadata_enum(
        WouldBeMeasuredBy,
        raw["would_be_measured_by"],
        play_id=play_id,
        field_name="would_be_measured_by",
    )
    archetype = _coerce_metadata_enum(
        AudienceArchetype,
        raw["audience_archetype"],
        play_id=play_id,
        field_name="audience_archetype",
    )

    # G-3: optional ``audience_floor_by_vertical`` mapping.
    by_vertical_raw = raw.get("audience_floor_by_vertical")
    audience_floor_by_vertical: Optional[Dict[str, int]] = None
    if by_vertical_raw is not None:
        if not isinstance(by_vertical_raw, dict) or not by_vertical_raw:
            raise PriorsMetadataError(
                f"plays[{play_id!r}].metadata.audience_floor_by_vertical must be a "
                f"non-empty mapping of {{vertical: int}}; got {by_vertical_raw!r}"
            )
        coerced: Dict[str, int] = {}
        for vk, vv in by_vertical_raw.items():
            if not isinstance(vk, str) or not vk.strip():
                raise PriorsMetadataError(
                    f"plays[{play_id!r}].metadata.audience_floor_by_vertical "
                    f"has a non-string vertical key {vk!r}"
                )
            vk_lc = vk.strip().lower()
            if vk_lc not in _SUPPORTED_VERTICALS_FOR_LOADER:
                raise PriorsMetadataError(
                    f"plays[{play_id!r}].metadata.audience_floor_by_vertical key "
                    f"{vk!r} is not in the supported vertical set "
                    f"{sorted(_SUPPORTED_VERTICALS_FOR_LOADER)} (D-8)."
                )
            if isinstance(vv, bool) or not isinstance(vv, int) or vv <= 0:
                raise PriorsMetadataError(
                    f"plays[{play_id!r}].metadata.audience_floor_by_vertical[{vk!r}] "
                    f"must be a positive int; got {vv!r}"
                )
            coerced[vk_lc] = int(vv)
        audience_floor_by_vertical = coerced

    return PlayMetadata(
        audience_floor=(int(audience_floor) if audience_floor is not None else None),
        mechanism=mechanism,
        vertical_applicability=list(vertical_applicability),
        would_be_measured_by=would_be,
        audience_archetype=archetype,
        audience_floor_by_vertical=audience_floor_by_vertical,
    )


def get_play_metadata(
    play_id: str,
    *,
    path: Optional[Path] = None,
) -> Optional[PlayMetadata]:
    """Return the typed metadata for ``play_id`` or ``None``.

    Plays that do not carry a ``metadata:`` block (the legacy list form,
    every play prior to Phase 6A) return ``None``. Plays that DO carry a
    block must validate cleanly; malformed blocks raise
    :class:`PriorsMetadataError`. Unknown ``play_id``s also return
    ``None`` (callers should not need to know whether a play exists).
    """

    doc = load_priors(path)
    _, metadata = _extract_play_block(doc, play_id)
    if metadata is None:
        return None
    return _coerce_metadata(play_id, metadata)


def schema_version(path: Optional[Path] = None) -> Optional[str]:
    """Return the priors-file ``schema_version`` (or ``None``)."""

    doc = load_priors(path)
    if not isinstance(doc, dict):
        return None
    v = doc.get("schema_version")
    return str(v) if v is not None else None


# ---------------------------------------------------------------------------
# Phase 6B Ticket C1 — typed mechanism accessor
# ---------------------------------------------------------------------------


def get_mechanism(
    play_id: str,
    *,
    vertical: Optional[str] = None,
    subvertical: Optional[str] = None,
    path: Optional[Path] = None,
) -> Optional[str]:
    """Return the merchant-readable ``mechanism`` string for ``play_id``, or ``None``.

    Phase 6B Ticket C1: small typed accessor that surfaces the
    already-loaded ``metadata.mechanism`` field from ``config/priors.yaml``
    for the V2 renderer ("What we'd send:" line). Routes through the
    existing :func:`_extract_play_block` path and reuses
    :func:`get_play_metadata` so the dual list/dict YAML form (Phase 6A
    Ticket A3) is honored without bypass.

    Resolution policy:

    - Plays carrying a ``metadata:`` block in ``config/priors.yaml`` (see
      :func:`get_play_metadata`) return their authored mechanism string.
    - Plays without a metadata block (legacy list form) return ``None``.
      The renderer treats ``None`` as "omit the line entirely" — silence
      is preferable to hallucination.
    - An empty / whitespace-only mechanism (defensive; current YAML
      validates against this) also returns ``None``.

    The ``vertical`` / ``subvertical`` kwargs are accepted for forward
    compatibility with the per-vertical scope keys already used by
    :func:`get_prior`. Today the metadata block is per-play (not
    vertically scoped); these kwargs are no-ops. A future YAML schema
    change that introduces per-vertical mechanism overrides would
    extend this function without breaking the call site.

    This function is conservatively non-raising: a malformed metadata
    block would raise from :func:`get_play_metadata`; we only call into
    that path when there is a metadata block to coerce, and we let the
    raise surface so the YAML can be fixed at content-author time. The
    renderer site already guards via ``Optional[str]`` so any string
    return is renderable directly.
    """

    del vertical, subvertical  # Forward-compatible; not used today.

    metadata = get_play_metadata(play_id, path=path)
    if metadata is None:
        return None
    mechanism = metadata.mechanism
    if not isinstance(mechanism, str):
        return None
    if not mechanism.strip():
        return None
    return mechanism


# ---------------------------------------------------------------------------
# Sprint 4 Ticket G-3 — per-vertical audience floor + mixed-blend resolver
# ---------------------------------------------------------------------------


def get_audience_floor(
    play_id: str,
    *,
    vertical: Optional[str] = None,
    path: Optional[Path] = None,
) -> Optional[int]:
    """Return the effective ``audience_floor`` for ``(play_id, vertical)``.

    Resolution policy (G-3):

    1. Load the play's :class:`PlayMetadata`. Plays without a metadata
       block return ``None`` (caller falls back to its legacy default,
       e.g. ``MIN_N_SKU``).
    2. If ``audience_floor_by_vertical`` is authored and the specific
       vertical key is present, return that value.
    3. Otherwise fall back to the scalar :attr:`PlayMetadata.audience_floor`.

    The ``vertical`` argument is case-insensitive and trimmed; unknown
    verticals (already refused by B-7 at engine entry) fall through to
    the scalar floor — they do NOT raise here.
    """

    metadata = get_play_metadata(play_id, path=path)
    if metadata is None:
        return None
    by_vert = getattr(metadata, "audience_floor_by_vertical", None) or {}
    if vertical is not None:
        v_lc = str(vertical).strip().lower()
        if v_lc in by_vert:
            try:
                return int(by_vert[v_lc])
            except (TypeError, ValueError):
                pass
    try:
        return int(metadata.audience_floor)
    except (TypeError, ValueError):
        return None


def resolve_mixed_prior(
    play_id: str,
    *,
    key: str,
    path: Optional[Path] = None,
) -> Optional[PriorEntry]:
    """Return the prior to use for ``vertical_mode="mixed"`` (G-3).

    Mixed semantics (D-8): ``mixed`` is the literal beauty+supplements
    blend, NOT a fallback for unknown verticals. This function formalises
    the contract:

    1. If an explicit ``vertical: mixed`` entry is authored in
       ``config/priors.yaml`` for ``(play_id, key)``, return it
       unchanged. The author has the final say.
    2. Otherwise, blend the beauty entry and the supplements entry
       50/50 deterministically. The blended entry's ``value`` /
       ``range_p10`` / ``range_p90`` are arithmetic means of the two
       inputs; ``source_class`` is downgraded to the more conservative
       of the two (``expert`` > ``observational`` > ``causal`` per the
       module docstring's conservative ordering); ``last_updated`` /
       ``notes`` are dropped (the blend is loader-derived, not
       author-attested).
    3. If either input is missing, the loader REFUSES to silently fall
       back to the present side (the D-8 hard guarantee — never default
       to beauty alone). Returns ``None`` instead; callers should treat
       this as "no prior available" and conservatively suppress the
       :attr:`revenue_range`.

    A wildcard ``vertical: "*"`` entry, when present, is honored before
    invoking the blend (it is the author's explicit "applies to all"
    statement, which is broader than "mixed").
    """

    # Step 0: an explicit ``vertical: "*"`` entry already returns from
    # :func:`get_prior` because the wildcard matches any vertical at
    # specificity rank 1. So an explicit mixed entry (rank 2) wins over
    # wildcard (rank 1). The blending path below is only invoked when
    # neither an explicit mixed nor a wildcard entry exists.
    explicit_or_wildcard = get_prior(
        play_id, vertical="mixed", key=key, path=path
    )
    if explicit_or_wildcard is not None:
        # If applies_to.vertical == "mixed" → authored mixed entry.
        # If applies_to.vertical == "*" → wildcard, also acceptable
        # (it's the author's "applies to all" statement, broader than
        # the blend would produce). Return as-is.
        return explicit_or_wildcard

    # Step 1: blend beauty + supplements.
    beauty_entry = get_prior(play_id, vertical="beauty", key=key, path=path)
    supp_entry = get_prior(play_id, vertical="supplements", key=key, path=path)

    if beauty_entry is None or supp_entry is None:
        # D-8 hard guarantee: never silently fall back to beauty alone.
        # Returning None forces the caller to treat this as "no prior"
        # rather than absorbing the present side.
        return None

    # Conservative source_class ordering: expert > observational > causal.
    _CONSERVATIVE_RANK = {"expert": 2, "observational": 1, "causal": 0}
    a_rank = _CONSERVATIVE_RANK.get(beauty_entry.source_class, 2)
    b_rank = _CONSERVATIVE_RANK.get(supp_entry.source_class, 2)
    if a_rank >= b_rank:
        blended_class = beauty_entry.source_class
    else:
        blended_class = supp_entry.source_class

    # Sprint 7.5 Ticket T3 (KI-19 conservative-min rule on validation_status):
    # the blended PriorEntry MUST carry the LESS validated of the two sides.
    # This prevents silent upgrades through the mixed blend (e.g. a
    # validated_external beauty entry + a heuristic_unvalidated supplements
    # entry must NOT mint a validated_external mixed prior). When either
    # side is HEURISTIC_UNVALIDATED or PLACEHOLDER, the blended entry
    # inherits that status; under the T3 flag-on sizing rule this causes
    # the mixed prior to be refused at the sizing seam — the same refusal
    # path the per-vertical priors take.
    _VALIDATION_RANK = {
        PriorValidationStatus.PLACEHOLDER: 0,
        PriorValidationStatus.HEURISTIC_UNVALIDATED: 1,
        PriorValidationStatus.ELICITED_EXPERT: 2,
        PriorValidationStatus.VALIDATED_INTERNAL: 3,
        PriorValidationStatus.VALIDATED_EXTERNAL: 4,
    }
    a_v = _VALIDATION_RANK.get(
        beauty_entry.validation_status, _VALIDATION_RANK[PriorValidationStatus.HEURISTIC_UNVALIDATED]
    )
    b_v = _VALIDATION_RANK.get(
        supp_entry.validation_status, _VALIDATION_RANK[PriorValidationStatus.HEURISTIC_UNVALIDATED]
    )
    blended_validation = (
        beauty_entry.validation_status if a_v <= b_v else supp_entry.validation_status
    )

    return PriorEntry(
        name=key,
        value=(beauty_entry.value + supp_entry.value) / 2.0,
        range_p10=(beauty_entry.range_p10 + supp_entry.range_p10) / 2.0,
        range_p90=(beauty_entry.range_p90 + supp_entry.range_p90) / 2.0,
        source_class=blended_class,
        last_updated=None,
        applies_to={"vertical": "mixed", "derived_from": ["beauty", "supplements"]},
        notes="Derived 50/50 blend of beauty+supplements (G-3 mixed semantics).",
        play_id=play_id,
        validation_status=blended_validation,
        source_artifact=None,
        effective_n=None,
    )


__all__ = [
    "PriorEntry",
    "PriorValidationStatus",
    "PriorsValidationError",
    "PlayMetadata",
    "AudienceArchetype",
    "PriorsMetadataError",
    "ConfigError",
    "load_priors",
    "clear_cache",
    "get_prior",
    "list_priors_for_play",
    "get_play_metadata",
    "get_mechanism",
    "get_audience_floor",
    "resolve_mixed_prior",
    "schema_version",
]
