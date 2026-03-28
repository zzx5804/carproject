"""
Fallback logic for LLM diagnosis.

Provides rule-based diagnosis when LLM is unavailable.
Uses centralized knowledge from diagnosis_knowledge module.

Supports both symptom-based and DTC-based diagnosis.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from llm.schemas import (
    DiagnosisRequest,
    DiagnosisResponse,
    DiagnosticHypothesis,
    ReasoningStep,
    ConfidenceFactor,
    Role,
)

# Import centralized knowledge (was duplicated before refactoring)
from diagnosis_knowledge import (
    RULES,
    HYPOTHESIS_TEMPLATES,
    OUTPUT_TEMPLATES,
    SCENARIO_RULES_MAP,
    # DTC Knowledge
    DTC_KNOWLEDGE_BASE,
    DTC_HYPOTHESIS_TEMPLATES,
    DTC_OUTPUT_TEMPLATES,
    DTC_TO_SCENARIO_MAP,
)
from scenario_detector import get_scenario_detector
from dtc_parser import get_dtc_parser


# =============================================================================
# Fallback Handler
# =============================================================================

class FallbackHandler:
    """
    Handles diagnosis when LLM is unavailable.
    
    Uses centralized knowledge from diagnosis_knowledge module.
    Supports both symptom-based and DTC-based diagnosis.
    """
    
    def __init__(self):
        self._scenario_detector = get_scenario_detector()
        self._dtc_parser = get_dtc_parser()
    
    def detect_scenario(self, symptom: str) -> str:
        """Detect diagnosis scenario from symptom text."""
        return self._scenario_detector.detect(symptom)
    
    def detect_scenario_from_dtc(self, dtc_codes: List[str]) -> List[str]:
        """Detect diagnosis scenarios from DTC codes."""
        return self._scenario_detector.detect_from_dtc(dtc_codes)
    
    def get_applicable_rules(self, scenario: str) -> List[Dict]:
        """Get rules for scenario."""
        rule_ids = SCENARIO_RULES_MAP.get(scenario, ["T_1_2"])
        return [RULES[rid] for rid in rule_ids if rid in RULES]
    
    def get_hypotheses(self, scenario: str) -> List[Dict]:
        """Get hypotheses for scenario."""
        return HYPOTHESIS_TEMPLATES.get(scenario, [
            {"name": "待进一步诊断", "pct": 50, "cls": "p"},
            {"name": "需现场检测", "pct": 50, "cls": "s"}
        ])
    
    def get_output(self, scenario: str, role: str) -> str:
        """Get output template for scenario and role."""
        templates = OUTPUT_TEMPLATES.get(scenario, {})
        
        if role in templates:
            return templates[role]
        if "owner" in templates:
            return templates["owner"]
        
        return f"""<div class="conc">诊断完成</div>
<p style="margin-top:8px">检测到故障场景: {scenario}</p>
<p>建议联系售后服务进行进一步诊断。</p>"""
    
    def get_dtc_output(self, dtc_codes: List[str], role: str) -> str:
        """Get output template for DTC codes."""
        if not dtc_codes:
            return "无DTC故障码"
        
        primary_dtc = dtc_codes[0].upper()
        
        # Check if we have output template for this DTC
        if primary_dtc in DTC_OUTPUT_TEMPLATES:
            templates = DTC_OUTPUT_TEMPLATES[primary_dtc]
            if role in templates:
                return templates[role]
            if "owner" in templates:
                return templates["owner"]
        
        # Generate default DTC output
        dtc_info = self._dtc_parser.parse(primary_dtc)
        if dtc_info:
            return self._generate_default_dtc_output(dtc_info, role)
        
        return f"""<div class="conc">⚠️ 检测到故障码 {primary_dtc}</div>
<p style="margin-top:8px">建议到店进行专业检测。</p>"""
    
    def _generate_default_dtc_output(self, dtc_info, role: str) -> str:
        """Generate default output for DTC without template."""
        code = dtc_info.code
        desc_zh = dtc_info.description_zh
        severity = dtc_info.severity.value
        
        if role == "owner":
            return f"""<div class="conc">⚠️ 检测到故障码 {code}</div>
