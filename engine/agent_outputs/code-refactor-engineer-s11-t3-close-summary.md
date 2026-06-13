# S11-T3-CLOSE — Sprint 11 sprint-close documentation receipt

**Date:** 2026-05-28
**Ticket:** S11-T3-CLOSE — docs updates + KI filings + sprint-close documentation
**Branch:** `post-6b-restructured-roadmap`
**Engineer:** code-refactor-engineer
**Status:** STAGED (orchestrator commits — no self-commit)
**Deviation check: none.**

---

## 1. Approved scope (restated)

Documentation-only sprint close. Updates seven doc surfaces; files no KI letters (P extends, Q+R+S file new); appends six chronological `memory.md` entries (T1, T1.5, T2, T2.5, T3, CLOSE) each ≤15 lines per the L20-36 template. PIVOTS.md SKIP per DS verdict (no direction shift). ARCHITECTURE_PLAN.md SKIP (archived). No code changes. No test changes. No fixture changes.

---

## 2. Files changed (line ranges approximate, post-edit)

| File | Status | Change |
|---|---|---|
| `memory.md` | MODIFIED | Appended six new chronological entries after the existing S10-CLOSE block: S11-T1, S11-T1.5, S11-T2, S11-T2.5, S11-T3, S11-CLOSE. Each ≤12 lines (well under the L20 ≤15-line cap). Updated S10-CLOSE **Next** line to reference `scikit-survival` (was `lifelines`). |
| `ROADMAP.md` | MODIFIED | (a) Header refresh date `2026-05-26 → 2026-05-28` + framing `post-S11 close, pre-S12 dispatch`. (b) §1 current-sprint block rewritten: S12 queued; S11 summary block replaces the S10 summary block; S11 outcome paragraph (Pivot 5 extended; 5/5 chained-refused on survival, 5/5 INSUFFICIENT_DATA on CF; synthetic positive controls c=0.838 + recall@10=0.344); S11 follow-ups (KI-NEW-P extended, KI-NEW-Q/R/S filed). §1 L13 `lifelines → scikit-survival` per DS substitution. (c) §2 L42 S11 row marked **SHIPPED 2026-05-28** + dependency text `lifelines → scikit-survival`. S12+ rows untouched. |
| `STATE.md` | MODIFIED | (a) Header refresh date `2026-05-26 → 2026-05-28`. (b) §4 gate table — ML-fit row updated to note substrate now spans 4 ML models (BG/NBD + Gamma-Gamma + Cox PH survival + CF/ALS); gate still DORMANT (no emitter — S13 wires). (c) §4 added composition-rules paragraph: survival CHAINS BG/NBD; CF INDEPENDENT of BG/NBD (4-layer pin); orthogonal-failure case "BG/NBD VALIDATED + survival REFUSED" is valid. (d) Ranking-strategy fallback chain text now notes RFM=floor / recency=last-resort explicitly. |
| `docs/engine_flags.md` | MODIFIED | (a) Header refresh `2026-05-25 → 2026-05-28` + sprint coverage list. (b) §"S10 predictive layer" heading renamed to "S10–S11 predictive layer" with intro paragraph noting S11 added two more ML rungs (survival + CF) to the same substrate layer; gate still DORMANT. (c) New "S11 predictive flags" subtable with `ENGINE_V2_ML_SURVIVAL` + `ENGINE_V2_ML_CF` rows. (d) Ranking-strategy fallback chain restated with RFM=floor / recency=last-resort explicit. (e) New "S11 audit copy (operator-readable)" subsection with verbatim Beauty-replenishment_due dormancy story (DS §B.8) + orthogonal-failure case (DS §A.5). |
| `docs/DECISIONS.md` | MODIFIED | `D-S6.5-16` (Right-censored empirical median) — appended a 2026-05-28 footnote recording the `lifelines → scikit-survival` substitution at S11-T1 (commit `3cfa06b`); rationale (same Cox PH math, better-maintained, sklearn-ecosystem-backed, zero refactor cost on greenfield substrate); scope clarification (S10 `lifetimes==0.11.3` stays — different family; refactor deferred to S15+); tracked dependency risk routed to KI-NEW-R. Override-mechanism line updated from `S11 will add lifelines` to `S11 will add a Cox PH survival fit`. |
| `KNOWN_ISSUES.md` | MODIFIED | (a) KI-NEW-P title extended to include `survival + CF`; **What** block extended to cover all 4 ML models + ~30-number stage-grid framing (was ~20 numbers covering BG/NBD + G-G only); 2 new 2026-05-28 sub-bullets (synthetic Beauty CF INSUFFICIENT_DATA expected per repeat-buyer ceiling; synthetic ALS DGP positive control recall@10=0.344). Cross-link list extended to S11 plan + S11-T1.5/T2.5 summaries + additive ModelCard fields list. (b) NEW `KI-NEW-Q` — operator parquet query CLI (`beacon query <store_id> --top-n N`); founder-deferred-then-filed per recent ack; closure trigger = post-beta operator-tooling sprint. (c) NEW `KI-NEW-R` — ML library vendor-fork escape hatches across THREE libraries: `lifetimes==0.11.3` (~2 days fork; scipy<1.13 defensive pin; pin silently bypassed on Python 3.14 dev envs); `scikit-survival>=0.22,<0.24` (~1 day fork via scipy.optimize); `implicit>=0.7,<0.8` (~3 days fork; highest medium-term risk due to BLAS dep). (d) NEW `KI-NEW-S` — wall-clock flake on `test_inventory_updated_at_is_fresh`; pre-existing pre-S10-T3 per stash-and-rerun verification; closure trigger = post-beta synthetic-fixture maintenance pass. (e) Open-count table: Deferred edge cases 1→2; Architectural limitations 19→21; **Total 28→31**. Tracked / Accepted columns unchanged. |
| `agent_outputs/INDEX.md` | MODIFIED | (a) Header regen date `2026-05-26 → 2026-05-28` + file count `161 → 168` (1 new T3-close summary + 5 referenced existing S11 closeouts + 1 IM plan + 1 DS verdict). (b) §1 active sprint blurb updated `Sprint 10 closed → Sprint 11 closed`, `Sprint 11 not yet dispatched → Sprint 12 not yet dispatched`. (c) §2 new "Sprint 11" subsection mirroring Sprint 10 structure: IM plan + DS plan review + 5 closeout entries (T1, T1.5, T2, T2.5, T3-close). |
| `agent_outputs/code-refactor-engineer-s11-t3-close-summary.md` | NEW | This file. |

