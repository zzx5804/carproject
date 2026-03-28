"""
Tests for diagnosis_knowledge module.
"""
import pytest
import re


class TestSymptomPatterns:
    def test_symptom_patterns_exists(self):
        from diagnosis_knowledge import SYMPTOM_PATTERNS
        assert isinstance(SYMPTOM_PATTERNS, dict)
        assert len(SYMPTOM_PATTERNS) == 7
    
    def test_symptom_patterns_has_required_scenarios(self):
        from diagnosis_knowledge import SYMPTOM_PATTERNS
        required_scenarios = ["ble_auth", "key_timeout", "bms_charging", "auto_poweroff"]
        for scenario in required_scenarios:
            assert scenario in SYMPTOM_PATTERNS
            assert isinstance(SYMPTOM_PATTERNS[scenario], list)
            assert len(SYMPTOM_PATTERNS[scenario]) > 0
    
    def test_patterns_are_regex_strings(self):
        from diagnosis_knowledge import SYMPTOM_PATTERNS
        for scenario, patterns in SYMPTOM_PATTERNS.items():
            for pattern in patterns:
                # Should compile as valid regex
                re.compile(pattern)
    
    def test_all_scenarios_present(self):
        from diagnosis_knowledge import SYMPTOM_PATTERNS
        expected_scenarios = [
            "ble_auth", "key_timeout", "forced_off", 
            "auto_poweroff", "remote_on", "alcohol_lock", "bms_charging"
        ]
        for scenario in expected_scenarios:
            assert scenario in SYMPTOM_PATTERNS, f"Missing scenario: {scenario}"


class TestRules:
    def test_rules_exists(self):
        from diagnosis_knowledge import RULES
        assert isinstance(RULES, dict)
        assert len(RULES) >= 7
    
    def test_rules_have_required_fields(self):
        from diagnosis_knowledge import RULES
        required_fields = ["id", "text", "src", "conf"]
        for rule_id, rule in RULES.items():
            for field in required_fields:
                assert field in rule, f"Rule {rule_id} missing field {field}"
    
    def test_confidence_is_string(self):
        from diagnosis_knowledge import RULES
        for rule_id, rule in RULES.items():
            assert isinstance(rule["conf"], str)
    
    def test_rule_ids_match_keys(self):
        from diagnosis_knowledge import RULES
        for rule_id, rule in RULES.items():
            assert rule["id"] == rule_id, f"Rule id mismatch: {rule_id} vs {rule['id']}"
    
    def test_specific_rules_exist(self):
        from diagnosis_knowledge import RULES
        expected_rules = ["T_1_2", "R-KEY001", "R-BLE001", "R-BLE002", "R-AUTO-OFF", "R-BMS001-P2", "R-SAFE-003"]
        for rule_id in expected_rules:
            assert rule_id in RULES, f"Missing rule: {rule_id}"


class TestHypothesisTemplates:
    def test_hypotheses_exists(self):
        from diagnosis_knowledge import HYPOTHESIS_TEMPLATES
        assert isinstance(HYPOTHESIS_TEMPLATES, dict)
    
    def test_hypotheses_have_required_fields(self):
        from diagnosis_knowledge import HYPOTHESIS_TEMPLATES
        for scenario, hypotheses in HYPOTHESIS_TEMPLATES.items():
            for hypo in hypotheses:
                assert "name" in hypo
                assert "pct" in hypo
                assert "cls" in hypo
    
    def test_hypothesis_classes_valid(self):
        from diagnosis_knowledge import HYPOTHESIS_TEMPLATES
        valid_classes = ["p", "s", "t"]
        for scenario, hypotheses in HYPOTHESIS_TEMPLATES.items():
            for hypo in hypotheses:
                assert hypo["cls"] in valid_classes, f"Invalid cls: {hypo['cls']}"
    
    def test_hypothesis_percentages_in_range(self):
        from diagnosis_knowledge import HYPOTHESIS_TEMPLATES
        for scenario, hypotheses in HYPOTHESIS_TEMPLATES.items():
            for hypo in hypotheses:
                assert 0 <= hypo["pct"] <= 100, f"Invalid pct: {hypo['pct']}"


