# Onboarding Optimization Guide

## Overview
This guide outlines the business context fields to capture during user onboarding that will optimize engine settings for each specific brand. By collecting this information upfront, we can automatically configure the action engine for maximum relevance and accuracy.

## Essential Business Context Fields

### 1. Business Stage & Scale

#### Business Stage
```javascript
business_stage: {
  type: 'select',
  options: ['startup', 'growth', 'mature', 'enterprise'],
  default: 'growth',
  impact: 'Sets CONFIDENCE_MODE and risk tolerance'
}
```

**Impact on Engine:**
- **Startup:** `CONFIDENCE_MODE=learning` - Lower thresholds for faster experimentation
- **Growth:** `CONFIDENCE_MODE=aggressive` - Balanced approach with good coverage
- **Mature:** `CONFIDENCE_MODE=conservative` - Higher rigor for established brands
- **Enterprise:** `CONFIDENCE_MODE=conservative` - Maximum statistical rigor

#### Monthly Revenue Range
```javascript
monthly_revenue_range: {
  type: 'select', 
  options: ['<10k', '10k-50k', '50k-200k', '200k-1M', '>1M'],
  impact: 'Adjusts financial floors and sample size requirements'
}
```

**Engine Configuration:**
```python
revenue_floors = {
    '<10k': 50,      # Lower barrier for small businesses
    '10k-50k': 100,   # Moderate threshold
    '50k-200k': 300,  # Standard threshold
    '200k-1M': 500,   # Higher expectations
    '>1M': 1000       # Enterprise-level requirements
}
```

### 2. Vertical & Product Mix

#### Primary Vertical
```javascript
primary_vertical: {
  type: 'select',
  options: ['beauty', 'supplements', 'skincare', 'wellness', 'mixed'],
  impact: 'Optimizes seasonal periods, subscription thresholds, window weights'
}
```

**Seasonal Optimization:**
- **Beauty:** Enhanced confidence during gift seasons (Valentine's, Mother's Day, holidays)
- **Supplements:** Boosted performance during January detox, reduced summer expectations
- **Skincare:** Routine-building periods emphasized, weather-based adjustments
- **Wellness:** New Year resolution periods, seasonal wellness trends
- **Mixed:** Balanced approach with auto-detection

#### Product Lifecycle
```javascript
product_lifecycle: {
  type: 'select', 
  options: ['consumable_fast', 'consumable_slow', 'durable', 'mixed'],
  help: 'Fast: 7-30 days, Slow: 30-90 days, Durable: >90 days',
  impact: 'Sets optimal analysis windows (L7 vs L28 vs L56/L90 focus)'
}
```

**Window Policy Mapping:**
```python
window_mapping = {
    'consumable_fast': 'L28',    # Focus on shorter cycles (beauty, snacks)
    'consumable_slow': 'auto',   # Multi-window with L56/L90 emphasis (supplements)
    'durable': 'L90',           # Long analysis windows (tools, devices)
    'mixed': 'auto'             # Full multi-window analysis
}
```

### 3. Customer Behavior Patterns

#### Typical Purchase Frequency
```javascript
typical_purchase_frequency: {
  type: 'select',
  options: ['weekly', 'monthly', 'quarterly', 'irregular', 'unknown'],
  impact: 'Optimizes repeat rate analysis windows and subscription detection'
}
```

**Analysis Window Optimization:**
- **Weekly:** Emphasize L7 and L28 windows, shorter subscription cycles
- **Monthly:** Focus on L28 and L56 windows, standard subscription detection
- **Quarterly:** Prioritize L56 and L90 windows, longer subscription cycles
- **Irregular:** Full multi-window analysis with equal weighting
- **Unknown:** Auto-detection from data patterns

#### Average Customer Orders Per Year
```javascript
average_customer_orders_per_year: {
  type: 'number',
  placeholder: '2-12 typical range',
  impact: 'Calibrates cohort detection and LTV calculations'
}
```

**Cohort Detection Calibration:**
```python
def calibrate_cohort_thresholds(orders_per_year):
    if orders_per_year >= 8:
        return {'loyal_threshold': 3, 'high_value_percentile': 75}
    elif orders_per_year >= 4:
        return {'loyal_threshold': 2, 'high_value_percentile': 80}
    else:
        return {'loyal_threshold': 1, 'high_value_percentile': 85}
```

