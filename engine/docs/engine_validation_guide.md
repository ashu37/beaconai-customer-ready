# Engine Validation Guide

## Overview
This guide provides a step-by-step approach to validate engine outputs using the generated files. Use this checklist to ensure the engine is working correctly and producing accurate recommendations.

## Key Output Files

### Primary Validation Files
1. **`candidate_debug.json`** - Raw candidate data with confidence scores and tiers
2. **`run_summary.json`** - Complete action details with all metadata  
3. **`validation_report.json`** - Data quality assessment
4. **`YOUR_BRAND_briefing.html`** - Final rendered output for user

### Supporting Files
5. **`actions_log.json`** - Action tracking and performance history
6. **`qa_report.json`** - Data processing quality metrics
7. **`normalization_debug.json`** - Data ingestion debugging

---

## Step-by-Step Validation Process

### Step 1: Data Quality Check
**File:** `validation_report.json`

```bash
# Check overall validation status
jq '.overall_status, .validation_score, .summary' validation_report.json
```

**✅ Good Indicators:**
- `overall_status`: "green" or "amber" 
- `validation_score`: ≥ 70
- `summary`: No critical data issues

**❌ Red Flags:**
- `overall_status`: "red"
- `validation_score`: < 60
- Critical anomalies in data

**Example:**
```json
{
  "overall_status": "amber", 
  "validation_score": 78,
  "summary": "Minor data issues detected"
}
```

### Step 2: Enhanced Candidate Generation Check
**File:** `candidate_debug.json`

```bash
# Check candidate counts and enhanced confidence scoring
jq '.counts, .candidates[] | {id, confidence_score, engine_tier, seasonal_multiplier, seasonal_period, contributing_windows, window_scores}' candidate_debug.json
```

**✅ Expected Behavior:**
- 4-6 base candidates generated
- `confidence_score`: **Always within** mode-specific bounds (enhancements work within limits):
  - Learning: 0.30-0.95 (30-95%)
  - Conservative: 0.20-0.85 (20-85%)
  - Aggressive: 0.35-0.95 (35-95%)
- `engine_tier`: PRIMARY/QUICK_WINS/EXPERIMENTS/WATCHLIST
- `seasonal_multiplier`: Present and appropriate for current period (0.7-1.3 range)
- `seasonal_period`: Detected seasonal context (e.g., "routine_building", "bfcm", "post_holiday")
- `contributing_windows`: Array showing analyzed windows (["L7", "L28", "L56", "L90"])
- `window_scores`: P-values for each contributing window (non-zero for valid signals)
- No duplicates by `play_id`

**✅ Multi-Window Analysis Validation:**
```bash
# Check multi-window scoring is active
jq '.multiwindow_analysis.enabled, .available_windows, .window_weights' candidate_debug.json
```

**✅ Seasonal Intelligence Validation:**
```bash
# Check seasonal detection
jq '.candidates[] | {id, seasonal_multiplier, seasonal_period}' candidate_debug.json | head -3
```

**✅ Cohort Enhancement Validation:**
```bash
# Check if cohort pooling is active and enhancing candidates
jq '.candidates[] | {id, base_score, engine_tier} | select(.base_score > 0)' candidate_debug.json
```

**❌ Red Flags:**
- **Confidence scores outside mode bounds** (indicates calculation error)
- Missing seasonal_multiplier or seasonal_period fields
- All window_scores showing 0.0 (indicates multi-window not working)
- No contributing_windows array
- Missing cohort enhancement fields when ENABLE_COHORT_POOLING=true

**Example:**
```json
{
  "counts": {
    "base_candidates": 4,
    "actions": 0,
    "pilots": 1,
    "watchlist": 3
  },
  "candidates": [
    {
      "id": "aov_increase",
      "confidence_score": 0.9358556480007892,
      "engine_tier": "QUICK_WINS"
    }
  ]
}
```

### Step 3: Action Details Validation
**File:** `run_summary.json`