No other files touched. No source code changed. No tests changed. No fixtures changed. PIVOTS.md untouched (DS-confirmed no direction shift). `ARCHITECTURE_PLAN.md` untouched (archived per Phase 2 cutover).

---

## 3. `memory.md` entries added (template envelope confirmation)

Six new chronological entries appended at the end of `memory.md`, in order:

| Entry | Line count | Within template (≤15)? |
|---|---|---|
| S11-T1 — Cox PH survival substrate | 12 | YES |
| S11-T1.5 — Cox PH survival atomic flip | 12 | YES |
| S11-T2 — CF substrate (independent of BG/NBD) | 12 | YES |
| S11-T2.5 — CF atomic flip + rollback (Case D) | 12 | YES |
| S11-T3 — sprint-close docs + KI filings | 12 | YES |
| S11-CLOSE — Sprint 11 substrate complete | 11 | YES |

All entries:
- Follow the L20-36 template ("Shipped:" / "Load-bearing invariants:" / "Caveats / dormant behavior:" / "Schema:" / "Suite:" / "Summary:")
- Narrative (file change tables, test counts, risk paragraphs) is in the relevant per-ticket summary file, NOT in memory.md
- Cite the relevant summary file inline

Template-envelope verification command (used during stage):

```
awk '/^## S11/{if(name)print name,n; name=$0; n=0; next} name{n++} END{if(name)print name,n}' memory.md
```

All six entries are well under the 15-line cap (max 12, min 11). No pre-commit lint script exists in the repo (`scripts/`, `.pre-commit-config.yaml`, `.git/hooks/` all checked — no `memory_lint.py` or similar present); the discipline is currently enforced by author review.

---