### 4. Marketing & Risk Profile

#### Risk Tolerance
```javascript
risk_tolerance: {
  type: 'select',
  options: ['conservative', 'balanced', 'aggressive'],
  impact: 'Sets CONFIDENCE_MODE and gate thresholds'
}
```

**Gate Threshold Adjustments:**
- **Conservative:** 
  - p-value threshold: p < 0.01
  - Sample size: 120% of standard requirements
  - Effect floor: 100% of standard thresholds
- **Balanced:** 
  - p-value threshold: p < 0.10
  - Sample size: 80% of standard requirements
  - Effect floor: 80% of standard thresholds
- **Aggressive:** 
  - p-value threshold: p < 0.20
  - Sample size: 50% of standard requirements
  - Effect floor: 50% of standard thresholds

#### Testing Budget Monthly
```javascript
testing_budget_monthly: {
  type: 'select',
  options: ['<500', '500-2k', '2k-10k', '>10k'],
  impact: 'Adjusts pilot budgets and audience fraction limits'
}
```

**Pilot Configuration:**
```python
pilot_configs = {
    '<500': {'audience_fraction': 0.1, 'budget_cap': 100},
    '500-2k': {'audience_fraction': 0.2, 'budget_cap': 300},
    '2k-10k': {'audience_fraction': 0.3, 'budget_cap': 1000},
    '>10k': {'audience_fraction': 0.4, 'budget_cap': 2500}
}
```

#### Primary Channels
```javascript
primary_channels: {
  type: 'multiselect',
  options: ['email', 'sms', 'paid_ads', 'social', 'influencer'],
  impact: 'Sets channel caps and interaction factors'
}
```

**Channel Caps Configuration:**
```python
def set_channel_caps(primary_channels):
    base_caps = {'email': 2, 'sms': 1, 'paid_ads': 1}
    
    # Increase caps for primary channels
    for channel in primary_channels:
        if channel in base_caps:
            base_caps[channel] += 1
    
    return base_caps
```

### 5. Seasonality Context

#### Peak Seasons
```javascript
peak_seasons: {
  type: 'multiselect',
  options: ['bfcm', 'january_detox', 'valentines', 'mothers_day', 'summer', 'back_to_school', 'holidays'],
  impact: 'Customizes seasonal multipliers beyond default calendar'
}
```

#### Off Seasons
```javascript
off_seasons: {
  type: 'multiselect', 
  options: ['january', 'february', 'summer', 'september', 'other'],
  impact: 'Applies seasonal penalties during known slow periods'
}
```

**Custom Seasonal Configuration:**
```python
def create_custom_seasonal_calendar(peak_seasons, off_seasons):
    calendar = default_seasonal_calendar.copy()
    
    # Boost multipliers for declared peak seasons
    for season in peak_seasons:
        if season in calendar:
            calendar[season]['multiplier'] *= 1.2
    
    # Reduce multipliers for declared off seasons
    for season in off_seasons:
        if season in calendar:
            calendar[season]['multiplier'] *= 0.8
    
    return calendar
```

### 6. Operational Constraints

#### Team Bandwidth
```javascript
team_bandwidth: {
  type: 'select',
  options: ['solo_founder', 'small_team_2_5', 'medium_team_6_20', 'large_team_20plus'],
  impact: 'Sets EFFORT_BUDGET and campaign complexity limits'
}
```

**Effort Budget Mapping:**
```python
effort_budgets = {
    'solo_founder': 3,        # Maximum 3 concurrent actions
    'small_team_2_5': 5,      # Moderate workload
    'medium_team_6_20': 8,    # Standard capacity
    'large_team_20plus': 12   # High capacity for multiple actions
}
```

#### Discount Policy
```javascript
discount_policy: {
  type: 'select',
  options: ['no_discounts', 'minimal_10_percent', 'moderate_25_percent', 'aggressive_50_percent'],
  impact: 'Configures discount hygiene thresholds and LTV preferences'
}
```