```bash
# Check action details and revenue projections
jq '.actions[], .watchlist[] | {play_id, confidence_score, engine_tier, "expected_$", tier}' run_summary.json
```

**✅ Expected Behavior:**
- `confidence_score` matches values from candidate_debug.json
- `engine_tier` assignment follows mode-specific rules:

**Learning Mode (CONFIDENCE_MODE=learning):**
  - PRIMARY: Pass all gates + ≥65% confidence
  - QUICK_WINS: Pass most gates + ≥50% confidence
  - EXPERIMENTS: Directional + ≥35% confidence
  - WATCHLIST: Directional but <35% confidence

**Conservative Mode (CONFIDENCE_MODE=conservative):**
  - PRIMARY: Pass all gates + ≥80% confidence
  - QUICK_WINS: Pass most gates + ≥65% confidence
  - EXPERIMENTS: Directional + ≥45% confidence
  - WATCHLIST: Directional but <45% confidence

**Aggressive Mode (CONFIDENCE_MODE=aggressive):**
  - PRIMARY: Pass all gates + ≥75% confidence
  - QUICK_WINS: Pass most gates + ≥60% confidence
  - EXPERIMENTS: Directional + ≥40% confidence
  - WATCHLIST: Directional but <40% confidence

- Revenue projections (`expected_$`) > 0 for viable actions

**❌ Red Flags:**
- Confidence scores don't match between files
- All actions have `expected_$ = 0`
- Tier assignments inconsistent with confidence/gates

### Step 4: HTML Output Validation
**File:** `YOUR_BRAND_briefing.html`

**Visual Checks:**
1. **Confidence Percentages:** Should show mode-appropriate ranges, not 1%
   - Learning: 30-95%
   - Conservative: 20-85%
   - Aggressive: 35-95%
2. **No Duplicates:** Each play appears exactly once
3. **Proper Tier Sections:**
   - 🎯 PRIMARY (rare, highest confidence + pass all gates)
   - ⚡ QUICK WINS (medium-high confidence)
   - 🔬 EXPERIMENTS (medium confidence, directional)
   - 👁️ WATCHLIST (low confidence or failed gates)

**HTML Grep Checks:**
```bash
# Check confidence percentages
grep -o 'unified-confidence-badge">[0-9]*%' YOUR_BRAND_briefing.html

# Check for duplicates
grep -o 'unified-card-title">[^<]*<' YOUR_BRAND_briefing.html | sort | uniq -d
```

**✅ Expected Output:**
```
unified-confidence-badge">94%
unified-confidence-badge">68%
unified-confidence-badge">57%
```

**❌ Red Flags:**
```
unified-confidence-badge">1%    # Wrong formatting
unified-confidence-badge">0%    # Missing confidence scores
```

### Step 5: Cross-File Consistency Check

**Confidence Score Consistency:**
```bash
# Extract confidence scores from both files
echo "=== candidate_debug.json ==="
jq -r '.candidates[] | "\(.play_id): \(.confidence_score)"' candidate_debug.json

echo "=== run_summary.json ==="  
jq -r '.watchlist[], .actions[] | "\(.play_id): \(.confidence_score)"' run_summary.json
```

**✅ Expected:** Same confidence_score for same play_id across files

**Tier Assignment Consistency:**
```bash
# Check tier assignments
echo "=== candidate_debug.json tiers ==="
jq -r '.candidates[] | "\(.play_id): \(.engine_tier)"' candidate_debug.json

echo "=== HTML tiers (manual check) ==="
# Verify each play appears in correct section of HTML
```

---

## Validation Checklist

### ✅ Data Quality (validation_report.json)
- [ ] `overall_status` is "green" or "amber"
- [ ] `validation_score` ≥ 70
- [ ] No critical data anomalies
- [ ] Sample size adequate (≥ 100 orders recommended)

