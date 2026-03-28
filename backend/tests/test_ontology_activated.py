"""Tests for ActivatedKnowledge models."""
import pytest
from models import ActivatedNode, ActivatedKnowledge, DiagnosisContext, Role


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
    from models import OntoActivatedMessage, ActivatedNode
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
    from pydantic import ValidationError
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
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ActivatedNode(
            node_id="T_1_2", node_type="invalid_type", label_zh="测试",
            confidence=0.5, source_triple="rules_model.ttl#ruleT_1_2"
        )