**Policy Configuration:**
```python
discount_configs = {
    'no_discounts': {
        'discount_hygiene_enabled': False,
        'ltv_preference_weight': 1.0
    },
    'minimal_10_percent': {
        'discount_threshold': 0.10,
        'ltv_preference_weight': 0.8
    },
    'moderate_25_percent': {
        'discount_threshold': 0.25,
        'ltv_preference_weight': 0.6
    },
    'aggressive_50_percent': {
        'discount_threshold': 0.50,
        'ltv_preference_weight': 0.4
    }
}
```

## Engine Configuration Mapping

### Automatic Configuration Function
```python
def configure_engine_from_onboarding(responses):
    """
    Automatically configure engine settings based on onboarding responses
    """
    config = {}
    
    # 1. Confidence mode from business stage + risk tolerance
    stage = responses.get('business_stage', 'growth')
    risk = responses.get('risk_tolerance', 'balanced')
    
    if stage == 'startup' or risk == 'aggressive':
        config['CONFIDENCE_MODE'] = 'learning'
    elif stage == 'mature' or risk == 'conservative':
        config['CONFIDENCE_MODE'] = 'conservative'  
    else:
        config['CONFIDENCE_MODE'] = 'aggressive'
    
    # 2. Window policy from product lifecycle
    lifecycle = responses.get('product_lifecycle', 'mixed')
    window_mapping = {
        'consumable_fast': 'L28',
        'consumable_slow': 'auto', 
        'durable': 'L90',
        'mixed': 'auto'
    }
    config['WINDOW_POLICY'] = window_mapping[lifecycle]
    
    # 3. Financial floors from revenue range
    revenue = responses.get('monthly_revenue_range', '50k-200k')
    revenue_floors = {
        '<10k': 50, '10k-50k': 100, '50k-200k': 300, 
        '200k-1M': 500, '>1M': 1000
    }
    config['FINANCIAL_FLOOR_FIXED'] = revenue_floors[revenue]
    config['FINANCIAL_FLOOR_MODE'] = 'fixed'
    
    # 4. Effort budget from team size
    team = responses.get('team_bandwidth', 'medium_team_6_20')
    effort_budgets = {
        'solo_founder': 3, 'small_team_2_5': 5, 
        'medium_team_6_20': 8, 'large_team_20plus': 12
    }
    config['EFFORT_BUDGET'] = effort_budgets[team]
    
    # 5. Vertical-specific settings
    vertical = responses.get('primary_vertical', 'mixed')
    config['VERTICAL_MODE'] = vertical
    
    # 6. Channel caps from primary channels
    channels = responses.get('primary_channels', ['email'])
    config['CHANNEL_CAPS'] = set_channel_caps(channels)
    
    # 7. Pilot settings from testing budget
    budget = responses.get('testing_budget_monthly', '500-2k')
    pilot_configs = {
        '<500': {'audience_fraction': 0.1, 'budget_cap': 100},
        '500-2k': {'audience_fraction': 0.2, 'budget_cap': 300},
        '2k-10k': {'audience_fraction': 0.3, 'budget_cap': 1000},
        '>10k': {'audience_fraction': 0.4, 'budget_cap': 2500}
    }
    pilot_config = pilot_configs[budget]
    config['PILOT_AUDIENCE_FRACTION'] = pilot_config['audience_fraction']
    config['PILOT_BUDGET_CAP'] = pilot_config['budget_cap']
    
    # 8. Enhanced features (always enabled)
    config['ENABLE_MULTIWINDOW_SCORING'] = True
    config['ENABLE_COHORT_POOLING'] = True
    
    return config

def write_engine_config(config, brand_name):
    """
    Write optimized .env configuration for the brand
    """
    env_content = f"""# Auto-generated configuration for {brand_name}
# Generated from onboarding responses

# Core confidence and analysis mode
CONFIDENCE_MODE={config['CONFIDENCE_MODE']}
WINDOW_POLICY={config['WINDOW_POLICY']}

# Financial thresholds
FINANCIAL_FLOOR_MODE={config['FINANCIAL_FLOOR_MODE']}
FINANCIAL_FLOOR_FIXED={config['FINANCIAL_FLOOR_FIXED']}

# Team and operational limits
EFFORT_BUDGET={config['EFFORT_BUDGET']}
PILOT_AUDIENCE_FRACTION={config['PILOT_AUDIENCE_FRACTION']}
PILOT_BUDGET_CAP={config['PILOT_BUDGET_CAP']}

# Vertical and behavior
VERTICAL_MODE={config['VERTICAL_MODE']}

# Enhanced features
ENABLE_MULTIWINDOW_SCORING={str(config['ENABLE_MULTIWINDOW_SCORING']).lower()}
ENABLE_COHORT_POOLING={str(config['ENABLE_COHORT_POOLING']).lower()}

# Channel configuration
CHANNEL_CAPS={json.dumps(config['CHANNEL_CAPS'])}
"""
    
    return env_content
```

