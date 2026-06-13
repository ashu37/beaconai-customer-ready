#!/usr/bin/env python3
"""
Multi-Window Engine Validator

Generates comprehensive validation reports for the multi-window analysis engine.
Validates KPI calculations, statistical testing, weighted scoring, and overall logic soundness.
"""

import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple
import pandas as pd

class MultiWindowValidator:
    """Validates multi-window engine logic and generates comprehensive reports"""

    def __init__(self, run_summary_path: str, output_dir: str):
        self.run_summary_path = run_summary_path
        self.output_dir = output_dir
        self.data = self._load_data()
        self.report = {
            "validation_timestamp": datetime.now().isoformat(),
            "dataset_info": {},
            "window_analysis": {},
            "scoring_validation": {},
            "statistical_assessment": {},
            "logic_soundness": {},
            "recommendations": []
        }

    def _load_data(self) -> Dict[str, Any]:
        """Load run summary data"""
        with open(self.run_summary_path, 'r') as f:
            return json.load(f)

    def validate_all(self) -> Dict[str, Any]:
        """Run complete validation suite"""
        self._validate_dataset_info()
        self._validate_window_kpis()
        self._validate_statistical_testing()
        self._validate_scoring_logic()
        self._validate_multi_window_aggregation()
        self._assess_overall_soundness()
        self._generate_recommendations()
        return self.report

    def _validate_dataset_info(self):
        """Validate basic dataset information"""
        aligned = self.data.get('aligned', {})

        # Extract anchor and window info
        anchor = aligned.get('anchor', 'Unknown')
        windows = ['L7', 'L28', 'L56', 'L90']

        dataset_info = {
            "anchor_date": anchor,
            "analysis_windows": windows,
            "total_actions_generated": len(self.data.get('actions', [])),
            "pilot_actions": len(self.data.get('pilot_actions', [])),
            "watchlist_actions": len(self.data.get('watchlist', [])),
            "beacon_score": self.data.get('aura_score', {}).get('overall', 'N/A'),
            "analysis_method": self.data.get('aura_score', {}).get('analysis_method', 'N/A')
        }

        self.report["dataset_info"] = dataset_info

    def _validate_window_kpis(self):
        """Validate KPI calculations across windows"""
        aligned = self.data.get('aligned', {})
        windows = ['L7', 'L28', 'L56', 'L90']

        window_analysis = {}

        for window in windows:
            if window in aligned:
                w_data = aligned[window]

                analysis = {
                    "orders": w_data.get('orders', 0),
                    "revenue": w_data.get('net_sales', 0),
                    "aov": w_data.get('aov', 0),
                    "repeat_rate": (w_data.get('repeat_rate_within_window') or 0) * 100,
                    "discount_rate": (w_data.get('discount_rate') or 0) * 100,
                    "returning_share": (w_data.get('returning_customer_share') or 0) * 100,
                    "delta_analysis": {
                        "aov_change": (w_data.get('delta', {}).get('aov') or 0) * 100,
                        "repeat_rate_change": (w_data.get('delta', {}).get('repeat_rate_within_window') or 0) * 100,
                        "orders_change": (w_data.get('delta', {}).get('orders') or 0) * 100
                    }
                }

                # Validate logical patterns
                analysis["validation_flags"] = self._validate_window_logic(window, analysis)

                window_analysis[window] = analysis

        # Cross-window pattern validation
        window_analysis["pattern_validation"] = self._validate_cross_window_patterns(window_analysis)

        self.report["window_analysis"] = window_analysis

    def _validate_window_logic(self, window: str, analysis: Dict) -> List[str]:
        """Validate logical consistency for a single window"""
        flags = []

        # Basic sanity checks
        if analysis["orders"] <= 0:
            flags.append(f"⚠️ {window}: No orders in window")

        if analysis["aov"] <= 0:
            flags.append(f"⚠️ {window}: Invalid AOV")

        if analysis["repeat_rate"] < 0 or analysis["repeat_rate"] > 100:
            flags.append(f"⚠️ {window}: Invalid repeat rate")

        if analysis["discount_rate"] < 0 or analysis["discount_rate"] > 100:
            flags.append(f"⚠️ {window}: Invalid discount rate")

        # Expected patterns
        if analysis["returning_share"] > 80:
            flags.append(f"📊 {window}: High returning customer share ({analysis['returning_share']:.1f}%)")

        if analysis["repeat_rate"] < 1 and analysis["orders"] > 500:
            flags.append(f"📊 {window}: Low repeat rate for sample size")

        if not flags:
            flags.append(f"✅ {window}: All metrics within expected ranges")

        return flags

    def _validate_cross_window_patterns(self, window_analysis: Dict) -> Dict[str, Any]:
        """Validate patterns across windows"""
        patterns = {
            "repeat_rate_trend": "Unknown",
            "aov_trend": "Unknown",
            "order_volume_trend": "Unknown",
            "insights": []
        }

        windows = ['L7', 'L28', 'L56', 'L90']
        valid_windows = [w for w in windows if w in window_analysis]

        if len(valid_windows) >= 2:
            # Repeat rate trend
            repeat_rates = [window_analysis[w]["repeat_rate"] for w in valid_windows]
            if repeat_rates[-1] > repeat_rates[0]:
                patterns["repeat_rate_trend"] = "Increasing (Expected)"
                patterns["insights"].append("✅ Repeat rates increase with longer windows (more opportunity)")
            else:
                patterns["repeat_rate_trend"] = "Decreasing (Unexpected)"
                patterns["insights"].append("⚠️ Repeat rates should typically increase with longer windows")

            # AOV trend
            aovs = [window_analysis[w]["aov"] for w in valid_windows]
            aov_variance = np.std(aovs) / np.mean(aovs) if np.mean(aovs) > 0 else 0
            if aov_variance < 0.1:
                patterns["aov_trend"] = "Stable"
                patterns["insights"].append(f"✅ AOV stable across windows (CV: {aov_variance:.1%})")
            else:
                patterns["aov_trend"] = "Variable"
                patterns["insights"].append(f"📊 AOV shows variation across windows (CV: {aov_variance:.1%})")

            # Order volume trend
            orders = [window_analysis[w]["orders"] for w in valid_windows]
            if all(orders[i] <= orders[i+1] for i in range(len(orders)-1)):
                patterns["order_volume_trend"] = "Increasing (Expected)"
                patterns["insights"].append("✅ Order volume increases with longer windows")
            else:
                patterns["order_volume_trend"] = "Variable"
                patterns["insights"].append("📊 Order volume pattern varies across windows")

        return patterns

    def _validate_statistical_testing(self):
        """Validate statistical significance testing"""
        aligned = self.data.get('aligned', {})
        windows = ['L7', 'L28', 'L56', 'L90']

        statistical_assessment = {
            "significance_by_window": {},
            "statistical_power_analysis": {},
            "confidence_patterns": []
        }

        metrics_to_check = ['aov', 'repeat_rate_within_window', 'returning_customer_share', 'discount_rate']

        for window in windows:
            if window in aligned:
                w_data = aligned[window]
                p_values = w_data.get('p', {})
                sig_flags = w_data.get('sig', {})

                window_stats = {}
                for metric in metrics_to_check:
                    if metric in p_values:
                        p_val = p_values[metric]
                        is_sig = sig_flags.get(metric, False)

                        # Classify significance level
                        if pd.isna(p_val) or p_val == "NaN":
                            sig_level = "Invalid"
                        elif p_val < 0.01:
                            sig_level = "Highly Significant"
                        elif p_val < 0.05:
                            sig_level = "Significant"
                        elif p_val < 0.20:
                            sig_level = "Learning Mode Threshold"
                        else:
                            sig_level = "Not Significant"

                        window_stats[metric] = {
                            "p_value": p_val,
                            "significant": is_sig,
                            "significance_level": sig_level,
                            "signal_strength": min(-np.log10(max(p_val, 1e-8)), 4.0) if isinstance(p_val, (int, float)) else 0
                        }

                statistical_assessment["significance_by_window"][window] = window_stats

        # Analyze statistical power trends
        statistical_assessment["statistical_power_analysis"] = self._analyze_statistical_power(statistical_assessment["significance_by_window"])

        # Generate confidence patterns
        statistical_assessment["confidence_patterns"] = self._analyze_confidence_patterns(statistical_assessment["significance_by_window"])

        self.report["statistical_assessment"] = statistical_assessment

    def _analyze_statistical_power(self, significance_data: Dict) -> Dict[str, Any]:
        """Analyze statistical power trends across windows"""
        analysis = {
            "power_trend": "Unknown",
            "best_performing_window": "Unknown",
            "insights": []
        }

        windows = ['L7', 'L28', 'L56', 'L90']
        valid_windows = [w for w in windows if w in significance_data]

        if len(valid_windows) >= 2:
            # Calculate average p-values by window
            avg_p_values = {}
            for window in valid_windows:
                p_vals = []
                for metric_data in significance_data[window].values():
                    p_val = metric_data.get('p_value')
                    if isinstance(p_val, (int, float)) and not pd.isna(p_val):
                        p_vals.append(p_val)

                if p_vals:
                    avg_p_values[window] = np.mean(p_vals)

            if avg_p_values:
                best_window = min(avg_p_values.keys(), key=lambda w: avg_p_values[w])
                analysis["best_performing_window"] = best_window

                # Check if p-values generally decrease with longer windows
                ordered_windows = [w for w in windows if w in avg_p_values]
                p_trend = [avg_p_values[w] for w in ordered_windows]

                if len(p_trend) >= 3:
                    decreasing_trend = sum(1 for i in range(len(p_trend)-1) if p_trend[i+1] < p_trend[i])
                    if decreasing_trend >= len(p_trend) - 2:
                        analysis["power_trend"] = "Improving with longer windows"
                        analysis["insights"].append("✅ Statistical power improves with longer windows (expected)")
                    else:
                        analysis["power_trend"] = "Mixed"
                        analysis["insights"].append("📊 Statistical power varies across windows")

                analysis["insights"].append(f"🎯 Best statistical signals in {best_window} window")

        return analysis

    def _analyze_confidence_patterns(self, significance_data: Dict) -> List[str]:
        """Analyze confidence patterns across the analysis"""
        patterns = []

        # Count significant results
        total_tests = 0
        significant_tests = 0

        for window_data in significance_data.values():
            for metric_data in window_data.values():
                total_tests += 1
                if metric_data.get('significant', False):
                    significant_tests += 1

        if total_tests > 0:
            sig_rate = significant_tests / total_tests
            patterns.append(f"📊 {significant_tests}/{total_tests} tests significant ({sig_rate:.1%})")

            if sig_rate == 0:
                patterns.append("⚠️ No statistically significant results - consider longer time periods")
            elif sig_rate < 0.1:
                patterns.append("📈 Low significance rate - results may need more data")
            elif sig_rate > 0.5:
                patterns.append("🎯 High significance rate - strong statistical foundation")
            else:
                patterns.append("✅ Moderate significance rate - appropriate statistical rigor")

        return patterns

    def _validate_scoring_logic(self):
        """Validate multi-window scoring logic"""
        watchlist = self.data.get('watchlist', [])

        scoring_validation = {
            "action_scoring_analysis": [],
            "window_weight_validation": {},
            "scoring_components": {},
            "consistency_checks": []
        }

        # Analyze action scoring for first few actions
        for i, action in enumerate(watchlist[:3]):
            action_analysis = self._analyze_action_scoring(action)
            scoring_validation["action_scoring_analysis"].append(action_analysis)

        # Validate window weights
        scoring_validation["window_weight_validation"] = self._validate_window_weights(watchlist)

        # Analyze scoring components
        scoring_validation["scoring_components"] = self._analyze_scoring_components(watchlist)

        # Consistency checks
        scoring_validation["consistency_checks"] = self._perform_scoring_consistency_checks(watchlist)

        self.report["scoring_validation"] = scoring_validation

    def _analyze_action_scoring(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze scoring for a single action"""
        analysis = {
            "title": action.get('title', 'Unknown'),
            "metric": action.get('metric', 'Unknown'),
            "effect_size": (action.get('effect_abs') or 0) * 100,
            "expected_revenue": action.get('expected_$', 0),
            "source_window": action.get('source_window', 'Unknown'),
            "contributing_windows": action.get('contributing_windows', []),
            "window_scores": action.get('window_scores', {}),
            "final_score": action.get('score', 0),
            "confidence": action.get('confidence_score', 0),
            "scoring_breakdown": {}
        }

        # Analyze window scoring pattern
        if analysis["window_scores"]:
            window_analysis = {}
            for window, p_val in analysis["window_scores"].items():
                signal_strength = min(-np.log10(max(p_val, 1e-8)), 4.0) if isinstance(p_val, (int, float)) else 0
                window_analysis[window] = {
                    "p_value": p_val,
                    "signal_strength": signal_strength
                }
            analysis["scoring_breakdown"]["window_signals"] = window_analysis

        # Calculate expected weighted signal (for validation)
        window_weights = {'L7': 0.3, 'L28': 0.4, 'L56': 0.2, 'L90': 0.1}
        if analysis["window_scores"] and analysis["contributing_windows"]:
            total_weighted_signal = 0.0
            total_weight = 0.0

            for window in analysis["contributing_windows"]:
                if window in analysis["window_scores"]:
                    p_val = analysis["window_scores"][window]
                    if isinstance(p_val, (int, float)):
                        weight = window_weights.get(window, 0.25)
                        signal = min(-np.log10(max(p_val, 1e-8)), 4.0)
                        total_weighted_signal += signal * weight
                        total_weight += weight

            if total_weight > 0:
                expected_signal = total_weighted_signal / total_weight
                analysis["scoring_breakdown"]["expected_weighted_signal"] = expected_signal

        # Analyze scoring components if available
        if 'scores_breakdown' in action:
            analysis["scoring_breakdown"]["confidence_components"] = action['scores_breakdown']

        return analysis

    def _validate_window_weights(self, watchlist: List[Dict]) -> Dict[str, Any]:
        """Validate window weight consistency"""
        validation = {
            "expected_weights": {'L7': 0.3, 'L28': 0.4, 'L56': 0.2, 'L90': 0.1},
            "observed_patterns": {},
            "consistency_check": "Unknown"
        }

        # Check if actions use consistent window weights
        observed_weights = {}
        for action in watchlist:
            window_weight = action.get('window_weight')
            source_window = action.get('source_window')
            if window_weight is not None and source_window:
                if source_window not in observed_weights:
                    observed_weights[source_window] = []
                observed_weights[source_window].append(window_weight)

        # Check consistency
        consistent = True
        for window, weights in observed_weights.items():
            unique_weights = set(weights)
            if len(unique_weights) > 1:
                consistent = False
            validation["observed_patterns"][window] = {
                "weights_observed": list(unique_weights),
                "count": len(weights)
            }

        validation["consistency_check"] = "Consistent" if consistent else "Inconsistent"
        return validation

    def _analyze_scoring_components(self, watchlist: List[Dict]) -> Dict[str, Any]:
        """Analyze scoring components across actions"""
        components = {
            "seasonal_adjustments": {},
            "confidence_patterns": {},
            "score_distribution": {}
        }

        # Seasonal adjustments
        seasonal_multipliers = [action.get('seasonal_multiplier') for action in watchlist if action.get('seasonal_multiplier')]
        seasonal_periods = [action.get('seasonal_period') for action in watchlist if action.get('seasonal_period')]

        if seasonal_multipliers:
            components["seasonal_adjustments"] = {
                "multipliers_range": [min(seasonal_multipliers), max(seasonal_multipliers)],
                "periods_observed": list(set(seasonal_periods)),
                "average_multiplier": np.mean(seasonal_multipliers)
            }

        # Confidence patterns
        confidence_scores = [action.get('confidence_score', 0) for action in watchlist]
        if confidence_scores:
            components["confidence_patterns"] = {
                "min": min(confidence_scores),
                "max": max(confidence_scores),
                "mean": np.mean(confidence_scores),
                "median": np.median(confidence_scores)
            }

        # Score distribution
        final_scores = [action.get('score', 0) for action in watchlist]
        if final_scores:
            components["score_distribution"] = {
                "min": min(final_scores),
                "max": max(final_scores),
                "mean": np.mean(final_scores),
                "median": np.median(final_scores)
            }

        return components

    def _perform_scoring_consistency_checks(self, watchlist: List[Dict]) -> List[str]:
        """Perform consistency checks on scoring logic"""
        checks = []

        # Check if higher effects generally lead to higher scores
        actions_with_effects = [(action.get('effect_abs', 0), action.get('score', 0)) for action in watchlist]
        actions_with_effects = [(e, s) for e, s in actions_with_effects if e > 0 and s > 0]

        if len(actions_with_effects) >= 2:
            effects, scores = zip(*actions_with_effects)
            correlation = np.corrcoef(effects, scores)[0, 1] if len(effects) > 1 else 0

            if correlation > 0.3:
                checks.append(f"✅ Positive correlation between effect size and score ({correlation:.2f})")
            elif correlation < -0.3:
                checks.append(f"⚠️ Negative correlation between effect size and score ({correlation:.2f})")
            else:
                checks.append(f"📊 Weak correlation between effect size and score ({correlation:.2f})")

        # Check if actions with expected revenue have reasonable scores
        revenue_actions = [action for action in watchlist if action.get('expected_$', 0) > 0]
        zero_revenue_actions = [action for action in watchlist if action.get('expected_$', 0) == 0]

        if revenue_actions and zero_revenue_actions:
            avg_score_with_revenue = np.mean([action.get('score', 0) for action in revenue_actions])
            avg_score_no_revenue = np.mean([action.get('score', 0) for action in zero_revenue_actions])

            if avg_score_with_revenue > avg_score_no_revenue:
                checks.append("✅ Actions with expected revenue have higher average scores")
            else:
                checks.append("📊 Actions with expected revenue don't necessarily have higher scores")

        return checks

    def _validate_multi_window_aggregation(self):
        """Validate multi-window aggregation methodology"""
        beacon_score = self.data.get('aura_score', {})

        aggregation_validation = {
            "methodology": beacon_score.get('analysis_method', 'Unknown'),
            "windows_used": beacon_score.get('windows_analyzed', []),
            "component_scores": beacon_score.get('components', {}),
            "overall_score": beacon_score.get('overall', 0),
            "validation_results": []
        }

        # Validate component scores
        components = aggregation_validation["component_scores"]
        if components:
            for component, score in components.items():
                if 0 <= score <= 100:
                    aggregation_validation["validation_results"].append(f"✅ {component}: {score:.1f}/100 (valid range)")
                else:
                    aggregation_validation["validation_results"].append(f"⚠️ {component}: {score:.1f}/100 (outside valid range)")

        # Validate overall methodology
        if aggregation_validation["methodology"] == "multi_window":
            aggregation_validation["validation_results"].append("✅ Using multi-window analysis methodology")
        else:
            aggregation_validation["validation_results"].append(f"📊 Using {aggregation_validation['methodology']} methodology")

        # Check if all expected windows are used
        expected_windows = ['L7', 'L28', 'L56', 'L90']
        used_windows = aggregation_validation["windows_used"]
        if set(expected_windows).issubset(set(used_windows)):
            aggregation_validation["validation_results"].append("✅ All expected windows included in analysis")
        else:
            missing = set(expected_windows) - set(used_windows)
            aggregation_validation["validation_results"].append(f"📊 Missing windows: {list(missing)}")

        self.report["multi_window_aggregation"] = aggregation_validation

    def _assess_overall_soundness(self):
        """Assess overall logic soundness"""
        soundness = {
            "kpi_calculation": "Unknown",
            "statistical_rigor": "Unknown",
            "scoring_logic": "Unknown",
            "multi_window_integration": "Unknown",
            "overall_assessment": "Unknown",
            "strengths": [],
            "areas_for_improvement": [],
            "confidence_level": "Unknown"
        }

        # Assess KPI calculation
        window_flags = []
        for window_data in self.report.get("window_analysis", {}).values():
            if isinstance(window_data, dict) and "validation_flags" in window_data:
                window_flags.extend(window_data["validation_flags"])

        error_flags = [f for f in window_flags if f.startswith("⚠️")]
        if not error_flags:
            soundness["kpi_calculation"] = "Sound"
            soundness["strengths"].append("KPI calculations are mathematically sound across all windows")
        else:
            soundness["kpi_calculation"] = "Issues Detected"
            soundness["areas_for_improvement"].append(f"KPI calculation issues: {len(error_flags)} warnings")

        # Assess statistical rigor
        stat_data = self.report.get("statistical_assessment", {})
        confidence_patterns = stat_data.get("confidence_patterns", [])

        if any("appropriate statistical rigor" in pattern or "strong statistical foundation" in pattern for pattern in confidence_patterns):
            soundness["statistical_rigor"] = "Rigorous"
            soundness["strengths"].append("Statistical testing methodology is rigorous and appropriate")
        elif any("No statistically significant" in pattern for pattern in confidence_patterns):
            soundness["statistical_rigor"] = "Conservative"
            soundness["strengths"].append("Conservative statistical approach prevents false positives")
        else:
            soundness["statistical_rigor"] = "Adequate"

        # Assess scoring logic
        scoring_data = self.report.get("scoring_validation", {})
        consistency_checks = scoring_data.get("consistency_checks", [])

        if any("✅" in check for check in consistency_checks):
            soundness["scoring_logic"] = "Sound"
            soundness["strengths"].append("Scoring logic shows consistent patterns")
        else:
            soundness["scoring_logic"] = "Complex"
            soundness["areas_for_improvement"].append("Scoring logic may benefit from additional documentation")

        # Assess multi-window integration
        aggregation_data = self.report.get("multi_window_aggregation", {})
        validation_results = aggregation_data.get("validation_results", [])

        if validation_results and most_positive(validation_results):
            soundness["multi_window_integration"] = "Excellent"
            soundness["strengths"].append("Multi-window aggregation methodology is well-implemented")
        else:
            soundness["multi_window_integration"] = "Adequate"

        # Overall assessment
        assessments = [soundness["kpi_calculation"], soundness["statistical_rigor"],
                      soundness["scoring_logic"], soundness["multi_window_integration"]]

        if all(a in ["Sound", "Rigorous", "Excellent"] for a in assessments):
            soundness["overall_assessment"] = "Excellent"
            soundness["confidence_level"] = "High"
        elif all(a in ["Sound", "Rigorous", "Excellent", "Conservative", "Adequate"] for a in assessments):
            soundness["overall_assessment"] = "Good"
            soundness["confidence_level"] = "Medium-High"
        else:
            soundness["overall_assessment"] = "Needs Review"
            soundness["confidence_level"] = "Medium"

        self.report["logic_soundness"] = soundness

    def _generate_recommendations(self):
        """Generate actionable recommendations based on validation"""
        recommendations = []

        # Based on statistical assessment
        stat_data = self.report.get("statistical_assessment", {})
        confidence_patterns = stat_data.get("confidence_patterns", [])

        if any("No statistically significant" in pattern for pattern in confidence_patterns):
            recommendations.append({
                "category": "Statistical Power",
                "recommendation": "Consider extending analysis period or increasing sample size",
                "rationale": "No statistically significant results detected",
                "priority": "Medium"
            })

        # Based on window analysis
        window_data = self.report.get("window_analysis", {})
        pattern_validation = window_data.get("pattern_validation", {})

        if pattern_validation.get("repeat_rate_trend") == "Decreasing (Unexpected)":
            recommendations.append({
                "category": "Data Quality",
                "recommendation": "Investigate repeat rate calculation methodology",
                "rationale": "Repeat rates should typically increase with longer windows",
                "priority": "High"
            })

        # Based on scoring validation
        scoring_data = self.report.get("scoring_validation", {})
        if scoring_data.get("window_weight_validation", {}).get("consistency_check") == "Inconsistent":
            recommendations.append({
                "category": "Scoring Logic",
                "recommendation": "Review window weight consistency across actions",
                "rationale": "Inconsistent window weights detected",
                "priority": "Medium"
            })

        # Based on overall soundness
        soundness = self.report.get("logic_soundness", {})
        if soundness.get("overall_assessment") == "Needs Review":
            recommendations.append({
                "category": "Overall System",
                "recommendation": "Conduct comprehensive system review",
                "rationale": "Multiple areas identified for improvement",
                "priority": "High"
            })

        # Positive reinforcement
        if soundness.get("overall_assessment") in ["Excellent", "Good"]:
            recommendations.append({
                "category": "System Status",
                "recommendation": "System is operating within expected parameters",
                "rationale": "Validation shows sound logic and methodology",
                "priority": "Info"
            })

        self.report["recommendations"] = recommendations

    def save_report(self, filename: str = None) -> str:
        """Save validation report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"engine_validation_report_{timestamp}.json"

        output_path = f"{self.output_dir}/{filename}"

        with open(output_path, 'w') as f:
            json.dump(self.report, f, indent=2, default=str)

        return output_path

    def generate_summary_text(self) -> str:
        """Generate human-readable summary"""
        summary = "# Multi-Window Engine Validation Report\n\n"

        # Dataset info
        dataset_info = self.report.get("dataset_info", {})
        summary += f"**Analysis Date:** {dataset_info.get('anchor_date', 'Unknown')}\n"
        summary += f"**Beacon Score:** {dataset_info.get('beacon_score', 'N/A')}/100\n"
        summary += f"**Actions Generated:** {dataset_info.get('total_actions_generated', 0)} main, "
        summary += f"{dataset_info.get('pilot_actions', 0)} pilot, {dataset_info.get('watchlist_actions', 0)} watchlist\n\n"

        # Key findings
        soundness = self.report.get("logic_soundness", {})
        summary += f"## Overall Assessment: {soundness.get('overall_assessment', 'Unknown')}\n\n"

        # Strengths
        strengths = soundness.get("strengths", [])
        if strengths:
            summary += "### ✅ Strengths:\n"
            for strength in strengths:
                summary += f"- {strength}\n"
            summary += "\n"

        # Areas for improvement
        improvements = soundness.get("areas_for_improvement", [])
        if improvements:
            summary += "### 📊 Areas for Improvement:\n"
            for improvement in improvements:
                summary += f"- {improvement}\n"
            summary += "\n"

        # Recommendations
        recommendations = self.report.get("recommendations", [])
        if recommendations:
            summary += "### 🎯 Recommendations:\n"
            for rec in recommendations:
                priority_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢", "Info": "ℹ️"}.get(rec.get("priority", ""), "")
                summary += f"{priority_icon} **{rec.get('category', 'Unknown')}:** {rec.get('recommendation', '')}\n"
            summary += "\n"

        return summary

def most_positive(items: List[str]) -> bool:
    """Helper function to check if most items are positive"""
    positive_count = sum(1 for item in items if "✅" in item)
    return positive_count > len(items) / 2

def validate_engine_run(run_summary_path: str, output_dir: str) -> Tuple[str, str]:
    """
    Main function to validate an engine run

    Args:
        run_summary_path: Path to run_summary.json
        output_dir: Directory to save validation report

    Returns:
        Tuple of (json_report_path, text_summary)
    """
    validator = MultiWindowValidator(run_summary_path, output_dir)
    validator.validate_all()

    # Save JSON report
    json_path = validator.save_report()

    # Generate text summary
    text_summary = validator.generate_summary_text()

    return json_path, text_summary

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python engine_validator.py <run_summary_path> <output_dir>")
        sys.exit(1)

    run_summary_path = sys.argv[1]
    output_dir = sys.argv[2]

    json_path, text_summary = validate_engine_run(run_summary_path, output_dir)

    print(f"Validation complete!")
    print(f"JSON report: {json_path}")
    print("\n" + text_summary)