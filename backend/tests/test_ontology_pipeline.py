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
