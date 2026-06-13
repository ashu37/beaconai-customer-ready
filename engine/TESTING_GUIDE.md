# BeaconAI Engine Testing Guide

## Overview

This guide provides testers with the formulas, definitions, and validation criteria needed to manually verify the BeaconAI engine's outputs.

---

## Table of Contents

1. [KPI Definitions & Formulas](#kpi-definitions--formulas)
2. [Multi-Window Analysis](#multi-window-analysis)
3. [Statistical Tests](#statistical-tests)
4. [Action Selection Criteria](#action-selection-criteria)
5. [Tier Assignment Logic](#tier-assignment-logic)
6. [Confidence Scoring](#confidence-scoring)
7. [Revenue Calculations](#revenue-calculations)
8. [Aura Score Calculation](#aura-score-calculation)
9. [Common Validation Scenarios](#common-validation-scenarios)

---

## 1. KPI Definitions & Formulas

### 1.1 Window Structure

The engine analyzes four time windows:
- **L7**: Last 7 days
- **L28**: Last 28 days
- **L56**: Last 56 days
- **L90**: Last 90 days

Each window compares **recent period** vs **prior period** of the same length.

**Example for L28:**
- Recent: Days 1-28 from anchor date
- Prior: Days 29-56 from anchor date

### 1.2 Core KPIs

#### Net Sales
```
Net Sales = Σ (Order Subtotal - Order Discount)

Alternative calculation:
Net Sales = Σ (Order Total - Shipping - Taxes)
```

**Validation:**
- Exclude cancelled orders (`Cancelled at` is NULL)
- Include refunds as negative values
- Deduplicate by order `Name` before summing

#### Orders
```
Orders = COUNT(DISTINCT order Name)
```

**Validation:**
- Count unique order names, not line items
- Exclude cancelled orders

#### AOV (Average Order Value)
```
AOV = Net Sales / Orders
```

**Example:**
```
Net Sales = $94,404.94
Orders = 1,374
AOV = $94,404.94 / 1,374 = $68.71
```

#### Discount Rate
```
Discount Rate = Σ(Order Discount) / Σ(Order Subtotal)
```

**Example:**
```
Total Discounts = $2,500
Total Subtotals = $100,000
Discount Rate = 2,500 / 100,000 = 0.025 (2.5%)
```

#### Repeat Rate Within Window
```
Repeat Rate = (Customers with 2+ orders in window) / (Total unique customers in window)
```

**Example:**
```
Customers with 2+ orders = 310
Total customers = 960
Repeat Rate = 310 / 960 = 0.323 (32.3%)
```

#### Returning Customer Share
```
Returning Share = (Orders from customers with prior history) / (Total orders)
```

**Validation:**
- "Prior history" = customer had at least one order before the window start date
- Check `customer_id` against historical orders

**Example:**
```
Orders from returning customers = 1,257
Total orders = 1,374
Returning Share = 1,257 / 1,374 = 0.915 (91.5%)
```

### 1.3 Delta Calculations

```
Delta (%) = (Recent - Prior) / Prior
```

**Example:**
```
Recent AOV = $68.71
Prior AOV = $67.54
Delta = (68.71 - 67.54) / 67.54 = 0.0173 (1.73%)
```

---

## 2. Multi-Window Analysis

### 2.1 Window Weights

Default weights by vertical (beauty):
```
L7:  0.00 (optional, real-time signal)
L28: 0.30 (primary business cycle)
L56: 0.60 (medium-term validation)
L90: 0.10 (long-term baseline)
```

### 2.2 Primary Window Selection

The engine selects the "best" window for each action based on:
1. **Highest weight** (L56 usually wins)
2. **Statistical significance** (p-value)
3. **Effect size magnitude**

**Validation:**
Check `source_window` field in action to see which window was selected.

---

## 3. Statistical Tests

### 3.1 Two-Proportion Test (Repeat Rate, Conversion)

Used for: Comparing proportions between two groups

**Formula:**
```
p1 = x1 / n1  (recent proportion)
p2 = x2 / n2  (prior proportion)
diff = p1 - p2

p_pooled = (x1 + x2) / (n1 + n2)
SE_pooled = sqrt(p_pooled * (1 - p_pooled) * (1/n1 + 1/n2))

z = diff / SE_pooled
p_value = 2 * (1 - Φ(|z|))  # Two-sided test
```

**Example:**
```
Recent: 310 repeat customers out of 960 total (32.3%)
Prior: 320 repeat customers out of 955 total (33.5%)

diff = 0.323 - 0.335 = -0.012
p_pooled = (310 + 320) / (960 + 955) = 0.329
SE = sqrt(0.329 * 0.671 * (1/960 + 1/955)) = 0.0215
z = -0.012 / 0.0215 = -0.558
p_value = 0.577 (not significant)
```

### 3.2 Welch T-Test (AOV)

Used for: Comparing means of two groups (unequal variances)

**Formula:**
```
t = (mean1 - mean2) / sqrt(var1/n1 + var2/n2)

degrees_of_freedom = complex formula (handled by scipy)
p_value = from t-distribution
```

**Validation:**
- Use `scipy.stats.ttest_ind(group1, group2, equal_var=False)`
- Compare engine's p-value with manual calculation

### 3.3 Benjamini-Hochberg FDR Correction

Used for: Adjusting p-values when testing multiple hypotheses

**Formula:**
```
1. Sort p-values in ascending order: p(1) ≤ p(2) ≤ ... ≤ p(m)
2. For each test i, calculate: q(i) = p(i) * m / i
3. Enforce monotonicity (work backwards): q(i) = min(q(i), q(i+1))
4. Reject if q(i) ≤ α (default α = 0.15)
```

**Example:**
```
FDR_ALPHA = 0.15
p-values = [0.002, 0.048, 0.119, 0.412]

Step 1: Already sorted
Step 2:
  q(1) = 0.002 * 4 / 1 = 0.008
  q(2) = 0.048 * 4 / 2 = 0.096
  q(3) = 0.119 * 4 / 3 = 0.159
  q(4) = 0.412 * 4 / 4 = 0.412

Step 3: Monotonicity (backwards)
  q(4) = 0.412
  q(3) = min(0.159, 0.412) = 0.159
  q(2) = min(0.096, 0.159) = 0.096
  q(1) = min(0.008, 0.096) = 0.008

Step 4: Reject?
  q(1) = 0.008 ≤ 0.15 → Reject H0 (significant)
  q(2) = 0.096 ≤ 0.15 → Reject H0 (significant)
  q(3) = 0.159 > 0.15 → Accept H0 (not significant)
  q(4) = 0.412 > 0.15 → Accept H0 (not significant)
```

---

## 4. Action Selection Criteria

### 4.1 All Available Actions (Plays)

| Play ID | Metric Tested | Segment Logic | Minimum Audience |
|---------|---------------|---------------|------------------|
| `winback_21_45` | Repeat rate | Last order 21-45 days ago | 75 |
| `bestseller_amplify` | AOV | Buyers of top product | 30 |
| `discount_hygiene` | Discount rate | High discount users (>20%) | 75 |
| `frequency_accelerator` | Frequency | 2+ orders in L90, idle 14+ days | 50 |
| `aov_momentum` | AOV growth | Recent customers (7-30d ago) | 30 |
| `retention_mastery` | Retention | At-risk (45+ days, 2+ orders) | 25 |
| `journey_optimization` | Conversion | Single-order customers | 50 |
| `category_expansion` | Cross-sell | Single-category buyers (2+ orders) | 40 |
| `subscription_nudge` | Subscription | 3+ repeat purchases of same product | 20 |
| `routine_builder` | Bundle AOV | Single-product skincare buyers | 75 |

### 4.2 Action Selection Example: Winback 21-45

**Segment Logic:**
```python
# Get last order per customer
last_orders = g.groupby('customer_id')['Created at'].max()

# Calculate days since last order from anchor
days_since_last = (anchor - last_orders).dt.days

# Filter for 21-45 day window
winback_customers = days_since_last[
    (days_since_last >= 21) & (days_since_last <= 45)
].index
```

**Statistical Test:**
```
Metric: repeat_rate
Test: Two-proportion test
H0: Repeat rate in recent period = Repeat rate in prior period
H1: Repeat rate in recent period ≠ Repeat rate in prior period

Windows tested: L28, L56, L90 (not L7)
Best window selected based on highest weight + significance
```

**Gates to Pass:**
1. **min_n**: Audience ≥ 75 (adjusted by mode)
2. **significance**: p < 0.20 (learning) OR q < 0.15 OR CI excludes 0
3. **effect_floor**: |effect| ≥ 0.03 (3% points, adjusted by mode)
4. **financial_floor**: Expected revenue ≥ $300 (adjusted by mode)

### 4.3 Action Selection Example: Discount Hygiene

**Segment Logic:**
```python
# Calculate per-customer average discount rate
customer_discount = g.groupby('customer_id')['discount_rate'].mean()

# Flag customers with high discount dependency
high_discount_customers = customer_discount[customer_discount >= 0.20].index
```

**Statistical Test:**
```
Metric: discount_rate
Test: Two-proportion or t-test on discount depth
H0: Discount rate in recent = Discount rate in prior
H1: Discount rate decreased (one-sided)

Effect measured: Reduction in discount rate (positive = improvement)
```

**Special Notes:**
- Only action where incrementality = 1.0 (margin protection)
- Revenue calculation based on margin recovery, not conversion

---

## 5. Tier Assignment Logic

### 5.1 The Four Gates

Every action must pass these gates to qualify for PRIMARY tier:

| Gate | Criteria (Learning Mode) | Criteria (Conservative) |
|------|--------------------------|-------------------------|
| **min_n** | n ≥ 0.5 × required_n | n ≥ 1.2 × required_n |
| **significance** | p < 0.20 OR q < 0.15 OR CI excludes 0 | p < 0.01 OR q < 0.15 |
| **effect_floor** | \|effect\| ≥ 0.5 × floor | \|effect\| ≥ 1.0 × floor |
| **financial_floor** | revenue ≥ 0.3 × $300 | revenue ≥ 1.0 × $300 |

### 5.2 Confidence Thresholds by Mode

| Mode | PRIMARY | QUICK_WINS | EXPERIMENTS |
|------|---------|------------|-------------|
| **learning** | ≥65% | ≥50% | ≥35% |
| **conservative** | ≥80% | ≥65% | ≥45% |
| **aggressive** | ≥75% | ≥60% | ≥40% |

### 5.3 Tier Assignment Algorithm

```python
gates_passed = count of passed gates (0-4)
confidence_score = engine confidence (0-1, converted to %)

if gates_passed == 4 AND confidence >= PRIMARY_threshold:
    tier = "PRIMARY"
elif (gates_passed >= 3 OR 'significance' in passed) AND confidence >= QUICK_WINS_threshold:
    tier = "QUICK_WINS"
elif gates_passed > 0 AND confidence >= EXPERIMENTS_threshold:
    tier = "EXPERIMENTS"
elif gates_passed > 0:
    tier = "WATCHLIST"
else:
    tier = "NO_CALL"
```

### 5.4 Validation Example

**Action: Bestseller Amplify (from run_summary.json)**
```json
{
  "play_id": "bestseller_amplify",
  "n": 8816,
  "p": 0.119,
  "q": 0.239,
  "effect_abs": 0.0188,
  "expected_$": 4305,
  "confidence_score": 0.675,
  "passed": ["min_n", "significance", "financial_floor"],
  "failed": ["effect_floor"],
  "engine_tier": "QUICK_WINS"
}
```

**Manual Validation (Learning Mode):**

1. **Gates Check:**
   - min_n: n=8816 ≥ 75×0.5=37.5 ✅ PASS
   - significance: p=0.119 < 0.20 ✅ PASS
   - effect_floor: |0.0188| ≥ 0.05×0.5=0.025? → 0.0188 < 0.025 ❌ FAIL
   - financial_floor: $4305 ≥ $300×0.3=$90 ✅ PASS
   - **Gates passed: 3/4**

2. **Confidence Check:**
   - Confidence: 67.5% ≥ 50% (QUICK_WINS threshold) ✅

3. **Tier Logic:**
   - Gates passed (3) ≥ 3? YES
   - Confidence (67.5%) ≥ 50%? YES
   - **Expected tier: QUICK_WINS** ✅

**Result: Tier assignment is CORRECT**

---

## 6. Confidence Scoring

### 6.1 Dual Scoring System

The engine uses TWO different scores:

#### Final Score (Merit-based)
```
final_score = 0.35×financial + 0.25×significance + 0.20×effect_size + 0.10×confidence + 0.10×audience_size
```

**Used for:** Ranking actions for selection

#### Confidence Score (Execution Risk)
```
confidence_score = (0.6 × statistical_confidence) + (0.4 × business_context)
```

**Used for:** Tier assignment

### 6.2 Statistical Confidence Tiers

Based on p-value:
```
p < 0.01  → 95% confidence (Very Strong)
p < 0.05  → 80% confidence (Strong)
p < 0.10  → 50% confidence (Moderate)
p < 0.20  → Linear interpolation: 50% → 10%
p ≥ 0.20  → 5% confidence (Very Weak)
```

**Example:**
```
p = 0.119
→ Falls in p < 0.20 range
→ Statistical confidence ≈ 40-50%
```

### 6.3 Business Context Factors

1. **Sample Size Adequacy:** n / required_n (capped at 1.0)
2. **Seasonal Timing:** 0.85x to 1.15x multiplier
3. **Effect Quality:** Magnitude vs floor
4. **Multi-window Alignment:** Signal strength across windows

### 6.4 Validation Example

**Action with p=0.048, n=5492, required_n=75:**

```
Statistical confidence (p=0.048 < 0.05) = 80%

Business context:
- Sample adequacy = min(5492/75, 1.0) = 1.0 (100%)
- Seasonal = 1.0 (neutral)
- Effect quality = 0.8 (good)
- Multi-window = 0.9 (strong)

Context score = 1.0 × 1.0 × 0.8 × 0.9 = 0.72 (72%)

Final confidence = 0.6×0.80 + 0.4×0.72 = 0.48 + 0.288 = 0.768 (76.8%)
```

---

## 7. Revenue Calculations

### 7.1 Base Revenue Formula

```
Converters = Audience × Conversion_Rate
Revenue_per_Converter = AOV × (1 + Effect_Size)
Gross_Revenue = Converters × Revenue_per_Converter × Incrementality
Net_Revenue = Gross_Revenue × Gross_Margin
```

### 7.2 Conversion Rate Calculation

```
Base_Rate = vertical_specific_rate[play_id]
Multiplier = stage_mult × performance_mult × health_boost × execution_mult × health_execution_boost
Final_Conversion = Base_Rate × Multiplier (capped at 2.5×)
```

**Example (Bestseller Amplify, Beauty, Growth stage):**
```
Base rate = 0.18 (18%)
Stage multiplier = 0.8 (growth)
Performance multiplier = 1.5 (high returning share)
Health boost = 1.35 (excellent retention)
Execution = 0.9
Health execution = 1.25

Combined = 0.8 × 1.5 × 1.35 × 0.9 × 1.25 = 1.82
Final rate = 0.18 × 1.82 = 0.328 (32.8%)
```

### 7.3 Validation Example

**Action: Discount Hygiene**
```json
{
  "audience_size": 1374,
  "effect_abs": 0.00485,
  "expected_$": 709.98
}
```

**Manual Calculation:**
```
For discount hygiene:
Margin_Recovery = Discount_Reduction × Current_Revenue

Current revenue (L28) = $94,404.94
Current discount rate = 2.69%
Discount reduction = 0.485% points

Revenue_Impact = $94,404.94 × (0.00485 / 0.0269) = $17,032
Net_Revenue = $17,032 × 0.70 (margin) × 0.30 (28-day factor) = $3,577

Note: This is a simplified calculation. Engine uses more complex
incrementality and decay factors.
```

### 7.4 Optimistic Revenue

```
Optimistic effect = Base effect × 1.3
Optimistic incrementality = Base incrementality + 0.05

Optimistic revenue follows same formula with adjusted parameters
```

**Range Calculation:**
```
expected_range = [base_revenue × 0.6, optimistic_revenue × 1.3]
```

---

## 8. Aura Score Calculation

### 8.1 Component Weights

```
Aura Score = 0.30×Revenue_Health + 0.25×Customer_Health + 0.20×Margin_Health + 0.15×Growth_Health + 0.10×LTV_Health
```

### 8.2 Component Definitions

#### Revenue Health (30%)
```
Based on:
- Order volume (L28 orders vs benchmarks)
- Revenue momentum (L28 vs L56 growth)
- Consistency across windows

Score: 0-100
```

#### Customer Health (25%)
```
Based on:
- Returning customer share (target: >80%)
- Repeat rate within window (target: >30%)
- New customer rate (balanced, not too high/low)

Score: 0-100
```

#### Margin Health (20%)
```
Based on:
- AOV trends (growing vs shrinking)
- Discount rate (lower is better, <5% ideal)
- Pricing power signals

Score: 0-100
```

#### Growth Health (15%)
```
Based on:
- Order growth rate (L28 vs prior)
- Customer acquisition momentum
- Revenue trajectory

Score: 0-100
```

#### LTV Health (10%)
```
Based on:
- 90-day customer LTV estimates
- Cohort retention curves
- Frequency acceleration signals

Score: 0-100
```

### 8.3 Validation Example

**From run_summary.json:**
```json
{
  "aura_score": {
    "overall": 77,
    "components": {
      "revenue_health": 85.0,
      "customer_health": 98.56,
      "margin_health": 58.55,
      "growth_health": 65.0,
      "ltv_health": 49.14
    }
  }
}
```

**Manual Verification:**
```
Score = 0.30×85.0 + 0.25×98.56 + 0.20×58.55 + 0.15×65.0 + 0.10×49.14
      = 25.5 + 24.64 + 11.71 + 9.75 + 4.914
      = 76.514
      ≈ 77 (rounded)

✅ CORRECT
```

### 8.4 Tier Classification

```
90-100: Exceptional
80-89:  Thriving
70-79:  Healthy
60-69:  Stable
50-59:  Watchful
<50:    Needs attention
```

---

## 9. Common Validation Scenarios

### 9.1 Scenario 1: Action with Mixed Gates

**Data:**
```
Play: winback_21_45
n: 2496
p: 0.637
q: 0.637
effect: -0.0093
expected_$: 4054
confidence: 3.2%
```

**Validation:**
1. Gates:
   - min_n: 2496 ≥ 150×0.5=75 ✅
   - significance: p=0.637 > 0.20 AND q=0.637 > 0.15 ❌
   - effect_floor: |-0.0093| ≥ 0.03×0.5=0.015? NO ❌
   - financial: 4054 ≥ 300×0.3=90 ✅

2. Gates passed: 2/4
3. Confidence: 3.2% < 50% (QUICK_WINS threshold)
4. **Expected tier: WATCHLIST** (has directional signal)

### 9.2 Scenario 2: Verifying Window Selection

**Data:**
```
Play: bestseller_amplify
Windows tested: L28, L56, L90
Window p-values:
  L28: p=0.412
  L56: p=0.879
  L90: p=0.119

source_window: L90
```

**Why L90 was selected:**
1. L90 has best (lowest) p-value: 0.119
2. Even though L56 has higher default weight (0.6), it's not significant (p=0.879)
3. Engine prioritizes significance over weight when signal quality differs

**Validation:** ✅ CORRECT (L90 has strongest signal)

### 9.3 Scenario 3: AOV Calculation Mismatch

**If you see:**
```
Your calculation: $68.50
Engine output: $68.71
Difference: $0.21
```

**Common causes:**
1. **Order deduplication:** Did you count unique order `Name`?
2. **Cancelled orders:** Did you exclude `Cancelled at IS NOT NULL`?
3. **Net sales method:** Did you use Subtotal-Discount or Total-Shipping-Taxes?
4. **Rounding:** Engine uses full precision, only rounds for display

**Validation:** Difference <1% is acceptable

### 9.4 Scenario 4: Confidence Score Seems Wrong

**Data:**
```
Action has p=0.002 (very significant)
But confidence_score = 0.35 (35%, low)
```

**Possible reasons:**
1. **Seasonal penalty:** Action proposed during off-season (0.85× multiplier)
2. **Effect direction:** Negative effect (harmful) gets 0.01× penalty
3. **Sample size:** n is below required threshold
4. **Multi-window conflict:** Only 1 of 3 windows shows signal

**Check:** Look at `reasons` array in action JSON

### 9.5 Scenario 5: Expected Revenue Seems High

**Data:**
```
Audience: 150
Conversion: 18%
AOV: $75
Effect: +15%
Expected revenue: $4,500
```

**Validation:**
```
Converters = 150 × 0.18 = 27
Revenue per = $75 × 1.15 = $86.25
Gross = 27 × $86.25 = $2,329
With incrementality (0.85) = $1,979
With margin (0.70) = $1,385

Engine shows: $4,500

MISMATCH! Possible causes:
- Performance multipliers boosted conversion from 18% to ~45%
- Check conversion_multiplier in debug logs
- High retention businesses (94%+) get 1.5-2.5× multipliers
```

---

## Testing Checklist

### Pre-Test Setup
- [ ] Upload valid orders CSV with required columns
- [ ] Set correct VERTICAL_MODE (beauty/supplements/mixed)
- [ ] Set correct BUSINESS_STAGE (startup/growth/mature/enterprise)
- [ ] Set correct CONFIDENCE_MODE (learning/conservative/aggressive)
- [ ] Set GROSS_MARGIN (typically 60-80% for beauty)
- [ ] Note the anchor date from run_summary.json

### KPI Validation
- [ ] Verify L28 net_sales matches your calculation (±1%)
- [ ] Verify L28 orders count
- [ ] Verify L28 AOV = net_sales / orders
- [ ] Check repeat_rate_within_window formula
- [ ] Check returning_customer_share includes prior history
- [ ] Verify discount_rate calculation

### Statistical Tests
- [ ] Verify p-values for AOV (Welch t-test)
- [ ] Verify p-values for repeat rate (two-proportion)
- [ ] Check q-values (BH-FDR correction)
- [ ] Verify delta calculations (recent vs prior)

### Action Validation
- [ ] Check each action has correct play_id
- [ ] Verify audience_size matches segment criteria
- [ ] Check statistical test matches action type
- [ ] Verify source_window selection logic
- [ ] Validate expected revenue calculation

### Tier Validation
- [ ] For each action, count gates passed (0-4)
- [ ] Verify confidence_score value
- [ ] Check tier matches threshold for mode
- [ ] Validate tier assignment logic
- [ ] Review failure reasons in `reasons` array

### Aura Score
- [ ] Verify component scores sum correctly
- [ ] Check component weights (30/25/20/15/10)
- [ ] Validate overall score calculation
- [ ] Confirm tier classification (healthy/thriving/etc)

### Edge Cases
- [ ] Actions with 0 gates passed → NO_CALL
- [ ] Actions with negative effects → Low confidence
- [ ] Actions with p > 0.20 and q > 0.15 → Watchlist
- [ ] Pure-directional signals → EXPERIMENTS or WATCHLIST

---

## Reporting Issues

When reporting validation discrepancies:

1. **Specify the KPI/Action:**
   - "L28 AOV calculation mismatch"
   - "Bestseller Amplify tier assignment incorrect"

2. **Provide your calculation:**
   - Show formulas used
   - Show intermediate steps
   - Show final result

3. **Show engine output:**
   - Copy relevant JSON from run_summary.json
   - Include confidence_score, gates passed, tier

4. **Note the difference:**
   - Absolute difference
   - Percentage difference
   - Expected vs actual

5. **Include context:**
   - Confidence mode used
   - Vertical/stage settings
   - Anchor date

---

## Quick Reference Tables

### Effect Floors by Action Type

| Action | Metric | Floor (Learning) | Floor (Conservative) |
|--------|--------|------------------|----------------------|
| Winback | Repeat rate | 1.5% pts | 3.0% pts |
| Bestseller | AOV | 2.5% | 5.0% |
| Discount | Discount rate | 2.5% pts | 5.0% pts |
| Frequency | Frequency | 12% | 12% |
| Retention | Retention | 2.5% pts | 2.5% pts |
| Journey | Conversion | 8% | 8% |

### Conversion Rates (Beauty, Mature Stage)

| Action | Base Rate | With Multipliers |
|--------|-----------|------------------|
| Winback 21-45 | 8% | 8-20% |
| Bestseller | 18% | 18-45% |
| Frequency | 22% | 22-55% |
| Retention | 85% | 85-100% |
| Journey | 35% | 35-70% |

### Incrementality Factors (Beauty)

| Action | Base Incrementality |
|--------|---------------------|
| Winback | 75% |
| Bestseller | 85% |
| Discount | 100% (margin action) |
| Frequency | 88% |
| Retention | 100% (retention) |
| Journey | 80% |

---

## Version

**Guide Version:** 2.0
**Engine Version:** 1.0
**Last Updated:** 2025-10-01

---

## Support

For questions about this testing guide:
- Check the `ENGINE.md` file for architecture details
- Review `run_summary.json` structure
- Examine `candidate_debug.json` for detailed action calculations
