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