class TestOutputTemplates:
    def test_output_templates_exists(self):
        from diagnosis_knowledge import OUTPUT_TEMPLATES
        assert isinstance(OUTPUT_TEMPLATES, dict)
    
    def test_output_templates_have_roles(self):
        from diagnosis_knowledge import OUTPUT_TEMPLATES
        for scenario, templates in OUTPUT_TEMPLATES.items():
            assert "owner" in templates
    
    def test_output_templates_are_html_strings(self):
        from diagnosis_knowledge import OUTPUT_TEMPLATES
        for scenario, templates in OUTPUT_TEMPLATES.items():
            for role, html in templates.items():
                assert isinstance(html, str)
                assert len(html) > 0
    
    def test_output_templates_for_key_scenarios(self):
        from diagnosis_knowledge import OUTPUT_TEMPLATES
        key_scenarios = ["ble_auth", "key_timeout", "bms_charging", "auto_poweroff"]
        for scenario in key_scenarios:
            assert scenario in OUTPUT_TEMPLATES
            assert "owner" in OUTPUT_TEMPLATES[scenario]
            assert "technician" in OUTPUT_TEMPLATES[scenario]


class TestEscalationHints:
    def test_escalation_hints_exists(self):
        from diagnosis_knowledge import ESCALATION_HINTS
        assert isinstance(ESCALATION_HINTS, dict)
    
    def test_escalation_hints_have_customer_service(self):
        from diagnosis_knowledge import ESCALATION_HINTS
        for scenario, hints in ESCALATION_HINTS.items():
            assert "customer_service" in hints
            assert isinstance(hints["customer_service"], str)


class TestSignalRelevance:
    def test_signal_relevance_exists(self):
        from diagnosis_knowledge import SIGNAL_RELEVANCE
        assert isinstance(SIGNAL_RELEVANCE, dict)
    
    def test_signal_relevance_has_primary_secondary(self):
        from diagnosis_knowledge import SIGNAL_RELEVANCE
        for scenario, relevance in SIGNAL_RELEVANCE.items():
            assert "primary" in relevance
            assert "secondary" in relevance
            assert isinstance(relevance["primary"], list)
            assert isinstance(relevance["secondary"], list)
    
    def test_primary_signals_not_empty(self):
        from diagnosis_knowledge import SIGNAL_RELEVANCE
        for scenario, relevance in SIGNAL_RELEVANCE.items():
            assert len(relevance["primary"]) > 0


class TestScenarioRulesMap:
    def test_scenario_rules_map_exists(self):
        from diagnosis_knowledge import SCENARIO_RULES_MAP
        assert isinstance(SCENARIO_RULES_MAP, dict)
    
    def test_all_scenarios_have_rules(self):
        from diagnosis_knowledge import SCENARIO_RULES_MAP
        for scenario, rule_ids in SCENARIO_RULES_MAP.items():
            assert isinstance(rule_ids, list)
            assert len(rule_ids) > 0
    
    def test_rule_ids_reference_valid_rules(self):
        from diagnosis_knowledge import SCENARIO_RULES_MAP, RULES
        for scenario, rule_ids in SCENARIO_RULES_MAP.items():
            for rule_id in rule_ids:
                assert rule_id in RULES, f"Rule {rule_id} referenced in {scenario} not found in RULES"


class TestAllExports:
    def test_all_exports_defined(self):
        from diagnosis_knowledge import __all__
        expected = [
            "SYMPTOM_PATTERNS", "RULES", "HYPOTHESIS_TEMPLATES",
            "OUTPUT_TEMPLATES", "ESCALATION_HINTS", "SIGNAL_RELEVANCE",
            "SCENARIO_RULES_MAP"
        ]
        for item in expected:
            assert item in __all__
    
    def test_all_exports_importable(self):
        import diagnosis_knowledge
        for name in diagnosis_knowledge.__all__:
            assert hasattr(diagnosis_knowledge, name)


class TestDataIntegrity:
    def test_symptom_patterns_match_scenarios(self):
        """Ensure all scenario keys are consistent across data structures."""
        from diagnosis_knowledge import (
            SYMPTOM_PATTERNS, HYPOTHESIS_TEMPLATES, 
            OUTPUT_TEMPLATES, SIGNAL_RELEVANCE, SCENARIO_RULES_MAP
        )
        # Not all scenarios have entries in every structure, but key ones should
        core_scenarios = {"ble_auth", "key_timeout", "bms_charging", "auto_poweroff"}
        
        for scenario in core_scenarios:
            assert scenario in SYMPTOM_PATTERNS
            assert scenario in SCENARIO_RULES_MAP
            assert scenario in SIGNAL_RELEVANCE
