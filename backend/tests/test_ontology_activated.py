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