### ✅ Candidate Generation (candidate_debug.json)  
- [ ] 4-6 base candidates generated
- [ ] All candidates have `confidence_score` in mode-appropriate ranges
- [ ] All candidates have `engine_tier` (PRIMARY/QUICK_WINS/EXPERIMENTS/WATCHLIST)
- [ ] No duplicate `play_id` values
- [ ] Tier assignments logical (higher confidence = higher tier)
- [ ] Gate failures explained in `reasons` array

### ✅ Action Details (run_summary.json)
- [ ] Confidence scores match candidate_debug.json
- [ ] Tier assignments consistent with rules
- [ ] Revenue projections reasonable (`expected_$` > 0 for viable actions)
- [ ] All required fields present (title, do_this, targeting, etc.)

### ✅ HTML Output (YOUR_BRAND_briefing.html)
- [ ] Confidence percentages in mode-appropriate ranges (not 1%)
- [ ] No duplicate plays in UI
- [ ] Plays appear in correct tier sections
- [ ] Revenue projections display correctly
- [ ] Gate failure reasons display properly in WATCHLIST
- [ ] Actions array has confidence_score field for HTML display

### ✅ Enhanced Features Validation (Multi-Window, Seasonal, Cohort)
- [ ] `ENABLE_MULTIWINDOW_SCORING=true` in .env
- [ ] `ENABLE_COHORT_POOLING=true` in .env  
- [ ] All candidates show seasonal_multiplier (0.7-1.3 range)
- [ ] All candidates show seasonal_period (not "unknown")
- [ ] Contributing_windows includes multiple windows (["L7", "L28", "L56", "L90"])
- [ ] Window_scores contain p-values (not all 0.0)
- [ ] Revenue calculations show realistic values (not $0 for viable actions)
- [ ] All revenue projections normalized to 28-day impact

### ✅ Revenue Calculation Validation
```bash
# Check for $0 revenue issues
jq '.candidates[] | select(.["expected_$"] == 0) | {id, play_id, p, effect_abs, n}' candidate_debug.json
```
- [ ] Actions with good stats (low p-value, decent effect, sufficient n) should have expected_$ > 0
- [ ] Revenue calculations use window-matched AOV and order data
- [ ] All revenue normalized to 28-day periods for fair comparison

### ✅ Cross-File Consistency
- [ ] Same confidence_score for same play_id across files
- [ ] Tier assignments match between candidate_debug and HTML
- [ ] No plays missing between files
- [ ] Enhanced features (seasonal, multi-window) consistent across debug files

---

## Mode-Adjusted Gate Thresholds

The engine applies mode-specific multipliers to base .env values:

**Current Base Values (.env) & Mode Adjustments:**
```
# Base .env Values → Mode Multipliers → Actual Thresholds
MIN_N_WINBACK=150      → 0.5/1.2/0.8 → Learning: 75, Conservative: 180, Aggressive: 120
MIN_N_SKU=75           → 0.5/1.2/0.8 → Learning: 37.5, Conservative: 90, Aggressive: 60  
AOV_EFFECT_FLOOR=0.05  → 0.5/1.0/0.8 → Learning: 2.5%, Conservative: 5%, Aggressive: 4%
REPEAT_PTS_FLOOR=0.03  → 0.5/1.0/0.8 → Learning: 1.5%, Conservative: 3%, Aggressive: 2.4%
DISCOUNT_PTS_FLOOR=0.05 → 0.5/1.0/0.8 → Learning: 2.5%, Conservative: 5%, Aggressive: 4%
FINANCIAL_FLOOR=auto   → 0.3/1.0/0.7 → Learning: 30%, Conservative: 100%, Aggressive: 70%
```

**Mode Multiplier Logic:**
- **Learning (PMF):** Relaxed barriers (0.5× sample, 0.5× effect, 0.3× financial)
- **Conservative:** Full rigor (1.2× sample, 1.0× effect, 1.0× financial)  
- **Aggressive:** Balanced (0.8× sample, 0.8× effect, 0.7× financial)

**Validation:** Check `reasons` array shows mode-adjusted values, not base .env values.

---