<p style="margin-top:8px">{desc_zh}（严重度：{severity}）</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>如故障灯持续亮起，请尽快到店检测</div>
  <div class="ai"><div class="an">2</div>如有其他异常症状，请联系：<span class="hi">400-XXX-XXXX</span></div>
</div>"""
        elif role == "technician":
            ecu_list = ", ".join(dtc_info.related_ecu[:3]) if dtc_info.related_ecu else "N/A"
            return f"""<div class="conc">【诊断结论】{code} - {desc_zh} ({severity.upper()})</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: {code} | Category: {dtc_info.category.value} | Related ECU: {ecu_list}</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>OBD读取DTC快照和冻结帧数据</div>
  <div class="ai"><div class="an">P2</div>检查相关ECU供电和接地</div>
</div>"""
        else:
            return f"""<div class="conc">【系统诊断】检测到故障码 {code}</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆检测到故障码 {code}，建议到店进行专业检测。"</p>"""
    
    def get_dtc_hypotheses(self, dtc_codes: List[str]) -> List[Dict]:
        """Get hypotheses from DTC codes."""
        hypotheses = []
        seen = set()
        
        for code in dtc_codes:
            code_upper = code.upper()
            if code_upper in DTC_HYPOTHESIS_TEMPLATES:
                for h in DTC_HYPOTHESIS_TEMPLATES[code_upper]:
                    if h["name"] not in seen:
                        hypotheses.append(h)
                        seen.add(h["name"])
        
        # If no specific DTC hypotheses, generate from parser
        if not hypotheses:
            for code in dtc_codes[:3]:  # Limit to first 3
                dtc_info = self._dtc_parser.parse(code)
                if dtc_info:
                    for h in dtc_info.hypothesis:
                        if h.name not in seen:
                            hypotheses.append({"name": h.name, "pct": h.pct, "cls": h.cls})
                            seen.add(h.name)
        
        return hypotheses if hypotheses else [
            {"name": "DTC相关故障", "pct": 70, "cls": "p"},
            {"name": "需进一步诊断", "pct": 30, "cls": "s"}
        ]
    
    async def diagnose(self, request: DiagnosisRequest) -> DiagnosisResponse:
        """
        Perform fallback diagnosis.
        
        Supports both symptom-based and DTC-based diagnosis.
        If DTC codes are provided, prioritizes DTC-based diagnosis.
        
        Args:
            request: Diagnosis request (may include dtc_codes)
            
        Returns:
            DiagnosisResponse with rule-based diagnosis
        """
        import time
        
        # Check if DTC codes are provided
        if hasattr(request, 'dtc_codes') and request.dtc_codes:
            return await self._diagnose_from_dtc(request)
        
        # Fall back to symptom-based diagnosis
        scenario = self.detect_scenario(request.symptom)
        matched_rules = self.get_applicable_rules(scenario)
        hypotheses = self.get_hypotheses(scenario)
        
        # Build reasoning steps
        reasoning_steps = self._build_reasoning_steps(
            request.symptom, scenario, request.signals
        )
        
        # Build primary hypothesis
        primary = None
        if hypotheses:
            h = hypotheses[0]
            primary = DiagnosticHypothesis(
                hypothesis_id="hypo_001",
                rank=1,
                root_cause=h["name"],
                description=f"基于规则推理的故障假设",
                confidence=h["pct"] / 100.0,
                affected_components=self._get_components(scenario),
                verification_steps=self._get_verification_steps(scenario),
                priority="high" if h["pct"] > 50 else "medium"
            )
        
        # Build secondary hypotheses
        secondary = []
        for i, h in enumerate(hypotheses[1:], 2):
            secondary.append(DiagnosticHypothesis(
                hypothesis_id=f"hypo_{i:03d}",
                rank=i,
                root_cause=h["name"],
                description=f"备选假设",
                confidence=h["pct"] / 100.0,
                priority="medium" if h["pct"] > 20 else "low"
            ))
        
        # Calculate confidence
        confidence_factors = self._calculate_confidence(
            matched_rules, hypotheses, request.signals
        )
        final_confidence = sum(f.value * f.weight for f in confidence_factors)
        
        # Get output text
        role_str = request.role.value if hasattr(request.role, 'value') else str(request.role)
        output_html = self.get_output(scenario, role_str)
        
        return DiagnosisResponse(
            diagnosis_id=f"diag_fallback_{int(time.time()*1000)}",
            summary=self._get_summary(scenario),
            reasoning_steps=reasoning_steps,
            primary_hypothesis=primary,
            secondary_hypotheses=secondary,
            final_confidence=final_confidence,
            confidence_factors=confidence_factors,
            output_for_owner=output_html if role_str == "owner" else None,
            output_for_technician=output_html if role_str == "technician" else None,
            output_for_customer_service=output_html if role_str == "customer_service" else None,
            model_used="fallback",
            escalation_hint=self._get_escalation(scenario, role_str)
        )
    
    async def _diagnose_from_dtc(self, request: DiagnosisRequest) -> DiagnosisResponse:
        """
        Perform DTC-based fallback diagnosis.
        
        Args:
            request: Diagnosis request with dtc_codes
            
        Returns:
            DiagnosisResponse with DTC-based diagnosis
        """
        import time
        
        dtc_codes = request.dtc_codes
        role_str = request.role.value if hasattr(request.role, 'value') else str(request.role)
        
        # Parse DTC codes
        parsed_dtcs = self._dtc_parser.parse_multiple(dtc_codes)
        
        # Get related scenarios
        related_scenarios = self.detect_scenario_from_dtc(dtc_codes)
        
        # Get hypotheses from DTCs
        hypotheses = self.get_dtc_hypotheses(dtc_codes)
        
        # Build reasoning steps
        reasoning_steps = self._build_dtc_reasoning_steps(parsed_dtcs)
        
        # Get severity
        max_severity = self._dtc_parser.get_max_severity(dtc_codes)
        is_critical = max_severity.value == "critical"
        
        # Build primary hypothesis
        primary = None
        if hypotheses:
            h = hypotheses[0]
            primary = DiagnosticHypothesis(
                hypothesis_id="hypo_dtc_001",
                rank=1,
                root_cause=h["name"],
                description=f"基于DTC故障码的故障假设",
                confidence=h["pct"] / 100.0,
                affected_components=list(set(
                    comp for dtc in parsed_dtcs for comp in dtc.related_ecu
                ))[:5],
                verification_steps=[
                    f"OBD读取{code}快照数据" for code in dtc_codes[:3]
                ],
                priority="critical" if is_critical else ("high" if h["pct"] > 50 else "medium")
            )
        
        # Build secondary hypotheses
        secondary = []
        for i, h in enumerate(hypotheses[1:4], 2):  # Limit to 3 secondary
            secondary.append(DiagnosticHypothesis(
                hypothesis_id=f"hypo_dtc_{i:03d}",
                rank=i,
                root_cause=h["name"],
                description=f"DTC相关备选假设",
                confidence=h["pct"] / 100.0,
                priority="medium" if h["pct"] > 20 else "low"
            ))
        
        # Calculate confidence
        confidence_factors = self._calculate_dtc_confidence(parsed_dtcs, hypotheses)
        final_confidence = sum(f.value * f.weight for f in confidence_factors)
        
        # Get output
        output_html = self.get_dtc_output(dtc_codes, role_str)
        
        # Build summary
        dtc_summary = ", ".join(dtc_codes[:3])
        if len(dtc_codes) > 3:
            dtc_summary += f" (+{len(dtc_codes) - 3})"
        summary = f"检测到DTC故障码: {dtc_summary}"
        
        return DiagnosisResponse(
            diagnosis_id=f"diag_dtc_fallback_{int(time.time()*1000)}",
            summary=summary,
            reasoning_steps=reasoning_steps,
            primary_hypothesis=primary,
            secondary_hypotheses=secondary,
            final_confidence=final_confidence,
            confidence_factors=confidence_factors,
            output_for_owner=output_html if role_str == "owner" else None,
            output_for_technician=output_html if role_str == "technician" else None,
            output_for_customer_service=output_html if role_str == "customer_service" else None,
            model_used="fallback_dtc",
            escalation_hint="立即到店检修" if is_critical else None
        )
    
    def _build_dtc_reasoning_steps(
        self,
        parsed_dtcs: List[Any]
    ) -> List[ReasoningStep]:
        """Build reasoning steps for DTC diagnosis."""
        from models import DTCSeverity
        
        steps = []
        
        # Step 1: DTC Summary
        dtc_codes = [d.code for d in parsed_dtcs]
        dtc_summary = ", ".join(dtc_codes[:5])
        if len(dtc_codes) > 5:
            dtc_summary += f" (+{len(dtc_codes) - 5})"
        
        steps.append(ReasoningStep(
            step_number=1,
            title="DTC故障码读取",
            body=f"检测到故障码: {dtc_summary}\n数量: {len(parsed_dtcs)} 个",
            confidence=0.95
        ))
        
        # Step 2: Severity Analysis
        severity_counts = {s: 0 for s in DTCSeverity}
        for dtc in parsed_dtcs:
            severity_counts[dtc.severity] += 1
        
        severity_text = []
        for severity, count in severity_counts.items():
            if count > 0:
                severity_text.append(f"{severity.value}: {count}")
        
        steps.append(ReasoningStep(
            step_number=2,
            title="故障严重度分析",
            body=f"严重度分布: {' | '.join(severity_text)}",
            confidence=0.90
        ))
        
        # Step 3: Primary DTC details
        if parsed_dtcs:
            primary_dtc = parsed_dtcs[0]
            causes_text = "\n".join([f"- {c}" for c in primary_dtc.possible_causes[:3]])
            
            steps.append(ReasoningStep(
                step_number=3,
                title=f"主故障码 {primary_dtc.code} 分析",
                body=f"描述: {primary_dtc.description_zh}\n"
                     f"类别: {primary_dtc.category.value}\n"
                     f"严重度: {primary_dtc.severity.value}\n"
                     f"可能原因:\n{causes_text if causes_text else '- 待确认'}",
                confidence=0.88
            ))
        
        # Step 4: Related ECUs
        all_ecus = set()
        for dtc in parsed_dtcs:
            all_ecus.update(dtc.related_ecu)
        
        if all_ecus:
            steps.append(ReasoningStep(
                step_number=4,
                title="相关ECU定位",
                body=f"相关控制单元: {', '.join(list(all_ecus)[:5])}",
                confidence=0.85
            ))
        
        return steps
    
    def _calculate_dtc_confidence(
        self,
        parsed_dtcs: List[Any],
        hypotheses: List[Dict]
    ) -> List[ConfidenceFactor]:
        """Calculate confidence factors for DTC diagnosis."""
        from models import DTCSeverity
        
        # Severity-based confidence
        max_severity = self._dtc_parser.get_max_severity([d.code for d in parsed_dtcs])
        severity_confidence = {
            DTCSeverity.CRITICAL: 0.95,
            DTCSeverity.HIGH: 0.85,
            DTCSeverity.MEDIUM: 0.70,
            DTCSeverity.LOW: 0.50,
        }.get(max_severity, 0.70)
        
        return [
            ConfidenceFactor(
                label="DTC确定性",
                value=0.95,
                weight=0.35,
                explanation="故障码明确指示故障类型"
            ),
            ConfidenceFactor(
                label="严重度置信",
                value=severity_confidence,
                weight=0.25,
                explanation=f"基于最高严重度 {max_severity.value}"
            ),
            ConfidenceFactor(
                label="知识库匹配",
                value=0.90 if len(parsed_dtcs) > 0 and parsed_dtcs[0].possible_causes else 0.60,
                weight=0.25,
                explanation="DTC知识库匹配度"
            ),
            ConfidenceFactor(
                label="假设一致性",
                value=0.85,
                weight=0.15,
                explanation="假设与DTC一致性"
            )
        ]
    
    def _build_reasoning_steps(
        self,
        symptom: str,
        scenario: str,
        signals: List[Any]
    ) -> List[ReasoningStep]:
        """Build reasoning steps for diagnosis."""
        signals_dict = {s.key: s.value for s in signals} if signals else {}
        
        steps = [
            ReasoningStep(
                step_number=1,
                title="症状解析",
                body=f"用户症状: {symptom[:100]}\n场景分类: {scenario}",
                confidence=0.90
            ),
            ReasoningStep(
                step_number=2,
                title="信号分析",
                body=f"当前信号状态:\n" + "\n".join([
                    f"- {k}: {v}" for k, v in list(signals_dict.items())[:5]
                ]) if signals_dict else "无信号数据",
                confidence=0.85
            ),
            ReasoningStep(
                step_number=3,
                title="规则匹配",
                body=f"匹配场景: {scenario}\n适用规则: {len(self.get_applicable_rules(scenario))}条",
                confidence=0.88
            )
        ]
        
        return steps
    
    def _get_components(self, scenario: str) -> List[str]:
        """Get affected components for scenario."""
        components_map = {
            "ble_auth": ["TBOX", "BLE模块", "手机App", "LDCU"],
            "key_timeout": ["手机蓝牙", "TBOX", "天线"],
            "bms_charging": ["BMS", "电池模组", "OBC"],
            "auto_poweroff": ["LDCU", "EEPROM"],
        }
        return components_map.get(scenario, ["待确认"])
    
    def _get_verification_steps(self, scenario: str) -> List[str]:
        """Get verification steps for scenario."""
        steps_map = {
            "ble_auth": [
                "检查手机蓝牙是否开启",
                "确认手机App蓝牙权限",
                "OBD读取TBOX BLE错误码",
                "尝试重新配对蓝牙钥匙"
            ],
            "key_timeout": [
                "确认手机蓝牙已开启",
                "靠近车辆(1米内)重试",
                "检查TBOX BLE搜索请求"
            ],
            "bms_charging": [
                "断开充电枪冷却20分钟",
                "检查电池温度传感器",
                "OBD读取BMS所有cell温度"
            ]
        }
        return steps_map.get(scenario, ["联系售后服务"])
    
    def _calculate_confidence(
        self,
        rules: List[Dict],
        hypotheses: List[Dict],
        signals: List[Any]
    ) -> List[ConfidenceFactor]:
        """Calculate confidence factors."""
        return [
            ConfidenceFactor(
                label="症状匹配度",
                value=0.90,
                weight=0.30,
                explanation="基于模式匹配"
            ),
            ConfidenceFactor(
                label="规则可信度",
                value=float(rules[0]["conf"]) if rules else 0.90,
                weight=0.35,
                explanation="来自知识库规则"
            ),
            ConfidenceFactor(
                label="数据质量",
                value=0.85 if signals else 0.50,
                weight=0.20,
                explanation="信号数据完整性"
            ),
            ConfidenceFactor(
                label="假设一致性",
                value=0.90,
                weight=0.15,
                explanation="假设与证据一致性"
            )
        ]
    
    def _get_summary(self, scenario: str) -> str:
        """Get diagnosis summary."""
        summaries = {
            "ble_auth": "BLE认证失败导致无法上电",
            "key_timeout": "蓝牙钥匙未检测到",
            "bms_charging": "电池热保护触发，充电中断",
            "auto_poweroff": "1小时自动下电正常触发"
        }
        return summaries.get(scenario, "诊断完成")
    
    def _get_escalation(self, scenario: str, role: str) -> Optional[str]:
        """Get escalation hint."""
        hints = {
            "ble_auth": {
                "customer_service": "升级条件：操作3次仍弹出「钥匙未找到」→ 升级技术支持"
            },
            "bms_charging": {
                "customer_service": "升级条件：冷却后仍无法恢复充电 → 创建服务工单"
            }
        }
        if scenario in hints and role in hints[scenario]:
            return hints[scenario][role]
        return None


# Singleton instance
_fallback_handler: Optional[FallbackHandler] = None


def get_fallback_handler() -> FallbackHandler:
    """Get or create fallback handler instance."""
    global _fallback_handler
    if _fallback_handler is None:
        _fallback_handler = FallbackHandler()
    return _fallback_handler
