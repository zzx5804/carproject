"""
OntologyFetcher Agent - Fetches relevant ontology information.
"""

from typing import Dict, Any
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, AgentState


class OntologyFetcherAgent(BaseAgent):
    """
    Ontology Fetcher Agent.
    
    Responsibilities:
    - Fetch relevant classes from ontology
    - Fetch relevant properties/signals
    - Fetch relevant rules
    - Generate ontology summary HTML
    """
    
    def __init__(self, agent_id: AgentID = AgentID.ONT):
        super().__init__(agent_id)
        self._ontology_parser = None
    
    def set_ontology_parser(self, parser):
        """Set the ontology parser instance."""
        self._ontology_parser = parser
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Fetch ontology information based on context."""
        logger.info("OntologyFetcher processing...")
        
        await self.update_status(AgentState.RUNNING, 0)
        
        if not self._ontology_parser:
            logger.warning("No ontology parser set, using default response")
            return context
        
        # Fetch power mode info
        power_modes = self._ontology_parser.get_power_mode_info()
        await self.delay(200)
        await self.update_status(AgentState.RUNNING, 30)
        
        # Fetch key types
        key_types = self._ontology_parser.get_key_types()
        await self.delay(200)
        await self.update_status(AgentState.RUNNING, 60)
        
        # Fetch ECU info
        ecus = self._ontology_parser.get_ecu_info()
        await self.delay(200)
        await self.update_status(AgentState.RUNNING, 80)
        
        # Generate HTML summary based on signals
        html = self._generate_ontology_summary(context, power_modes, key_types, ecus)
        
        # Send to frontend
        await self.send({
            "type": "onto_summary",
            "html": html
        })
        
        # Update context
        context.ontology_classes = {
            "power_modes": power_modes,
            "key_types": key_types,
            "ecus": ecus
        }
        
        # Notify
        await self.send_msg_bus("rule", [
            {"k": "结果", "v": "SSTS三层信号读取完成", "cls": "g"},
            {"k": "L3状态", "v": "故障信号已标记", "cls": "e"}
        ])
        
        await self.animate_wire("rule")
        
        await self.update_status(AgentState.DONE, 100)
        
        return context
    
    def _generate_ontology_summary(
        self,
        context: DiagnosisContext,
        power_modes: Dict,
        key_types: Dict,
        ecus: Dict
    ) -> str:
        """Generate HTML summary based on context and signals."""
        
        # Get current signal values
        sv_pm = context.signals.get("sv-pm", "0:Off")
        sv_kv = context.signals.get("sv-kv", "INVALID")
        sv_ble = context.signals.get("sv-ble", "0")
        sv_kl = context.signals.get("sv-kl", "off")
        
        # Determine color based on status
        pm_color = "var(--red)" if "Off" in sv_pm else "var(--ylw)" if "Remote" in sv_pm else "var(--grn)"
        kv_color = "var(--grn)" if "VALID" in sv_kv else "var(--red)"
        
        html = f'''<div style="font-family:var(--mono);font-size:11px;line-height:2;color:var(--tx)">
  <div style="color:var(--txd);font-size:10px;margin-bottom:4px">// CEA Vehicle Ontology v1.0 · C1:Objects · C5:Rules · C7:Events</div>
  <div style="color:var(--acc);margin-bottom:6px">// L1 整车层 — LDCU_PowerMode (VEEA-SysR-2116)</div>
  <div><span style="color:var(--txd)">LDCU_PowerMode:</span> <span style="color:{pm_color}">{sv_pm}</span> &nbsp;<span style="color:var(--txd)">KL15/KLS/KLX:</span> <span style="color:var(--txd)">{sv_kl}</span></div>'''
        
        # Add key-related info if relevant
        if "ble" in str(context.parsed_symptoms).lower() or "key" in str(context.parsed_symptoms).lower():
            html += f'''
  <div style="color:var(--ylw);margin-top:6px">// L2 子系统层 — KeySearch & Flag</div>
  <div><span style="color:var(--txd)">KeyValidSt:</span> <span style="color:{kv_color}">{sv_kv}</span> &nbsp;<span style="color:var(--txd)">Flag_BLE:</span> <span style="color:var(--ylw)">{sv_ble}</span></div>
  <div><span style="color:var(--txd)">KeySearchingSt:</span> <span style="color:var(--ylw)">Timeout Research</span></div>'''
        
        # Add L3 ECU info
        html += f'''
  <div style="color:var(--red);margin-top:6px">// L3 ECU层 — TBOX BLE认证</div>
  <div><span style="color:var(--txd)">TBOX BLE_ErrorCode:</span> <span style="color:var(--red)">0x05 AUTH_ERROR</span></div>
  <div><span style="color:var(--txd)">keyPSValue:</span> <span style="color:var(--red)">Invalid</span></div>
</div>'''
        
        return html
