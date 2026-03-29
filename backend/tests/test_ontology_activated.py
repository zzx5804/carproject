"""Tests for ActivatedKnowledge models."""
import pytest
from pydantic import ValidationError
from models import ActivatedNode, ActivatedKnowledge, DiagnosisContext, OntoActivatedMessage, Role


def test_activated_node_creation():
    node = ActivatedNode(
        node_id="T_1_2",
        node_type="rule",
        label_zh="Disable跳转至Enable",
        confidence=0.92,
        source_triple="rules_model.ttl#ruleT_1_2",
    )
    assert node.node_id == "T_1_2"
    assert node.node_type == "rule"
    assert node.confidence == 0.92


@pytest.mark.parametrize("node_type", ["rule", "class", "individual"])
def test_activated_node_valid_types(node_type):
    node = ActivatedNode(
        node_id="T_1_2", node_type=node_type, label_zh="测试",
        confidence=0.5, source_triple="rules_model.ttl#ruleT_1_2"
    )
    assert node.node_type == node_type


def test_activated_knowledge_creation():
    rule = ActivatedNode(
        node_id="T_1_2",
        node_type="rule",
        label_zh="Disable跳转至Enable",
        confidence=0.92,
        source_triple="rules_model.ttl#ruleT_1_2",
    )
    knowledge = ActivatedKnowledge(
        activated_rules=[rule],
        activated_classes=[],
        signal_mappings={"sv-kv": ":ReadyEnableDisable"},
        sparql_queries=["SELECT ?rule WHERE { ?rule rdf:type :TransitionRule }"],
    )
    assert len(knowledge.activated_rules) == 1
    assert knowledge.signal_mappings["sv-kv"] == ":ReadyEnableDisable"


def test_diagnosis_context_has_activated_knowledge(sample_context):
    assert sample_context.activated_knowledge is None


def test_onto_activated_message():
    node = ActivatedNode(
        node_id="T_1_2", node_type="rule", label_zh="测试", confidence=0.9,
        source_triple="rules_model.ttl#ruleT_1_2"
    )
    msg = OntoActivatedMessage(
        nodes=[node],
        signal_mappings={"sv-kv": ":ReadyEnableDisable"},
    )
    assert msg.type == "onto_activated"
    assert len(msg.nodes) == 1


def test_activated_node_confidence_boundary_values():
    """Test boundary values for confidence field."""
    node_min = ActivatedNode(
        node_id="T_1_2", node_type="rule", label_zh="测试",
        confidence=0.0, source_triple="rules_model.ttl#ruleT_1_2"
    )
    assert node_min.confidence == 0.0

    node_max = ActivatedNode(
        node_id="T_1_2", node_type="rule", label_zh="测试",
        confidence=1.0, source_triple="rules_model.ttl#ruleT_1_2"
    )
    assert node_max.confidence == 1.0


def test_activated_node_confidence_out_of_range():
    """Test that confidence values outside [0, 1] are rejected."""
    with pytest.raises(ValidationError):
        ActivatedNode(
            node_id="T_1_2", node_type="rule", label_zh="测试",
            confidence=1.5, source_triple="rules_model.ttl#ruleT_1_2"
        )
    with pytest.raises(ValidationError):
        ActivatedNode(
            node_id="T_1_2", node_type="rule", label_zh="测试",
            confidence=-0.1, source_triple="rules_model.ttl#ruleT_1_2"
        )


def test_activated_node_invalid_type():
    """Test that invalid node_type values are rejected."""
    with pytest.raises(ValidationError):
        ActivatedNode(
            node_id="T_1_2", node_type="invalid_type", label_zh="测试",
            confidence=0.5, source_triple="rules_model.ttl#ruleT_1_2"
        )


def test_activated_knowledge_default_construction():
    """Test ActivatedKnowledge with no arguments produces empty collections."""
    knowledge = ActivatedKnowledge()
    assert knowledge.activated_rules == []
    assert knowledge.activated_classes == []
    assert knowledge.signal_mappings == {}
    assert knowledge.sparql_queries == []


# ── SPARQL query tests ────────────────────────────────────────────────────────

@pytest.fixture
def real_parser():
    """OntologyParser loaded from the project ontology folder."""
    from pathlib import Path
    from ontology.parser import OntologyParser
    folder = Path(__file__).parent.parent.parent / "ontology files"
    if not folder.exists():
        pytest.skip(f"Ontology folder not found: {folder}")
    parser = OntologyParser(str(folder))
    if not parser.load():
        pytest.skip("Failed to load ontology")
    return parser


def test_query_matching_rules_returns_list(real_parser):
    results = real_parser.query_matching_rules(["上电", "BLE"])
    assert isinstance(results, list)


def test_query_matching_rules_finds_t12(real_parser):
    """T_1_2 covers the Disable→Enable transition relevant to startup failure."""
    results = real_parser.query_matching_rules(["上电", "Enable", "Disable"])
    rule_ids = [n.node_id for n in results]
    assert "T_1_2" in rule_ids


