"""
LLM Diagnosis Agent - LLM-powered intelligent diagnosis.

This agent replaces the hardcoded SymptomParser + RuleEngine + OutputAdapter
pipeline with a fully LLM-driven diagnosis approach.
"""

import time
from typing import Dict, Any, Optional, List
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, AgentState
from llm import (
    LLMService,
    get_llm_service,
    DiagnosisRequest,
    DiagnosisResponse,
    SignalInfo,
    Role,
    FallbackHandler,
    get_fallback_handler,
)


class LLMDiagnosisAgent(BaseAgent):
    """
    LLM-powered Diagnosis Agent.

    This agent performs the complete diagnosis pipeline:
    1. Parse symptom using LLM semantic understanding
    2. Match rules using LLM reasoning
    3. Generate hypotheses with confidence
    4. Produce role-adapted output

    When LLM is unavailable, falls back to hardcoded rules.
    """

    def __init__(self, agent_id: AgentID = AgentID.LLM):
        super().__init__(agent_id)
        self._llm_service: Optional[LLMService] = None
        self._fallback_handler: Optional[FallbackHandler] = None
        self._ontology_parser = None

    def set_ontology_parser(self, parser):
        """Set the ontology parser instance."""
        self._ontology_parser = parser

    @property
    def llm_service(self) -> LLMService:
        """Get or create LLM service."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    @property
    def fallback_handler(self) -> FallbackHandler:
        """Get or create fallback handler."""
        if self._fallback_handler is None:
            self._fallback_handler = get_fallback_handler()
        return self._fallback_handler

    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """
        Process diagnosis using LLM.

        Main diagnosis pipeline:
        1. Build diagnosis request from context
        2. Call LLM service for diagnosis
        3. Update context with results
        4. Send results to frontend

        Args:
            context: Diagnosis context

        Returns:
            Updated diagnosis context
        """
        logger.info(f"LLMDiagnosisAgent processing: {context.symptom[:50]}...")

        start_time = time.time()
        await self.update_status(AgentState.RUNNING, 0)

        # ✨ Send initial thinking status
        await self.send(
            {
                "type": "llm_thinking",
                "agent": "llm",
                "content": "🔄 开始分析症状...",
                "phase": "init",
            }
        )

        # Notify frontend
        await self.send_msg_bus(
            "ALL",
            [
                {"k": "任务", "v": "LLM智能诊断启动"},
                {"k": "症状", "v": context.symptom[:30] + "..."},
                {
                    "k": "角色",
                    "v": context.role.value
                    if hasattr(context.role, "value")
                    else str(context.role),
                },
            ],
        )

        await self.delay(300)
        await self.update_status(AgentState.RUNNING, 10)

        # Build request
        request = self._build_request(context)
        await self.update_status(AgentState.RUNNING, 20)

        # ✨ Send thinking: Building request
        await self.send(
            {
                "type": "llm_thinking",
                "agent": "llm",
                "content": "📋 构建诊断请求，提取关键信号...",
                "phase": "build_request",
            }
        )

        # Perform diagnosis
        try:
            # ✨ Send thinking: Parsing symptom
            await self.send(
                {
                    "type": "llm_thinking",
                    "agent": "llm",
                    "content": "🔍 解析症状语义，识别关键实体...",
                    "phase": "parse_symptom",
                }
            )

            # Try LLM diagnosis first
            response = await self.llm_service.diagnose(
                request,
                ontology_parser=self._ontology_parser,
                fallback_handler=self.fallback_handler.diagnose,
            )

            # ✨ Send thinking: Rules matched
            await self.send(
                {
                    "type": "llm_thinking",
                    "agent": "llm",
                    "content": "⚡ 匹配诊断规则，生成假设...",
                    "phase": "rule_matching",
                }
            )

            await self.update_status(AgentState.RUNNING, 70)

        except Exception as e:
            logger.warning(
                f"LLM diagnosis failed ({type(e).__name__}), using fallback: {e}"
            )

            # ✨ Send thinking: Using fallback
            await self.send(
                {
                    "type": "llm_thinking",
                    "agent": "llm",
                    "content": f"⚠️ LLM调用失败，使用规则引擎 fallback: {str(e)[:50]}",
                    "phase": "fallback",
                }
            )

            # Use fallback handler directly
            response = await self.fallback_handler.diagnose(request)

            await self.update_status(AgentState.RUNNING, 70)

        # Update context with diagnosis results
        context = self._update_context(context, response)

        # ✨ Send thinking: Reasoning complete
        await self.send(
            {
                "type": "llm_thinking",
                "agent": "llm",
                "content": "📊 计算置信度，生成最终输出...",
                "phase": "finalize",
            }
        )

        # Send reasoning steps to frontend
        await self._send_reasoning_steps(response)
        await self.update_status(AgentState.RUNNING, 85)

        # Send matched rules to frontend
        await self._send_matched_rules(response)
        await self.update_status(AgentState.RUNNING, 88)

        # Send hypothesis to frontend
        await self._send_hypothesis(response)
        await self.update_status(AgentState.RUNNING, 90)

        # Send confidence factors
        await self._send_confidence_factors(response)
        await self.update_status(AgentState.RUNNING, 95)

        # ✨ Send thinking: Complete
        await self.send(
            {
                "type": "llm_thinking",
                "agent": "llm",
                "content": "✅ 诊断完成！",
                "phase": "complete",
            }
        )

        # Send output
        role_str = (
            context.role.value if hasattr(context.role, "value") else str(context.role)
        )
        output_html = response.to_html(Role(role_str))

        await self.send(
            {
                "type": "output",
                "html": output_html,
                "output": {
                    "text": response.get_output_for_role(Role(role_str)),
                    "role": role_str,
                    "escalation": bool(response.escalation_hint)
                    if response.escalation_hint
                    else False,
                    "hint": response.escalation_hint,
                },
                "escalation": response.escalation_hint,
            }
        )

        # Update context output
        context.output_html = output_html
        context.escalation_hint = response.escalation_hint

        # Notify completion
        processing_time = int((time.time() - start_time) * 1000)
        await self.send_msg_bus(
            "ALL",
            [
                {"k": "状态", "v": "LLM诊断完成 ✓", "cls": "g"},
                {
                    "k": "置信度",
                    "v": f"{int(response.final_confidence * 100)}%",
                    "cls": "g",
                },
                {"k": "耗时", "v": f"{processing_time}ms"},
                {"k": "模型", "v": response.model_used},
            ],
        )

        await self.update_status(AgentState.DONE, 100)

        logger.info(
            f"LLM diagnosis complete. Confidence: {response.final_confidence:.0%}, Time: {processing_time}ms"
        )

        return context

    def _build_request(self, context: DiagnosisContext) -> DiagnosisRequest:
        """Build diagnosis request from context."""
        # Convert signals dict to SignalInfo list
        signals = [SignalInfo(key=k, value=v) for k, v in context.signals.items()]

        # Get role
        role = Role.OWNER
        if hasattr(context.role, "value"):
            role = Role(context.role.value)

        return DiagnosisRequest(symptom=context.symptom, role=role, signals=signals)

    def _update_context(
        self, context: DiagnosisContext, response: DiagnosisResponse
    ) -> DiagnosisContext:
        """Update context with diagnosis response."""
        # Update reasoning steps
        from models import ReasoningStep as ContextReasoningStep

        context.reasoning_steps = [
            ContextReasoningStep(title=step.title, body=step.body)
            for step in response.reasoning_steps
        ]

        # Update hypotheses
        from models import Hypothesis

        if response.primary_hypothesis:
            context.hypotheses = [
                Hypothesis(
                    name=response.primary_hypothesis.root_cause,
                    pct=int(response.primary_hypothesis.confidence * 100),
                    cls="p",
                )
            ]

        for hypo in response.secondary_hypotheses:
            context.hypotheses.append(
                Hypothesis(
                    name=hypo.root_cause,
                    pct=int(hypo.confidence * 100),
                    cls="s" if hypo.rank == 2 else "t",
                )
            )

        # Update confidence
        context.final_confidence = int(response.final_confidence * 100)

        # Update matched rules (from confidence factors)
        from models import Rule, ConfFactor

        context.confidence_factors = [
            ConfFactor(label=f.label, val=f.value, display=f"{int(f.value * 100)}%")
            for f in response.confidence_factors
        ]

        return context

    async def _send_reasoning_steps(self, response: DiagnosisResponse):
        """Send reasoning steps to frontend."""
        for step in response.reasoning_steps:
            await self.delay(200)
            await self.send(
                {
                    "type": "reasoning_step",
                    "step": {
                        "title": f"[{step.step_number}] {step.title}",
                        "body": step.body,
                    },
                }
            )

    async def _send_hypothesis(self, response: DiagnosisResponse):
        """Send hypothesis to frontend."""
        if response.primary_hypothesis:
            await self.send(
                {
                    "type": "hypothesis",
                    "hypothesis": {
                        "name": response.primary_hypothesis.root_cause,
                        "pct": int(response.primary_hypothesis.confidence * 100),
                        "cls": "p",
                        "desc": response.primary_hypothesis.root_cause,
                        "conf": response.primary_hypothesis.confidence,
                    },
                }
            )

        for hypo in response.secondary_hypotheses[:2]:  # Max 2 secondary
            await self.delay(150)
            await self.send(
                {
                    "type": "hypothesis",
                    "hypothesis": {
                        "name": hypo.root_cause,
                        "pct": int(hypo.confidence * 100),
                        "cls": "s" if hypo.rank == 2 else "t",
                        "desc": hypo.root_cause,
                        "conf": hypo.confidence,
                    },
                }
            )

    async def _send_matched_rules(self, response: DiagnosisResponse):
        """Send matched rules to frontend."""
        # Import rules from diagnosis_knowledge
        from diagnosis_knowledge import RULES

        # Get top matched rules based on confidence factors
        matched_rule_ids = []
        for factor in response.confidence_factors:
            if factor.value > 0.7:
                # Find related rules based on factor label
                for rule_id, rule in RULES.items():
                    if rule_id not in matched_rule_ids and len(matched_rule_ids) < 3:
                        matched_rule_ids.append(rule_id)
                        await self.send(
                            {
                                "type": "rule_matched",
                                "rule": {
                                    "id": rule["id"],
                                    "text": rule["text"][:100] + "..."
                                    if len(rule["text"]) > 100
                                    else rule["text"],
                                    "src": rule["src"],
                                    "conf": rule["conf"],
                                },
                            }
                        )
                        await self.delay(200)

    async def _send_confidence_factors(self, response: DiagnosisResponse):
        """Send confidence factors to frontend."""
        await self.send(
            {
                "type": "conf_factors",
                "factors": [
                    {
                        "label": f.label,
                        "val": f.value,
                        "display": f"{int(f.value * 100)}%",
                    }
                    for f in response.confidence_factors
                ],
            }
        )

        confidence_pct = int(response.final_confidence * 100)
        await self.send(
            {
                "type": "conf_final",
                "confidence": confidence_pct,
                "level": "high"
                if confidence_pct >= 80
                else "medium"
                if confidence_pct >= 60
                else "low",
            }
        )


# Note: Agent registration is handled in agents/__init__.py
# to avoid side-effects at module import time
