# Doc-Migration Drift Audit — 2026-05-25

**Scope:** Pre-cutover read-only audit of the 5 new active-read-path docs (PRODUCT.md, STATE.md, PIVOTS.md, ROADMAP.md, KNOWN_ISSUES.md), CLAUDE.md, agent_outputs/INDEX.md, and their drafts. Triggered by the founder concern that the known S9 framing drift in ROADMAP.md may have analogues elsewhere.

**Audit hypothesis (from DS verdict):** ML is beta-blocking and must take the kickoff slot; lifecycle/structural cleanup is post-beta. Old-S9 (lifecycle/KI-NEW-L/M/N + Play Library wave 2) → New-S15. Old-S10..S14 each shift down by 1 (ML Part 1 becomes new-S9; beta launch becomes new-S13). S13.5 (KI-NEW-L) stays as a label but logically sits between new-S12 and new-S13. The drift hunt is: where does the active read path still encode the old sequencing or paraphrase a stale claim?

---

## Gate A — Sprint number drift

Every sprint-number occurrence in the active read path was located and classified against the new numbering. The "old/new" semantic test is the one the founder gave: *"S9 = lifecycle/cleanup"* is OLD; *"S9 = ML Part 1 kickoff"* is NEW.

| File:Line | Quoted sentence | Semantics | Verdict |
|---|---|---|---|
| ROADMAP.md:13 | `**Sprint 9 — Structural cleanup + play lifecycle.** PAUSED pending completion of the docs migration` | OLD (S9 = lifecycle/cleanup) | **FIX** |
| ROADMAP.md:20-24 | `**S9 anchor goals (queued, not yet dispatched):** 1. Play lifecycle prerequisite … 2. KI-NEW-L collapse … 3. KI-NEW-M … 4. KI-NEW-N` | OLD (all KI-NEW-L/M/N + lifecycle bundled into S9) | **FIX** — under new numbering this is S15 |
| ROADMAP.md:26 | `S9 is the natural carrier for Play Library wave 2+.` | OLD | **FIX** — wave 2 carrier becomes S15 |
| ROADMAP.md:30 | `## 2. Beta-blocking sequence (S9 → S14)` | OLD (beta launch at S14) | **FIX** — new sequence is S9 → S13 with S13 = beta launch |
| ROADMAP.md:32 | `Target: private beta launch at S14 close, ~12 wall-clock weeks from S9 kickoff.` | OLD | **FIX** — new = S13 close |
| ROADMAP.md:36 | row `**S9** \| Structural cleanup (KI-NEW-L/M/N) + play lifecycle prerequisite + Play Library wave 2 \| yes — lifecycle gates ML` | OLD + paraphrase drift ("lifecycle gates ML") | **FIX** (known drift) |
| ROADMAP.md:37 | `**S10** \| ML Predictive Layer Part 1 — BG/NBD + Gamma-Gamma + ModelFitStatus 3rd-gate` | OLD | **FIX** — new = S9 |
| ROADMAP.md:38 | `**S11** \| ML Predictive Layer Part 2 — survival + collaborative filtering` | OLD | **FIX** — new = S10 |
| ROADMAP.md:39 | `**S12** \| ML Predictive Layer Part 3 — statistical RFM + cohort retention` | OLD | **FIX** — new = S11 |
| ROADMAP.md:40 | `**S13** \| Integration — ML feeds AUDIENCE via ranking_strategy …` | OLD | **FIX** — new = S12 |
| ROADMAP.md:41 | `**S14** \| Private beta launch — onboard 1–2 hand-picked merchants` | OLD | **FIX** — new = S13 |
| ROADMAP.md:43 | `Lifecycle ships before any ML model so the audience-identity / lineage substrate is settled before per-customer scores ride on top.` | OLD (load-bearing ordering claim) | **FIX** — this is the rejected linear sequencing |
| ROADMAP.md:45 | `ModelFitStatus (per model, S10+)` | OLD | **FIX** — new = S9+ |
| ROADMAP.md:54 | `Play Library wave 2+ migration. … natural carrier for the KI-NEW-L collapse` | OLD framing — wave 2 still attached to lifecycle/KI-NEW-L | **FIX** — wave 2 may carry forward or attach to ML sprints; KI-NEW-L sits at new-S12.5 |
| ROADMAP.md:55 | `KI-NEW-L / M / N deferred to S9.` | OLD | **FIX** — KI-NEW-L → new-S12.5; KI-NEW-M/N → new-S13-T3 |
| ROADMAP.md:58 | `S10–S13 ML predictive layer extends predicted_segment + model_card_ref stubs additively` | OLD | **FIX** — new = S9–S12 |
| ROADMAP.md:62 | `## 4. Post-beta deferrals (S15+)` | OLD | **FIX** — new = S14+ (and the OLD-S9 lifecycle/cleanup work folds in here as new-S15) |
| ROADMAP.md:66 | `Was the previous plan's S10; reframed post-beta.` | Historical reference, OK if rephrased to "previous plan's Phase 9" | **AMBIGUOUS** (this references a third numbering — Phase 9 — which is itself OK; but the "previous plan's S10" claim is OLD-of-OLD and may confuse) |
| ROADMAP.md:70 | `Portfolio optimization (S22+)` | Far-future, semantics-neutral (could shift to S21+ under new numbering) | **FIX** — should be S21+ for consistency, or rephrased as "post-PMF" |
| ROADMAP.md:71 | `LLM mechanism generation (S26+)` | Same | **FIX** — S25+ or "post-PMF" |
| ROADMAP.md:114 | `KI-NEW-L/M/N = S9 structural` | OLD | **FIX** |
| STATE.md:73 | `*Not active yet* — lands in S10–S13.` (ModelFitStatus gate) | OLD | **FIX** — new = S9–S12 |
| STATE.md:145 | `Supplements goes from "ABSTAIN_SOFT, 0 cards" to non-empty only after S10–S13 ML AUDIENCE layer + Tier-B activation on supplements-specific signal.` | OLD | **FIX** — new = S9–S12 |
| STATE.md:149 | `Real-merchant private-beta onboarding (S14) is unblocked once S10–S13 ML AUDIENCE layer lands.` | OLD | **FIX** — new = S13 onboarding, S9–S12 ML |
| STATE.md:165 | `Five V2 prior-anchored injection blocks at \`1380-1597\` (collapse deferred to S13.5 per KI-NEW-L).` | OLD | **FIX** — new-S12.5 (or whatever the new label is; the founder spec said S13.5 *stays* as a label sitting between S12-T4 and S13-T1) |
| STATE.md:190 | `BG/NBD + Gamma-Gamma LTV, survival, collaborative filtering, RFM, retention curves all land S10–S13.` | OLD | **FIX** |
| STATE.md:196 | `Scheduled S13.5 per KI-NEW-L.` | Same label per founder spec. | **KEEP** (label is preserved) |
| PRODUCT.md:79 | `The ML predictive layer (Sprints 10–13) gives audience-level intelligence` | OLD | **FIX** — new = Sprints 9–12 |
| PRODUCT.md:114 | `ML refit \| Once month-2 of beta lands` | semantics-neutral | KEEP |
| PIVOTS.md:89 | `Sprint sequence prioritizes ML-as-audience-ranking over Phase 9. ModelFitStatus gate; ML never adds plays, only ranks customers within a play's audience.` | NEW-compatible (no sprint numbers) | **KEEP** |
| CLAUDE.md | (no sprint numbers in body) | n/a | KEEP |
| INDEX.md:20 | `Sprint 9 not yet started.` | OLD or NEW depending on intent. Under new numbering S9 *is* "ML Part 1 kickoff" — this sentence is still accurate ("not yet started") but should be re-anchored to "new-S9 = ML Part 1." | **FIX** (rephrase to avoid ambiguity) |
| KNOWN_ISSUES.md (KI-NEW-L body) | `KI-NEW-L deferred to S13.5 — a dedicated single-ticket structural-cleanup window between S13-T4 atomic flip and S14-T1` | OLD | **FIX** — under new numbering this becomes "between S12-T4 and S13-T1" |
| KNOWN_ISSUES.md (KI-NEW-L body) | `S13's per-builder audit (extending all 5 Tier-B audience builders with ranking_strategy)` | OLD | **FIX** — new-S12 |
| KNOWN_ISSUES.md (KI-NEW-L body) | `Deferral conditional invariant … "no new Tier-B builders through S13"` | OLD | **FIX** — new-S12 |
| KNOWN_ISSUES.md (KI-NEW-M body) | `S14-driven resolution window … S14-T3 surfaces ≥2 distinct beta-merchant reports` | OLD | **FIX** — new-S13-T3 |
| KNOWN_ISSUES.md (KI-NEW-N body) | `S14-driven resolution window … Same resume trigger as KI-NEW-M — S14-T3 beta-merchant feedback` | OLD | **FIX** — new-S13-T3 |
| KNOWN_ISSUES.md (KI-NEW-J body, 2026-05-24 update) | `DEFER to S14 pre-private-beta calibration window` | OLD | **FIX** — new-S13 |
| KNOWN_ISSUES.md (KI-NEW-K body) | `re-fit at effective_n=60 before Sprint 8 calibration` | Historical (RESOLVED already), safe | KEEP |
| memory.md L1921 | `KI-NEW-L → S13.5 (between S13-T4 atomic flip and S14-T1 dispatch); KI-NEW-M/N → S14-T3 beta-merchant feedback resolution window; KI-NEW-J → S14 pre-private-beta calibration` | OLD | **OUT OF SCOPE** for cutover (memory.md is chronology), but every reader of memory.md after 2026-05-25 will hit this OLD sequence. Note as risk; not a doc-migration cutover blocker. |

