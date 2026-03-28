"""
SymptomParser Agent - Parses user symptoms and extracts relevant information.
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, AgentState, ReasoningStep
from diagnosis_knowledge import SYMPTOM_PATTERNS, SIGNAL_RELEVANCE
from scenario_detector import get_scenario_detector


class SymptomParserAgent(BaseAgent):
    """
    Symptom Parser Agent.
    
    Responsibilities:
    - Parse user input symptoms
    - Identify relevant vehicle signals
    - Generate reasoning steps
    - Determine scenario type
    """
    
    def __init__(self, agent_id: AgentID = AgentID.SYM):
        super().__init__(agent_id)
        self.detected_scenario: Optional[str] = None
        self._scenario_detector = get_scenario_detector()
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Process symptoms and generate reasoning steps."""
        logger.info(f"SymptomParser processing: {context.symptom[:50]}...")
        
        # Step 1: Detect scenario
        self.detected_scenario = self._detect_scenario(context.symptom)
        await self.delay(300)
        
        # Step 2: Parse symptom details
        symptom_details = self._parse_symptom_details(context.symptom)
        await self.update_status(AgentState.RUNNING, 20)
        
        # Step 3: Generate reasoning steps
        reasoning_steps = self._generate_reasoning_steps(
            context.symptom,
            self.detected_scenario,
            symptom_details,
            context.signals
        )
        
        # Send reasoning steps to frontend
        for i, step in enumerate(reasoning_steps):
            await self.delay(400)
            await self.send({
                "type": "reasoning_step",
                "step": {
                    "title": step.title,
                    "body": step.body
                }
            })
            await self.update_status(AgentState.RUNNING, 20 + int((i + 1) / len(reasoning_steps) * 60))
        
        # Step 4: Extract relevant signals
        relevant_signals = self._extract_relevant_signals(
            self.detected_scenario,
            context.signals
        )
        
        # Update context
        context.parsed_symptoms = symptom_details
        context.reasoning_steps = reasoning_steps
        context.relevant_signals = relevant_signals
        
        # Notify orchestrator
        await self.send_msg_bus("orch", [
            {"k": "结果", "v": "解析完成", "cls": "g"},
            {"k": "场景", "v": self.detected_scenario or "unknown"},
            {"k": "步骤", "v": f"{len(reasoning_steps)}条推理链"}
        ])
        
        await self.animate_wire("rule")
        
        return context
    
    def _detect_scenario(self, symptom: str) -> Optional[str]:
        """Detect which scenario matches the symptom."""
        return self._scenario_detector.detect(symptom)
    
    def _parse_symptom_details(self, symptom: str) -> List[str]:
        """Extract specific details from symptom text."""
        details = []
        
        # Extract action patterns
        actions = re.findall(r"踩刹车|按启动|开门|闭锁|解锁|充电", symptom)
        details.extend(actions)
        
        # Extract error patterns
        errors = re.findall(r"无法上电|无法启动|认证失败|超时|异常|中断", symptom)
        details.extend(errors)
        
        # Extract component mentions
        components = re.findall(r"BLE|蓝牙|钥匙|档位|电池|OTA", symptom)
        details.extend(components)
        
        return list(set(details))
    
    def _generate_reasoning_steps(
        self,
        symptom: str,
        scenario: Optional[str],
        details: List[str],
        signals: Dict[str, str]
    ) -> List[ReasoningStep]:
        """Generate reasoning steps based on scenario."""
        
        # Get signal values
        sv_pm = signals.get("sv-pm", "0:Off")
        sv_kl = signals.get("sv-kl", "off")
        sv_zat = signals.get("sv-zat", "NOT_PRESSED")
        sv_brk = signals.get("sv-brk", "NOT_PRESSED")
        sv_kv = signals.get("sv-kv", "INVALID")
        sv_ble = signals.get("sv-ble", "0")
        
        # Generate steps based on scenario
        if scenario == "ble_auth":
            return [
                ReasoningStep(
                    title="[S1] 症状解析 & 场景识别 (VEEA-SysR-2117)",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">用户症状:</span><span class="sv">{symptom[:40]}...</span></div>'
                         f'<div class="sr"><span class="sk">触发路径:</span><span class="sv">T_1_2 Off→Local On 触发链</span></div>'
                         f'<div class="sr"><span class="sk">当前状态:</span><span class="sv e">{sv_pm}</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S2] T_1_2 前置条件校验",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">BrkPedalStVD:</span><span class="sv g">VALID ✅</span></div>'
                         f'<div class="sr"><span class="sk">GE_Fahrstufe:</span><span class="sv g">0x5 Pos_P ✅</span></div>'
                         f'<div class="sr"><span class="sk">ZATButtonSwSt:</span><span class="sv g">{sv_zat} ✅</span></div>'
                         f'<div class="sr"><span class="sk">结论:</span><span class="sv w">→ 触发 KeySearchingSt=Initial Search</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S3] KeyValidSt 超时 / Flag_BLE 异常",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">tKeyValid:</span><span class="sv e">超时 ❌</span></div>'
                         f'<div class="sr"><span class="sk">KeyValidSt:</span><span class="sv e">{sv_kv} ❌</span></div>'
                         f'<div class="sr"><span class="sk">Flag_BLE:</span><span class="sv w">{sv_ble}</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S4] L3 BLE认证链路定位",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">LDCU_BLEKeySeachReq:</span><span class="sv w">已发起</span></div>'
                         f'<div class="sr"><span class="sk">BLE_ErrorCode:</span><span class="sv e">AUTH_ERR(0x05)</span></div>'
                         f'<div class="sr"><span class="sk">keyPSValue:</span><span class="sv e">Invalid</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S5] 最终结论",
                    body=f'<span style="color:var(--acc);font-weight:600">'
                         f'T_1_2 触发失败：BLE认证 AUTH_ERR → KeyValidSt=INVALID → Off→Local On 转移阻断'
                         f'</span>'
                )
            ]
        
        elif scenario == "key_timeout":
            return [
                ReasoningStep(
                    title="[S1] 症状解析 (VEEA-SysR-2117)",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">动作:</span><span class="sv">ZAT单按（无踏板）</span></div>'
                         f'<div class="sr"><span class="sk">路径:</span><span class="sv">T_1_2 ZAT路径</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S2] KeySearchingSt 状态",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">KeySearchingSt:</span><span class="sv w">→ Initial Search 启动</span></div>'
                         f'<div class="sr"><span class="sk">tKeyValid:</span><span class="sv w">30s 计时开始</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S3] BLE 设备未发现",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">Flag_BLE:</span><span class="sv e">0 (无BLE解锁授权) ❌</span></div>'
                         f'<div class="sr"><span class="sk">BLE_Status:</span><span class="sv e">NOT_DETECTED ❌</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S4] 结论",
                    body=f'<span style="color:var(--acc);font-weight:600">'
                         f'手机蓝牙未开启 → BLE设备未发现 → tKeyValid超时 → keyNotFound弹窗'
                         f'</span>'
                )
            ]
        
        elif scenario == "bms_charging":
            return [
                ReasoningStep(
                    title="[S1] 症状解析 — C7.Event: ChargingPowerCutoff",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">触发事件:</span><span class="sv e">packSOPCharge=0.0kW</span></div>'
                         f'<div class="sr"><span class="sk">C7.Event类型:</span><span class="sv w">ChargingPowerCutoff</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S2] C1.Object 三级BMS层级读取",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">L1 BatteryPack:</span><span class="sv">packSOPCharge=0.0kW</span></div>'
                         f'<div class="sr"><span class="sk">L2 BatteryModule[02]:</span><span class="sv w">tempHigh=true</span></div>'
                         f'<div class="sr"><span class="sk">L3 BatteryCell[02_14]:</span><span class="sv e">cellTemp=47.2°C ❌</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S3] C3.Constraint — NMC化学体系充电温度约束违反",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">chemistry:</span><span class="sv">NMC (三元锂)</span></div>'
                         f'<div class="sr"><span class="sk">约束:</span><span class="sv e">47.2°C > 45°C 违反!</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S4] 结论",
                    body=f'<span style="color:var(--red);font-weight:600">'
                         f'cellTemp超NMC充电约束(45°C) → R-BMS001-P2触发 → packSOPCharge=0kW'
                         f'</span>'
                )
            ]
        
        else:
            # Default steps
            return [
                ReasoningStep(
                    title="[S1] 症状解析",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">症状:</span><span class="sv">{symptom[:50]}...</span></div>'
                         f'<div class="sr"><span class="sk">场景:</span><span class="sv">{scenario or "unknown"}</span></div>'
                         f'</div>'
                ),
                ReasoningStep(
                    title="[S2] 初步分析",
                    body=f'<div class="sl">'
                         f'<div class="sr"><span class="sk">信号状态:</span><span class="sv">{sv_pm}</span></div>'
                         f'</div>'
                )
            ]
    
    def _extract_relevant_signals(
        self,
        scenario: Optional[str],
        signals: Dict[str, str]
    ) -> Dict[str, Any]:
        """Extract relevant signals for the detected scenario."""
        relevant = {}
        
        if scenario and scenario in SIGNAL_RELEVANCE:
            mapping = SIGNAL_RELEVANCE[scenario]
            
            for signal in mapping.get("primary", []):
                # Map to frontend signal IDs
                fe_id = self._map_to_frontend_id(signal)
                if fe_id in signals:
                    relevant[signal] = signals[fe_id]
            
            for signal in mapping.get("secondary", []):
                fe_id = self._map_to_frontend_id(signal)
                if fe_id in signals:
                    relevant[signal] = signals[fe_id]
        
        return relevant
    
    def _map_to_frontend_id(self, ontology_signal: str) -> str:
        """Map ontology signal name to frontend signal ID."""
        mapping = {
            "LDCU_PowerMode": "sv-pm",
            "KeyValidSt": "sv-kv",
            "Flag_BLE": "sv-ble",
            "BrkPedalSt": "sv-brk",
            "Gearlev": "sv-gear",
            "packSoC": "sv-soc",
            "packSOPCharge": "sv-sopcharge",
            "cellTempMax": "sv-celltemp",
        }
        return mapping.get(ontology_signal, ontology_signal)
