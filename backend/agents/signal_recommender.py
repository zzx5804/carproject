"""
SignalRecommender Agent - Recommends signals to read for diagnosis.
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from agents.base import BaseAgent
from models import (
    DiagnosisContext,
    AgentID,
    AgentState,
    Role,
    SignalRecommendation,
    SignalPriority,
)
from diagnosis_knowledge import SIGNAL_RECOMMENDATIONS
from scenario_detector import get_scenario_detector


class SignalRecommenderAgent(BaseAgent):
    """
    Signal Recommender Agent.

    Responsibilities:
    - Detect the diagnosis scenario from context
    - Look up signal recommendations for the scenario
    - Filter recommendations based on signals already available
    - Generate role-adapted output for the recommendations
    - Send recommendations via WebSocket and update context
    """

    def __init__(self, agent_id: AgentID = AgentID.SIG):
        super().__init__(agent_id)
        self._scenario_detector = get_scenario_detector()

    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Generate signal recommendations based on detected scenario."""
        logger.info("SignalRecommender processing...")

        await self.update_status(AgentState.RUNNING, 0)

        # Detect scenario
        scenario = self._detect_scenario(context)
        role = context.role

        # Get recommendations for the scenario
        recommendations = self._get_recommendations(scenario, context)

        # Filter out signals already available in context
        filtered_recommendations = self._filter_available_signals(
            recommendations, context
        )

        # Store in context
        context.signal_recommendations = filtered_recommendations

        await self.delay(300)
        await self.update_status(AgentState.RUNNING, 50)

        # Generate and send WebSocket message
        await self._send_recommendations(filtered_recommendations, scenario, role)

        # Generate HTML output for non-WebSocket clients
        html_output = self._generate_html_output(
            filtered_recommendations, scenario, role
        )

        # Append to context output_html
        if context.output_html:
            context.output_html += "\n" + html_output
        else:
            context.output_html = html_output

        # Notify orchestrator
        count = len(filtered_recommendations)
        await self.send_msg_bus("orch", [
            {"k": "信号建议", "v": f"{count}条推荐", "cls": "g"},
            {"k": "场景", "v": scenario}
        ])

        await self.update_status(AgentState.DONE, 100)

        return context

    def _detect_scenario(self, context: DiagnosisContext) -> str:
        """Detect scenario from context using ScenarioDetector."""
        return self._scenario_detector.detect_from_context_with_dtc(context)

    def _get_recommendations(
        self, scenario: str, context: DiagnosisContext
    ) -> List[SignalRecommendation]:
        """Get signal recommendations for the scenario."""
        recommendations: List[SignalRecommendation] = []

        # Get raw recommendations from knowledge base
        raw_recs = SIGNAL_RECOMMENDATIONS.get(scenario, [])

        if not raw_recs:
            logger.warning(f"No signal recommendations found for scenario: {scenario}")
            return recommendations

        # Convert to SignalRecommendation objects
        for rec in raw_recs:
            priority = SignalPriority.REQUIRED
            if rec.get("priority") == "optional":
                priority = SignalPriority.OPTIONAL

            recommendation = SignalRecommendation(
                signal_name=rec.get("name", ""),
                description_zh=rec.get("description_zh", ""),
                description_en=rec.get("description_en", ""),
                reason=rec.get("reason", ""),
                priority=priority,
                read_method=rec.get("read_method", ""),
            )
            recommendations.append(recommendation)

        return recommendations

    def _filter_available_signals(
        self,
        recommendations: List[SignalRecommendation],
        context: DiagnosisContext,
    ) -> List[SignalRecommendation]:
        """Filter out signals that are already available in context."""
        # Get the set of signal names already available
        available_signals = set(context.signals.keys())

        # Also check vehicle_signals if present
        if context.vehicle_signals:
            # Get all non-None vehicle signal names
            vs_dict = context.vehicle_signals.model_dump(by_alias=True, exclude_none=True)
            available_signals.update(vs_dict.keys())

        # Filter recommendations
        filtered = []
        for rec in recommendations:
            # Check if signal name or alias is already available
            signal_available = False

            # Check direct match
            if rec.signal_name in available_signals:
                signal_available = True

            # Check common aliases
            alias_map = {
                "LDCU_PowerMode": ["ldcu_power_mode", "LDCU_PowerMode"],
                "KeyValidSt": ["key_valid_st", "KeyValidSt", "sv-kv"],
                "Flag_BLE": ["flag_ble", "Flag_BLE"],
                "BrkPedalSt": ["brk_pedal_st", "BrkPedalSt"],
                "Gearlev": ["gearlev", "Gearlev"],
            }

            if rec.signal_name in alias_map:
                for alias in alias_map[rec.signal_name]:
                    if alias in available_signals:
                        signal_available = True
                        break

            if not signal_available:
                filtered.append(rec)

        logger.info(
            f"Filtered {len(recommendations)} recommendations to {len(filtered)} "
            f"(available: {len(available_signals)} signals)"
        )

        return filtered

    async def _send_recommendations(
        self,
        recommendations: List[SignalRecommendation],
        scenario: str,
        role: Role,
    ) -> None:
        """Send recommendations via WebSocket."""
        # Send the structured message
        await self.send({
            "type": "signal_recommendations",
            "recommendations": [rec.model_dump() for rec in recommendations],
            "scenario": scenario,
        })

        # Send a reasoning step for UI display
        step_html = self._generate_reasoning_step_html(recommendations, role)
        await self.send({
            "type": "reasoning_step",
            "step": {
                "title": "📊 信号读取建议",
                "body": step_html,
            }
        })

    def _generate_reasoning_step_html(
        self,
        recommendations: List[SignalRecommendation],
        role: Role,
    ) -> str:
        """Generate HTML for reasoning step display."""
        if not recommendations:
            return "<p style='color:var(--txd)'>所有必要信号已获取，无需额外读取。</p>"

        # Format differently based on role
        if role == Role.TECHNICIAN:
            return self._generate_technician_html(recommendations)
        else:
            return self._generate_owner_html(recommendations)

    def _generate_technician_html(
        self, recommendations: List[SignalRecommendation]
    ) -> str:
        """Generate detailed HTML for technician role."""
        lines = ["<div class='signal-rec-list'>"]

        for rec in recommendations:
            priority_badge = "🔴" if rec.priority == SignalPriority.REQUIRED else "🟡"
            priority_text = "必读" if rec.priority == SignalPriority.REQUIRED else "可选"

            lines.append(f"""
  <div class='signal-item' style='margin:8px 0;padding:8px;border-left:3px solid var(--accent);background:var(--bg2)'>
    <div style='display:flex;align-items:center;gap:8px;margin-bottom:4px'>
      <span class='sig-name' style='font-family:var(--mono);font-weight:600'>{rec.signal_name}</span>
      <span class='priority-badge' style='font-size:11px;padding:2px 6px;border-radius:4px;background:var(--bg3)'>{priority_badge} {priority_text}</span>
    </div>
    <div style='font-size:13px;color:var(--tx)'>{rec.description_zh}</div>
    <div style='font-size:12px;color:var(--txd);margin-top:4px'>
      <span>📋 {rec.reason}</span>
    </div>
    <div style='font-size:11px;color:var(--txd);margin-top:2px;font-family:var(--mono)'>
      读取方式: {rec.read_method}
    </div>
  </div>""")

        lines.append("</div>")
        return "\n".join(lines)

    def _generate_owner_html(
        self, recommendations: List[SignalRecommendation]
    ) -> str:
        """Generate simplified HTML for owner role."""
        lines = ["<div class='signal-rec-list' style='font-size:14px'>"]
        lines.append("<p style='margin-bottom:8px'>建议技术人员读取以下信号以辅助诊断：</p>")

        # Group by priority
        required = [r for r in recommendations if r.priority == SignalPriority.REQUIRED]
        optional = [r for r in recommendations if r.priority == SignalPriority.OPTIONAL]

        if required:
            lines.append("<div style='margin:8px 0'>")
            lines.append("<strong>🔴 必要信号：</strong>")
            for rec in required:
                lines.append(f"<div style='margin:4px 0 4px 12px'>• {rec.description_zh}</div>")
            lines.append("</div>")

        if optional:
            lines.append("<div style='margin:8px 0'>")
            lines.append("<strong>🟡 辅助信号：</strong>")
            for rec in optional:
                lines.append(f"<div style='margin:4px 0 4px 12px'>• {rec.description_zh}</div>")
            lines.append("</div>")

        lines.append("</div>")
        return "\n".join(lines)

    def _generate_html_output(
        self,
        recommendations: List[SignalRecommendation],
        scenario: str,
        role: Role,
    ) -> str:
        """Generate HTML output for context.output_html."""
        if not recommendations:
            return ""

        lines = [
            "<div class='signal-section' style='margin-top:16px'>",
            "<h4 style='margin:0 0 12px 0;color:var(--accent)'>📊 信号读取建议</h4>",
        ]

        if role == Role.TECHNICIAN:
            # Detailed table for technicians
            lines.append("<table style='width:100%;border-collapse:collapse;font-size:13px'>")
            lines.append("<thead>")
            lines.append("<tr style='background:var(--bg2)'>")
            lines.append("<th style='text-align:left;padding:8px'>信号名称</th>")
            lines.append("<th style='text-align:left;padding:8px'>描述</th>")
            lines.append("<th style='text-align:left;padding:8px'>读取原因</th>")
            lines.append("<th style='text-align:center;padding:8px'>优先级</th>")
            lines.append("<th style='text-align:left;padding:8px'>读取方式</th>")
            lines.append("</tr>")
            lines.append("</thead>")
            lines.append("<tbody>")

            for rec in recommendations:
                priority_badge = "🔴" if rec.priority == SignalPriority.REQUIRED else "🟡"
                priority_text = "必读" if rec.priority == SignalPriority.REQUIRED else "可选"

                lines.append("<tr style='border-bottom:1px solid var(--bg3)'>")
                lines.append(f"<td style='padding:8px;font-family:var(--mono)'>{rec.signal_name}</td>")
                lines.append(f"<td style='padding:8px'>{rec.description_zh}</td>")
                lines.append(f"<td style='padding:8px;color:var(--txd)'>{rec.reason}</td>")
                lines.append(f"<td style='padding:8px;text-align:center'>{priority_badge} {priority_text}</td>")
                lines.append(f"<td style='padding:8px;font-size:12px;color:var(--txd)'>{rec.read_method}</td>")
                lines.append("</tr>")

            lines.append("</tbody>")
            lines.append("</table>")
        else:
            # Simplified list for owners
            lines.append("<div style='background:var(--bg2);padding:12px;border-radius:8px'>")
            lines.append("<p style='margin:0 0 8px 0;font-size:14px'>建议由技术人员读取以下信号进行诊断：</p>")

            for rec in recommendations:
                priority_badge = "🔴" if rec.priority == SignalPriority.REQUIRED else "🟡"
                lines.append(f"<div style='margin:6px 0'>")
                lines.append(f"{priority_badge} {rec.description_zh}")
                lines.append("</div>")

            lines.append("</div>")

        lines.append("</div>")
        return "\n".join(lines)