## Tier Assignment Math & Examples

### Confidence Score Calculation
**Formula:** `base_confidence × direction_mult × effect_mult × (0.7 + 0.3 × adequacy)`

**Real Example from current output:**
```json
{
  "id": "routine_builder",
  "p": 0.03,                    // p-value
  "effect_abs": 0.08,           // 8% effect size
  "n": 839,                     // sample size
  "confidence_score": 0.5495    // 54.95% final confidence
}
```

**Calculation Breakdown:**
1. **Signal strength:** `min(-log10(0.03), 4.0) = 1.52`
2. **Base confidence (learning):** Map 1.52 to 30-95% range = ~55%
3. **Direction multiplier:** 1.0 (positive effect)
4. **Effect multiplier:** `min(1.15, 1.0 + 0.08 × 0.3) = 1.024`
5. **Adequacy:** `min(log1p(839/100) / log1p(10), 1.0) = 0.95`
6. **Final:** `55% × 1.0 × 1.024 × (0.7 + 0.3 × 0.95) = 54.95%`

### Tier Assignment Logic
**Gates + Confidence → Tier Assignment**

**Example from current data:**
```json
{
  "id": "routine_builder",
  "passed": ["min_n", "significance", "effect_floor", "financial_floor"],
  "failed": [],
  "confidence_score": 0.5495,  // 54.95%
  "engine_tier": "QUICK_WINS"  // Because 54.95% ≥ 50% but < 65%
}
```

**Learning Mode Tier Bands:**
- **PRIMARY:** Pass all 4 gates + confidence ≥65% → **Would need 65%+ confidence**
- **QUICK_WINS:** Pass most gates + confidence ≥50% → **✅ Matches (54.95% ≥ 50%)**
- **EXPERIMENTS:** Directional + confidence ≥35%
- **WATCHLIST:** Directional but confidence <35%

### Gate Failure Examples

**Example: Winback failing multiple gates**
```json
{
  "id": "repeat_rate_improve", 
  "n": 2153,                    // ✅ Passes min_n (2153 ≥ 75)
  "p": 1.0,                     // ❌ Fails significance (1.0 > 0.20)  
  "effect_abs": 0.0,            // ❌ Fails effect_floor (0% < 1.5%)
  "expected_$": 0.0,            // ❌ Fails financial_floor ($0 < $59)
  "confidence_score": 0.3,      // 30% confidence
  "engine_tier": "WATCHLIST"    // Low confidence + failed gates
}
```

**Math Check:**
- Sample gate: `2153 ≥ 75` ✅
- Significance gate: `1.0 < 0.20` ❌ 
- Effect gate: `0.0% ≥ 1.5%` ❌
- Financial gate: `$0 ≥ $59` ❌

**Result:** 1 pass, 3 fails → WATCHLIST regardless of confidence

---

## Common Issues & Troubleshooting

### Issue: All confidence scores show 1%
**Cause:** Template not multiplying decimal by 100  
**Fix:** Check template uses `(confidence_score * 100)`
**Validation:** `grep "confidence_score.*100" templates/briefing.html.j2`

### Issue: Duplicate plays in HTML
**Cause:** Multiple tier systems processing same plays  
**Fix:** Ensure template uses `organize_by_engine_tiers()` function
**Validation:** Check only one play_id per tier in HTML

### Issue: No PRIMARY actions
**Cause:** PRIMARY requires pass all gates + high confidence:
- Learning mode: ≥65% confidence + pass all gates
- Conservative mode: ≥80% confidence + pass all gates  
- Aggressive mode: ≥75% confidence + pass all gates
**Expected:** This is normal if actions fail significance/effect/financial gates
**Validation:** Check `failed` array and gate reasons in candidate_debug.json

### Issue: All revenue projections $0
**Cause:** Data quality issues affecting statistical significance  
**Fix:** Address data anomalies in validation_report.json
**Validation:** Check for test data, outliers, date parsing issues

