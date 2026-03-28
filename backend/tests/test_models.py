"""
Tests for Pydantic models.
"""
import pytest
from pydantic import ValidationError

from models import (
    DiagnosisContext, Role, AgentState, AgentID,
    StartRequest, Rule, Hypothesis, ReasoningStep
)


class TestRole:
    def test_role_values(self):
        assert Role.OWNER.value == "owner"
        assert Role.TECHNICIAN.value == "technician"
        assert Role.CUSTOMER_SERVICE.value == "customer_service"


class TestAgentState:
    def test_state_values(self):
        assert AgentState.IDLE.value == "idle"
        assert AgentState.RUNNING.value == "running"
        assert AgentState.DONE.value == "done"
        assert AgentState.ERROR.value == "error"


class TestAgentID:
    def test_agent_id_values(self):
        assert AgentID.ORCH.value == "orch"
        assert AgentID.SYM.value == "sym"
        assert AgentID.ONT.value == "ont"
        assert AgentID.RULE.value == "rule"
        assert AgentID.CONF.value == "conf"
        assert AgentID.OUT.value == "out"
        assert AgentID.LLM.value == "llm"


class TestStartRequest:
    def test_valid_request(self):
        req = StartRequest(symptom="test symptom")
        assert req.symptom == "test symptom"
        assert req.role == Role.OWNER
        assert req.signals == {}
    
    def test_with_role_and_signals(self):
        req = StartRequest(
            symptom="test",
            role=Role.TECHNICIAN,
            signals={"key": "value"}
        )
        assert req.role == Role.TECHNICIAN
        assert req.signals == {"key": "value"}
    
    def test_type_literal(self):
        req = StartRequest(symptom="test")
        assert req.type == "start"


class TestDiagnosisContext:
    def test_create_context(self, sample_symptom, sample_signals):
        ctx = DiagnosisContext(
            symptom=sample_symptom,
            role=Role.OWNER,
            signals=sample_signals
        )
        assert ctx.symptom == sample_symptom
        assert ctx.role == Role.OWNER
        assert ctx.signals == sample_signals
    
    def test_default_values(self, sample_symptom, sample_signals):
        ctx = DiagnosisContext(
            symptom=sample_symptom,
            role=Role.OWNER,
            signals=sample_signals
        )
        assert ctx.parsed_symptoms == []
        assert ctx.matched_rules == []
        assert ctx.final_confidence == 0
    
    def test_optional_vehicle_signals(self, sample_symptom, sample_signals):
        ctx = DiagnosisContext(
            symptom=sample_symptom,
            role=Role.OWNER,
            signals=sample_signals
        )
        assert ctx.vehicle_signals is None
    
    def test_with_reasoning_steps(self, sample_context):
        step = ReasoningStep(title="Test", body="Test body")
        sample_context.reasoning_steps.append(step)
        assert len(sample_context.reasoning_steps) == 1
        assert sample_context.reasoning_steps[0].title == "Test"


class TestRule:
    def test_create_rule(self):
        rule = Rule(
            id="T_1_2",
            text="Test rule",
            src="VEEA-SysR",
            conf="0.98"
        )
        assert rule.id == "T_1_2"
        assert rule.text == "Test rule"
        assert rule.src == "VEEA-SysR"
        assert rule.conf == "0.98"


class TestHypothesis:
    def test_create_hypothesis(self):
        hypo = Hypothesis(
            name="Test hypothesis",
            pct=75,
            cls="p"
        )
        assert hypo.name == "Test hypothesis"
        assert hypo.pct == 75
        assert hypo.cls == "p"
    
    def test_hypothesis_classes(self):
        """Test all valid hypothesis class types."""
        for cls_type in ["p", "s", "t"]:
            hypo = Hypothesis(name="test", pct=50, cls=cls_type)
            assert hypo.cls == cls_type


class TestReasoningStep:
    def test_create_reasoning_step(self):
        step = ReasoningStep(
            title="Analysis Step",
            body="Detailed analysis content"
        )
        assert step.title == "Analysis Step"
        assert step.body == "Detailed analysis content"


class TestConfFactor:
    """Tests for confidence factor model."""
    
    def test_create_conf_factor(self):
        from models import ConfFactor
        factor = ConfFactor(
            label="Signal Match",
            val=0.85,
            display="85%"
        )
        assert factor.label == "Signal Match"
        assert factor.val == 0.85
        assert factor.display == "85%"


class TestMsgPair:
    """Tests for message bus key-value pair."""
    
    def test_create_msg_pair(self):
        from models import MsgPair
        pair = MsgPair(k="key", v="value")
        assert pair.k == "key"
        assert pair.v == "value"
        assert pair.cls is None
    
    def test_msg_pair_with_class(self):
        from models import MsgPair
        pair = MsgPair(k="key", v="value", cls="g")
        assert pair.cls == "g"