**Gate A count:** **26 instances of sprint-number drift requiring renumbering before cutover** (1 known + 25 newly surfaced).

The cutover ROADMAP.md is functionally identical to the draft — the known drift was not fixed in the file currently on disk; the founder's audit catch on ROADMAP.md was correct that the drift exists, AND it has not yet been corrected at the destination.

---

## Gate B — KI status + sprint-pin drift

| KI | Status | Old sprint pin | New sprint pin | Verdict |
|---|---|---|---|---|
| KI-1..KI-5 | open | "Phase 9 entry conditions" (no S-number) | unchanged | KEEP |
| KI-7 | open (Swarm coordination) | no sprint | unchanged | KEEP |
| KI-NEW-G | open (Commit C activation tracker) | "real-beta dependency" (no S-number); T2.5 sub-thread RESOLVED-AS-DOCUMENTED 2026-05-23 | unchanged | KEEP |
| KI-NEW-J | open | "DEFER to S14 pre-private-beta calibration" | new-S13 | **FIX** |
| KI-NEW-K | RESOLVED 2026-05-24 (S8-T0, `77086fd`) | n/a | n/a | KEEP |
| KI-NEW-L | open | "deferred to S13.5 between S13-T4 and S14-T1"; conditional "no new Tier-B builders through S13" | new pin per founder spec: S13.5 label *stays*, but underlying anchors S13-T4 → new-S12-T4 and S14-T1 → new-S13-T1; "no new Tier-B builders through S12" | **FIX** — the *label* "S13.5" is preserved by founder spec, but the anchored sprint references inside the body MUST renumber |
| KI-NEW-M | open | "deferred to S14-T3 beta-merchant feedback" | new-S13-T3 | **FIX** |
| KI-NEW-N | open | "deferred to S14-T3 beta-merchant feedback, paired with KI-NEW-M" | new-S13-T3 | **FIX** |
| KI-NEW-O | open | "follow-on doc/test-hygiene ticket" (no sprint) | unchanged | KEEP |
| KI-NEW-A..F, H, I | open | no sprint pin, Phase 9 / real beta triggers | unchanged | KEEP |
| KI-NEW-P, Q | newly opened post-S8 per ROADMAP.md:56; cross-check: **no entries in KNOWN_ISSUES.md** | n/a | n/a | **AMBIGUOUS — FIX or DELETE.** ROADMAP.md L56 says "KI-NEW-P / Q opened post-S8"; ROADMAP.md L114 says "KI-NEW-P/Q = post-S8 newly opened"; but `KNOWN_ISSUES.md` has no entries P or Q (the file ends at KI-NEW-O). Either KI-NEW-P/Q were never filed in KNOWN_ISSUES.md and ROADMAP.md fabricates them, or they were lost in a doc-migration sweep. **This is a load-bearing inventory drift.** |

