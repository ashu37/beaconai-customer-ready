"""
Execution templates for each play.

Each template provides structured execution data that gets merged with
runtime values (audience size, segment path, expected revenue) to produce
actionable step-by-step instructions.
"""

from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Play Execution Templates
# ---------------------------------------------------------------------------

PLAY_EXECUTION_TEMPLATES: Dict[str, Dict[str, Any]] = {

    "journey_optimization": {
        "audience": {
            "description": "Customers with browse/cart activity but no purchase in L28",
        },
        "channel": {
            "primary": "email",
            "secondary": "sms",
            "platform": None,  # Defaults to "Email ESP"
        },
        "sequence": {
            "touches": 3,
            "timing": ["Day 0", "Day 3", "Day 7"],
            "format": ["email", "sms", "email"],
        },
        "offer": {
            "type": "progressive",
            "structure": "None → 10% off → 10% + free shipping",
            "cap": "$15 max discount",
        },
        "creative": {
            "templates": ["journey_recovery_email_1.txt", "journey_recovery_sms.txt"],
            "assets_needed": ["Product images", "Brand header"],
        },
        "measurement": {
            "holdout_pct": 15,
            "kpi": "Segment conversion rate",
            "target": "2.5–4%",
            "window_days": 14,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Journey_Recovery_{month}'.",
            "Create a 3-touch flow: Email Day 0, SMS Day 3, Email Day 7.",
            "Day 0 email: Remind product value and benefits. No discount yet.",
            "Day 3 SMS: Offer 10% off if no purchase. Keep copy short and urgent.",
            "Day 7 email: Final reminder with 10% + free shipping. Add urgency.",
            "Set flow exit condition: Purchase or unsubscribe.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "frequency_accelerator": {
        "audience": {
            "description": "Repeat customers (2+ orders in L90) who haven't ordered in 14+ days",
        },
        "channel": {
            "primary": "email",
            "secondary": "sms",
            "platform": None,
        },
        "sequence": {
            "touches": 2,
            "timing": ["Day 0", "Day 5"],
            "format": ["email", "email"],
        },
        "offer": {
            "type": "loyalty",
            "structure": "Early access or loyalty points → 10% off",
            "cap": "$12 max discount",
        },
        "creative": {
            "templates": ["frequency_email_1.txt", "frequency_email_2.txt"],
            "assets_needed": ["Personalized product recs", "Purchase history callout"],
        },
        "measurement": {
            "holdout_pct": 15,
            "kpi": "Reorder rate",
            "target": "+15% vs holdout",
            "window_days": 28,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform}.",
            "Create a 2-touch flow: Email Day 0, Email Day 5.",
            "Day 0 email: Personalized product recommendations based on purchase history. Offer early access or loyalty points.",
            "Day 5 email: If no purchase, offer 10% off their most-purchased category.",
            "Exclude customers who purchased in last 14 days from flow.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "retention_mastery": {
        "audience": {
            "description": "High-value customers at churn risk (45+ days since last order)",
        },
        "channel": {
            "primary": "email",
            "secondary": "sms",
            "platform": None,
        },
        "sequence": {
            "touches": 4,
            "timing": ["Day 0", "Day 3", "Day 7", "Day 14"],
            "format": ["email", "sms", "email", "email"],
        },
        "offer": {
            "type": "escalating",
            "structure": "None → 10% → 15% → 20% (VIP only)",
            "cap": "$25 max discount",
        },
        "creative": {
            "templates": ["retention_email_1.txt", "retention_sms.txt", "retention_email_2.txt"],
            "assets_needed": ["Customer history summary", "VIP badge for top tier"],
        },
        "measurement": {
            "holdout_pct": 20,
            "kpi": "Reactivation rate",
            "target": "5–8%",
            "window_days": 28,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Retention_AtRisk_{month}'.",
            "Create a 4-touch escalating flow: Email D0, SMS D3, Email D7, Email D14.",
            "Day 0 email: We miss you message. Highlight new products or restocks. No discount.",
            "Day 3 SMS: Quick check-in with 10% off code if no engagement.",
            "Day 7 email: Offer 15% off with product recommendations based on past purchases.",
            "Day 14 email (VIP only): Final offer of 20% off for top-tier customers. Personal tone.",
            "Cap total discount at $25 per customer to protect margin.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "winback_21_45": {
        "audience": {
            "description": "Lapsed customers with last order 21-45 days ago",
        },
        "channel": {
            "primary": "email",
            "secondary": "sms",
            "platform": None,
        },
        "sequence": {
            "touches": 3,
            "timing": ["Day 0", "Day 7", "Day 14"],
            "format": ["email", "email", "sms"],
        },
        "offer": {
            "type": "fixed",
            "structure": "15% off from first touch",
            "cap": "$20 max discount",
        },
        "creative": {
            "templates": ["winback_email_1.txt", "winback_email_2.txt", "winback_sms.txt"],
            "assets_needed": ["Bestseller images", "Time-limited offer badge"],
        },
        "measurement": {
            "holdout_pct": 15,
            "kpi": "Reactivation rate",
            "target": "8–12%",
            "window_days": 21,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Winback_21_45_{month}'.",
            "Create a 3-touch flow: Email D0, Email D7, SMS D14.",
            "Day 0 email: 'We miss you' with 15% off code. Feature bestsellers they haven't tried.",
            "Day 7 email: Reminder of offer expiring. Add social proof (reviews, purchase counts).",
            "Day 14 SMS: Last chance message. Short, urgent, include discount code.",
            "Set offer expiration at 21 days from first touch.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "dormant_multibuyers_60_120": {
        "audience": {
            "description": "Multi-buyers (3+ orders) dormant for 60-120 days",
        },
        "channel": {
            "primary": "email",
            "secondary": "direct_mail",
            "platform": None,
        },
        "sequence": {
            "touches": 3,
            "timing": ["Day 0", "Day 7", "Day 21"],
            "format": ["email", "email", "email"],
        },
        "offer": {
            "type": "escalating",
            "structure": "20% off → 25% off → 30% off (final)",
            "cap": "$40 max discount",
        },
        "creative": {
            "templates": ["dormant_email_1.txt", "dormant_email_2.txt", "dormant_email_3.txt"],
            "assets_needed": ["Purchase history recap", "Exclusive return offer"],
        },
        "measurement": {
            "holdout_pct": 20,
            "kpi": "Reactivation rate",
            "target": "4–7%",
            "window_days": 30,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Dormant_VIP_{month}'.",
            "Create a 3-touch flow: Email D0, Email D7, Email D21.",
            "Day 0 email: Personalized 'We miss our VIP' message. 20% off. Recap their purchase history.",
            "Day 7 email: Increase to 25% off. Highlight what's new since their last order.",
            "Day 21 email: Final 30% off offer. Make it feel exclusive and time-limited.",
            "Consider direct mail postcard for top 10% by LTV if budget allows.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "bestseller_amplify": {
        "audience": {
            "description": "Customers who purchased hero SKU but not complementary products",
        },
        "channel": {
            "primary": "email",
            "secondary": "onsite",
            "platform": None,
        },
        "sequence": {
            "touches": 2,
            "timing": ["Day 0", "Day 4"],
            "format": ["email", "email"],
        },
        "offer": {
            "type": "bundle",
            "structure": "15% off when buying 2+ items",
            "cap": "$18 max discount",
        },
        "creative": {
            "templates": ["bestseller_email_1.txt", "bestseller_email_2.txt"],
            "assets_needed": ["Bundle product shots", "Cross-sell recommendations"],
        },
        "measurement": {
            "holdout_pct": 15,
            "kpi": "AOV lift",
            "target": "+$5–8",
            "window_days": 14,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Bestseller_Xsell_{month}'.",
            "Create a 2-touch flow: Email D0, Email D4.",
            "Day 0 email: 'Complete your routine' with complementary product recommendations. 15% bundle discount.",
            "Day 4 email: If no purchase, show customer reviews for recommended products. Maintain 15% offer.",
            "Add onsite banner for this segment showing bundle deals.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "discount_hygiene": {
        "audience": {
            "description": "Customers who only purchase with discounts (3+ discounted orders)",
        },
        "channel": {
            "primary": "email",
            "secondary": None,
            "platform": None,
        },
        "sequence": {
            "touches": 2,
            "timing": ["Day 0", "Day 7"],
            "format": ["email", "email"],
        },
        "offer": {
            "type": "value",
            "structure": "No discount - value messaging only",
            "cap": "None",
        },
        "creative": {
            "templates": ["discount_hygiene_email_1.txt", "discount_hygiene_email_2.txt"],
            "assets_needed": ["Brand story content", "Product quality callouts"],
        },
        "measurement": {
            "holdout_pct": 20,
            "kpi": "Full-price purchase rate",
            "target": "+5% vs baseline",
            "window_days": 28,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Discount_Hygiene_{month}'.",
            "Create a 2-touch educational flow: Email D0, Email D7.",
            "Day 0 email: Lead with brand story, ingredient quality, or customer testimonials. No discount.",
            "Day 7 email: Feature product benefits and value proposition. Still no discount.",
            "Remove this segment from promotional discount campaigns for 28 days.",
            "Goal: Train segment to purchase at full price by emphasizing value over price.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "subscription_nudge": {
        "audience": {
            "description": "Repeat purchasers of consumable products (3+ orders of same SKU)",
        },
        "channel": {
            "primary": "email",
            "secondary": "onsite",
            "platform": None,
        },
        "sequence": {
            "touches": 2,
            "timing": ["Day 0", "Day 5"],
            "format": ["email", "email"],
        },
        "offer": {
            "type": "subscription",
            "structure": "10% off + free shipping on subscription",
            "cap": "Ongoing 10%",
        },
        "creative": {
            "templates": ["subscription_email_1.txt", "subscription_email_2.txt"],
            "assets_needed": ["Subscription benefits graphic", "Easy cancel messaging"],
        },
        "measurement": {
            "holdout_pct": 15,
            "kpi": "Subscription conversion rate",
            "target": "3–5%",
            "window_days": 21,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Sub_Nudge_{month}'.",
            "Create a 2-touch flow: Email D0, Email D5.",
            "Day 0 email: 'Never run out' message. Highlight 10% savings + free shipping on subscription.",
            "Day 5 email: Address objections - easy to pause, cancel anytime, modify frequency.",
            "Add onsite subscription upsell for this segment's repeat-purchased products.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "routine_builder": {
        "audience": {
            "description": "Single-category buyers ready for cross-category expansion",
        },
        "channel": {
            "primary": "email",
            "secondary": "onsite",
            "platform": None,
        },
        "sequence": {
            "touches": 2,
            "timing": ["Day 0", "Day 5"],
            "format": ["email", "email"],
        },
        "offer": {
            "type": "bundle",
            "structure": "15% off routine bundle",
            "cap": "$20 max discount",
        },
        "creative": {
            "templates": ["routine_email_1.txt", "routine_email_2.txt"],
            "assets_needed": ["Routine bundle shots", "Step-by-step usage guide"],
        },
        "measurement": {
            "holdout_pct": 15,
            "kpi": "Cross-category purchase rate",
            "target": "8–12%",
            "window_days": 21,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'Routine_Builder_{month}'.",
            "Create a 2-touch flow: Email D0, Email D5.",
            "Day 0 email: 'Build your complete routine' with curated bundle. 15% off bundle price.",
            "Day 5 email: Educational content on how products work together. Maintain 15% offer.",
            "Include step-by-step usage guide as value-add content.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },

    "aov_momentum": {
        "audience": {
            "description": "Customers with recent AOV increase trend",
        },
        "channel": {
            "primary": "email",
            "secondary": None,
            "platform": None,
        },
        "sequence": {
            "touches": 2,
            "timing": ["Day 0", "Day 7"],
            "format": ["email", "email"],
        },
        "offer": {
            "type": "threshold",
            "structure": "Free gift at $X spend (10% above their avg AOV)",
            "cap": "Gift value < $15",
        },
        "creative": {
            "templates": ["aov_email_1.txt", "aov_email_2.txt"],
            "assets_needed": ["Free gift image", "Threshold progress bar"],
        },
        "measurement": {
            "holdout_pct": 15,
            "kpi": "AOV lift",
            "target": "+10%",
            "window_days": 28,
        },
        "steps_template": [
            "Export {segment_label} ({audience_size} customers) and upload to {platform} as 'AOV_Momentum_{month}'.",
            "Create a 2-touch flow: Email D0, Email D7.",
            "Day 0 email: Offer free gift at spend threshold (set 10% above their average AOV).",
            "Day 7 email: Reminder of free gift offer with product recommendations to hit threshold.",
            "Personalize threshold based on each customer's historical AOV.",
            "Hold out {holdout_pct}% of segment for measurement ({holdout_size} customers).",
        ],
    },
}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_execution_template(play_id: str) -> Optional[Dict[str, Any]]:
    """Get execution template for a play, or None if not found."""
    return PLAY_EXECUTION_TEMPLATES.get(play_id)


def build_execution_plan(
    play_id: str,
    segment_path: str,
    segment_label: str,
    audience_size: int,
    expected_revenue: float,
    platform: str = "Email ESP",
    month: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build a complete execution plan by merging template with runtime values.

    Args:
        play_id: The play identifier (e.g., 'journey_optimization')
        segment_path: Path to the segment CSV file
        segment_label: Human-readable segment name
        audience_size: Number of customers in segment
        expected_revenue: Expected revenue from action
        platform: Email platform name (default: "Email ESP")
        month: Month label for campaign naming (default: current month)

    Returns:
        Complete execution plan dict, or None if play not found
    """
    import datetime

    template = get_execution_template(play_id)
    if not template:
        return None

    # Default month to current
    if month is None:
        month = datetime.datetime.now().strftime("%b%y")

    # Calculate holdout size
    holdout_pct = template.get("measurement", {}).get("holdout_pct", 15)
    holdout_size = int(audience_size * holdout_pct / 100)

    # Use provided platform or template platform or default
    final_platform = platform
    if template.get("channel", {}).get("platform"):
        final_platform = template["channel"]["platform"]

    # Build the execution plan
    execution = {
        "audience": {
            **template.get("audience", {}),
            "segment_path": segment_path,
            "segment_label": segment_label,
            "size": audience_size,
        },
        "channel": {
            **template.get("channel", {}),
            "platform": final_platform,
        },
        "sequence": template.get("sequence", {}),
        "offer": template.get("offer", {}),
        "creative": template.get("creative", {}),
        "measurement": {
            **template.get("measurement", {}),
            "holdout_size": holdout_size,
        },
        "expected_revenue": expected_revenue,
    }

    # Build steps by interpolating template
    steps_template = template.get("steps_template", [])
    steps = []
    for step in steps_template:
        formatted_step = step.format(
            segment_path=segment_path,
            segment_label=segment_label,
            audience_size=audience_size,
            platform=final_platform,
            month=month,
            holdout_pct=holdout_pct,
            holdout_size=holdout_size,
            expected_revenue=f"${expected_revenue:,.0f}",
        )
        steps.append(formatted_step)

    execution["steps"] = steps

    return execution


def get_available_plays() -> List[str]:
    """Return list of all plays with execution templates."""
    return list(PLAY_EXECUTION_TEMPLATES.keys())
