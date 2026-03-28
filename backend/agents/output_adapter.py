"""
OutputAdapter Agent - Adapts output based on user role.
"""

from typing import Optional, Dict
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, AgentState
from diagnosis_knowledge import OUTPUT_TEMPLATES, ESCALATION_HINTS
from scenario_detector import get_scenario_detector


class OutputAdapterAgent(BaseAgent):
    """
    Output Adapter Agent.
    
    Responsibilities:
    - Adapt output text based on user role (owner/technician/customer_service)
    - Generate appropriate escalation hints
    - Format final output for frontend display
    """
    
    def __init__(self, agent_id: AgentID = AgentID.OUT):
        super().__init__(agent_id)
        self._scenario_detector = get_scenario_detector()
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Generate role-adapted output."""
        logger.info("OutputAdapter processing...")
        
        await self.update_status(AgentState.RUNNING, 0)
        
        # Determine scenario
        scenario = self._detect_scenario(context)
        role = context.role.value if hasattr(context.role, 'value') else str(context.role)
        
        # Get output template
        output_html = self._get_output(scenario, role, context)
        
        # Get escalation hint
        escalation = self._get_escalation(scenario, role)
        
        # Send output
        await self.delay(400)
        await self.update_status(AgentState.RUNNING, 60)
        
        await self.send({
            "type": "output",
            "html": output_html,
            "escalation": escalation
        })
        
        # Update context
        context.output_html = output_html
        context.escalation_hint = escalation
        
        # Notify
        await self.send_msg_bus("orch", [
            {"k": "结果", "v": "输出生成完成", "cls": "g"},
            {"k": "角色", "v": role}
        ])
        
        await self.update_status(AgentState.DONE, 100)
        
        return context
    
    def _detect_scenario(self, context: DiagnosisContext) -> str:
        """Detect scenario from context using ScenarioDetector."""
        return self._scenario_detector.detect(context.symptom)
    
    def _get_output(self, scenario: str, role: str, context: DiagnosisContext) -> str:
        """Get output for the scenario and role."""
        # Try scenario-specific template for the role
        if scenario in OUTPUT_TEMPLATES and role in OUTPUT_TEMPLATES[scenario]:
            return OUTPUT_TEMPLATES[scenario][role]
        
        # Fallback to owner template
        if scenario in OUTPUT_TEMPLATES and "owner" in OUTPUT_TEMPLATES[scenario]:
            return OUTPUT_TEMPLATES[scenario]["owner"]
        
        # Default output
        confidence = context.final_confidence
        conf_text = "🔴 高置信度 · 可直接建议" if confidence >= 80 else "🟡 中置信度 · 引导排查"
        
        return f"""<div class="conc">诊断完成 - 置信度 {confidence}%</div>
<p style="margin-top:8px">{conf_text}</p>
<p style="margin-top:8px">基于症状「{context.symptom[:30]}...」的分析，建议按以下步骤排查：</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>检查相关信号状态</div>
  <div class="ai"><div class="an">2</div>根据规则匹配结果进行诊断</div>
  <div class="ai"><div class="an">3</div>如需进一步帮助请联系技术支持</div>
</div>"""
    
    def _get_escalation(self, scenario: str, role: str) -> Optional[str]:
        """Get escalation hint for scenario and role."""
        if scenario in ESCALATION_HINTS:
            return ESCALATION_HINTS[scenario].get(role)
        return None