**Gate B count:** **5 KI-pin drift entries requiring fix** (KI-NEW-J, L, M, N) + **1 inventory drift** (KI-NEW-P/Q claimed but not present).

---

## Gate C — Paraphrase drift (the S9 pattern, generalized)

Each source citation in the new docs audited against the cited source.

| File:Line | Claim | Cited source | Source supports? | Verdict |
|---|---|---|---|---|
| ROADMAP.md:36 | `S9 = "lifecycle gates ML"` | implicit: "per the reconciled ML-roadmap review" (cited L43, L130) | **NO** — `beacon-ml-roadmap-reconciled-review.md` Addendum 2 L674-685 says substrate doesn't depend on Swarm and parallel-track ships I-1 alongside substrate. The "lifecycle ships before any ML model" linear sequencing is not present at the cited lines. | **FIX** (known drift; reconfirmed) |
| ROADMAP.md:43 | `affinity-then-survival-then-uplift sequencing per beacon-ml-roadmap-reconciled-review.md` | same | **PARTIAL** — the doc supports an affinity-first emitter, but the cited Addendum 2 is the parallel-track restructure, not the affinity→survival→uplift sequencing. The sequence may live in a different addendum or section; the citation as written is imprecise. | **FIX** — re-cite the actual passage that defines affinity → survival → uplift |
| ROADMAP.md:127 | `ENGINE_OVERVIEW.md §6 redesign plan + table (lines 88-117)` | ENGINE_OVERVIEW.md L88-117 | **STALE-WITH-ARCHIVE-RISK** — ENGINE_OVERVIEW.md L94-101 still encodes the OLD S6-14 sequencing ("Build the ML Predictive Layer (Sprints 10-13)"). Citing it for the new sequence imports the old sequence. ENGINE_OVERVIEW.md is also slated for Phase 4 archive. | **FIX** — ROADMAP.md must either (a) cite the *new* IM plan (the s6-s14 reconciled plan path is itself OLD numbering by name), or (b) become self-sufficient and stop citing ENGINE_OVERVIEW.md. Phase 4 archive amplifies this risk. |
| STATE.md:188-190 | "Phase 9 outcome ingestion → prior recalibration is post-beta"; "No ML predictive layer yet. … all land S10–S13" | implicit memory.md / ROADMAP.md cross-ref | **PARTIAL** — the post-beta posture is correct (matches ENGINE_OVERVIEW.md L109-114 and memory.md S8 close); the S10–S13 number is OLD. | **FIX** (the framing is correct; only the number is wrong) |
| STATE.md:83 (invariant 1) | "Every Tier-B Recommended card populates Measurement.observed_effect, p_internal, n from blend_provenance." | `agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md` | **YES** — verdict text and memory.md S7.6 CLI-fix close (commit `d8ede8c`) confirm. | KEEP |
| STATE.md:91 (invariant 5) | "PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}. Locked through S8–S14." | S8 pseudo_N verdict | **PARTIAL** — verdict locks 30/15/10 (matches). "Locked through S14" uses OLD beta-launch number; new-S13 is beta launch. | **FIX** (numeric "S14" → "S13" or rephrase as "locked through private-beta launch") |
| STATE.md:103 (invariant 11) | "Play Library wave-1 byte-identity by construction. … on every run with ENGINE_V2_PLAY_LIBRARY_WAVE1=ON." | S8-T4/T4.5 verdict | **YES** — matches memory.md L1904. | KEEP |
| PIVOTS.md (Pivot 8) | "Sprint sequence prioritizes ML-as-audience-ranking over Phase 9. … ML never adds plays, only ranks customers within a play's audience." | `ENGINE_OVERVIEW.md §6 and §10` + `implementation-manager-s6-s14-revised-plan-ml-layer.md` | **YES** — both sources confirm. No numeric drift in this paraphrase. | KEEP |
| PIVOTS.md (Pivot 4) | "A `SOFT_PRIOR_UNVALIDATED` abstain status routes the play to Considered when its prior lacks an empirical anchor." | `memory.md` S7.5 entries L403-530 | **YES** | KEEP |
| PIVOTS.md (Pivot 7) | "All demote paths route through `apply_guardrails_to_injected`" | `ARCHITECTURE_PLAN.md` 2026-05-22 LOAD-BEARING UPDATE + memory.md S7.6 close L1645-1708 | **YES** — confirmed against CLAUDE.md L67-68 invariant text. | KEEP |
| PIVOTS.md (Sources L113) | `ARCHITECTURE_PLAN.md` 2026-05-22 LOAD-BEARING UPDATE block | This file is slated for Phase 4 archive. Body of PIVOTS.md L80, L113 cites it directly. | **STALE-WITH-ARCHIVE-RISK** | **FIX** Phase 4 readiness — either lift the relevant text into PIVOTS.md or guard the citation with an archive-aware footnote |
| PRODUCT.md:79 | "The ML predictive layer (Sprints 10–13) gives audience-level intelligence" | "Sources" footer lists ENGINE_OVERVIEW.md §6 L88-117 | **PARTIAL** — ENGINE_OVERVIEW.md L100 says "Sprints 10-13"; matches PRODUCT.md L79. But both encode OLD numbering. | **FIX** |
| PRODUCT.md:134 | "ENGINE_OVERVIEW.md §1 (L9–16), §3 (L37–48), §6 (L88–117), §10 (L193–204)" | ENGINE_OVERVIEW.md | **PARTIAL** — line ranges check out, but ENGINE_OVERVIEW.md is slated for archive. | **FIX** Phase 4 readiness (see Gate H) |
| PRODUCT.md:135 | "ARCHITECTURE_PLAN.md Executive Summary L75–87 … L70–84 S7.6 close beta-readiness statement" | ARCHITECTURE_PLAN.md | **STALE-WITH-ARCHIVE-RISK** | **FIX** Phase 4 readiness |
| STATE.md:204 | "ARCHITECTURE_PLAN.md Part I §A (Tier definitions), Part IV (Store Profile Layer), LOAD-BEARING UPDATE blocks 1–9" | ARCHITECTURE_PLAN.md | **STALE-WITH-ARCHIVE-RISK** | **FIX** |

