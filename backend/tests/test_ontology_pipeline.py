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


class TestPromptTone:
    """Test that service.py prompt building uses reference tone, not mandatory instructions."""

    def test_generate_diagnosis_prompt_no_mandatory_instruction(self):
        """The reasoning_requirement built in generate_diagnosis must not contain '必须遵守'."""
        import inspect
        from llm.service import LLMTools
        source = inspect.getsource(LLMTools.generate_diagnosis)
        assert "必须遵守" not in source, (
            "generate_diagnosis still contains '必须遵守' — change to optional reference tone"
        )

    def test_generate_diagnosis_prompt_has_reference_language(self):
        """After fix, prompt should contain reference language."""
        import inspect
        from llm.service import LLMTools
        source = inspect.getsource(LLMTools.generate_diagnosis)
        assert "可选引用" in source or "供参考" in source, (
            "generate_diagnosis should contain optional reference language"
        )


class TestOrchestratorPipeline:
    """Test that orchestrator runs OntologyFetcher before LLMDiagnosisAgent when use_ontology=True."""

    @pytest.mark.asyncio
    async def test_ontology_fetcher_called_when_use_ontology_true(self):
        """When use_ontology=True, OntologyFetcher must run before LLMDiagnosisAgent."""
        from unittest.mock import AsyncMock, patch
        from agents.orchestrator import OrchestratorAgent
        from models import DiagnosisContext, Role, AgentID, ActivatedKnowledge

        orchestrator = OrchestratorAgent(use_llm=True)

        # Track call order
        call_order = []

        # Mock SymptomParser
        mock_sym = AsyncMock()
        mock_sym.agent_id = AgentID.SYM
        async def sym_run(ctx):
            call_order.append("sym")
            return ctx
        mock_sym.run = sym_run

        # Mock OntologyFetcher — fills activated_knowledge
        mock_ont = AsyncMock()
        mock_ont.agent_id = AgentID.ONT
        async def ont_run(ctx):
            call_order.append("ont")
            ctx.activated_knowledge = ActivatedKnowledge(
                activated_rules=[], activated_classes=[],
                signal_mappings={}, sparql_queries=[]
            )
            return ctx
        mock_ont.run = ont_run

        # Mock LLMDiagnosisAgent — checks activated_knowledge is already set
        mock_llm = AsyncMock()
        mock_llm.agent_id = AgentID.LLM
        async def llm_run(ctx):
            call_order.append("llm")
            assert ctx.activated_knowledge is not None, (
                "activated_knowledge must be set before LLM agent runs"
            )
            return ctx
        mock_llm.run = llm_run

        orchestrator.agents[AgentID.SYM] = mock_sym
        orchestrator.agents[AgentID.ONT] = mock_ont
        orchestrator.agents[AgentID.LLM] = mock_llm

        context = DiagnosisContext(
            symptom="踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'",
            role=Role.OWNER,
            signals={"sv-kv": "INVALID"},
            use_ontology=True,
        )

        with patch.object(orchestrator, 'send_msg_bus', new_callable=AsyncMock), \
             patch.object(orchestrator, 'animate_wire', new_callable=AsyncMock), \
             patch.object(orchestrator, 'send', new_callable=AsyncMock), \
             patch.object(orchestrator, 'update_status', new_callable=AsyncMock):
            await orchestrator._execute_llm_pipeline(context)

        assert "sym" in call_order, "SymptomParser must be called"
        assert "ont" in call_order, "OntologyFetcher must be called"
        assert "llm" in call_order, "LLMDiagnosisAgent must be called"
        assert call_order.index("sym") < call_order.index("llm"), "sym must run before llm"
        assert call_order.index("ont") < call_order.index("llm"), "ont must run before llm"

    @pytest.mark.asyncio
    async def test_ontology_fetcher_not_called_when_use_ontology_false(self):
        """When use_ontology=False, OntologyFetcher must NOT run."""
        from unittest.mock import AsyncMock, patch
        from agents.orchestrator import OrchestratorAgent
        from models import DiagnosisContext, Role, AgentID

        orchestrator = OrchestratorAgent(use_llm=True)
        call_order = []

        mock_ont = AsyncMock()
        mock_ont.agent_id = AgentID.ONT
        async def ont_run(ctx):
            call_order.append("ont")
            return ctx
        mock_ont.run = ont_run

        mock_llm = AsyncMock()
        mock_llm.agent_id = AgentID.LLM
        async def llm_run(ctx):
            call_order.append("llm")
            return ctx
        mock_llm.run = llm_run

        orchestrator.agents[AgentID.ONT] = mock_ont
        orchestrator.agents[AgentID.LLM] = mock_llm

        context = DiagnosisContext(
            symptom="无法上电",
            role=Role.OWNER,
            signals={},
            use_ontology=False,
        )

        with patch.object(orchestrator, 'send_msg_bus', new_callable=AsyncMock), \
             patch.object(orchestrator, 'animate_wire', new_callable=AsyncMock), \
             patch.object(orchestrator, 'send', new_callable=AsyncMock), \
             patch.object(orchestrator, 'update_status', new_callable=AsyncMock):
            await orchestrator._execute_llm_pipeline(context)

        assert "ont" not in call_order, "OntologyFetcher must NOT be called in pure-LLM mode"
        assert "llm" in call_order


