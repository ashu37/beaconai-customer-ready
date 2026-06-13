# BeaconAI Action Engine

## Overview

The Action Engine analyzes e-commerce data to recommend monthly marketing actions that drive incremental revenue. It uses statistical testing across multiple time windows to identify opportunities and provides confidence-scored recommendations.

Key characteristics:
- Multi-window statistical testing with vertical-aware weights
- Per-play revenue projections with base & optimistic ranges
- Vertical + stage aware conversion, effect, and gating parameters
- Confidence and materiality gates calibrated for premium pricing


## Core Functionality

### 1. Multi-Window Analysis
Analyzes four time horizons with vertical-aware weights (default: L7=0.0, L28=0.30, L56=0.60, L90=0.10) for robustness and signal stability:
- **L7 (7 days)**: Real-time signals (weight optional per vertical)
- **L28 (28 days)**: Primary business cycle
- **L56 (56 days)**: Medium-term validation
- **L90 (90 days)**: Long-term baseline

### 2. Statistical Testing
Each recommendation is backed by statistical tests:
- **AOV testing**: Welch t-test comparing recent vs prior periods
- **Repeat rate testing**: Two-proportion z-test for customer behavior changes
- **Discount testing**: Two-proportion z-test for discount pattern changes
- **FDR correction**: Adjusts for multiple testing to reduce false positives

### 3. Revenue Calculations
Each play produces a **base** and **optimistic** 28-day projection. The model adapts to the store’s vertical, stage, and health metrics:

1. **Baseline conversion** from vertical templates (beauty, supplements, mixed)
2. **Unified multiplier** combining stage, performance, retention, and execution levers (e.g., a growth store with exceptional retention scales like a mature store)
3. **Action effect assumptions** tuned per play (frequency lift, churn reduction, bundle value, etc.) with stage/health caps
4. **Incrementality & decay** based on vertical plus retention signals
5. **Saturation guard** to down-weight audiences that cover too much of the customer base

The optimistic projection uses lifted effect/decay multipliers and is logged alongside the base result for context.

### 4. Confidence & Scoring
Two scores drive recommendations:

- **final_score** – merit-based selection (financial impact, statistical strength, audience, etc.)
- **confidence_score** – execution risk calibrated by seasonal timing, multi-window alignment, effect direction safety, sample size, cohort pooling, and confidence mode

Confidence modes (`CONFIDENCE_MODE` in `.env`) shift thresholds:
- **learning** – lower statistical bar, good during onboarding
- **conservative** – stricter gates for established brands
- **aggressive** – widest funnel for experimentation

Tier assignment (PRIMARY / QUICK_WINS / WATCHLIST / EXPERIMENTS) arises from the combination of the two scores.

## Action Types

### Key Playbooks

- **Winback Campaign** – Retarget lapsed buyers; conversion & orders-per-customer scale with stage and retention health.
- **Bestseller Amplify** – Drive attach value for hero SKUs; bundle value capped by AOV and stage multipliers.
- **Discount Hygiene** – Reduce discount dependency; margin recovery linked to vertical averages.
- **Frequency Accelerator** – Increase cadence among loyalists; lift tied to repeat rate and business health.
- **Retention Mastery** – Prevent churn for high-value cohorts; churn reduction and realized LTV adapt to stage.
- **Journey Optimization** – Fix funnel drop-offs; conversion improvement tuned by vertical norms.
- **Routine Builder / Category Expansion** – Bundle or cross-sell adjacent products with stage-aware caps.
- **Subscription Nudge** – Promote subscriptions on repeat-purchase products using per-vertical adoption rates.

## Tier System

Actions are classified into 4 tiers based on confidence and impact:

- **PRIMARY**: High confidence + significant impact + passes all gates
- **QUICK_WINS**: Good signals + reasonable impact + passes most gates
- **WATCHLIST**: Promising signals but needs more data or impact
- **EXPERIMENTS**: Directional signals worth testing at small scale

### Two-Dimensional Scoring Architecture

The engine uses **two different scores** that serve complementary purposes:

**final_score** = "Should we recommend this?" (Selection Criteria)
```python
score = 0.35*financial + 0.25*significance + 0.20*effect_size + 0.10*confidence + 0.10*audience_size
```
- **Purpose**: Merit-based selection for statistical/financial soundness
- **Usage**: Primary ranking for action selection and pilot recommendations
- **Focus**: Revenue potential + statistical evidence quality

**confidence_score** = "How likely is this to succeed?" (Business Confidence)
```python
# 7-factor calibrated confidence including:
# Multi-window signals, seasonal timing, effect direction safety,
# sample size adequacy, cohort enhancement, mode-specific calibration
```
- **Purpose**: Context-aware presentation of execution risk
- **Usage**: Tier assignment (PRIMARY/QUICK_WINS/WATCHLIST/EXPERIMENTS)
- **Focus**: Real-world success probability + business context