**Gate C count:** **9 paraphrase-drift items** (1 known + 4 number drift + 4 archive-risk citations).

---

## Gate D — Founder-decision (D-1..D-8) drift

memory.md L173-180 carries D-1..D-8 verbatim; below is the per-doc paraphrase audit. The summary text in each new doc is checked against the canonical wording in memory.md L173-180.

| D-N | memory.md text (verbatim) | New-doc paraphrase | File:Line | Match |
|---|---|---|---|---|
| D-1 | "`audience_definition_version` policy. Any change to SQL/Python audience-definition logic MUST increment `audience_definition_version` by 1. Old lineages remain readable but fork to a new `lineage_id`. Required arg in `compute_lineage_id`." | "Audience-definition versioning. Logic changes bump `audience_definition_version`; old lineages remain readable." | PRODUCT.md:91 | PARAPHRASED — captures the spirit, drops "Required arg in `compute_lineage_id`" load-bearing clause |
| D-2 | "Retention forever. No TTLs, auto-deletion, archival tiers. SQLite grows monotonically." | "Forever retention. No TTLs, no auto-deletion, no archival tiers." | PRODUCT.md:92 | PARAPHRASED — close; drops "SQLite grows monotonically" |
| D-3 | "Merchant deletion = full wipe only. Per-store `data/<store_id>/memory.db` is the deletion unit. No row-level deletion APIs, soft-delete flags, or partial redaction." | "Merchant deletion = full per-store wipe only. No row-level deletion, no soft-delete flags." | PRODUCT.md:93 | PARAPHRASED — drops "partial redaction" |
| D-4 | "Full per-store JSON export from Day 1 (`tools/export_store.py`). Round-trip test required." | "Full per-store JSON export from day one. Round-trip tested." | PRODUCT.md:94 | PARAPHRASED — present-tense "tested" vs canonical "required"; drops tool path |
| D-5 | "Manual JSON import ONLY for v1. NO Klaviyo API pollers, OAuth flows, or webhook receivers in Beacon-track scope." | "**Manual JSON import only** for v1. No Klaviyo API pollers, no OAuth flows, no webhook receivers in the Beacon-track engine. Klaviyo network calls are revisited at AWS migration, not before. (KI-7 tracks `provider` enum coordination.)" | PRODUCT.md:95 | PARAPHRASED + extension — extra "Klaviyo revisited at AWS migration" + "(KI-7)" addition is supportable but not in the D-5 canonical text. Risk: future agents may treat the extension as part of D-5. |
| D-6 | "ML models EXPLICITLY BANNED for the planning horizon: quiz contextual bandits (LinUCB/Thompson), VIP/loyalty tier optimization, new product launch targeting, bundle combinatorial optimization, stockout prediction, cause/limited-edition→core conversion. NO empty modules, placeholder classes, prior entries, or `play_id` registrations for these. Re-additions require explicit founder approval + new addendum." | "ML is **explicitly banned** for: quiz contextual bandits, VIP/loyalty tier optimization, new-product-launch targeting, bundle combinatorial optimization, stockout prediction, cause/limited-edition→core conversion. No placeholder modules. Re-additions require explicit founder approval." | PRODUCT.md:96 | PARAPHRASED — drops parenthetical (LinUCB/Thompson), drops "+ new addendum" requirement |
| D-7 | "I-1 affinity audience-builder spec deferred to Sprint 3 spike memo." | "Affinity audience-builder spec deferred to a spike memo (`agent_outputs/i1-spike-findings.md`)." | PRODUCT.md:97 | PARAPHRASED — drops "I-1" load-bearing identifier; drops "Sprint 3" anchor. Code paths and tests reference "I-1"; future readers will struggle to map. |
| D-8 | "Vertical scope hard-locked at `{beauty, supplements, mixed}`. `mixed` = literal beauty+supplements blend, NOT a fallback for unknown verticals. Apparel, food/bev, home goods, wellness are out of scope PERMANENTLY — refused at engine entry, never absorbed by `mixed`." | "**Vertical hard-lock**: `{beauty, supplements, mixed}` only. `mixed` is a literal beauty+supplements blend, **not** a fallback for unknown verticals. Apparel, food/bev, home, generic wellness are refused at engine entry — permanently." | PRODUCT.md:98 | PARAPHRASED — close; "home goods" → "home", "wellness" → "generic wellness" (minor — but a string-grep on the canonical "home goods" or "wellness" wording would now miss PRODUCT.md). |