### Issue: Unexpected gate failures  
**Cause:** Mode-adjusted thresholds may be stricter/looser than expected
**Expected:** Learning mode relaxes thresholds, conservative mode tightens them
**Validation:** Check `CONFIDENCE_MODE` in .env and verify reasons show adjusted values

### Issue: Financial floor different than expected
**Cause:** `FINANCIAL_FLOOR_MODE=auto` calculates based on L28 revenue (0.5% × L28 × gross_margin)
**Expected:** Auto mode adapts to business scale, not fixed $300
**Validation:** Check if mode=auto vs fixed in .env

### Issue: Missing confidence scores in actions array
**Cause:** `candidate_debug.json` has confidence_score but `actions` array doesn't copy it
**Symptoms:** HTML can't display confidence percentages, actions may not tier properly
**Validation:** Check both files have same confidence_score for same play_id
**Example Problem:**
```json
// candidate_debug.json ✅
{"id": "routine_builder", "confidence_score": 0.5495, "engine_tier": "QUICK_WINS"}

// actions array ❌ 
{"id": "routine_builder", "score": 0.81, "confidence_label": "High"}
// Missing confidence_score field!
```

### Issue: No PRIMARY actions appearing
**Cause:** PRIMARY requires pass all gates + high confidence for mode
**Current example:** routine_builder has 54.95% confidence, needs ≥65% for PRIMARY
**Expected:** QUICK_WINS tier is correct (54.95% ≥ 50% threshold)
**Validation:** Check confidence vs tier thresholds for your mode

---

## Enhanced Features Validation Guide

### Multi-Window Analysis Check
```bash
# Verify multi-window is active
jq '.multiwindow_analysis.enabled' candidate_debug.json  # Should be true

# Check window coverage
jq '.candidates[0].contributing_windows' candidate_debug.json  # Should show ["L7", "L28", "L56", "L90"]

# Verify window scores are populated
jq '.candidates[] | {id, window_scores} | select(.window_scores | values != 0.0)' candidate_debug.json
```

### Seasonal Intelligence Check  
```bash
# Current seasonal period detection
jq '.candidates[0] | {seasonal_period, seasonal_multiplier}' candidate_debug.json

# Expected seasonal periods:
# - "routine_building" (Aug-Nov): 1.2x multiplier
# - "bfcm" (Nov 20-Dec 5): 1.3x multiplier  
# - "post_holiday" (Dec 26-Jan 15): 0.7x multiplier
# - "summer_slowdown" (Jun 15-Aug 15): 0.8x multiplier
```

### Cohort Enhancement Check
```bash
# Check if cohort pooling enhanced any candidates
jq '.candidates[] | select(.base_score > 0) | {id, base_score, confidence_score}' candidate_debug.json

# Verify cohort pooling is enabled
grep "ENABLE_COHORT_POOLING=true" .env
```

### Revenue Normalization Check
```bash
# Check all revenue values are realistic (not $0 for viable actions)
jq '.candidates[] | {id, "expected_$", p, effect_abs, n} | select(.p < 0.1 and .effect_abs > 0.02 and .n > 100)' candidate_debug.json

# These should have expected_$ > 0 if stats are good
```

## Quick Enhanced Validation Script

