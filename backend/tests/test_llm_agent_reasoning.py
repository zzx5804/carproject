"""Tests for _send_reasoning_steps in LLMDiagnosisAgent."""
import pytest
from agents.llm_diagnosis_agent import LLMDiagnosisAgent
from llm.schemas import ReasoningStep, DiagnosisResponse


def make_response(steps):
    return DiagnosisResponse(
        diagnosis_id="test_001",
        summary="测试",
        reasoning_steps=steps,
        final_confidence=0.85,
        model_used="test-model",
    )


@pytest.mark.asyncio
async def test_send_reasoning_steps_includes_elapsed_ms():
    """elapsed_ms must be injected even if LLM returned None."""
    agent = LLMDiagnosisAgent()
    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    async def mock_delay(ms):
        pass

    agent.send = mock_send
    agent.delay = mock_delay

    steps = [
        ReasoningStep(step_number=1, title="信号分析", body="BLE错误", confidence=0.88),
    ]
    response = make_response(steps)
    await agent._send_reasoning_steps(response)

    assert len(sent_messages) == 1
    step_payload = sent_messages[0]["step"]
    assert "elapsed_ms" in step_payload
    assert isinstance(step_payload["elapsed_ms"], int)
    assert step_payload["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_send_reasoning_steps_passes_new_fields():
    """signals_referenced, rules_matched, confidence_delta must be forwarded."""
    agent = LLMDiagnosisAgent()
    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    async def mock_delay(ms):
        pass

    agent.send = mock_send
    agent.delay = mock_delay

    steps = [
        ReasoningStep(
            step_number=1, title="信号分析", body="BLE错误",
            confidence=0.88, confidence_delta=0.05,
            signals_referenced=[{"key": "BLE_Auth_Error", "value": "AUTH_ERR", "level": "error"}],
            rules_matched=["T_1_3"],
        ),
    ]
    response = make_response(steps)
    await agent._send_reasoning_steps(response)

    step_payload = sent_messages[0]["step"]
    assert step_payload["confidence"] == 0.88
    assert step_payload["confidence_delta"] == 0.05
    # signals_referenced 是 SignalRef 对象，model_dump() 后变为 dict
    assert step_payload["signals_referenced"][0]["key"] == "BLE_Auth_Error"
    assert step_payload["rules_matched"] == ["T_1_3"]


@pytest.mark.asyncio
async def test_send_reasoning_steps_elapsed_ms_overrides_llm_value():
    """Backend-injected elapsed_ms should replace any LLM-provided value."""
    agent = LLMDiagnosisAgent()
    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    async def mock_delay(ms):
        pass

    agent.send = mock_send
    agent.delay = mock_delay

    steps = [
        ReasoningStep(step_number=1, title="T", body="B", elapsed_ms=99999),
    ]
    response = make_response(steps)
    await agent._send_reasoning_steps(response)

    step_payload = sent_messages[0]["step"]
    # Backend should override with real measurement, not LLM's 99999
    assert step_payload["elapsed_ms"] != 99999