**Gate D count:** **8 paraphrase drifts** (all 8 D-N in PRODUCT.md are paraphrases, not verbatim).

This is a *systemic* concern, not a single fix. The risk shape: ~50 code/test sites grep for D-N strings. PRODUCT.md becoming an authoritative source-of-truth secondary to memory.md L173-180 means a future maintainer editing PRODUCT.md's D-5 (e.g., loosening D-5 to add an AWS preview path) may not realize they've forked the canonical text. Recommendation: PRODUCT.md §6 should *quote* memory.md L173-180 verbatim, or explicitly include the line "Canonical text: memory.md L173-180; this section is a copy."

---

## Gate E — Assumption / "this is true because" audit

Load-bearing assumptions across the new docs, with source-supportability verdict.

| File:Line | Assumption | Cited / implicit source | Verdict |
|---|---|---|---|
| STATE.md:73 | "ModelFitStatus gate … Not active yet — lands in S10–S13." | ROADMAP / ENGINE_OVERVIEW | STALE (sprint number) |
| STATE.md:91 | "PSEUDO_N_BY_STATUS = {30, 15, 10}. Locked through S8–S14." | S8 verdict | STALE (S14 reference) |
| STATE.md:111 | "`docs/engine_flags.md` is the source of truth for live flag values." | self | SUPPORTED but flagged STATE.md:123 itself: "Note: `docs/engine_flags.md` 'Last updated: 2026-05-03' predates S6/S7/S7.5/S7.6/S8 — it needs its own refresh." This is honest acknowledgement but means the chain "STATE → engine_flags.md → truth" is broken today. |
| STATE.md:165 | "Five V2 prior-anchored injection blocks at `1380-1597` (collapse deferred to S13.5 per KI-NEW-L)." | KI-NEW-L (KNOWN_ISSUES.md) | SUPPORTED but uses OLD-sprint label inside; cross-check vs Gate B verdict |
| ROADMAP.md:32 | "Target: private beta launch at S14 close, ~12 wall-clock weeks from S9 kickoff." | implicit estimate | STALE (numbers); estimate methodology unverified |
| ROADMAP.md:43 | "Lifecycle ships before any ML model so the audience-identity / lineage substrate is settled before per-customer scores ride on top." | implicit (cited later L130 as reconciled-review) | STALE — directly contradicted by the DS verdict the founder issued; this is the load-bearing assumption that needs flipping. |
| PRODUCT.md:77 | "Month-2 return — … evolution comes from the **ML predictive layer refit** on 30 more days of data, not from realized outcomes." | sources L134-138 | SUPPORTED — matches ENGINE_OVERVIEW.md L202 |
| PRODUCT.md:79 | "(Sprints 10–13) … ranks customers within each play's audience and gates itself via `ModelFitStatus` (VALIDATED / PROVISIONAL / REFUSED)." | ENGINE_OVERVIEW.md §6 | STALE (sprint number) + otherwise SUPPORTED |
| PRODUCT.md:81 | "Phase 9 outcome loop is deferred post-beta." | ENGINE_OVERVIEW.md §6 L109-114 | SUPPORTED |
| STATE.md:113 | "All currently default ON unless noted, post-S8 close" (S7.6/S8 flags) | implicit cross-ref to docs/engine_flags.md | WEAK — STATE.md L123 itself flags that engine_flags.md hasn't been refreshed since 2026-05-03, predating S6/S7/S7.5/S7.6/S8. The "default ON" claim is unverifiable against the doc STATE.md routes you to. Recommend: either refresh engine_flags.md as a Phase-2 prerequisite, or weaken STATE.md's flag claims to "asserted live, see commit log." |
| CLAUDE.md:28 | "What is the current flag default? \| `docs/engine_flags.md`" | self | WEAK (same reason as above) |
| CLAUDE.md:67-68 | Single-demote-channel invariant body | `PIVOTS.md` and the cited helper `src/guardrails.py` | SUPPORTED — verified against memory.md S7.6 close + src/guardrails.py |

