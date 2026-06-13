# Mechanism Contract — BeaconAI Engine v2.0.0

**Authority:** DS-locked 2026-05-30 (see `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` §(d))
**Decision anchor:** `docs/DECISIONS.md` D-S13.6-4
**Schema source:** `src/engine_run.py` (`MechanismType`, `MechanismIntent`)
**Parameter implementation:** `src/decide.py` (`_parameters_for_mechanism`)
**Last updated:** 2026-06-01

---

## Purpose

`PlayCard.mechanism_intent` carries a typed `MechanismType` enum value and a `parameters` dict via the `MechanismIntent` dataclass. Narration agents read this field to compose merchant-facing prose — the engine emits the typed atom; agents author the language. This file locks the meaning of each `MechanismType` value and the expected keys in `parameters` for every type.

---

## Per-type entries

### WINBACK_REACTIVATION_EMAIL

**Enum value:** `"WINBACK_REACTIVATION_EMAIL"`

**Semantic:** A re-engagement email sequence targeting customers who have gone dormant past a threshold window, with an optional offer to reactivate purchase behavior.

**parameters dict shape:**

| Key | Type | Meaning |
|---|---|---|
| `dormancy_window_days` | `int` | Minimum days since last order for a customer to be considered dormant and eligible for the winback sequence. |
| `offer_type` | `Literal["percent_off", "dollar_off", "none"]` | The type of incentive attached to the reactivation outreach. `"none"` means the sequence runs without a discount offer. |
| `measurement_window_days` | `int` | Days post-send within which a reactivation purchase is attributed to this mechanism. |

**Current values (v2.0.0):** `dormancy_window_days=21`, `offer_type="percent_off"`, `measurement_window_days=30`. The `dormancy_window_days` is sourced from the Beauty vertical entry boundary (`_winback_window_bounds`). `offer_type` is a default pending per-merchant config at S14.

**Narration guidance:** Emphasize the dormancy window and the reactivation offer type — do not frame as a discount unless `offer_type` is `"percent_off"` or `"dollar_off"`.

---

### FIRST_TO_SECOND_NUDGE

**Enum value:** `"FIRST_TO_SECOND_NUDGE"`

**Semantic:** A post-purchase nudge targeting customers who made their first order but have not yet returned within a defined window, designed to convert them to repeat buyers.

**parameters dict shape:**

| Key | Type | Meaning |
|---|---|---|
| `days_since_first_order_window` | `[int, int]` | Two-element list `[min, max]` — the range of days since first order that defines the eligible cohort (customers in this window are still in the nudge opportunity; outside it they have either converted or lapsed). |
| `measurement_window_days` | `int` | Days post-nudge within which a second purchase is attributed to this mechanism. |

**Current values (v2.0.0):** `days_since_first_order_window=[30, 90]` (sourced from the `cohort_journey_first_to_second_candidates` builder constants at `src/audience_builders.py`, DS-locked 2026-05-19). `measurement_window_days=30` (text-derived from the `_PRIOR_ANCHORED` registry mechanism_text).

**Narration guidance:** Emphasize the conversion window and the recency of the first purchase — the play targets customers who are still engaged, not lapsed.

---

### THRESHOLD_BUNDLE_OFFER

**Enum value:** `"THRESHOLD_BUNDLE_OFFER"`

**Semantic:** An offer that incentivizes customers to cross an AOV threshold (e.g., "spend $X more to get free shipping or a gift"), designed to lift average order value through bundle construction.

**parameters dict shape:**

| Key | Type | Meaning |
|---|---|---|
| `threshold_aov` | `float` | The bundle target dollar amount — the AOV level customers need to reach to unlock the offer. |
| `current_median_aov` | `float` | The store's current observed median AOV — the gap between this and `threshold_aov` informs offer sizing. |

**Current values (v2.0.0):** Both `threshold_aov=None` and `current_median_aov=None` with `TODO(S14)` markers. `threshold_aov` requires a per-merchant bundle target not yet threaded to the decide-seam. `current_median_aov` lives on the store profile / measurement context and is not yet passed to the `MechanismIntent` producer.

> **Implementation note:** Both values are `None` in the current implementation. Narration agents should check for `None` before using these values in copy. Values will be wired at S14 when the bundle-offer builder is promoted.

**Narration guidance:** Emphasize the gap between the current AOV and the threshold, and the reward for crossing it — do not fabricate a specific dollar gap if `threshold_aov` or `current_median_aov` is `None`.

---

### DISCOUNT_DEPENDENCY_HYGIENE

**Enum value:** `"DISCOUNT_DEPENDENCY_HYGIENE"`

**Semantic:** A suppression-style play that targets customers trained to buy only under discount, with the goal of shifting a portion of that cohort to full-price purchase behavior over time.

**parameters dict shape:**

| Key | Type | Meaning |
|---|---|---|
| `current_discount_share` | `float` | The store's measured share of revenue from heavy-discount orders (0.0–1.0). |
| `target_discount_share` | `float` | The target share after the hygiene play's intervention (0.0–1.0). |

**Current values (v2.0.0):** Both `current_discount_share=None` and `target_discount_share=None` with `TODO(S14)` markers. `current_discount_share` is computed by `measurement_builder.compute_heavy_discount_share_of_revenue` but is not threaded to the decide-seam. `target_discount_share` is not yet carried on the builder or registry entry.

> **Implementation note:** Both values are `None` in the current implementation. Narration agents should check for `None` before using these values in copy. Values will be wired at S14 when the discount-dependency builder is promoted.