def test_query_matching_rules_returns_activated_nodes(real_parser):
    results = real_parser.query_matching_rules(["上电"])
    for node in results:
        assert isinstance(node.node_id, str)
        assert node.node_type == "rule"
        assert 0.0 <= node.confidence <= 1.0
        assert "rules_model.ttl" in node.source_triple or node.source_triple != ""


def test_query_signal_individuals_off_mode(real_parser):
    signals = {"sv-pm": "0:Off", "sv-kv": "INVALID"}
    mappings = real_parser.query_signal_individuals(signals)
    assert isinstance(mappings, dict)
    # sv-pm=0:Off should map to OffMode or similar
    assert "sv-pm" in mappings


def test_query_rule_chain_returns_string(real_parser):
    chain = real_parser.query_rule_chain("T_1_2")
    assert isinstance(chain, str)
    assert len(chain) > 0
    assert "T_1_2" in chain


# ── OntologyFetcher integration tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ontology_fetcher_populates_activated_knowledge(
    real_parser, sample_context
):
    """After process(), context.activated_knowledge should be populated."""
    from agents.ontology_fetcher import OntologyFetcherAgent
    from unittest.mock import AsyncMock

    sent_messages = []

    agent = OntologyFetcherAgent()
    agent.set_ontology_parser(real_parser)
    agent._send = AsyncMock(side_effect=lambda msg: sent_messages.append(msg))

    result = await agent.process(sample_context)

    assert result.activated_knowledge is not None
    assert isinstance(result.activated_knowledge.activated_rules, list)
    assert isinstance(result.activated_knowledge.signal_mappings, dict)


@pytest.mark.asyncio
async def test_ontology_fetcher_sends_onto_activated_event(
    real_parser, sample_context
):
    """OntologyFetcher must emit onto_activated WebSocket event."""
    from agents.ontology_fetcher import OntologyFetcherAgent
    from unittest.mock import AsyncMock

    sent_messages = []
    agent = OntologyFetcherAgent()
    agent.set_ontology_parser(real_parser)
    agent._send = AsyncMock(side_effect=lambda msg: sent_messages.append(msg))

    await agent.process(sample_context)

    types = [m.get("type") for m in sent_messages if isinstance(m, dict)]
    assert "onto_activated" in types


# ── Prompt injection tests ────────────────────────────────────────────────────

def test_build_diagnosis_prompt_includes_rule_ids():
    """Prompt must contain activated rule IDs in [T_x_x] format."""
    from llm.prompts import get_prompt_builder
    from models import ActivatedNode, ActivatedKnowledge

    builder = get_prompt_builder()
    knowledge = ActivatedKnowledge(
        activated_rules=[
            ActivatedNode(
                node_id="T_1_2",
                node_type="rule",
                label_zh="Disable跳转至Enable",
                confidence=0.92,
                source_triple="rules_model.ttl#ruleT_1_2",
            )
        ],
        signal_mappings={"sv-kv": ":ReadyEnableDisable"},
        sparql_queries=[],
    )
    prompt = builder.build_diagnosis_prompt(
        symptom="踩刹车无法上电",
        role="owner",
        signals={"sv-pm": "0:Off", "sv-kv": "INVALID"},
        ontology_context="",
        matched_rules=[],
        activated_knowledge=knowledge,
    )
    assert "[T_1_2]" in prompt
    assert "rules_model.ttl#ruleT_1_2" in prompt
    assert "推理要求" in prompt


def test_build_diagnosis_prompt_includes_signal_mappings():
    from llm.prompts import get_prompt_builder
    from models import ActivatedKnowledge

    builder = get_prompt_builder()
    knowledge = ActivatedKnowledge(
        signal_mappings={"sv-kv": ":ReadyEnableDisable", "sv-pm": ":OffMode"},
    )
    prompt = builder.build_diagnosis_prompt(
        symptom="无法上电",
        role="owner",
        signals={"sv-pm": "0:Off", "sv-kv": "INVALID"},
        ontology_context="",
        matched_rules=[],
        activated_knowledge=knowledge,
    )
    assert ":ReadyEnableDisable" in prompt
    assert ":OffMode" in prompt


def test_fault_scenario_weighted_higher(real_parser):
    """faultScenario keyword must yield >= confidence vs label-only keyword for same rule."""
    fault_results = real_parser.query_matching_rules(["钥匙未找到"])
    label_results = real_parser.query_matching_rules(["Enable"])
    fault_node = next((n for n in fault_results if n.node_id == "T_1_2"), None)
    label_node = next((n for n in label_results if n.node_id == "T_1_2"), None)
    if fault_node and label_node:
        assert fault_node.confidence >= label_node.confidence, (
            f"faultScenario hit ({fault_node.confidence}) should be >= "
            f"label-only hit ({label_node.confidence})"
        )


def test_multiple_fault_scenarios_all_searchable(real_parser):
    """Multiple :faultScenario values for the same rule must all be matchable."""
    results1 = real_parser.query_matching_rules(["远程启动失败"])
    results2 = real_parser.query_matching_rules(["APP下发远程上电无响应"])
    assert "T_1_3" in [n.node_id for n in results1], "T_1_3 should match '远程启动失败'"
    assert "T_1_3" in [n.node_id for n in results2], "T_1_3 should match 'APP下发远程上电无响应'"