**Gate E count:** **6 weak/stale load-bearing assumptions.** Three are the same sprint-number drift surfaced in Gate A; two are the engine_flags.md staleness chain; one is the load-bearing "lifecycle ships before ML" claim that the DS verdict explicitly reverses.

---

## Gate F — INDEX.md citation correctness

INDEX.md §4 lists 4 "Load-bearing forever" orphans + 4 "load-bearing until superseded" orphans. Cross-check each against the active read path.

| Orphan | INDEX says cited from | Actually cited? | Verdict |
|---|---|---|---|
| `i1-spike-findings.md` | PRODUCT.md and PIVOTS.md | PRODUCT.md: no (D-7 paraphrase L97 references "`agent_outputs/i1-spike-findings.md`" parenthetically — YES). PIVOTS.md: "Dropped candidates" L99 mentions "Source `agent_outputs/i1-spike-findings.md` cited from ROADMAP.md" but ROADMAP.md does NOT cite it. | **PARTIAL FIX** — PRODUCT.md cite is real; PIVOTS.md says it's cited from ROADMAP.md but it isn't. INDEX.md needs to drop ROADMAP from the citation list and add PRODUCT.md. |
| `legacy-vs-v2-final-recommendation.md` | PIVOTS.md | PIVOTS.md L20 + L108: YES | KEEP |
| `phase6b-stop-coding-line-reconciled.md` | PIVOTS.md and PRODUCT.md | PIVOTS.md L30, L110: YES. PRODUCT.md L138: YES. | KEEP |
| `ds-architect-store-profile-layer-proposal.md` | STATE.md | STATE.md body and Sources L201-213: **NOT CITED**. STATE.md §1 references `src/store_profile.py` but never cites the proposal. | **FIX** — either STATE.md must cite the proposal in its Sources, or INDEX.md must move this orphan to "no longer load-bearing" |
| `beacon-ml-roadmap-reconciled-review.md` | ROADMAP.md | ROADMAP.md L43, L120, L130: YES | KEEP |
| `campaign-slate-contract-final.md` | STATE.md | STATE.md L208: YES (Sources) | KEEP |
| `m0-m9-final-review-reconciled.md` | STATE.md and PIVOTS.md | STATE.md L209: YES. PIVOTS.md L20, L109: YES | KEEP |
| `play-lifecycle-discussion-reconciled.md` | ROADMAP.md | ROADMAP.md L21, L89, L119, L131: YES | KEEP |

**Gate F count:** **2 INDEX.md citation drifts** — `i1-spike-findings.md` claimed cited from ROADMAP but isn't; `ds-architect-store-profile-layer-proposal.md` claimed cited from STATE but isn't.

---

## Gate G — CLAUDE.md Doc Map completeness

