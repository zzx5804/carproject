"""
DTCAgent - DTC-based diagnosis agent for vehicle power system.

Parses DTC codes, generates hypotheses, and enriches diagnosis context
with DTC-specific information.
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from agents.base import BaseAgent
from models import (
    DiagnosisContext,
    AgentID,
    AgentState,
    ReasoningStep,
    Hypothesis,
    DTCParsedInfo,
    DTCSeverity,
)
from dtc_parser import get_dtc_parser, DTCParser
from diagnosis_knowledge import DTC_OUTPUT_TEMPLATES, DTC_TO_SCENARIO_MAP


class DTCAgent(BaseAgent):
    """
    DTC (Diagnostic Trouble Code) Analysis Agent.
    
    Responsibilities:
    - Parse DTC codes from input
    - Generate DTC-specific hypotheses
    - Map DTCs to diagnosis scenarios
    - Provide role-adapted output for DTC alerts
    - Enrich context with DTC-related signals
    
    Workflow:
    1. Parse each DTC code using dtc_parser
    2. Generate reasoning steps for DTC analysis
    3. Collect hypotheses from DTC knowledge base
    4. Map DTCs to relevant scenarios
    5. Send results to orchestrator
    """
    
    def __init__(self, agent_id: AgentID = AgentID.DTC):
        super().__init__(agent_id)
        self._parser: Optional[DTCParser] = None
        self._parsed_dtcs: List[DTCParsedInfo] = []
    
    @property
    def parser(self) -> DTCParser:
        """Lazy load DTC parser."""
        if self._parser is None:
            self._parser = get_dtc_parser()
        return self._parser
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Process DTC codes and generate diagnosis information."""
        dtc_codes = context.dtc_codes
        
        if not dtc_codes:
            logger.info("No DTC codes provided, skipping DTC agent")
            await self.send_msg_bus("orch", [
                {"k": "状态", "v": "无DTC输入"},
            ])
            return context
        
        logger.info(f"DTCAgent processing {len(dtc_codes)} DTC codes: {dtc_codes}")
        
        # Step 1: Parse all DTC codes
        await self.update_status(AgentState.RUNNING, 10)
        self._parsed_dtcs = self.parser.parse_multiple(dtc_codes)
        await self.delay(300)
        
        # Step 2: Generate reasoning steps for each DTC
        await self.update_status(AgentState.RUNNING, 20)
        reasoning_steps = self._generate_reasoning_steps(self._parsed_dtcs)
        
        for i, step in enumerate(reasoning_steps):
            await self.delay(400)
            await self.send({
                "type": "reasoning_step",
                "step": {
                    "title": step.title,
                    "body": step.body
                }
            })
            progress = 20 + int((i + 1) / len(reasoning_steps) * 40)
            await self.update_status(AgentState.RUNNING, progress)
        
        # Step 3: Collect all hypotheses
        await self.update_status(AgentState.RUNNING, 60)
        all_hypotheses = self._collect_hypotheses(self._parsed_dtcs)
        await self.delay(200)
        
        # Send hypotheses to frontend
        for hypo in all_hypotheses[:5]:  # Limit to top 5
            await self.send({
                "type": "hypothesis",
                "hypo": {
                    "name": hypo.name,
                    "pct": hypo.pct,
                    "cls": hypo.cls
                }
            })
            await self.delay(100)
        
        # Step 4: Determine related scenarios
        await self.update_status(AgentState.RUNNING, 75)
        related_scenarios = self._get_related_scenarios(dtc_codes)
        await self.delay(200)
        
        # Step 5: Get related signals
        related_signals = self.parser.get_related_signals(dtc_codes)
        related_ecus = self.parser.get_related_ecus(dtc_codes)
        
        # Step 6: Determine max severity
        max_severity = self.parser.get_max_severity(dtc_codes)
        is_critical = self.parser.has_critical_dtc(dtc_codes)
        
        # Update context
        context.parsed_dtc_info = self._parsed_dtcs
        context.hypotheses.extend(all_hypotheses)
        
        # Add DTC-related signals to relevant_signals
        for signal in related_signals:
            if signal not in context.relevant_signals:
                context.relevant_signals[signal] = "DTC_RELATED"
        
        # Notify orchestrator
        await self.send_msg_bus("orch", [
            {"k": "状态", "v": "DTC解析完成", "cls": "g"},
            {"k": "DTC数量", "v": str(len(self._parsed_dtcs))},
            {"k": "最高严重度", "v": max_severity.value, "cls": "e" if is_critical else "w"},
            {"k": "相关场景", "v": ", ".join(related_scenarios) if related_scenarios else "无"},
            {"k": "相关ECU", "v": ", ".join(related_ecus[:5]) if related_ecus else "无"},
        ])
        
        # If there are critical DTCs, send alert
        if is_critical:
            await self.send({
                "type": "reasoning_step",
                "step": {
                    "title": "⚠️ 检测到严重故障码",
                    "body": f'<span style="color:var(--red);font-weight:600">'
                            f'发现 {sum(1 for d in self._parsed_dtcs if d.severity == DTCSeverity.CRITICAL)} 个严重级别故障码，需要立即检修！'
                            f'</span>'
                }
            })
        
        await self.animate_wire("sym")  # Pass to symptom parser or orchestrator
        
        return context
    
    def _generate_reasoning_steps(self, dtcs: List[DTCParsedInfo]) -> List[ReasoningStep]:
        """Generate reasoning steps for DTC analysis."""
        steps = []
        
        if not dtcs:
            return steps
        
        # Step 1: DTC Summary
        dtc_summary = ", ".join([d.code for d in dtcs[:5]])
        if len(dtcs) > 5:
            dtc_summary += f" (+{len(dtcs) - 5} more)"
        
        steps.append(ReasoningStep(
            title="[D1] DTC故障码读取",
            body=f'<div class="sl">'
                 f'<div class="sr"><span class="sk">检测到故障码:</span><span class="sv">{dtc_summary}</span></div>'
                 f'<div class="sr"><span class="sk">数量:</span><span class="sv">{len(dtcs)} 个</span></div>'
                 f'</div>'
        ))
        
        # Step 2: Severity Analysis
        severity_counts = {s: 0 for s in DTCSeverity}
        for dtc in dtcs:
            severity_counts[dtc.severity] += 1
        
        severity_text = []
        for severity, count in severity_counts.items():
            if count > 0:
                cls = "e" if severity == DTCSeverity.CRITICAL else ("w" if severity == DTCSeverity.HIGH else "")
                severity_text.append(f'<span class="sv {cls}">{severity.value}: {count}</span>')
        
        steps.append(ReasoningStep(
            title="[D2] 故障严重度分析",
            body=f'<div class="sl">'
                 f'<div class="sr"><span class="sk">严重度分布:</span>{" | ".join(severity_text)}</div>'
                 f'</div>'
        ))
        
        # Step 3-5: Detail for each DTC (up to 3)
        for i, dtc in enumerate(dtcs[:3]):
            severity_cls = "e" if dtc.severity == DTCSeverity.CRITICAL else ("w" if dtc.severity == DTCSeverity.HIGH else "")
            
            causes_text = ""
            if dtc.possible_causes:
                causes_text = '<div class="sr"><span class="sk">可能原因:</span>'
                causes_text += '<span class="sv">' + ", ".join(dtc.possible_causes[:2]) + '</span></div>'
            
            steps.append(ReasoningStep(
                title=f"[D{3+i}] {dtc.code} — {dtc.category.value.upper()}",
                body=f'<div class="sl">'
                     f'<div class="sr"><span class="sk">故障码:</span><span class="sv {severity_cls}">{dtc.code}</span></div>'
                     f'<div class="sr"><span class="sk">描述:</span><span class="sv">{dtc.description_zh}</span></div>'
                     f'<div class="sr"><span class="sk">严重度:</span><span class="sv {severity_cls}">{dtc.severity.value}</span></div>'
                     f'{causes_text}'
                     f'</div>'
            ))
        
        # Final step: Conclusion
        critical_count = severity_counts[DTCSeverity.CRITICAL]
        high_count = severity_counts[DTCSeverity.HIGH]
        
        if critical_count > 0:
            conclusion = f"发现 {critical_count} 个严重故障码，需要立即检修！"
            conclusion_cls = "var(--red)"
        elif high_count > 0:
            conclusion = f"发现 {high_count} 个高优先级故障码，建议尽快检修。"
            conclusion_cls = "var(--acc)"
        else:
            conclusion = "故障码已记录，建议预约检修。"
            conclusion_cls = "var(--tx)"
        
        steps.append(ReasoningStep(
            title="[D6] 诊断结论",
            body=f'<span style="color:{conclusion_cls};font-weight:600">{conclusion}</span>'
        ))
        
        return steps
    
    def _collect_hypotheses(self, dtcs: List[DTCParsedInfo]) -> List[Hypothesis]:
        """Collect all hypotheses from parsed DTCs."""
        all_hypotheses = []
        seen_names = set()
        
        for dtc in dtcs:
            for hypo in dtc.hypothesis:
                if hypo.name not in seen_names:
                    all_hypotheses.append(hypo)
                    seen_names.add(hypo.name)
        
        # Sort by percentage (descending)
        all_hypotheses.sort(key=lambda h: h.pct, reverse=True)
        
        return all_hypotheses
    
    def _get_related_scenarios(self, dtc_codes: List[str]) -> List[str]:
        """Get all related scenarios from DTC codes."""
        scenarios = set()
        
        for code in dtc_codes:
            code_upper = code.upper()
            if code_upper in DTC_TO_SCENARIO_MAP:
                scenarios.update(DTC_TO_SCENARIO_MAP[code_upper])
        
        return list(scenarios)
    
    def get_dtc_output(self, role: str, dtc_codes: List[str]) -> Optional[str]:
        """
        Get role-adapted output HTML for primary DTC.
        
        Args:
            role: User role (owner/technician/customer_service)
            dtc_codes: List of DTC codes
            
        Returns:
            HTML output string or None
        """
        if not dtc_codes:
            return None
        
        # Use the most severe DTC for output
        primary_dtc = self.parser.normalize_dtc(dtc_codes[0])
        
        # Check if we have output template for this DTC
        if primary_dtc in DTC_OUTPUT_TEMPLATES:
            templates = DTC_OUTPUT_TEMPLATES[primary_dtc]
            return templates.get(role, templates.get("owner"))
        
        # Generate default output
        dtcs = self.parser.parse_multiple(dtc_codes)
        if not dtcs:
            return None
        
        primary = dtcs[0]
        return self._generate_default_output(primary, role, dtcs)
    
    def _generate_default_output(
        self,
        primary_dtc: DTCParsedInfo,
        role: str,
        all_dtcs: List[DTCParsedInfo]
    ) -> str:
        """Generate default output for DTC without template."""
        severity = primary_dtc.severity.value
        code = primary_dtc.code
        desc_zh = primary_dtc.description_zh
        
        if role == "owner":
            return f"""<div class="conc">⚠️ 检测到故障码 {code}</div>
<p style="margin-top:8px">{desc_zh}（严重度：{severity}）</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>如故障灯持续亮起，请尽快到店检测</div>
  <div class="ai"><div class="an">2</div>如有其他异常症状，请联系：<span class="hi">400-XXX-XXXX</span></div>
</div>"""
        
        elif role == "technician":
            ecu_list = ", ".join(primary_dtc.related_ecu[:3]) if primary_dtc.related_ecu else "N/A"
            signals_list = ", ".join(primary_dtc.related_signals[:3]) if primary_dtc.related_signals else "N/A"
            return f"""<div class="conc">【诊断结论】{code} - {desc_zh} ({severity.upper()})</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: {code} | Category: {primary_dtc.category.value} | Related ECU: {ecu_list}</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>OBD读取DTC快照和冻结帧数据</div>
  <div class="ai"><div class="an">P2</div>检查相关ECU供电和接地</div>
  <div class="ai"><div class="an">P3</div>检查CAN通信链路</div>
</div>"""
        
        else:  # customer_service
            return f"""<div class="conc">【系统诊断】检测到故障码 {code}</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆检测到故障码 {code}，建议到店进行专业检测。"</p>"""