## Onboarding UI Flow Recommendation

### Page 1: Business Basics (Required)
**Title:** "Tell us about your business"

Fields:
- Business stage
- Monthly revenue range  
- Team bandwidth

**Helper Text:** *"This helps us set the right confidence levels and workload for your recommendations"*

**Progress:** 1/5 pages

### Page 2: Products & Customers (Required)
**Title:** "What do you sell and how do customers buy?"

Fields:
- Primary vertical
- Product lifecycle
- Typical purchase frequency
- Average customer orders per year

**Helper Text:** *"We'll optimize analysis windows and patterns for your specific product type"*

**Progress:** 2/5 pages

### Page 3: Marketing Approach (Required)
**Title:** "How do you approach marketing and testing?"

Fields:
- Risk tolerance
- Testing budget monthly
- Primary channels (multiselect)

**Helper Text:** *"This calibrates our recommendation aggressiveness to your comfort level"*

**Progress:** 3/5 pages

### Page 4: Seasonality (Optional)
**Title:** "When does your business peak and slow down?"

Fields:
- Peak seasons (multiselect)
- Off seasons (multiselect)

**Helper Text:** *"Skip if unknown - we'll detect patterns from your data. This helps us time recommendations better."*

**Skip Option:** "Detect automatically from my data"

**Progress:** 4/5 pages

### Page 5: Business Rules (Optional)  
**Title:** "Any specific constraints or policies?"

Fields:
- Discount policy
- Additional operational constraints (free text)

**Helper Text:** *"These settings help us recommend realistic actions that fit your brand guidelines"*

**Skip Option:** "Use smart defaults"

**Progress:** 5/5 pages

## Smart Defaults & Progressive Enhancement

### Default Configuration
```javascript
const smart_defaults = {
  // Safe defaults for unknown context
  business_stage: 'growth',
  risk_tolerance: 'balanced', 
  primary_vertical: 'mixed',
  product_lifecycle: 'mixed',
  monthly_revenue_range: '50k-200k',
  team_bandwidth: 'medium_team_6_20',
  
  // Progressive enhancement flags
  show_advanced_seasonality: false,  // Show only if they select specific verticals
  auto_detect_patterns: true,        // Learn from data over time
  allow_confidence_override: true,   // Manual override in settings later
  
  // Enhanced features (always on)
  enable_multiwindow: true,
  enable_cohort_pooling: true,
  enable_seasonal_intelligence: true
}
```

### Conditional Logic
```javascript
// Show advanced seasonality only for specific verticals
if (['beauty', 'supplements', 'skincare'].includes(primary_vertical)) {
  showAdvancedSeasonality = true;
}

// Suggest specific configurations based on combinations
if (business_stage === 'startup' && monthly_revenue < '10k') {
  suggestConfiguration = {
    confidence_mode: 'learning',
    financial_floors: 'minimal',
    effort_budget: 'conservative'
  }
}
```

## Implementation Notes

### Backend Integration
1. **Configuration Generation:** Auto-generate `.env` files based on onboarding
2. **Progressive Learning:** Update configurations as more data becomes available
3. **A/B Testing:** Test different configuration combinations for similar business profiles
4. **Validation:** Ensure generated configurations are valid and safe

### Frontend UX
1. **Progressive Disclosure:** Show advanced options only when relevant
2. **Smart Defaults:** Pre-populate based on previous selections
3. **Contextual Help:** Explain impact of each setting on recommendations
4. **Configuration Preview:** Show how settings will affect their analysis before saving

### Data Storage
```sql
CREATE TABLE brand_configurations (
    id SERIAL PRIMARY KEY,
    brand_id VARCHAR NOT NULL,
    onboarding_responses JSONB,
    generated_config JSONB,
    config_version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

This onboarding optimization will dramatically improve first-time user experience and recommendation quality by tailoring the engine to each brand's specific context and constraints.