### Risk-Adjusted Recommendation Matrix

| | High Confidence | Low Confidence |
|---|---|---|
| **High final_score** | 🟢 **PRIMARY**<br/>Strong evidence + high confidence<br/>*Top recommendations* | 🟡 **QUICK_WINS**<br/>Strong evidence + execution risk<br/>*Good opportunity, careful timing* |
| **Low final_score** | 🟠 **EXPERIMENTS**<br/>Weak evidence + high confidence<br/>*Low impact but reliable* | 🔴 **WATCHLIST**<br/>Weak evidence + execution risk<br/>*Monitor for improvement* |

### Example: High Merit, Low Confidence Action

An action might have:
- **High final_score (0.85)**: Strong statistical evidence (p=0.001) + big financial impact ($5,000)
- **Low confidence_score (0.25)**: Bad seasonal timing + weak multi-window signals + negative effect direction

**Result**: Gets recommended for consideration (high final_score) but assigned WATCHLIST tier (low confidence_score)

**Interpretation**: *"This looks promising on paper with strong statistical evidence and financial potential, but be very careful about execution timing and context - consider waiting for better conditions."*

This design prevents both:
- **False negatives**: Missing good opportunities due to poor timing
- **False positives**: Over-promising on contextually risky actions

## Key Features Removed in Recent Cleanup

✅ **Removed ActionTracker system** (~435 lines): Complete action tracking infrastructure that wasn't being used yet

✅ **Removed specialty candidates** (~270 lines):
- `sample_to_full`: Complex travel/sample product detection
- `ingredient_education`: Technical ingredient matching

✅ **Simplified revenue calculations**: Replaced complex normalization function with direct decay factors

✅ **Cleaned up dead code**: Removed unused imports, functions, and references

## Configuration

### Material Impact & Gating

Thresholds (effect floors, revenue floor, audience minimum, confidence) are computed through `get_material_thresholds()` using:
- **Vertical** (`VERTICAL_MODE`)
- **Business stage** (`BUSINESS_STAGE` or inferred from `ANNUAL_REVENUE`)
- **Current metrics** (monthly revenue, customer counts, retention)

Accepted actions record the thresholds that were applied.

### Key Environment Variables
- `VERTICAL_MODE`: beauty | supplements | mixed
- `SUBVERTICAL`: fitness | wellness | skincare | haircare | makeup | general (affects seasonality only)
- `BUSINESS_STAGE`: startup | growth | mature | enterprise (or inferred from `ANNUAL_REVENUE`)
- `CONFIDENCE_MODE`: learning | conservative | aggressive
- `ENGINE_DEBUG_CATEGORIES`: opt-in comma list for console logs (e.g. `revenue,actions`)

### Seasonality

Seasonal multipliers adjust action scoring based on retail calendar periods:

| Period | Dates | Base | Notes |
|--------|-------|------|-------|
| BFCM | Nov 15 - Dec 5 | 1.4x | Peak retail season |
| Holiday | Dec 6 - Dec 31 | 1.1x | Gift-giving period |
| January Detox | Jan 1 - Feb 15 | 0.7x | Post-holiday slowdown (except fitness) |
| Spring Reset | Mar - May 15 | 1.1x | Beauty/wellness refresh |
| Summer Slowdown | Jun 15 - Aug 15 | 0.8x | Vacation period |
| Routine Building | Aug 16 - Sep 30 | 1.2x | Back-to-school habits |

**Sub-vertical overrides** apply when `SUBVERTICAL` is set:
- `fitness`: January = 1.8x (New Year resolutions), Spring = 1.5x
- `wellness`: January = 1.4x, Spring = 1.3x
- `skincare`: Spring = 1.4x, Summer = 1.1x (SPF season)
- `makeup`: BFCM = 1.6x, Holiday = 1.4x

**Briefing callout**: When multiplier deviates >15% from 1.0, the HTML briefing displays a seasonal context banner (e.g., "This period is seasonally elevated. Interpret gains cautiously.")

### Logging & Debugging
Runtime output is governed by `ENGINE_DEBUG_CATEGORIES`. By default no categories are enabled; set the env var (e.g. `revenue,actions`) to opt into concise logs.

## Output Files

The engine generates:
- **Actions list**: Recommended campaigns with confidence scores, base/optimistic revenue, and applied thresholds
- **Segments**: Customer CSV files for campaign targeting
- **Charts**: Performance visualizations
- **Briefing**: HTML report with full analysis
- **Debug files**: Statistical details and validation data

## BeaconAI Score