```bash
#!/bin/bash
# Enhanced engine validation script with new features

RECEIPTS_DIR="analysis/YOUR_BRAND/receipts"

echo "=== Enhanced Engine Validation Report ==="

echo "📊 Data Quality:"
jq -r '"\(.overall_status) (\(.validation_score)%): \(.summary)"' $RECEIPTS_DIR/validation_report.json

echo -e "\n🎯 Candidate Overview:"
jq -r '.counts | "Actions: \(.actions), Pilots: \(.pilots), Watchlist: \(.watchlist)"' $RECEIPTS_DIR/candidate_debug.json

echo -e "\n📈 Enhanced Confidence Scores:"
jq -r '.candidates[] | "\(.play_id): \(.confidence_score * 100 | floor)% (\(.engine_tier)) [seasonal: \(.seasonal_multiplier)x, period: \(.seasonal_period)]"' $RECEIPTS_DIR/candidate_debug.json

echo -e "\n🔄 Multi-Window Analysis:"
echo "Multi-window enabled: $(jq -r '.multiwindow_analysis.enabled // "not found"' $RECEIPTS_DIR/candidate_debug.json)"
echo "Available windows: $(jq -r '.available_windows // ["L7", "L28", "L56", "L90"] | join(", ")' $RECEIPTS_DIR/candidate_debug.json)"

echo -e "\n🌟 Seasonal Intelligence:"
jq -r '"Current period: \(.candidates[0].seasonal_period // "unknown") (multiplier: \(.candidates[0].seasonal_multiplier // "none")x)"' $RECEIPTS_DIR/candidate_debug.json

echo -e "\n👥 Cohort Enhancement:"
COHORT_ENHANCED=$(jq -r '[.candidates[] | select(.base_score > 0)] | length' $RECEIPTS_DIR/candidate_debug.json)
echo "Cohort-enhanced candidates: $COHORT_ENHANCED"
echo "Cohort pooling enabled: $(grep -q "ENABLE_COHORT_POOLING=true" .env && echo "✅ Yes" || echo "❌ No")"

echo -e "\n💰 Revenue Validation:"
ZERO_REVENUE=$(jq -r '[.candidates[] | select(.["expected_$"] == 0)] | length' $RECEIPTS_DIR/candidate_debug.json)
TOTAL_CANDIDATES=$(jq -r '.candidates | length' $RECEIPTS_DIR/candidate_debug.json)
echo "Candidates with $0 revenue: $ZERO_REVENUE/$TOTAL_CANDIDATES"

echo -e "\n🖥️  HTML Display Check:"
grep -o 'unified-confidence-badge">[0-9]*%' analysis/YOUR_BRAND/briefings/YOUR_BRAND_briefing.html | head -5

echo -e "\n🔍 Duplicate Check:"
DUPLICATES=$(grep -o 'unified-card-title">[^<]*<' analysis/YOUR_BRAND/briefings/YOUR_BRAND_briefing.html | sort | uniq -d)
if [ -z "$DUPLICATES" ]; then
    echo "✅ No duplicates found"
else
    echo "❌ Duplicates found: $DUPLICATES"
fi

echo -e "\n⚙️  Configuration Check:"
echo "Multi-window scoring: $(grep "ENABLE_MULTIWINDOW_SCORING" .env || echo "Not configured")"
echo "Cohort pooling: $(grep "ENABLE_COHORT_POOLING" .env || echo "Not configured")"
echo "Confidence mode: $(grep "CONFIDENCE_MODE" .env || echo "Not configured")"
```

---

## Success Criteria

**A properly functioning engine should show:**

1. **Data Quality:** Validation score ≥70, minimal critical issues
2. **Candidate Generation:** 4-6 candidates with mode-appropriate confidence scores
3. **Tier Assignment:** Logical distribution across PRIMARY/QUICK_WINS/EXPERIMENTS/WATCHLIST based on gates + confidence
4. **No Duplicates:** Each play appears exactly once
5. **Accurate Display:** Confidence percentages match calculated values  
6. **Revenue Projections:** Realistic expected revenue for viable actions
7. **Gate Logic:** Clear reasons for failures, mode-adjusted thresholds working correctly

**Use this guide to validate every engine run and ensure consistent, accurate recommendations.**

 Quick Validation Commands:

  Check confidence scores:
  jq '.candidates[] | {play_id, confidence_score, engine_tier}' analysis/YOUR_BRAND/receipts/candidate_debug.json

  Verify no duplicates in HTML:
  grep -o 'unified-card-title">[^<]*<' analysis/YOUR_BRAND/briefings/YOUR_BRAND_briefing.html | sort | uniq -d

  Check data quality:
  jq '.overall_status, .validation_score' analysis/YOUR_BRAND/receipts/validation_report.json