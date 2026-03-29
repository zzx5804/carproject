"""Tests for enhanced ReasoningStep schema fields."""
import pytest
from pydantic import ValidationError
from llm.schemas import ReasoningStep


def test_reasoning_step_new_fields_all_optional():
    """New fields are optional — old payloads must still parse."""
    step = ReasoningStep(step_number=1, title="信号分析", body="BLE错误")
    assert step.confidence_delta is None
    assert step.signals_referenced is None
    assert step.rules_matched is None
    assert step.elapsed_ms is None


def test_reasoning_step_with_all_new_fields():
    step = ReasoningStep(
        step_number=1,
        title="信号分析",
        body="检测到 BLE 错误",
        confidence=0.88,
        confidence_delta=0.05,
        signals_referenced=[
            {"key": "BLE_Auth_Error", "value": "AUTH_ERR(0x05)", "level": "error"},
            {"key": "KeyValidSt", "value": "INVALID", "level": "error"},
        ],
        rules_matched=["T_1_3"],
        elapsed_ms=800,
    )
    assert step.confidence == 0.88
    assert step.confidence_delta == 0.05
    assert len(step.signals_referenced) == 2
    assert step.signals_referenced[0].key == "BLE_Auth_Error"
    assert step.rules_matched == ["T_1_3"]
    assert step.elapsed_ms == 800


def test_reasoning_step_confidence_delta_can_be_negative():
    step = ReasoningStep(
        step_number=2, title="验证", body="部分排除",
        confidence=0.85, confidence_delta=-0.03
    )
    assert step.confidence_delta == -0.03


def test_reasoning_step_elapsed_ms_must_be_positive():
    with pytest.raises(ValidationError):
        ReasoningStep(
            step_number=1, title="T", body="B",
            elapsed_ms=-100
        )


def test_reasoning_step_signals_referenced_level_values():
    """level 字段只接受 error/warn/ok，非法值应被拒绝。"""
    # 合法值
    step = ReasoningStep(
        step_number=1, title="T", body="B",
        signals_referenced=[
            {"key": "K", "value": "V", "level": "ok"}
        ]
    )
    assert step.signals_referenced[0].level == "ok"

    # 非法值
    with pytest.raises(ValidationError):
        ReasoningStep(
            step_number=1, title="T", body="B",
            signals_referenced=[
                {"key": "K", "value": "V", "level": "critical"}
            ]
        )


def test_reasoning_step_rules_matched_invalid_format():
    """rules_matched 中非 T_N_N 格式应被拒绝。"""
    with pytest.raises(ValidationError):
        ReasoningStep(
            step_number=1, title="T", body="B",
            rules_matched=["INVALID_RULE"]
        )


def test_reasoning_step_agent_default():
    """agent field defaults to 'llm' when not provided."""
    step = ReasoningStep(step_number=1, title="t", body="b")
    assert step.agent == "llm"


def test_reasoning_step_agent_ont():
    """agent field accepts 'ont'."""
    step = ReasoningStep(step_number=1, title="t", body="b", agent="ont")
    assert step.agent == "ont"


def test_reasoning_step_agent_output():
    """agent field accepts 'output'."""
    step = ReasoningStep(step_number=1, title="t", body="b", agent="output")
    assert step.agent == "output"


def test_reasoning_step_agent_invalid_value():
    """Invalid agent value should raise ValidationError."""
    with pytest.raises(ValidationError):
        ReasoningStep(step_number=1, title="t", body="b", agent="unknown")


def test_reasoning_step_deficit_note_default():
    """deficit_note defaults to None when not provided."""
    step = ReasoningStep(step_number=1, title="t", body="b")
    assert step.deficit_note is None


def test_reasoning_step_deficit_note_string():
    """deficit_note accepts any string value."""
    step = ReasoningStep(
        step_number=1, title="t", body="b",
        deficit_note="识别到信号异常，但未通过本体规则链验证"
    )
    assert step.deficit_note == "识别到信号异常，但未通过本体规则链验证"


def test_fill_deficit_notes_no_ontology():
    """_fill_deficit_notes sets notes when activated_knowledge is None."""
    from llm.service import LLMTools
    from llm.config import get_llm_config

    tools = LLMTools(get_llm_config())

    steps = [
        ReasoningStep(step_number=1, title="分析", body="b"),  # 兜底
        ReasoningStep(
            step_number=2, title="验证", body="b",
            signals_referenced=[{"key": "K", "value": "V", "level": "ok"}]
        ),  # 有信号无规则
        ReasoningStep(
            step_number=3, title="结论", body="b",
            agent="output"
        ),  # output → None
        ReasoningStep(
            step_number=4, title="规则验证", body="b",
            rules_matched=["T_1_3"]
        ),  # 有规则（LLM 幻觉）
    ]

    result = tools._fill_deficit_notes(steps, activated_knowledge=None)

    assert result[0].deficit_note == "无信号引用与规则依据，推理基于语义理解"
    assert result[1].deficit_note == "识别到信号异常，但未通过本体规则链验证"
    assert result[2].deficit_note is None
    assert result[3].deficit_note == "规则引用来自 LLM 推测，未经 SPARQL 验证"


def test_fill_deficit_notes_with_ontology():
    """_fill_deficit_notes does nothing when activated_knowledge is present."""
    from llm.service import LLMTools
    from llm.config import get_llm_config

    tools = LLMTools(get_llm_config())

    steps = [
        ReasoningStep(step_number=1, title="t", body="b"),
    ]

    class FakeKnowledge:
        pass

    result = tools._fill_deficit_notes(steps, activated_knowledge=FakeKnowledge())
    assert result[0].deficit_note is None