Health score (0-100) calculated from 5 components:
- **Revenue Health (30%)**: Order volume + growth momentum
- **Customer Health (25%)**: Retention + loyalty patterns
- **Margin Health (20%)**: AOV trends + pricing efficiency
- **Growth Health (15%)**: Business trajectory signals
- **LTV Health (10%)**: Long-term value indicators

Score influences action confidence and risk tolerance.

## Key Architecture Files

- **`src/action_engine.py`**: Core selection logic and statistical testing
- **`src/features.py`**: Multi-window data preparation
- **`src/segments.py`**: Customer targeting and CSV generation
- **`src/utils.py`**: Configuration and seasonal adjustments
- **`src/main.py`**: Orchestration and file generation

## Statistical Examples

**AOV Test Example:**
```
Recent 28 days: [$45, $52, $48, $51...] → Avg: $49
Prior 28 days:  [$41, $46, $43, $47...] → Avg: $44
Welch t-test p-value: 0.0001 → Significant improvement
Effect: ($49 - $44) / $44 = 11.4% increase
```

**Repeat Rate Example:**
```
Recent: 10 of 15 customers bought 2+ times → 67%
Prior:  3 of 16 customers bought 2+ times → 19%
Two-proportion test p-value: 0.007 → Significant
Wilson CI: [5.7%, 81.3%] → Real improvement likely
```

## Recent Improvements

1. **Simplified revenue calculations**: Removed complex normalization in favor of direct decay factors
2. **Enhanced confidence scoring**: Multi-window aggregation with seasonal intelligence
3. **Code cleanup**: 16.6% reduction in file size while maintaining functionality
4. **Improved statistical rigor**: Better handling of multiple time windows
5. **Cleaner architecture**: Removed unused tracking system and specialty candidates

The engine now focuses on core functionality that drives real business results while maintaining statistical rigor and operational practicality.



## Conversion Rate logic explained

🔧 Base Conversion Rates (Fixed by Vertical)

  Hard-coded but changeable in action_engine.py:287-300:
  # FIXED per vertical - would need code changes
  'beauty': {
      'bestseller_amplify': 0.18,      # 18% base
      'journey_optimization': 0.35,    # 35% base  
      'frequency_accelerator': 0.22,   # 22% base
  }

  🎛️ Dynamic Multipliers (Business Performance Driven)

  Final conversion rate = base_rate × multiplier

  The multiplier combines 5 factors that automatically adjust based on your business health:

  1. Business Stage Multiplier (env: BUSINESS_STAGE)

  stage_multipliers = {
      'startup': 0.6x,      # 60% of base rates
      'growth': 0.8x,       # 80% of base rates  
      'mature': 1.0x,       # 100% of base rates
      'enterprise': 1.2x,   # 120% of base rates
  }

  2. Performance Multiplier (data-driven: 0.5x - 2.0x)

  Based on business_metrics from your data:
  - Returning share ≥90%: 1.5x boost 🎯 You qualify!
  - AOV growth ≥5%: 1.2x boost
  - Strong repeat rate: Additional boosts

  3. Health Conversion Boost (data-driven: 1.0x - 1.35x)

  - ≥95% returning + ≥30% repeat: 1.35x 🎯 You qualify!
  - ≥90% returning + ≥25% repeat: 1.20x
  - ≥85% returning + ≥20% repeat: 1.10x

  4. Execution Capability (business stage dependent)

  'growth': {
      'bestseller_amplify': 0.9x,
      'journey_optimization': 0.75x,
      'frequency_accelerator': 0.9x,
  }

  5. Health Execution Boost (data-driven: 1.0x - 1.25x)

  - ≥93% returning + ≥30% repeat: 1.25x 🎯 You qualify!

  🧮 Your Actual Multipliers

  For your beauty business (94.9% returning, 82.6% repeat):

  # Example: bestseller_amplify
  final_rate = 0.18 × growth_stage(0.8) × performance(1.5) × health_conversion(1.35) × execution(0.9) ×
  health_execution(1.25)
  final_rate = 0.18 × 0.8 × 1.5 × 1.35 × 0.9 × 1.25 = 0.37 = 37%

  Capped at 2.5x maximum (action_engine.py:388)

  🎚️ Environment Controls Available

  1. BUSINESS_STAGE = startup|growth|mature|enterprise
  2. ANNUAL_REVENUE = fallback for stage detection
  3. ENGINE_DEBUG_CATEGORIES = for debugging multipliers

## Frontend Sample Report Sync

After generating a report, you can sync the rendered briefing HTML and chart assets
into the frontend's static sample report folder. This copies the latest output into
`beaconai-frontend/public/reports/sample_report/` for preview in the web app.

Run from the beaconai repo:

```
python3 scripts/sync_sample_report.py --brand ACME --dest "/Users/atul.jena/Projects/Personal/beaconai-frontend/public/reports/sample_report"
```