| Agent question | Doc Map points to | Doc exists? | Doc answers question? | Verdict |
|---|---|---|---|---|
| What is BeaconAI as a product? | `PRODUCT.md` | YES | YES — §1 + §2 + §7 cover product framing + journey + future | KEEP |
| What does the engine do right now? | `STATE.md` | YES | YES | KEEP |
| Why is X invariant locked? What changed our minds? | `PIVOTS.md` | YES | YES — 8 pivots + dropped-candidates section | KEEP |
| What is next? | `ROADMAP.md` | YES | YES — but contains the OLD sprint sequence; agents will be misled | FLAG (consumer issue, not Doc Map issue) |
| What happened in sprint X? | `memory.md` | YES | YES | KEEP |
| What ticket shipped what? | `agent_outputs/code-refactor-engineer-<ticket>-summary.md` | files exist per INDEX.md §2 | YES | KEEP |
| What open issues exist? | `KNOWN_ISSUES.md` | YES | YES | KEEP |
| What is the current flag default? | `docs/engine_flags.md` | YES | **PARTIAL** — engine_flags.md was last updated 2026-05-03 (per STATE.md L123 self-flag) and predates S6/S7/S7.5/S7.6/S8 | **FIX** — either refresh engine_flags.md or rephrase the Doc Map row to "live flag defaults (refresh pending)" |
| Which founder decisions bound the design space? | `memory.md` § Founder Decisions (L173–182); cross-refs in `docs/DECISIONS.md` | memory.md confirmed; docs/DECISIONS.md unread in this audit | **AMBIGUOUS** — docs/DECISIONS.md existence and content unverified by this audit. Recommend confirming the cross-ref points to a real, current file before commit. |
| Which agent_outputs file should I read? | `agent_outputs/INDEX.md` | YES | YES | KEEP |

**Gate G count:** **2 Doc Map issues** (engine_flags.md staleness; docs/DECISIONS.md cross-ref unverified) + 1 downstream consumer issue (ROADMAP carries OLD sequencing).

No active doc appears to be missing from the Doc Map.

---

## Gate H — Phase 4 archive readiness

Phase 4 archives: `ARCHITECTURE_PLAN.md`, `memory_archive.md`, `ENGINE_OVERVIEW.md`, `ENGINE.md`, `TESTING_GUIDE.md`, `PILOT_UPLOAD_GUIDE.md`, `onboarding-optimization-guide.md`.

For each of these references in the new active docs:

| New-doc location | Referenced archive-bound doc | Cites file path or content? | Phase 4 risk |
|---|---|---|---|
| PRODUCT.md:134 | `ENGINE_OVERVIEW.md §1, §3, §6, §10` | file path + content (line numbers) | HIGH — agent following the cite hits the archive path; line numbers stale post-move |
| PRODUCT.md:135 | `ARCHITECTURE_PLAN.md Executive Summary L75–87`, `L70–84` | file path + line numbers | HIGH |
| STATE.md:203 | `ENGINE_OVERVIEW.md §§2, 3, 5, 6, 8, 8.5` | content + section refs | HIGH |
| STATE.md:204 | `ARCHITECTURE_PLAN.md Part I §A, Part IV, LOAD-BEARING UPDATE blocks 1–9` | content + section refs | HIGH |
| PIVOTS.md:40 | `ARCHITECTURE_PLAN.md Part I §A and §B` (Pivot 3) | content | HIGH (body, not just Sources) |
| PIVOTS.md:50 | `ARCHITECTURE_PLAN.md Part III-1` (Pivot 4) | content | HIGH (body) |
| PIVOTS.md:80, 113 | `ARCHITECTURE_PLAN.md 2026-05-22 LOAD-BEARING UPDATE block` (Pivot 7 + Sources) | content + block name | HIGH (body) |
| PIVOTS.md:90 | `ENGINE_OVERVIEW.md §6 and §10` (Pivot 8) | section refs | HIGH (body) |
| ROADMAP.md:5 | `Replaces: ARCHITECTURE_PLAN.md Part II sequencing + "What This Plan Does NOT Do" L88-98` | meta-cite + line numbers | HIGH — "Replaces" framing means ROADMAP claims to *be* the new version of an archive-bound section. Confirm migration is complete; if any reader still hits ARCHITECTURE_PLAN.md Part II for sprint sequencing, ROADMAP's authority is non-load-bearing. |
| ROADMAP.md:81, 127, 132 | `ARCHITECTURE_PLAN.md "What This Plan Does NOT Do" L88-98` | content + line numbers | HIGH |
| ROADMAP.md:127 | `ENGINE_OVERVIEW.md §6 redesign plan + table (lines 88-117)` | content + line numbers | HIGH (and STALE — see Gate C) |
| STATE.md:158 | `src/measurement_builder.py:2252-2270` | code path | OK (code paths unaffected) |
| CLAUDE.md:39 | "the prior pointer to `ENGINE.md` is retired; that doc now lives in `docs/legacy/`" | acknowledges archive | KEEP — explicitly handles the archive transition |
| memory.md L182 | "Storage backend note" | n/a (memory.md is not archived) | n/a |

**Gate H count:** **11 high-risk archive-citation patterns.** All are body or Sources references to files that will not exist at the cited paths after Phase 4.

Phase 4 readiness recommendation: before archiving, either (a) lift quoted text into the citing doc as inline content; or (b) update all citations to point to `docs/legacy/<file>` (mirroring the CLAUDE.md:39 pattern); or (c) include a one-line migration footnote in each citing doc explaining how to find archived content.

---

## Drift Inventory Summary

### Must fix before commit (founder + DS sign-off blockers)

**Count: 7**

