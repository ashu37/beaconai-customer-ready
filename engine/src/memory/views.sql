-- S-5 — Substrate read-views.
--
-- Four views projected over the append-only events table from S-2.
-- All views are READ-ONLY by SQLite construction (no INSTEAD OF triggers
-- defined): a direct INSERT/UPDATE/DELETE against any view raises
-- ``sqlite3.OperationalError``. The forbidden-write acceptance test
-- pins this behaviour.
--
-- Ordering guarantee: every view that returns multiple rows orders by
-- ``created_seq`` (the canonical insertion-order field per S-2). Wall-
-- clock ``created_at`` is informational and may collide on fast systems;
-- consumers MUST treat ``created_seq`` as the source of truth.
--
-- Schema-freeze: column names below are part of the Sprint 2/3 freeze
-- contract for the Swarm team. Adding a column is additive; renaming or
-- removing one requires the same coordination as bumping
-- ``RECOMMENDATION_EVENT_VERSION``.

-- ---------------------------------------------------------------------------
-- v_lineage_timeline
--   Ordered event history per lineage_id. Rows for events whose
--   ``lineage_id`` is NULL are excluded — the timeline is per-lineage by
--   construction.
--
--   Columns:
--     lineage_id     TEXT     not null
--     created_seq    INTEGER  monotonic insertion order (S-2 invariant)
--     event_type     TEXT     e.g. recommendation_emitted, outcome_observed
--     payload_json   TEXT     canonical JSON payload (sort_keys, separators)
--
--   Ordering: lineage_id ASC, created_seq ASC.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_lineage_timeline AS
SELECT
    lineage_id,
    created_seq,
    event_type,
    payload_json
FROM events
WHERE lineage_id IS NOT NULL
ORDER BY lineage_id ASC, created_seq ASC;


-- ---------------------------------------------------------------------------
-- v_calibration_state
--   Projection of ``calibration_updated`` events into the contract dict
--   shape consumed by ``src/calibration_stub.py::load_realization_factors``:
--
--       {
--         "prior_overrides":       {prior_key: override_value},
--         "evidence_thresholds":   {play_id: {threshold_name: value}},
--         "materiality_overrides": {scale_band: {floor_param: value}},
--       }
--
--   Each calibration_updated event payload is expected to carry one of
--   the three keys above. The view returns ONE ROW PER calibration_updated
--   event, projecting:
--
--     created_seq   INTEGER  the event's insertion order
--     play_id       TEXT     scope (nullable for global overrides)
--     payload_json  TEXT     full event payload; helper code in
--                            ``src/memory/views.py::read_calibration_state``
--                            walks payloads in created_seq order, last-write-wins
--                            per (section, key) tuple.
--
--   With zero calibration_updated events present (today's state — no
--   writer ships before Phase 9), the view returns ZERO rows and the
--   helper returns the empty-shape dict, byte-identical to the stub's
--   pre-S-5 return value.
--
--   Ordering: created_seq ASC (last-write-wins requires this).
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_calibration_state AS
SELECT
    created_seq,
    play_id,
    payload_json
FROM events
WHERE event_type = 'calibration_updated'
ORDER BY created_seq ASC;


-- ---------------------------------------------------------------------------
-- v_open_recommendations
--   Most recent ``recommendation_emitted`` event per lineage_id that has
--   no later ``outcome_observed`` event for the same lineage_id.
--
--   "Most recent" is by ``created_seq``. "No matching outcome yet" is
--   defined as "no outcome_observed row exists for this lineage_id with
--   created_seq strictly greater than the emission's created_seq."
--
--   Columns:
--     lineage_id        TEXT     not null
--     run_id            TEXT     run that emitted
--     play_id           TEXT
--     emitted_seq       INTEGER  created_seq of the emission row
--     emitted_at        TEXT     wall-clock; informational
--     payload_json      TEXT     emission payload
--
--   Ordering: emitted_seq ASC.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_open_recommendations AS
SELECT
    e.lineage_id      AS lineage_id,
    e.run_id          AS run_id,
    e.play_id         AS play_id,
    e.created_seq     AS emitted_seq,
    e.created_at      AS emitted_at,
    e.payload_json    AS payload_json
FROM events e
WHERE e.event_type = 'recommendation_emitted'
  AND e.lineage_id IS NOT NULL
  AND e.created_seq = (
      SELECT MAX(e2.created_seq)
      FROM events e2
      WHERE e2.event_type = 'recommendation_emitted'
        AND e2.lineage_id = e.lineage_id
  )
  AND NOT EXISTS (
      SELECT 1
      FROM events o
      WHERE o.event_type = 'outcome_observed'
        AND o.lineage_id = e.lineage_id
        AND o.created_seq > e.created_seq
  )
ORDER BY e.created_seq ASC;


-- ---------------------------------------------------------------------------
-- v_lineage_recent_emissions
--   Fatigue-supporting count: number of ``recommendation_emitted`` rows
--   per lineage_id whose ``created_at`` falls within the last 28 days
--   relative to the most recent event in the table.
--
--   The "now" anchor is derived from the events table itself
--   (``MAX(created_at)``) rather than wall-clock so the view is
--   deterministic at test time and reproducible across runs. Production
--   callers that want a true wall-clock window should add their own
--   filter; the view is meant for the existing ``gate_recently_run``
--   shape, which compares within-store recency.
--
--   Columns:
--     lineage_id          TEXT     not null
--     count_in_last_28d   INTEGER  >= 1 (lineages with zero emissions in
--                                  the window are excluded)
--
--   Ordering: lineage_id ASC.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_lineage_recent_emissions AS
SELECT
    lineage_id,
    COUNT(*) AS count_in_last_28d
FROM events
WHERE event_type = 'recommendation_emitted'
  AND lineage_id IS NOT NULL
  AND created_at >= (
      SELECT datetime(MAX(created_at), '-28 days') FROM events
  )
GROUP BY lineage_id
ORDER BY lineage_id ASC;