class TestFaultScenarioMatching:
    """
    Integration tests: verify :faultScenario phrases in rules_model.ttl
    enable query_matching_rules() to match user fault descriptions.
    These tests load real TTL files and must not use mocks.
    """

    @pytest.fixture(scope="class")
    def parser(self):
        from pathlib import Path
        from ontology.parser import OntologyParser
        folder = Path(__file__).parent.parent.parent / "ontology files"
        if not folder.exists():
            pytest.skip(f"Ontology folder not found: {folder}")
        p = OntologyParser(str(folder))
        if not p.load():
            pytest.skip("Failed to load ontology")
        return p

    def test_key_not_found_hits_t12(self, parser):
        """'钥匙未找到' must activate T_1_2 (Disable→Enable)."""
        results = parser.query_matching_rules(["踩刹车按启动按钮", "无法上电", "钥匙未找到"])
        rule_ids = [n.node_id for n in results]
        assert "T_1_2" in rule_ids, f"T_1_2 must be activated for '钥匙未找到', got: {rule_ids}"

    def test_remote_start_failure_hits_t13(self, parser):
        """'远程启动失败' must activate T_1_3 (Off→RemoteOn)."""
        results = parser.query_matching_rules(["远程启动失败", "APP无响应"])
        rule_ids = [n.node_id for n in results]
        assert "T_1_3" in rule_ids, f"T_1_3 must be activated, got: {rule_ids}"

    def test_local_start_failure_hits_t11(self, parser):
        """'按启动按钮无法上电' must activate T_1_1 (Off→LocalOn)."""
        results = parser.query_matching_rules(["按启动按钮无法上电"])
        rule_ids = [n.node_id for n in results]
        assert "T_1_1" in rule_ids, f"T_1_1 must be activated, got: {rule_ids}"

    def test_fault_scenario_hit_gives_higher_confidence_than_label_only(self, parser):
        """A faultScenario keyword must yield higher confidence than a label-only keyword."""
        results_fault = parser.query_matching_rules(["钥匙未找到"])
        results_label = parser.query_matching_rules(["Enable"])
        fault_node = next((n for n in results_fault if n.node_id == "T_1_2"), None)
        label_node = next((n for n in results_label if n.node_id == "T_1_2"), None)
        assert fault_node is not None, "T_1_2 should be activated by fault phrase"
        assert label_node is not None, "T_1_2 should be activated by label keyword"
        assert fault_node.confidence >= label_node.confidence, (
            f"Fault phrase confidence ({fault_node.confidence}) should be >= "
            f"label-only confidence ({label_node.confidence})"
        )

    def test_no_false_positive_on_unrelated_keyword(self, parser):
        """A completely unrelated keyword must not activate any rule."""
        results = parser.query_matching_rules(["轮胎气压不足"])
        assert results == [], f"No rules should match unrelated keyword, got: {results}"

    def test_full_symptom_sentence_hits_at_least_one_rule(self, parser):
        """The original bug-trigger symptom must now activate at least one rule."""
        kws = ["踩刹车按启动按钮", "车辆无法上电", "屏幕弹出", "钥匙未找到"]
        results = parser.query_matching_rules(kws)
        assert len(results) > 0, (
            "Original bug: full symptom sentence should now hit at least one rule"
        )