1. **Renumber all sprint references in ROADMAP.md** (26 occurrences; see Gate A). The committed file is identical to the draft and the known drift is uncorrected at the destination. This is the founder's original concern, confirmed.
2. **Renumber sprint pins inside KI-NEW-J / L / M / N bodies in KNOWN_ISSUES.md** (Gate B). Sprint labels referenced in resume triggers must match the new sequence; the S13.5 label survives by founder spec but anchored references (S13-T4, S14-T1, S14-T3) all shift down by one.
3. **Resolve the KI-NEW-P / Q inventory drift** (Gate B). ROADMAP.md cites them as "newly opened post-S8" but no entries exist in KNOWN_ISSUES.md. Either file them or remove the ROADMAP claim.
4. **Renumber sprint references in STATE.md** (4 occurrences: L73, L145, L149, L165, L190; see Gate A). The pseudo_N "locked through S8–S14" assumption in invariant 5 must update to new-S13 or rephrase.
5. **Renumber PRODUCT.md L79** ("Sprints 10–13" → "Sprints 9–12").
6. **Fix the load-bearing "lifecycle ships before any ML model" claim in ROADMAP.md L43 + the "lifecycle gates ML" cell in the L36 table** (Gate C / Gate E). This is the load-bearing assumption that the DS verdict explicitly inverts; it cannot survive cutover.
7. **Replace ROADMAP.md L127 citation of ENGINE_OVERVIEW.md §6** (Gate C). ENGINE_OVERVIEW.md L94-101 still encodes "Sprints 10-13" — citing it as authority for the new sequence imports the old sequence.

### Should fix before commit

**Count: 5**

1. **D-1..D-8 paraphrase drift in PRODUCT.md §6** (Gate D, 8 entries). Replace with a verbatim quote of memory.md L173-180 or add the disclaimer "Canonical text: memory.md L173-180; this section is a copy." The "I-1" identifier in D-7 and "Sprint 3 spike memo" anchor should not be lost — code/tests reference them.
2. **engine_flags.md staleness chain** (Gate E + Gate G). STATE.md L123 self-flags this; CLAUDE.md routes agents there; the file has not been touched since 2026-05-03. Either refresh engine_flags.md or weaken the route.
3. **INDEX.md citation accuracy** (Gate F). Drop the "PIVOTS → i1-spike-findings via ROADMAP" claim (ROADMAP doesn't cite it; PRODUCT.md does); add an explicit STATE.md citation for `ds-architect-store-profile-layer-proposal.md` or move it out of the load-bearing list.
4. **docs/DECISIONS.md cross-ref verification** (Gate G). CLAUDE.md and STATE.md both route to docs/DECISIONS.md; this file's existence and content should be confirmed before relying on the route.
5. **PIVOTS.md L113 citation of `ARCHITECTURE_PLAN.md 2026-05-22 LOAD-BEARING UPDATE block`** (Gate H). Body-level reference (L80) to an archive-bound file; lift the quoted invariant text inline or guard with `docs/legacy/` redirect.

### OK to fix in follow-up

**Count: 6**

1. **Far-future sprint references** (ROADMAP.md L70-71: "Portfolio optimization (S22+)", "LLM mechanism generation (S26+)"). Shift by 1 for consistency or rephrase as "post-PMF."
2. **Phase 4 archive citations in body of PIVOTS.md Pivots 3, 4, 7, 8** (Gate H). These should migrate to `docs/legacy/` paths or get inline-quoted content. Not commit-blocking because the archive itself hasn't happened yet; the fix should land *with* the archive, not before it.
3. **memory.md L1921 OLD-sprint pins** for KI-NEW-L/M/N/J (Gate A). Memory.md is chronology; rewriting history is wrong. Add a forward-pointer in the next memory entry: "Note: sprint numbers re-anchored 2026-05-25 per doc-migration ROADMAP refresh; old S9/S13.5/S14 references in this entry map to new S15/S12.5/S13."
4. **ROADMAP.md L66** ("Was the previous plan's S10"). Rephrase to "Was previously planned for the post-substrate phase" to avoid number-of-number-of confusion.
5. **STATE.md L196** ("Scheduled S13.5 per KI-NEW-L"). S13.5 *label* survives per founder spec, but the body text could clarify "S13.5 = the cleanup window between new-S12-T4 and new-S13-T1, preserving the historical label."
6. **INDEX.md L20** "Sprint 9 not yet started" — under new numbering this is still accurate ("new-S9 = ML Part 1 kickoff, not yet started") but worth re-phrasing for unambiguous reading.

### No action needed

**Count: 5**

1. CLAUDE.md Doc Map structure (Gate G). Routing is correct.
2. PIVOTS.md Pivots 1, 2, 5, 6 (no sprint numbers in body).
3. STATE.md invariants 1–4, 6–12 (Gate C cross-check: source-supported, no number drift).
4. KI-1..KI-5, KI-NEW-A..F, H, I, O (Gate B: no sprint pins to renumber).
5. PRODUCT.md sections 1–5, 7–8 (no sprint numbers in body, paraphrase concerns only in §6).

---

*End of audit.*