## 4. KI filings — letters used

Confirmed next-available letter sequence by inspecting the KI heading grep on KNOWN_ISSUES.md before staging:

- KI-NEW-O — last existing (filed S7.6 continuation 2026-05-23)
- KI-NEW-P — last extended (originally filed S10-T3 2026-05-26)
- **KI-NEW-Q** — NEW (operator parquet query CLI; founder-deferred at S10, filed at S11-T3 per ack)
- **KI-NEW-R** — NEW (ML library vendor-fork escape hatches across 3 libraries)
- **KI-NEW-S** — NEW (wall-clock flake on `test_inventory_updated_at_is_fresh`)

No letter collisions. Q + R land under "Architectural limitations (parked for DS review)"; S lands under "Deferred edge cases".

Open-count table updated:

| Category | Before | After |
|---|---|---|
| Deferred edge cases | 1 / 0 / 3 | **2** / 0 / 3 |
| Architectural limitations (parked for DS review) | 19 / 0 / 0 | **21** / 0 / 0 |
| **Total** | 28 / 3 / 10 | **31** / 3 / 10 |

KI-NEW-P remains a single entry (extension is a content broaden, not a re-file).

---

## 5. Suite / lint checks

Per the brief, sprint-close is documentation-only. No source code touched, so:

- **briefing.html byte-identity:** preserved **by construction** (zero changes to `src/`, `tests/fixtures/`, `config/priors.yaml`, `config/gate_calibration.yaml`, renderer, or any code path that participates in the briefing render). The S11-T2.5 sprint-pin sha values are documented in that ticket's summary §4 and are unchanged at this commit.
- **memory.md template lint:** no lint script present in repo (checked `scripts/`, `.pre-commit-config.yaml`, `.git/hooks/`). Template envelope verified manually via awk script above — all six new entries between 11 and 12 lines, well under the 15-line cap.
- **No targeted test runs:** not required for documentation-only change. The slate_regression / golden_diff / s8_t3_provenance / s6_5_t5_atomic_repin / precedence-invariant / ML rollback / determinism suites would all be no-ops at this commit (identical inputs, identical outputs).

If the orchestrator wishes to defensively re-run the briefing byte-identity suite as a post-stage sanity check, the standard command is:

```
PYTHONPATH=. pytest tests/test_golden_diff.py tests/test_slate_regression_beauty_brand.py tests/test_slate_regression_supplements_brand.py tests/test_s6_5_t5_atomic_repin.py tests/test_s8_t3_provenance.py
```

(Expected: same 44 passed / 2 xfailed / 2 xpassed pattern as S11-T2.5 close.)

---

## 6. Behavior changes

**None.** Documentation-only commit. No `src/` change, no `tests/` change, no `config/` change, no fixture change. PlayCard stubs (`predicted_segment`, `model_card_ref`) stay None. ML-fit gate stays DORMANT. Three orthogonal active gates unchanged.

---

## 7. Artifacts added

- 6 new chronological entries in `memory.md` (template-shape, ≤15 lines each).
- 1 new section in `agent_outputs/INDEX.md` (Sprint 11; mirrors Sprint 10 structure).
- 3 new KI entries (`KI-NEW-Q`, `KI-NEW-R`, `KI-NEW-S`) in `KNOWN_ISSUES.md`.
- 1 footnote on `docs/DECISIONS.md::D-S6.5-16` recording the `lifelines → scikit-survival` substitution rationale.
- This summary file: `agent_outputs/code-refactor-engineer-s11-t3-close-summary.md`.

---

## 8. Remaining risks / follow-up

- **PIVOTS.md unchanged at S11 close** per DS verdict. If founder later decides S11's "honest 5/5 REFUSED+INSUFFICIENT_DATA" outcome warrants a Pivot-8-related framing update, that is a separate doc ticket.
- **`ARCHITECTURE_PLAN.md`** archived per Phase 2 cutover (now under `docs/legacy/`). Not updated, by design.
- **KI-NEW-P closure deferred to S14** — same posture as at S10-T3 close. Extended scope (~30 numbers across 4 ML models) increases the calibration surface but does not change the closure criterion (≥3 real beta merchants per stage cell with realized-vs-predicted ranking + calibration data).
- **KI-NEW-Q/R/S all post-beta deferred.** No beta-blocking items added by this sprint close.
- **`scipy<1.13` pin Python-3.14-dev caveat** is now documented in KI-NEW-R; operator-target Pythons (3.11 / 3.12) still enforce the pin correctly. Worth surfacing on dependency-bump tickets.

