"""S-6 — Manual ``campaign_sent`` import path acceptance tests.

Pins the Swarm-integration contract:

1. **Schema validation refusals** — malformed JSON, missing required
   fields, unknown fields, lineage_id not matching any
   recommendation_emitted, duplicate campaign_id, channel enum
   violation, audience_size type/sign violations.
2. **Two-run integration** — T0 produces recommendation_emitted via
   the substrate; manual import drops a valid campaign_sent JSON;
   ``v_lineage_timeline`` for that lineage_id returns
   ``[recommendation_emitted, campaign_sent]`` in created_seq order;
   T1 engine still runs identically (engine never reads
   campaign_sent events).
3. **Single-writer grep** for ``campaign_sent`` is enforced separately
   by ``tests/test_single_writer_per_event_type.py``; this module
   does not duplicate that.

The CLI surface (``main()``) is exercised end-to-end, including
exit-code semantics under ``--strict`` (default) vs ``--no-strict``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.memory import (
    open_memory,
    read_lineage_timeline,
)
from src.memory.events import CAMPAIGN_SENT_EVENT_VERSION
from tools.import_campaign_sent import (
    CAMPAIGN_SENT_EVENT_TYPE,
    _validate_payload_shape,
    import_inbox,
    import_one,
    main as cli_main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_recommendation(
    store, *, lineage_id: str = "lin_a", play_id: str = "discount_hygiene"
) -> str:
    """Seed one ``recommendation_emitted`` event; return its event_id."""
    return store.append_event(
        event_type="recommendation_emitted",
        payload={
            "event_version": 1,
            "lineage_id": lineage_id,
            "play_id": play_id,
            "store_id": store.store_id,
            "audience_definition_id": "aud_a",
            "audience_definition_version": 1,
            "role": "recommendation",
        },
        lineage_id=lineage_id,
        play_id=play_id,
        audience_definition_id="aud_a",
        audience_definition_version=1,
        run_id="run_t0",
    )


def _good_payload(
    *,
    lineage_id: str = "lin_a",
    rec_event_id: str,
    campaign_id: str = "camp_001",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = {
        "lineage_id": lineage_id,
        "recommendation_event_id": rec_event_id,
        "campaign_id": campaign_id,
        "sent_at": "2026-05-10T12:00:00Z",
        "audience_size": 1247,
        "channel": "email",
    }
    if extra:
        out.update(extra)
    return out


def _drop(inbox: Path, name: str, payload: Any) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    p = inbox / name
    if isinstance(payload, str):
        p.write_text(payload, encoding="utf-8")
    else:
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def store_env(tmp_path: Path):
    """Per-test store + inbox under an isolated tempdir base."""
    base = tmp_path / "data"
    store_id = "test_store"
    store = open_memory(store_id, base=base)
    inbox = base / store_id / "inbox" / "campaigns"
    yield {"store": store, "store_id": store_id, "base": base, "inbox": inbox}
    store.close()


# ---------------------------------------------------------------------------
# Schema validation (pure shape checks)
# ---------------------------------------------------------------------------


class TestValidateShape:
    def test_accepts_valid_minimal_payload(self):
        payload, err = _validate_payload_shape(
            _good_payload(rec_event_id="rec1")
        )
        assert err is None
        assert payload is not None
        assert payload.event_version == CAMPAIGN_SENT_EVENT_VERSION
        assert payload.audience_size == 1247

    def test_refuses_non_object_top_level(self):
        _, err = _validate_payload_shape([1, 2, 3])
        assert err is not None and "object" in err

    def test_refuses_missing_required_field(self):
        bad = _good_payload(rec_event_id="r")
        del bad["channel"]
        _, err = _validate_payload_shape(bad)
        assert err is not None and "channel" in err

    def test_refuses_unknown_field_strict_v1(self):
        bad = _good_payload(rec_event_id="r", extra={"future_field": "x"})
        _, err = _validate_payload_shape(bad)
        assert err is not None and "unknown" in err and "future_field" in err

    def test_refuses_bad_channel_enum(self):
        bad = _good_payload(rec_event_id="r")
        bad["channel"] = "fax"
        _, err = _validate_payload_shape(bad)
        assert err is not None and "channel" in err

    def test_refuses_negative_audience_size(self):
        bad = _good_payload(rec_event_id="r")
        bad["audience_size"] = -1
        _, err = _validate_payload_shape(bad)
        assert err is not None and "audience_size" in err

    def test_refuses_audience_size_bool(self):
        bad = _good_payload(rec_event_id="r")
        bad["audience_size"] = True
        _, err = _validate_payload_shape(bad)
        assert err is not None and "audience_size" in err

    def test_refuses_empty_required_string(self):
        bad = _good_payload(rec_event_id="r")
        bad["lineage_id"] = ""
        _, err = _validate_payload_shape(bad)
        assert err is not None and "lineage_id" in err

    def test_accepts_optional_fields(self):
        good = _good_payload(
            rec_event_id="r",
            extra={
                "campaign_name": "May VIP push",
                "provider": "klaviyo",
                "provider_message_id": "kl_abc",
                "notes": "manual import",
            },
        )
        payload, err = _validate_payload_shape(good)
        assert err is None and payload is not None
        assert payload.provider == "klaviyo"


# ---------------------------------------------------------------------------
# Substrate cross-checks
# ---------------------------------------------------------------------------


class TestSubstrateCrossChecks:
    def test_imports_valid_campaign(self, store_env):
        store = store_env["store"]
        rid = _seed_recommendation(store)
        path = _drop(
            store_env["inbox"],
            "valid.json",
            _good_payload(rec_event_id=rid),
        )
        outcome = import_one(path, store)
        assert outcome.status == "imported"
        assert outcome.event_id is not None
        # Event landed.
        rows = store.query_events(event_type=CAMPAIGN_SENT_EVENT_TYPE)
        assert len(rows) == 1
        assert rows[0]["payload"]["campaign_id"] == "camp_001"

    def test_refuses_orphan_lineage(self, store_env):
        store = store_env["store"]
        # No recommendation seeded.
        path = _drop(
            store_env["inbox"],
            "orphan.json",
            _good_payload(rec_event_id="missing"),
        )
        outcome = import_one(path, store)
        assert outcome.status == "refused"
        assert "lineage_id" in (outcome.reason or "")

    def test_refuses_unknown_recommendation_event_id(self, store_env):
        store = store_env["store"]
        _seed_recommendation(store)
        # Lineage matches but event_id doesn't.
        path = _drop(
            store_env["inbox"],
            "wrong_rec.json",
            _good_payload(rec_event_id="not_a_real_event_id"),
        )
        outcome = import_one(path, store)
        assert outcome.status == "refused"
        assert "recommendation_event_id" in (outcome.reason or "")

    def test_refuses_recommendation_event_id_mismatched_lineage(self, store_env):
        store = store_env["store"]
        rid_a = _seed_recommendation(store, lineage_id="lin_a")
        # Seed a second lineage so we have a second event.
        _seed_recommendation(store, lineage_id="lin_b", play_id="bestseller_amplify")
        # Pair lineage lin_b with rid_a (which is lin_a).
        path = _drop(
            store_env["inbox"],
            "wrong_pair.json",
            _good_payload(lineage_id="lin_b", rec_event_id=rid_a),
        )
        outcome = import_one(path, store)
        assert outcome.status == "refused"
        assert "lineage_id" in (outcome.reason or "")

    def test_refuses_duplicate_campaign_id(self, store_env):
        store = store_env["store"]
        rid = _seed_recommendation(store)
        path1 = _drop(
            store_env["inbox"],
            "first.json",
            _good_payload(rec_event_id=rid, campaign_id="dup"),
        )
        path2 = _drop(
            store_env["inbox"],
            "second.json",
            _good_payload(rec_event_id=rid, campaign_id="dup"),
        )
        first = import_one(path1, store)
        second = import_one(path2, store)
        assert first.status == "imported"
        assert second.status == "refused"
        assert "duplicate" in (second.reason or "")

    def test_refuses_malformed_json(self, store_env):
        store = store_env["store"]
        _seed_recommendation(store)
        path = _drop(store_env["inbox"], "bad.json", "{not valid json")
        outcome = import_one(path, store)
        assert outcome.status == "refused"
        assert "JSON" in (outcome.reason or "")

    def test_dry_run_does_not_append(self, store_env):
        store = store_env["store"]
        rid = _seed_recommendation(store)
        path = _drop(
            store_env["inbox"],
            "dry.json",
            _good_payload(rec_event_id=rid),
        )
        outcome = import_one(path, store, dry_run=True)
        assert outcome.status == "dry_run_ok"
        rows = store.query_events(event_type=CAMPAIGN_SENT_EVENT_TYPE)
        assert rows == []


# ---------------------------------------------------------------------------
# Inbox-level + CLI
# ---------------------------------------------------------------------------


class TestImportInbox:
    def test_inbox_processes_lex_order(self, store_env):
        store = store_env["store"]
        rid = _seed_recommendation(store)
        # Drop in reverse order on disk; importer processes lex.
        _drop(store_env["inbox"], "b.json",
              _good_payload(rec_event_id=rid, campaign_id="c_b"))
        _drop(store_env["inbox"], "a.json",
              _good_payload(rec_event_id=rid, campaign_id="c_a"))
        store.close()  # importer reopens
        outcomes = import_inbox(
            store_env["store_id"], base=store_env["base"]
        )
        assert [o.path.name for o in outcomes] == ["a.json", "b.json"]
        assert all(o.status == "imported" for o in outcomes)

    def test_empty_inbox_returns_empty(self, store_env):
        store_env["inbox"].mkdir(parents=True, exist_ok=True)
        store_env["store"].close()
        outcomes = import_inbox(
            store_env["store_id"], base=store_env["base"]
        )
        assert outcomes == []


class TestCli:
    def test_cli_strict_exit_1_on_refusal(self, store_env, capsys):
        store_env["store"].close()
        # Drop an invalid file; no recommendation seeded → refused.
        _drop(store_env["inbox"], "x.json",
              _good_payload(rec_event_id="missing"))
        rc = cli_main([
            store_env["store_id"], "--base", str(store_env["base"]),
        ])
        assert rc == 1
        out = capsys.readouterr().out
        assert "[refused]" in out

    def test_cli_no_strict_exit_0_on_refusal(self, store_env, capsys):
        store_env["store"].close()
        _drop(store_env["inbox"], "x.json",
              _good_payload(rec_event_id="missing"))
        rc = cli_main([
            store_env["store_id"], "--base", str(store_env["base"]),
            "--no-strict",
        ])
        assert rc == 0


# ---------------------------------------------------------------------------
# Two-run integration: timeline ordering, engine read-isolation
# ---------------------------------------------------------------------------


class TestTwoRunIntegration:
    def test_timeline_returns_emitted_then_sent(self, store_env):
        """T0: seed recommendation_emitted. Manual import drops
        campaign_sent. T1 reads ``v_lineage_timeline`` for the lineage
        and gets [recommendation_emitted, campaign_sent] in
        ``created_seq`` order.
        """
        store = store_env["store"]
        # T0: three recommendations like the ticket calls out.
        rid_a = _seed_recommendation(store, lineage_id="lin_a", play_id="play_a")
        _seed_recommendation(store, lineage_id="lin_b", play_id="play_b")
        _seed_recommendation(store, lineage_id="lin_c", play_id="play_c")

        # Manual import drops a campaign for lineage lin_a only.
        _drop(
            store_env["inbox"],
            "send_a.json",
            _good_payload(lineage_id="lin_a", rec_event_id=rid_a),
        )
        store.close()
        outcomes = import_inbox(
            store_env["store_id"], base=store_env["base"]
        )
        assert [o.status for o in outcomes] == ["imported"]

        # T1: read the timeline view.
        store2 = open_memory(store_env["store_id"], base=store_env["base"])
        try:
            timeline = read_lineage_timeline(store2, lineage_id="lin_a")
        finally:
            store2.close()
        types_in_order = [r["event_type"] for r in timeline]
        assert types_in_order == ["recommendation_emitted", "campaign_sent"]
        # created_seq strictly increasing.
        seqs = [r["created_seq"] for r in timeline]
        assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
        # Other lineages untouched (only their emission, no campaign).
        store3 = open_memory(store_env["store_id"], base=store_env["base"])
        try:
            tl_b = read_lineage_timeline(store3, lineage_id="lin_b")
        finally:
            store3.close()
        assert [r["event_type"] for r in tl_b] == ["recommendation_emitted"]

    def test_engine_does_not_read_campaign_sent_event_type(self):
        """Structural assertion: no source file under ``src/`` references
        the literal ``campaign_sent`` as a quoted string. The engine
        cannot read what it does not name. Single-writer grep test
        already enforces this for writes; this complements it on the
        read side.
        """
        repo_root = Path(__file__).resolve().parent.parent
        src_dir = repo_root / "src"
        offenders: List[str] = []
        for p in src_dir.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if "'campaign_sent'" in text or '"campaign_sent"' in text:
                offenders.append(str(p.relative_to(repo_root)))
        assert offenders == [], (
            f"engine source mentions 'campaign_sent' literal: {offenders}; "
            f"engine must not read or write this event type"
        )
