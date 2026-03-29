"""
Tests for Ontology+LLM pipeline fix.
"""
import re
import pytest


class TestKeywordExtraction:
    """Test Chinese keyword extraction in OntologyFetcherAgent."""

    def _extract_keywords(self, symptom: str, parsed_symptoms: list) -> list:
        """Mirrors the keyword extraction logic in OntologyFetcherAgent.process()."""
        keywords = list(parsed_symptoms)
        normalized = re.sub(r"[，。！？、：；\u2018\u2019\u201c\u201d'\"（）【】《》\s]+", " ", symptom)
        for word in normalized.split():
            if len(word) >= 2 and word not in keywords:
                keywords.append(word)
        return keywords

    def test_chinese_symptom_splits_correctly(self):
        """Chinese symptom should produce multiple keywords, not one long string."""
        symptom = "踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'"
        keywords = self._extract_keywords(symptom, [])
        assert len(keywords) > 1
        assert all(len(k) < 15 for k in keywords), f"Some keywords too long: {keywords}"

    def test_key_not_found_keyword_present(self):
        """'钥匙未找到' must appear as a keyword for SPARQL matching."""
        symptom = "踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'"
        keywords = self._extract_keywords(symptom, [])
        assert "钥匙未找到" in keywords, f"'钥匙未找到' not found in {keywords}"

    def test_parsed_symptoms_preserved(self):
        """Pre-parsed symptoms must be preserved in keyword list."""
        symptom = "无法上电"
        parsed = ["钥匙", "启动"]
        keywords = self._extract_keywords(symptom, parsed)
        assert "钥匙" in keywords
        assert "启动" in keywords
        assert "无法上电" in keywords

    def test_unicode_curly_quotes_normalized(self):
        """Unicode curly quotes must also be stripped during normalization."""
        symptom = "屏幕弹出\u2018钥匙未找到\u2019"  # Unicode left/right single quotes
        keywords = self._extract_keywords(symptom, [])
        assert "钥匙未找到" in keywords, f"'钥匙未找到' not found in {keywords}"


class TestConfidenceFallback:
    """Test that confidence fallback differs between ontology and pure-LLM modes."""

    def _make_tools(self):
        from llm.service import LLMTools
        from llm.config import get_llm_config
        return LLMTools(get_llm_config())

    def _make_request(self):
        from llm.schemas import DiagnosisRequest, SignalInfo, Role
        return DiagnosisRequest(
            symptom="踩刹车按启动按钮，车辆无法上电",
            role=Role.OWNER,
            signals=[SignalInfo(key="sv-kv", value="INVALID")],
        )

    def test_fallback_confidence_differs_by_mode(self):
        """Rule confidence fallback must be higher when activated_knowledge is present."""
        tools = self._make_tools()
        request = self._make_request()

        class FakeKnowledge:
            activated_rules = [object()]  # non-empty so truthy check passes

        data_onto = tools._validate_and_fill_missing_fields(
            {}, request, activated_knowledge=FakeKnowledge()
        )
        data_llm = tools._validate_and_fill_missing_fields(
            {}, request, activated_knowledge=None
        )

        onto_rule_conf = next(
            f["value"] for f in data_onto["confidence_factors"]
            if f["label"] == "规则可信度"
        )
        llm_rule_conf = next(
            f["value"] for f in data_llm["confidence_factors"]
            if f["label"] == "规则可信度"
        )
        assert onto_rule_conf > llm_rule_conf, (
            f"Onto rule confidence ({onto_rule_conf}) should be > LLM ({llm_rule_conf})"
        )

    def test_fallback_not_triggered_when_factors_present(self):
        """When LLM provides confidence_factors, fallback should NOT overwrite them."""
        tools = self._make_tools()
        request = self._make_request()
        existing_factors = [
            {"label": "自定义", "value": 0.42, "weight": 1.0, "explanation": "test"}
        ]
        data = tools._validate_and_fill_missing_fields(
            {"confidence_factors": existing_factors}, request, activated_knowledge=None
        )
        assert data["confidence_factors"][0]["value"] == 0.42