---

## 9. S11 sprint-close one-paragraph summary

Sprint 11 shipped the second half of the predictive substrate: Cox PH survival via `scikit-survival>=0.22,<0.24` (DS-substituted for `lifelines` for the same Cox PH math at lower maintenance cost; greenfield substrate so zero refactor cost) chained to BG/NBD via the S10 contract; and Collaborative Filtering via `implicit>=0.7,<0.8` (ALS), **independent** of BG/NBD with a 4-layer architectural pin (API signature + docstring + Case D rollback test + YAML comment). Five tickets shipped atomically (T1, T1.5, T2, T2.5, T3). Pivot 5 honest-synthetic posture preserved: all 5 pinned fixtures land REFUSED via `chained_bgnbd_refusal` on survival (BG/NBD already REFUSED/INSUFFICIENT_DATA from S10), and all 5 land INSUFFICIENT_DATA on CF (synthetic Beauty's `n_active_customers` sits below the MATURE `min_customers=200` floor — the synthetic-data repeat-buyer ceiling, not a calibration failure). VALIDATED paths verified by in-code synthetic sanity (Cox PH c=0.838 on a healthy Cox DGP; ALS recall@10=0.344 on a healthy latent-segment DGP). KI-NEW-P extended to ~30 numbers across 4 ML models; KI-NEW-Q (operator parquet CLI), KI-NEW-R (3-library vendor-fork escape hatch), and KI-NEW-S (wall-clock flake) filed. The ML-fit gate substrate now spans all 4 beta-blocking ML models (BG/NBD + Gamma-Gamma + Cox PH survival + CF/ALS) but the gate itself stays DORMANT — S13 wires consumers, S14 brings real-merchant VALIDATED evidence. PlayCard stubs `predicted_segment` and `model_card_ref` remain None. PIVOTS.md untouched per DS confirmation (no direction shift at S11 close; Option γ posture extended, not amended).

---

## 10. Suggested commit message

```
docs: S11-T3-CLOSE — Sprint 11 sprint-close documentation receipt

Documentation-only close for Sprint 11 (ML Predictive Layer Part 2).

- memory.md: 6 new chronological entries (T1, T1.5, T2, T2.5, T3, CLOSE),
  template-shape, ≤12 lines each (well under L20 ≤15-line cap).
- ROADMAP.md: S11 marked SHIPPED 2026-05-28; S12 queued; §1 L13 + §2 L42
  lifelines → scikit-survival per DS S11 plan review §B.
- STATE.md §4: predictive layer now 4 models (BG/NBD + G-G + Cox PH +
  CF/ALS); ML-fit gate still DORMANT; survival CHAINS BG/NBD, CF
  INDEPENDENT of BG/NBD.
- docs/engine_flags.md: S11 predictive flag rows + ranking-strategy
  fallback chain (BG/NBD → CF → survival → RFM → recency) + audit copy
  (Beauty-replenishment_due dormancy + orthogonal-failure case).
- docs/DECISIONS.md::D-S6.5-16: 2026-05-28 footnote — lifelines →
  scikit-survival substitution rationale.
- KNOWN_ISSUES.md: KI-NEW-P extended to ~30 numbers across 4 ML models;
  KI-NEW-Q (operator parquet CLI), KI-NEW-R (3-library vendor-fork
  escape hatch), KI-NEW-S (wall-clock flake) filed. Total 28 → 31.
- agent_outputs/INDEX.md: Sprint 11 section.

No code changes. No test changes. No fixture changes. briefing.html
byte-identity preserved by construction. PIVOTS.md untouched per DS.
ARCHITECTURE_PLAN.md untouched (archived).

Deviation check: none.
```

---

*End of S11-T3-CLOSE summary.*