**Narration guidance:** Emphasize the cost of discount dependency and the shift toward full-price behavior — do not frame as a discount play; this mechanism reduces discount exposure, not increases it.

---

### REPLENISHMENT_REMINDER

**Enum value:** `"REPLENISHMENT_REMINDER"`

**Semantic:** A reminder targeted at customers whose replenishment cadence for a specific SKU class predicts they are due to reorder, sent before they lapse or switch to a competitor.

**parameters dict shape:**

| Key | Type | Meaning |
|---|---|---|
| `replenishment_window_days` | `int` | The number of days defining the replenishment window — customers within this window of their predicted reorder date are the eligible cohort. |
| `sku_class` | `str` | The SKU class or product vertical identifier for which this replenishment cadence applies (e.g., a beauty regex key or supplements unit-coherent key). |

**Current values (v2.0.0):** Both `replenishment_window_days=None` and `sku_class=None` with `TODO(S14)` markers. The `replenishment_due_candidates` builder computes a per-SKU cadence median at runtime (`src/audience_builders.py` L351–358); there is no single store-level integer or SKU class string available at the decide-seam.

> **Implementation note:** Both values are `None` in the current implementation. Narration agents should check for `None` before using these values in copy. Values will be wired at S14 when the replenishment builder is promoted and the per-SKU seam is threaded.

**Narration guidance:** Emphasize the timing signal — customers are due to reorder based on their individual cadence, not a generic schedule — and the specific SKU class if `sku_class` is populated.

---

### BESTSELLER_AMPLIFY

**Enum value:** `"BESTSELLER_AMPLIFY"`

**Semantic:** A play that amplifies acquisition or conversion around the store's bestselling SKU(s), capitalizing on the existing social proof and conversion rate of top performers.

**parameters:** `{}` (empty; Tier-B placeholder — flesh out at S14+ when the builder is promoted out of Tier-B.)

**Narration guidance:** Narrate around the concept of amplifying an existing winning product — do not invent specific parameters (lift %, SKU name, audience size) that are not present in the typed atom.

---

### CATEGORY_EXPANSION

**Enum value:** `"CATEGORY_EXPANSION"`

**Semantic:** A play that introduces customers in one product category to an adjacent category, using cross-category purchase affinity to extend lifetime value.

**parameters:** `{}` (empty; Tier-B placeholder — flesh out at S14+ when the builder is promoted out of Tier-B.)

**Narration guidance:** Narrate around cross-category affinity and the opportunity to expand the customer's relationship with the brand — do not fabricate a specific target category unless populated in `parameters`.

---

### SUBSCRIPTION_NUDGE

**Enum value:** `"SUBSCRIPTION_NUDGE"`

**Semantic:** A play that nudges one-time buyers of replenishable products toward a subscription plan, converting transactional behavior to recurring revenue.

**parameters:** `{}` (empty; Tier-B placeholder — flesh out at S14+ when the builder is promoted out of Tier-B.)

**Narration guidance:** Narrate around the convenience and savings angle of subscription versus single-purchase — do not assert a specific subscriber LTV multiplier unless populated in `parameters`.

---

### ROUTINE_BUILDER

**Enum value:** `"ROUTINE_BUILDER"`

**Semantic:** A play that converts single-product customers into multi-step routine adopters (common in beauty/skincare), increasing purchase frequency and basket size through a sequenced product introduction.

**parameters:** `{}` (empty; Tier-B placeholder — flesh out at S14+ when the builder is promoted out of Tier-B.)

**Narration guidance:** Narrate around the routine-adoption behavioral pattern and the sequencing logic — do not fabricate specific product sequence steps unless populated in `parameters`.

---

### LOOKALIKE_HIGH_VALUE_PROSPECT

**Enum value:** `"LOOKALIKE_HIGH_VALUE_PROSPECT"`

**Semantic:** A prospecting play targeting new customers whose behavioral or demographic profile resembles the store's highest-value retained customers, as a paid or owned-channel acquisition mechanism.

**parameters:** `{}` (empty; Tier-B placeholder — flesh out at S14+ when the lookalike builder is promoted and an emission site is wired.)

**Narration guidance:** Narrate around the similarity signal and the acquisition objective — do not fabricate a specific match score, CAC estimate, or lookalike audience size unless populated in `parameters`.

---

## RULE A — When mechanism_intent is None

When `PlayCard.mechanism_intent` is `None`, the narration agent must not fabricate a mechanism type. The absence is typed: it means the engine did not assign a mechanism to this play (the play_id was not in the `_PLAY_ID_TO_MECHANISM_TYPE` map at the time of the run, or the play is a legacy play without a typed mechanism atom). The agent should narrate the play without a mechanism line — silence on mechanism is correct behavior, not a missing-data error.

---

## Tier-B note

Tier-B mechanism types (`BESTSELLER_AMPLIFY`, `CATEGORY_EXPANSION`, `SUBSCRIPTION_NUDGE`, `ROUTINE_BUILDER`, `LOOKALIKE_HIGH_VALUE_PROSPECT`) carry empty `parameters` dicts (`{}`) in v2.0.0. The per-type parameter shapes will be specified at S14+ when the corresponding builders are promoted out of Tier-B and their decide-seam values are threaded to the `MechanismIntent` producer. Narration agents must not assume any parameter keys are present for these types — always check before accessing.

---

*This file is a locked DS contract. Changes require DS review and a version bump in `src/engine_run.py`. See `docs/DECISIONS.md` D-S13.6-4.*
