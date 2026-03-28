"""
Diagnosis Knowledge - Centralized knowledge constants for vehicle power diagnosis.

This module provides a single source of truth for all diagnosis-related constants,
including symptom patterns, rules, hypotheses, output templates, and signal mappings.

Used by:
- agents/symptom_parser.py
- agents/rule_engine.py
- agents/output_adapter.py
- llm/fallback.py
"""

from typing import Dict, List, Any, Optional


__all__ = [
    "SYMPTOM_PATTERNS",
    "RULES",
    "HYPOTHESIS_TEMPLATES",
    "REASONING_STEP_TEMPLATES",
    "CONFIDENCE_WEIGHTS",
    "generate_reasoning_steps",
    "OUTPUT_TEMPLATES",
    "ESCALATION_HINTS",
    "SIGNAL_RELEVANCE",
    "SIGNAL_RECOMMENDATIONS",
    "SCENARIO_RULES_MAP",
    # DTC Knowledge
    "DTC_KNOWLEDGE_BASE",
    "DTC_TO_SCENARIO_MAP",
    "DTC_HYPOTHESIS_TEMPLATES",
    "DTC_OUTPUT_TEMPLATES",
]


# =============================================================================
# Symptom Patterns
# =============================================================================

SYMPTOM_PATTERNS: Dict[str, List[str]] = {
    "ble_auth": [
        r"蓝牙.*认证.*失败",
        r"BLE.*认证",
        r"钥匙未找到",
        r"踩刹车.*启动.*无法上电",
        r"ZAT.*无法上电",
        r"AUTH_ERR",
    ],
    "key_timeout": [
        r"钥匙搜索.*超时",
        r"检测不到.*钥匙",
        r"钥匙.*未开启",
        r"蓝牙.*未开启",
    ],
    "forced_off": [r"强制下电", r"长按.*启动.*无响应", r"档位.*异常"],
    "auto_poweroff": [r"自动下电", r"停放.*小时.*无响应", r"一小时.*无响应"],
    "remote_on": [r"OTA.*上电", r"远程.*升级", r"Remote.*On"],
    "alcohol_lock": [r"酒精.*锁", r"吹气.*检测", r"无法进入.*Ready", r"AlcoholLock"],
    "bms_charging": [
        r"充电.*功率.*降",
        r"SOC.*停止",
        r"BMS.*热保护",
        r"电池.*高温",
        r"充电.*中断",
    ],
}


# =============================================================================
# Diagnostic Rules
# =============================================================================

RULES: Dict[str, Dict[str, str]] = {
    "T_1_2": {
        "id": "T_1_2",
        "text": "IF BrkPedalStVD=VALID AND GE_Fahrstufe=P/N AND ZATPressed → KeySearchingSt=Initial Search → tKeyValid(30s)",
        "src": "VEEA-SysR-2117",
        "conf": "0.98",
    },
    "R-KEY001": {
        "id": "R-KEY001",
        "text": "IF tKeyValid超时 AND KeyValidSt=INVALID → PowerMode保持Off + LDCU_KeyInvalidAlertReq=Key Not Found Alert",
        "src": "VEEA-SysR-2147",
        "conf": "0.98",
    },
    "R-BLE001": {
        "id": "R-BLE001",
        "text": "IF Flag_BLE=1(20min计时) AND LDCU_BLEKeySeachReq发起 → 检查BLE认证链路",
        "src": "VEEA-SysR-2123",
        "conf": "0.92",
    },
    "R-BLE002": {
        "id": "R-BLE002",
        "text": "IF bleErrorCode=0x05(AUTH_ERR) AND keyPSValue=Invalid → BLE钥匙认证失败，需重新配对",
        "src": "TBOX LDCU_TBOX_AuthentSt",
        "conf": "0.95",
    },
    "R-AUTO-OFF": {
        "id": "R-AUTO-OFF",
        "text": "IF AutoPoweroffCfgSt=Active AND St2(1:Local On) AND 1h无操作 → T_2_1触发",
        "src": "VEEA-SysR-2132",
        "conf": "0.99",
    },
    "R-BMS001-P2": {
        "id": "R-BMS001-P2",
        "text": "IF BatteryCell.cellTemp > 45°C(NMC) AND ChargingMode=Active → packSOPCharge=0kW",
        "src": "CEA Ontology v1.0 § C5",
        "conf": "0.95",
    },
    "R-SAFE-003": {
        "id": "R-SAFE-003",
        "text": "IF BatteryCell.cellTemp > thermalThreshold(NMC:45°C) → 热保护触发，禁止充电",
        "src": "VEEA-SysR",
        "conf": "0.96",
    },
}


# =============================================================================
# Reasoning Step Templates
# =============================================================================

REASONING_STEP_TEMPLATES: Dict[str, Dict[str, str]] = {
    "symptom_parsing": {
        "title": "症状解析",
        "body": "正在解析用户描述的症状: {symptom}",
    },
    "ontology_lookup": {"title": "本体查询", "body": "检索与症状相关的车辆概念和关系"},
    "rule_matching": {
        "title": "规则匹配",
        "body": "匹配诊断规则库中的相关规则: {rule_count} 条候选规则",
    },
    "hypothesis_generation": {"title": "假设生成", "body": "基于匹配规则生成诊断假设"},
    "confidence_calculation": {"title": "置信度计算", "body": "计算各假设的置信度得分"},
    "output_generation": {
        "title": "输出生成",
        "body": "生成针对 {role} 角色的诊断报告",
    },
}


CONFIDENCE_WEIGHTS: Dict[str, float] = {
    "symptom_match": 0.30,
    "signal_match": 0.30,
    "rule_support": 0.25,
    "ontology_relevance": 0.15,
}


def generate_reasoning_steps(symptom: str, role: str) -> List[Dict[str, str]]:
    """Generate standard reasoning steps for diagnosis visualization."""
    return [
        {
            "title": REASONING_STEP_TEMPLATES["symptom_parsing"]["title"],
            "body": REASONING_STEP_TEMPLATES["symptom_parsing"]["body"].format(
                symptom=symptom[:50]
            ),
        },
        {
            "title": REASONING_STEP_TEMPLATES["ontology_lookup"]["title"],
            "body": REASONING_STEP_TEMPLATES["ontology_lookup"]["body"],
        },
        {
            "title": REASONING_STEP_TEMPLATES["rule_matching"]["title"],
            "body": REASONING_STEP_TEMPLATES["rule_matching"]["body"].format(
                rule_count=len(RULES)
            ),
        },
        {
            "title": REASONING_STEP_TEMPLATES["hypothesis_generation"]["title"],
            "body": REASONING_STEP_TEMPLATES["hypothesis_generation"]["body"],
        },
        {
            "title": REASONING_STEP_TEMPLATES["confidence_calculation"]["title"],
            "body": REASONING_STEP_TEMPLATES["confidence_calculation"]["body"],
        },
        {
            "title": REASONING_STEP_TEMPLATES["output_generation"]["title"],
            "body": REASONING_STEP_TEMPLATES["output_generation"]["body"].format(
                role=role
            ),
        },
    ]


# =============================================================================
# Hypothesis Templates
# =============================================================================

HYPOTHESIS_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "ble_auth": [
        {"name": "手机BLE连接认证失败（配对信息/权限）", "pct": 55, "cls": "p"},
        {"name": "BLE配对信息丢失需重新绑定", "pct": 30, "cls": "s"},
        {"name": "TBOX BLE模块固件/硬件异常", "pct": 15, "cls": "t"},
    ],
    "key_timeout": [
        {"name": "手机蓝牙未开启", "pct": 75, "cls": "p"},
        {"name": "手机超出BLE范围(>10m)", "pct": 20, "cls": "s"},
        {"name": "手机蓝牙模块故障", "pct": 5, "cls": "t"},
    ],
    "bms_charging": [
        {"name": "BatteryCell[02_14]高温 → SOP截断", "pct": 92, "cls": "p"},
        {"name": "BMS固件热保护限流策略触发", "pct": 21, "cls": "s"},
        {"name": "OBC-BMS通信链路中断", "pct": 12, "cls": "t"},
    ],
    "auto_poweroff": [
        {"name": "SSTS R-AUTO-OFF 1h自动下电（正常功能）", "pct": 88, "cls": "p"},
        {"name": "EEPROM_PowerMode读取短暂延迟", "pct": 9, "cls": "s"},
        {"name": "低电量LVEM下电", "pct": 3, "cls": "t"},
    ],
}


# =============================================================================
# Output Templates (Role-adapted HTML)
# =============================================================================

OUTPUT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "ble_auth": {
        "owner": """<div class="conc">📱 手机蓝牙钥匙认证失败，无法上电</div>
<p style="margin-top:8px">踩刹车按启动键时，车辆检测到手机但无法完成蓝牙认证，屏幕弹出"钥匙未找到"提示。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>关闭手机蓝牙，等待5秒后重新打开，靠近车辆再次尝试</div>
  <div class="ai"><div class="an">2</div>检查手机 App 蓝牙权限是否已开启</div>
  <div class="ai"><div class="an">3</div>可使用备用 NFC 钥匙卡（tNFCReadyEnable）应急上电</div>
  <div class="ai"><div class="an">4</div>仍无法解决请拨打 <span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】T_1_2 转移失败 — BLE认证失败 → PowerMode 保持 0:Off</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">链路: T_1_2 → KeySearchingSt=Initial Search → tKeyValid超时 → KeyValidSt=Invalid → LDCU_KeyInvalidAlertReq=Key Not Found Alert</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>重开手机BLE重试，确认 RSSI > -80dBm，Flag_BLE 状态</div>
  <div class="ai"><div class="an">P2</div>OBD 读取 TBOX_ECU：BLE_ErrorCode + keyPSValue + LDCU_TBOX_AuthentSt</div>
  <div class="ai"><div class="an">P3</div>App 解绑重新配对，清除 TBOX 端 BLE 配对记录</div>
  <div class="ai"><div class="an">P4</div>读取 LDCU EEPROM_PowerMode，确认电源状态持久化是否正常</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】车辆蓝牙钥匙认证异常，上电被阻断</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆检测到您的手机但认证失败，出现了"钥匙未找到"提示。重新开关蓝牙通常可以解决。"</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">1</div>关闭手机蓝牙等5秒，重新打开后靠近车辆踩刹车</div>
  <div class="ai"><div class="an">2</div>确认手机 App 已授权蓝牙权限</div>
</div>""",
    },
    "key_timeout": {
        "owner": """<div class="conc">📱 手机蓝牙未开启，无法检测到钥匙</div>
<p style="margin-top:8px">车辆在 tKeyValid 时间内未检测到任何有效钥匙信号，触发了"钥匙未找到"提示。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>开启手机蓝牙，靠近车辆（1米以内）</div>
  <div class="ai"><div class="an">2</div>重新踩刹车按启动按钮，或开门触发上电</div>
</div>""",
        "technician": """<div class="conc">【诊断结论】Flag_BLE=0 & BLE_Status=NOT_DETECTED → tKeyValid超时 → KeySearchingSt=Timeout</div>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>确认手机蓝牙已开启并在范围内（&lt;10m），检查 Flag_BLE 是否更新为1</div>
  <div class="ai"><div class="an">P2</div>检查 TBOX LDCU_BLEKeySeachReq 是否正常发出</div>
  <div class="ai"><div class="an">P3</div>备选：验证 Flag_4GReady / Flag_NFC 路径是否可用</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】手机蓝牙未开启，车辆无法识别钥匙</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆未检测到手机蓝牙信号，请先开启手机蓝牙再尝试上电，或用NFC钥匙卡上车。"</p>""",
    },
    "bms_charging": {
        "owner": """<div class="conc">🔋 充电中断：电池热保护触发，SOC停止在78.3%</div>
<p style="margin-top:8px">充电过程中，BMS检测到某节电芯温度（47.2°C）超过NMC电池安全充电阈值（45°C），自动触发热保护截断了充电功率，以保护电池安全。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>断开充电枪，让车辆在通风环境中自然冷却约20-30分钟</div>
  <div class="ai"><div class="an">2</div>避免在高温环境（>35°C）或阳光直射下充电</div>
  <div class="ai"><div class="an">3</div>冷却后重新插充电枪，系统将自动恢复充电</div>
  <div class="ai"><div class="an">4</div>若反复出现或冷却后仍无法充电，请预约检测：<span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】C3.Constraint违反 → R-BMS001-P2(conf:0.95)触发 — cellTemp=47.2°C超NMC约束(≤45°C) → packSOPCharge=0kW</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">FaultPropagation: Cell[02_14]→Module[02]→Pack→OBC | R-SAFE-003热保护</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>OBD读取BMS所有cell温度，确认cell_02_14是否持续>45°C</div>
  <div class="ai"><div class="an">P2</div>检查BatteryModule[02]冷却液流量、温控阀和热管理ECU状态</div>
  <div class="ai"><div class="an">P3</div>读取R-BMS001-P2历史触发记录，判断是否趋势性故障</div>
  <div class="ai"><div class="an">P4</div>若多次触发：更换module_02热管理组件或升级BMS固件</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】电池热保护启动，充电功率截断，SOC停止在78.3%</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆在充电过程中电池温度偏高，系统为保护电池安全自动暂停了充电。请断开充电枪，将车停在阴凉通风处冷却约20-30分钟后再试。若问题反复出现，建议预约售后检测。"</p>""",
    },
    "auto_poweroff": {
        "owner": """<div class="conc">✅ 车辆1小时自动下电，功能无异常</div>
<p style="margin-top:8px">车辆停放超过1小时（50分钟+10分钟）会自动下电（节能功能），开门或踩刹车按启动键即可正常上电。</p>""",
        "technician": """<div class="conc">【诊断结论】SSTS R-AUTO-OFF 1h自动下电正常触发，T_1_2重新上电验证通过</div>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>确认 LDCU_AutoPowerOffFuncSt 已回 Not Active（上电后）</div>
  <div class="ai"><div class="an">P2</div>确认 EEPROM_PowerMode 已正确恢复</div>
  <div class="ai"><div class="an">P3</div>如需关闭自动下电，可通过诊断命令设置 AutoPoweroffCfgSt=Not Active</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】车辆1小时自动下电功能正常，可直接重新上电</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，停车1小时后自动下电是正常的节能功能，开门或踩刹车按启动键就能上电。"</p>""",
    },
    "forced_off": {
        "owner": """<div class="conc">⚠️ 车辆触发强制下电保护</div>
<p style="margin-top:8px">车辆检测到异常状态（档位异常或长按启动键无响应），触发强制下电保护机制。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>确认车辆已停在安全位置，档位处于P档</div>
  <div class="ai"><div class="an">2</div>等待30秒后重新尝试上电</div>
  <div class="ai"><div class="an">3</div>如反复出现请联系 <span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】强制下电触发 — 档位异常/长按启动键超时 → LDCU_ForceOffReq=Active</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">链路: GE_Fahrstufe异常检测 → LDCU_SafetyReq → 强制PowerMode=Off</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>OBD读取GE_Fahrstufe当前值，确认档位传感器状态</div>
  <div class="ai"><div class="an">P2</div>检查ZAT开关状态及LDCU_StartBtnSt信号</div>
  <div class="ai"><div class="an">P3</div>读取LDCU_ForceOffReason历史记录</div>
  <div class="ai"><div class="an">P4</div>验证档位传感器线束连接及信号完整性</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】车辆触发强制下电保护机制</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆因档位异常触发了安全保护机制自动下电。请确认车辆停在P档，等待30秒后重新尝试上电。"</p>""",
    },
    "remote_on": {
        "owner": """<div class="conc">📡 远程上电/OTA升级过程中</div>
<p style="margin-top:8px">车辆正在执行远程上电或OTA升级任务，此期间部分功能可能受限。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>等待远程任务完成（通常5-15分钟）</div>
  <div class="ai"><div class="an">2</div>任务完成后车辆会自动恢复常态</div>
  <div class="ai"><div class="an">3</div>如长时间无响应请拨打 <span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】远程上电/OTA模式激活 — TBOX RemoteOnReq=Active</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">链路: TBOX_OTA_Req → LDCU_RemoteEnable → PowerMode=Remote On</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>检查TBOX_OTAStatus及升级进度</div>
  <div class="ai"><div class="an">P2</div>确认4G连接状态及Flag_4GReady</div>
  <div class="ai"><div class="an">P3</div>监控OTA任务日志，确认无卡顿或失败</div>
  <div class="ai"><div class="an">P4</div>如超时，检查TBOX固件版本及OTA模块状态</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】车辆正在进行远程上电或OTA升级</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆正在执行远程任务，请耐心等待5-15分钟。任务完成后您会收到通知。"</p>""",
    },
    "alcohol_lock": {
        "owner": """<div class="conc">🚫 酒精锁激活，车辆无法进入Ready状态</div>
<p style="margin-top:8px">车辆检测到酒精浓度超标或酒精锁系统激活，禁止进入Ready模式以保障安全。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>请等待酒精浓度降低后重新吹气检测</div>
  <div class="ai"><div class="an">2</div>确保吹气检测时用力均匀、时长充足</div>
  <div class="ai"><div class="an">3</div>多次检测失败请联系 <span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】酒精锁系统激活 — AlcoholLockSt=Active → Ready禁止</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">链路: AlcoholSensor检测 → AlcoholLock_ECU → LDCU_ReadyEnable=Not Active</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>OBD读取AlcoholLock_ECU：酒精浓度值及传感器状态</div>
  <div class="ai"><div class="an">P2</div>检查吹气传感器灵敏度及校准状态</div>
  <div class="ai"><div class="an">P3</div>验证AlcoholLockSt信号链路完整性</div>
  <div class="ai"><div class="an">P4</div>如传感器异常，检查供电及CAN通信</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】酒精锁系统激活，车辆无法启动</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆酒精锁系统检测到异常，需要重新进行吹气检测。请确保吹气均匀、时长充足。"</p>""",
    },
}


# =============================================================================
# Escalation Hints
# =============================================================================

ESCALATION_HINTS: Dict[str, Dict[str, str]] = {
    "ble_auth": {
        "customer_service": "升级条件：操作3次仍弹出「钥匙未找到」→ 升级技术支持 | BLE_ErrorCode 持续0x05 → 创建服务工单硬件检测"
    },
    "key_timeout": {
        "customer_service": "升级条件：蓝牙已开且靠近车辆仍NOT_DETECTED → 检查TBOX BLE模块 / LDCU_BLEKeySeachReq"
    },
    "bms_charging": {
        "customer_service": "升级条件：冷却后仍无法恢复充电 → BMS固件检测 / cell_02_14热管理组件异常 → 创建服务工单现场检测"
    },
}


# =============================================================================
# Signal Relevance Mapping
# =============================================================================

SIGNAL_RELEVANCE: Dict[str, Dict[str, List[str]]] = {
    "ble_auth": {
        "primary": [
            "LDCU_PowerMode",
            "KeyValidSt",
            "Flag_BLE",
            "KeySearchingSt",
            "BrkPedalSt",
        ],
        "secondary": ["AlarmSt", "DriverDoorAjarSt", "Gearlev"],
    },
    "key_timeout": {
        "primary": ["LDCU_PowerMode", "KeyValidSt", "KeySearchingSt", "Flag_BLE"],
        "secondary": ["AlarmSt", "BrkPedalSt"],
    },
    "forced_off": {
        "primary": [
            "LDCU_PowerMode",
            "Gearlev",
            "LDCU_PowerCtrlError",
            "EmergencyPowerOffSwSt",
        ],
        "secondary": ["BrkPedalSt", "KeyValidSt"],
    },
    "auto_poweroff": {
        "primary": ["LDCU_PowerMode", "CCU_AutoPoweroffConfig", "DrvSeatOccupancySt"],
        "secondary": ["AlarmSt", "KeyValidSt"],
    },
    "remote_on": {
        "primary": ["LDCU_PowerMode", "CCU_DiagnosticSt", "OTAPowerOnValid"],
        "secondary": ["KeyValidSt", "AlarmSt"],
    },
    "alcohol_lock": {
        "primary": ["LDCU_PowerMode", "AlcoholInterlockBlockingSt"],
        "secondary": ["KeyValidSt", "BrkPedalSt"],
    },
    "bms_charging": {
        "primary": ["packSoC", "packSOPCharge", "cellTempMax", "packSOPDischarge"],
        "secondary": ["LDCU_PowerMode", "CCU_DiagnosticSt"],
    },
}


# =============================================================================
# Signal Recommendations for Diagnosis
# =============================================================================

SIGNAL_RECOMMENDATIONS: Dict[str, List[Dict[str, Any]]] = {
    "ble_auth": [
        {
            "name": "LDCU_PowerMode",
            "description_zh": "电源模式状态",
            "description_en": "Power mode state",
            "reason": "确认当前电源状态，判断是否已上电",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "KeyValidSt",
            "description_zh": "钥匙有效性状态",
            "description_en": "Key valid status",
            "reason": "判断钥匙是否通过认证",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "Flag_BLE",
            "description_zh": "蓝牙钥匙连接标志",
            "description_en": "BLE key connection flag",
            "reason": "确认蓝牙钥匙是否已连接",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "KeySearchingSt",
            "description_zh": "钥匙搜索状态",
            "description_en": "Key searching status",
            "reason": "确认钥匙搜索阶段和超时状态",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "BrkPedalSt",
            "description_zh": "刹车踏板状态",
            "description_en": "Brake pedal status",
            "reason": "确认刹车是否踩下（上电前提条件）",
            "priority": "required",
            "read_method": "OBD读取BCM报文",
        },
        {
            "name": "LDCU_TBOX_AuthentSt",
            "description_zh": "TBOX认证状态",
            "description_en": "TBOX authentication status",
            "reason": "确认TBOX认证链路状态，诊断认证失败原因",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "bleErrorCode",
            "description_zh": "蓝牙错误码",
            "description_en": "BLE error code",
            "reason": "获取详细BLE错误信息，定位认证失败原因",
            "priority": "optional",
            "read_method": "诊断仪读取TBOX_DTC",
        },
    ],
    "key_timeout": [
        {
            "name": "LDCU_PowerMode",
            "description_zh": "电源模式状态",
            "description_en": "Power mode state",
            "reason": "确认当前电源状态",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "KeyValidSt",
            "description_zh": "钥匙有效性状态",
            "description_en": "Key valid status",
            "reason": "判断钥匙是否有效",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "KeySearchingSt",
            "description_zh": "钥匙搜索状态",
            "description_en": "Key searching status",
            "reason": "确认钥匙搜索是否超时",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "Flag_BLE",
            "description_zh": "蓝牙钥匙连接标志",
            "description_en": "BLE key connection flag",
            "reason": "确认蓝牙钥匙是否已连接",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "Flag_4GReady",
            "description_zh": "4G网络就绪状态",
            "description_en": "4G network ready status",
            "reason": "检查备用上电路径是否可用",
            "priority": "optional",
            "read_method": "OBD读取TBOX_ECU报文",
        },
    ],
    "forced_off": [
        {
            "name": "LDCU_PowerMode",
            "description_zh": "电源模式状态",
            "description_en": "Power mode state",
            "reason": "确认当前电源模式",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "Gearlev",
            "description_zh": "档位状态",
            "description_en": "Gear position status",
            "reason": "确认档位是否在P/N档，判断是否非预期下电",
            "priority": "required",
            "read_method": "OBD读取TCU报文",
        },
        {
            "name": "LDCU_PowerCtrlError",
            "description_zh": "电源控制错误",
            "description_en": "Power control error",
            "reason": "获取电源控制故障码，分析下电原因",
            "priority": "required",
            "read_method": "OBD读取TBOX_DTC",
        },
        {
            "name": "EmergencyPowerOffSwSt",
            "description_zh": "紧急下电开关状态",
            "description_en": "Emergency power off switch status",
            "reason": "检查是否触发了紧急下电",
            "priority": "required",
            "read_method": "OBD读取BCM报文",
        },
        {
            "name": "VehSpd",
            "description_zh": "车速",
            "description_en": "Vehicle speed",
            "reason": "确认车辆是否在行驶中非预期下电",
            "priority": "optional",
            "read_method": "OBD读取ESP报文",
        },
    ],
    "auto_poweroff": [
        {
            "name": "LDCU_PowerMode",
            "description_zh": "电源模式状态",
            "description_en": "Power mode state",
            "reason": "确认当前电源模式",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "CCU_AutoPoweroffConfig",
            "description_zh": "自动下电配置",
            "description_en": "Auto power off configuration",
            "reason": "确认自动下电功能是否启用",
            "priority": "required",
            "read_method": "OBD读取CCU报文",
        },
        {
            "name": "DrvSeatOccupancySt",
            "description_zh": "驾驶员在座状态",
            "description_en": "Driver seat occupancy status",
            "reason": "判断驾驶员是否在座（自动下电条件）",
            "priority": "required",
            "read_method": "OBD读取BCM报文",
        },
        {
            "name": "LDCU_AutoPowerOffFuncSt",
            "description_zh": "自动下电功能状态",
            "description_en": "Auto power off function status",
            "reason": "确认自动下电功能是否触发",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
    ],
    "remote_on": [
        {
            "name": "LDCU_PowerMode",
            "description_zh": "电源模式状态",
            "description_en": "Power mode state",
            "reason": "确认当前电源模式",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "CCU_DiagnosticSt",
            "description_zh": "诊断状态",
            "description_en": "Diagnostic status",
            "reason": "确认车辆是否处于诊断模式",
            "priority": "required",
            "read_method": "OBD读取CCU报文",
        },
        {
            "name": "OTAPowerOnValid",
            "description_zh": "OTA上电有效性",
            "description_en": "OTA power on validation",
            "reason": "确认OTA远程上电是否被授权",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
    ],
    "alcohol_lock": [
        {
            "name": "LDCU_PowerMode",
            "description_zh": "电源模式状态",
            "description_en": "Power mode state",
            "reason": "确认当前电源模式",
            "priority": "required",
            "read_method": "OBD读取TBOX_ECU报文",
        },
        {
            "name": "AlcoholInterlockBlockingSt",
            "description_zh": "酒精锁阻止状态",
            "description_en": "Alcohol interlock blocking status",
            "reason": "确认酒精锁是否阻止上电",
            "priority": "required",
            "read_method": "OBD读取BCM报文",
        },
    ],
    "bms_charging": [
        {
            "name": "packSoC",
            "description_zh": "电池包荷电状态",
            "description_en": "Battery pack state of charge",
            "reason": "确认当前电池SOC，充电停止位置",
            "priority": "required",
            "read_method": "OBD读取BMS报文",
        },
        {
            "name": "packSOPCharge",
            "description_zh": "充电功率限制",
            "description_en": "Charging power limit",
            "reason": "确认当前充电功率是否被限制",
            "priority": "required",
            "read_method": "OBD读取BMS报文",
        },
        {
            "name": "cellTempMax",
            "description_zh": "电芯最高温度",
            "description_en": "Maximum cell temperature",
            "reason": "确认电芯温度是否超过阈值触发热保护",
            "priority": "required",
            "read_method": "OBD读取BMS报文",
        },
        {
            "name": "packSOPDischarge",
            "description_zh": "放电功率限制",
            "description_en": "Discharging power limit",
            "reason": "确认放电功率是否受限",
            "priority": "optional",
            "read_method": "OBD读取BMS报文",
        },
        {
            "name": "cellTemp_02_14",
            "description_zh": "特定电芯温度",
            "description_en": "Specific cell temperature",
            "reason": "定位具体高温电芯位置",
            "priority": "optional",
            "read_method": "OBD读取BMS报文",
        },
    ],
}


# =============================================================================
# Scenario to Rules Mapping
# =============================================================================

SCENARIO_RULES_MAP: Dict[str, List[str]] = {
    "ble_auth": ["T_1_2", "R-KEY001", "R-BLE001", "R-BLE002"],
    "key_timeout": ["T_1_2", "R-KEY001"],
    "bms_charging": ["R-BMS001-P2", "R-SAFE-003"],
    "auto_poweroff": ["R-AUTO-OFF"],
    "remote_on": ["R-AUTO-OFF"],
    "alcohol_lock": ["R-KEY001"],
    "forced_off": ["T_1_2"],
}


# =============================================================================
# DTC Knowledge Base (SAE J2012 / ISO 15031-6)
# =============================================================================

DTC_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # Network Codes (U0xxx) - Most relevant to power mode system
    # -------------------------------------------------------------------------
    "U0100": {
        "code": "U0100",
        "category": "network",
        "severity": "critical",
        "description": "Lost Communication with ECM/PCM",
        "description_zh": "与ECM/PCM失去通信",
        "related_ecu": ["ECM", "PCM", "TBOX"],
        "related_signals": ["LDCU_PowerMode", "EVSysReadySt"],
        "possible_causes": [
            "CAN bus communication failure",
            "ECM/PCM power supply issue",
            "CAN bus wiring harness damage",
            "ECM/PCM internal failure",
        ],
        "scenarios": ["remote_on", "forced_off"],
    },
    "U0101": {
        "code": "U0101",
        "category": "network",
        "severity": "critical",
        "description": "Lost Communication with TCM",
        "description_zh": "与TCM失去通信",
        "related_ecu": ["TCM", "BCM"],
        "related_signals": ["Gearlev", "LDCU_PowerMode"],
        "possible_causes": [
            "TCM CAN communication failure",
            "TCM power supply issue",
            "Transmission control module failure",
        ],
        "scenarios": ["forced_off"],
    },
    "U0140": {
        "code": "U0140",
        "category": "network",
        "severity": "critical",
        "description": "Lost Communication with Body Control Module",
        "description_zh": "与BCM失去通信",
        "related_ecu": ["BCM", "LDCU"],
        "related_signals": ["LDCU_PowerMode", "KeyValidSt", "DriverDoorAjarSt"],
        "possible_causes": [
            "BCM CAN communication failure",
            "BCM power supply issue",
            "Body control module failure",
        ],
        "scenarios": ["ble_auth", "key_timeout", "forced_off"],
    },
    "U0155": {
        "code": "U0155",
        "category": "network",
        "severity": "critical",
        "description": "Lost Communication with Instrument Panel Cluster",
        "description_zh": "与仪表盘失去通信",
        "related_ecu": ["IPC", "BCM"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "IPC CAN communication failure",
            "Instrument cluster power issue",
        ],
        "scenarios": [],
    },
    "U0167": {
        "code": "U0167",
        "category": "network",
        "severity": "high",
        "description": "Lost Communication with Immobilizer Control Module",
        "description_zh": "与防盗控制模块失去通信",
        "related_ecu": ["IMMO", "BCM", "TBOX"],
        "related_signals": ["KeyValidSt", "Flag_BLE", "NFCKeyValidSt"],
        "possible_causes": [
            "Immobilizer module communication failure",
            "Key authentication system fault",
            "CAN bus issue between IMMO and BCM",
        ],
        "scenarios": ["ble_auth", "key_timeout"],
    },
    "U0184": {
        "code": "U0184",
        "category": "network",
        "severity": "medium",
        "description": "Lost Communication with Radio",
        "description_zh": "与收音机失去通信",
        "related_ecu": ["HU", "BCM"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "Head unit CAN communication failure",
            "Infotainment system power issue",
        ],
        "scenarios": [],
    },
    "U0214": {
        "code": "U0214",
        "category": "network",
        "severity": "high",
        "description": "Lost Communication with Remote Function Actuation",
        "description_zh": "与远程控制执行器失去通信",
        "related_ecu": ["RFA", "TBOX", "BCM"],
        "related_signals": ["KeyValidSt", "Flag_BLE", "OTAPowerOnValid"],
        "possible_causes": [
            "RFA module communication failure",
            "Remote keyless entry system fault",
            "CAN bus wiring issue",
        ],
        "scenarios": ["ble_auth", "key_timeout", "remote_on"],
    },
    "U0300": {
        "code": "U0300",
        "category": "network",
        "severity": "high",
        "description": "Internal Control Module Software Incompatibility",
        "description_zh": "内部控制模块软件不兼容",
        "related_ecu": ["BCM", "ECM", "TBOX"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "Software version mismatch after update",
            "Corrupted ECU firmware",
            "Incomplete programming",
        ],
        "scenarios": ["remote_on"],
    },
    "U0401": {
        "code": "U0401",
        "category": "network",
        "severity": "medium",
        "description": "Invalid Data Received from ECM/PCM",
        "description_zh": "从ECM/PCM接收到的数据无效",
        "related_ecu": ["ECM", "PCM"],
        "related_signals": ["LDCU_PowerMode", "EVSysReadySt"],
        "possible_causes": [
            "CAN signal corruption",
            "ECM/PCM sending invalid data",
            "Configuration mismatch",
        ],
        "scenarios": [],
    },
    "U0415": {
        "code": "U0415",
        "category": "network",
        "severity": "medium",
        "description": "Invalid Data Received from Anti-lock Brake System",
        "description_zh": "从ABS接收到的数据无效",
        "related_ecu": ["ABS", "BCM"],
        "related_signals": ["BrkPedalSt", "BrkPedalStVD"],
        "possible_causes": [
            "ABS module communication issue",
            "Brake signal data corruption",
        ],
        "scenarios": ["ble_auth", "forced_off"],
    },
    "U1000": {
        "code": "U1000",
        "category": "network",
        "severity": "critical",
        "description": "Class 2 Communication Malfunction",
        "description_zh": "Class 2通信故障",
        "related_ecu": ["BCM", "ALL_ECU"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "CAN bus network failure",
            "Multiple ECU communication loss",
            "CAN bus terminator issue",
        ],
        "scenarios": ["forced_off"],
    },
    "U1113": {
        "code": "U1113",
        "category": "network",
        "severity": "high",
        "description": "Lost Communication with Headlamp Leveling Control Module",
        "description_zh": "与大灯水平控制模块失去通信",
        "related_ecu": ["HLCM", "BCM"],
        "related_signals": [],
        "possible_causes": [
            "Headlamp leveling module failure",
            "CAN communication issue",
        ],
        "scenarios": [],
    },
    "U1201": {
        "code": "U1201",
        "category": "network",
        "severity": "high",
        "description": "CAN Bus Off",
        "description_zh": "CAN总线关闭",
        "related_ecu": ["ALL_ECU"],
        "related_signals": ["LDCU_PowerMode", "KeyValidSt"],
        "possible_causes": [
            "CAN bus physical layer failure",
            "CAN transceiver fault",
            "Bus contention or short circuit",
        ],
        "scenarios": ["forced_off", "ble_auth"],
    },
    "U1300": {
        "code": "U1300",
        "category": "network",
        "severity": "critical",
        "description": "Class 2 Data Link Short to Battery",
        "description_zh": "Class 2数据链路对电池短路",
        "related_ecu": ["ALL_ECU"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "CAN bus wiring short to power",
            "Faulty ECU causing bus short",
        ],
        "scenarios": ["forced_off"],
    },
    "U1301": {
        "code": "U1301",
        "category": "network",
        "severity": "critical",
        "description": "Class 2 Data Link Short to Ground",
        "description_zh": "Class 2数据链路对地短路",
        "related_ecu": ["ALL_ECU"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "CAN bus wiring short to ground",
            "Faulty ECU causing bus short",
        ],
        "scenarios": ["forced_off"],
    },
    # -------------------------------------------------------------------------
    # Powertrain Codes (P0xxx) - Engine/Transmission/Charging
    # -------------------------------------------------------------------------
    "P0562": {
        "code": "P0562",
        "category": "powertrain",
        "severity": "high",
        "description": "System Voltage Low",
        "description_zh": "系统电压过低",
        "related_ecu": ["BCM", "BMS", "ECM"],
        "related_signals": ["LDCU_PowerMode", "EVSysReadySt"],
        "possible_causes": [
            "Weak 12V battery",
            "Alternator/generator failure",
            "DC-DC converter issue",
            "Excessive parasitic drain",
        ],
        "scenarios": ["forced_off", "auto_poweroff"],
    },
    "P0563": {
        "code": "P0563",
        "category": "powertrain",
        "severity": "high",
        "description": "System Voltage High",
        "description_zh": "系统电压过高",
        "related_ecu": ["BCM", "BMS", "ECM"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "DC-DC converter overcharging",
            "Voltage regulator failure",
            "Battery management system fault",
        ],
        "scenarios": [],
    },
    "P0A1F": {
        "code": "P0A1F",
        "category": "powertrain",
        "severity": "critical",
        "description": "DC/DC Converter Control Module Performance",
        "description_zh": "DC/DC转换器控制模块性能问题",
        "related_ecu": ["DCDC", "BMS"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "DC-DC converter internal fault",
            "Converter thermal protection triggered",
            "Converter control circuit issue",
        ],
        "scenarios": ["auto_poweroff", "forced_off"],
    },
    "P0A7F": {
        "code": "P0A7F",
        "category": "powertrain",
        "severity": "critical",
        "description": "Hybrid Battery Pack Deterioration",
        "description_zh": "高压电池包劣化",
        "related_ecu": ["BMS"],
        "related_signals": ["packSoC", "packSOPCharge", "packSOPDischarge"],
        "possible_causes": [
            "Battery cell degradation",
            "Battery pack aging",
            "Cell balancing issue",
        ],
        "scenarios": ["bms_charging"],
    },
    "P0A80": {
        "code": "P0A80",
        "category": "powertrain",
        "severity": "high",
        "description": "Replace Hybrid/EV Battery Pack",
        "description_zh": "需要更换高压电池包",
        "related_ecu": ["BMS"],
        "related_signals": ["packSoC", "cellTempMax"],
        "possible_causes": [
            "Battery pack end of life",
            "Severe cell degradation",
            "Battery pack damage",
        ],
        "scenarios": ["bms_charging"],
    },
    "P0AA6": {
        "code": "P0AA6",
        "category": "powertrain",
        "severity": "critical",
        "description": "Hybrid Battery Voltage System Isolation Fault",
        "description_zh": "高压电池电压系统隔离故障",
        "related_ecu": ["BMS", "VCU"],
        "related_signals": ["LDCU_PowerMode", "EVSysReadySt"],
        "possible_causes": [
            "High voltage isolation failure",
            "Insulation resistance too low",
            "HV cable damage",
        ],
        "scenarios": ["forced_off"],
    },
    "P0C73": {
        "code": "P0C73",
        "category": "powertrain",
        "severity": "high",
        "description": "Hybrid/EV Battery Temperature Too High",
        "description_zh": "高压电池温度过高",
        "related_ecu": ["BMS", "TMS"],
        "related_signals": ["cellTempMax", "packSOPCharge"],
        "possible_causes": [
            "Battery thermal management failure",
            "Cooling system malfunction",
            "Excessive ambient temperature",
        ],
        "scenarios": ["bms_charging"],
    },
    # -------------------------------------------------------------------------
    # Chassis Codes (C0xxx) - Brake/Steering/Suspension
    # -------------------------------------------------------------------------
    "C0035": {
        "code": "C0035",
        "category": "chassis",
        "severity": "high",
        "description": "Left Front Wheel Speed Circuit Malfunction",
        "description_zh": "左前轮速传感器电路故障",
        "related_ecu": ["ABS", "ESP"],
        "related_signals": ["VehSpd", "BrkPedalSt"],
        "possible_causes": [
            "Wheel speed sensor failure",
            "Sensor wiring issue",
            "Tone ring damage",
        ],
        "scenarios": [],
    },
    "C0040": {
        "code": "C0040",
        "category": "chassis",
        "severity": "high",
        "description": "Right Front Wheel Speed Circuit Malfunction",
        "description_zh": "右前轮速传感器电路故障",
        "related_ecu": ["ABS", "ESP"],
        "related_signals": ["VehSpd", "BrkPedalSt"],
        "possible_causes": [
            "Wheel speed sensor failure",
            "Sensor wiring issue",
            "Tone ring damage",
        ],
        "scenarios": [],
    },
    "C0050": {
        "code": "C0050",
        "category": "chassis",
        "severity": "medium",
        "description": "Left Rear Wheel Speed Circuit Malfunction",
        "description_zh": "左后轮速传感器电路故障",
        "related_ecu": ["ABS", "ESP"],
        "related_signals": ["VehSpd"],
        "possible_causes": ["Wheel speed sensor failure", "Sensor wiring issue"],
        "scenarios": [],
    },
    "C0060": {
        "code": "C0060",
        "category": "chassis",
        "severity": "medium",
        "description": "Right Rear Wheel Speed Circuit Malfunction",
        "description_zh": "右后轮速传感器电路故障",
        "related_ecu": ["ABS", "ESP"],
        "related_signals": ["VehSpd"],
        "possible_causes": ["Wheel speed sensor failure", "Sensor wiring issue"],
        "scenarios": [],
    },
    "C121C": {
        "code": "C121C",
        "category": "chassis",
        "severity": "high",
        "description": "Electronic Brake Control Module Software Performance",
        "description_zh": "电子制动控制模块软件性能问题",
        "related_ecu": ["ABS", "ESP", "BCM"],
        "related_signals": ["BrkPedalSt", "BrkPedalStVD"],
        "possible_causes": [
            "ABS/ESP module software issue",
            "Module needs reprogramming",
            "Internal module fault",
        ],
        "scenarios": ["ble_auth", "forced_off"],
    },
    # -------------------------------------------------------------------------
    # Body Codes (B0xxx) - Airbag/Climate/Lights/Doors
    # -------------------------------------------------------------------------
    "B0070": {
        "code": "B0070",
        "category": "body",
        "severity": "medium",
        "description": "Driver Seatbelt Pretensioner Deployment Controlled",
        "description_zh": "驾驶员安全带预紧器已展开",
        "related_ecu": ["RCM", "BCM"],
        "related_signals": ["DrvSeatOccupancySt"],
        "possible_causes": [
            "Seatbelt pretensioner deployed in crash",
            "Pretensioner circuit issue",
        ],
        "scenarios": [],
    },
    "B0071": {
        "code": "B0071",
        "category": "body",
        "severity": "medium",
        "description": "Passenger Seatbelt Pretensioner Deployment Controlled",
        "description_zh": "乘客安全带预紧器已展开",
        "related_ecu": ["RCM", "BCM"],
        "related_signals": [],
        "possible_causes": [
            "Seatbelt pretensioner deployed in crash",
            "Pretensioner circuit issue",
        ],
        "scenarios": [],
    },
    "B1000": {
        "code": "B1000",
        "category": "body",
        "severity": "medium",
        "description": "Electronic Control Unit Internal Failure",
        "description_zh": "电子控制单元内部故障",
        "related_ecu": ["BCM"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "Body control module internal fault",
            "BCM memory error",
            "BCM needs replacement",
        ],
        "scenarios": ["forced_off"],
    },
    "B1085": {
        "code": "B1085",
        "category": "body",
        "severity": "low",
        "description": "Passenger Door Ajar Switch Circuit Failure",
        "description_zh": "乘客车门未关开关电路故障",
        "related_ecu": ["BCM"],
        "related_signals": ["DriverDoorAjarSt"],
        "possible_causes": [
            "Door ajar switch failure",
            "Wiring issue",
            "Door latch problem",
        ],
        "scenarios": [],
    },
    "B10C2": {
        "code": "B10C2",
        "category": "body",
        "severity": "high",
        "description": "Key Fob Battery Low",
        "description_zh": "遥控钥匙电池电量低",
        "related_ecu": ["RFA", "BCM", "TBOX"],
        "related_signals": ["KeyValidSt", "RKEKeyValidSt"],
        "possible_causes": [
            "Key fob battery depleted",
            "Key fob battery contact issue",
        ],
        "scenarios": ["key_timeout", "ble_auth"],
    },
    "B10D4": {
        "code": "B10D4",
        "category": "body",
        "severity": "critical",
        "description": "Keyless Enter Module Antenna Circuit Short to Ground",
        "description_zh": "无钥匙进入模块天线电路对地短路",
        "related_ecu": ["PEPS", "BCM", "TBOX"],
        "related_signals": ["Flag_BLE", "NFCKeyValidSt", "KeyValidSt"],
        "possible_causes": [
            "PEPS antenna wiring short",
            "PEPS module internal fault",
            "Antenna damage",
        ],
        "scenarios": ["ble_auth", "key_timeout"],
    },
    "B10E0": {
        "code": "B10E0",
        "category": "body",
        "severity": "high",
        "description": "Keyless Start Button Circuit Failure",
        "description_zh": "无钥匙启动按钮电路故障",
        "related_ecu": ["PEPS", "BCM"],
        "related_signals": ["LDCU_PowerMode", "BrkPedalSt"],
        "possible_causes": [
            "Start button switch failure",
            "Start button wiring issue",
            "PEPS module fault",
        ],
        "scenarios": ["ble_auth", "forced_off"],
    },
    "B1428": {
        "code": "B1428",
        "category": "body",
        "severity": "medium",
        "description": "Wiper Park Signal Circuit Failure",
        "description_zh": "雨刮器驻车信号电路故障",
        "related_ecu": ["BCM"],
        "related_signals": [],
        "possible_causes": ["Wiper motor park switch failure", "Wiring issue"],
        "scenarios": [],
    },
    "B1650": {
        "code": "B1650",
        "category": "body",
        "severity": "critical",
        "description": "Seatbelt Buckle Switch Driver Circuit Short to Ground",
        "description_zh": "驾驶员安全带扣开关电路对地短路",
        "related_ecu": ["BCM", "RCM"],
        "related_signals": ["DrvSeatOccupancySt"],
        "possible_causes": [
            "Seatbelt buckle switch failure",
            "Wiring short to ground",
            "BCM input circuit fault",
        ],
        "scenarios": [],
    },
    "B1670": {
        "code": "B1670",
        "category": "body",
        "severity": "high",
        "description": "Battery Module Voltage Out of Range",
        "description_zh": "电池模块电压超出范围",
        "related_ecu": ["BCM", "BMS"],
        "related_signals": ["LDCU_PowerMode"],
        "possible_causes": [
            "12V battery voltage abnormal",
            "DC-DC converter issue",
            "Battery sensor failure",
        ],
        "scenarios": ["forced_off", "auto_poweroff"],
    },
    "B1860": {
        "code": "B1860",
        "category": "body",
        "severity": "medium",
        "description": "Driver Seatbelt Buckle Circuit Open",
        "description_zh": "驾驶员安全带扣电路断路",
        "related_ecu": ["BCM", "RCM"],
        "related_signals": ["DrvSeatOccupancySt"],
        "possible_causes": [
            "Seatbelt buckle switch open circuit",
            "Wiring disconnected",
            "Connector issue",
        ],
        "scenarios": [],
    },
    "B2275": {
        "code": "B2275",
        "category": "body",
        "severity": "high",
        "description": "Steering Wheel Switch Assembly Circuit Failure",
        "description_zh": "方向盘开关组件电路故障",
        "related_ecu": ["BCM", "SCCM"],
        "related_signals": [],
        "possible_causes": [
            "Steering wheel control module fault",
            "Clock spring issue",
            "Wiring problem",
        ],
        "scenarios": [],
    },
    "B2603": {
        "code": "B2603",
        "category": "body",
        "severity": "medium",
        "description": "Headlamp High Beam Relay Circuit Short to Battery",
        "description_zh": "大灯远光继电器电路对电池短路",
        "related_ecu": ["BCM"],
        "related_signals": [],
        "possible_causes": ["High beam relay failure", "Wiring short to power"],
        "scenarios": [],
    },
    "B2610": {
        "code": "B2610",
        "category": "body",
        "severity": "low",
        "description": "Passenger Compartment Lamp Driver Circuit Open",
        "description_zh": "乘客舱灯驱动电路断路",
        "related_ecu": ["BCM"],
        "related_signals": [],
        "possible_causes": ["Interior lamp failure", "Wiring open circuit"],
        "scenarios": [],
    },
    "B2723": {
        "code": "B2723",
        "category": "body",
        "severity": "high",
        "description": "Push Button Start Circuit Performance",
        "description_zh": "一键启动电路性能问题",
        "related_ecu": ["PEPS", "BCM"],
        "related_signals": ["LDCU_PowerMode", "BrkPedalSt"],
        "possible_causes": [
            "Start button intermittent fault",
            "PEPS module fault",
            "Wiring issue",
        ],
        "scenarios": ["ble_auth", "forced_off"],
    },
    "B2799": {
        "code": "B2799",
        "category": "body",
        "severity": "critical",
        "description": "Engine Immobilizer System No Communication",
        "description_zh": "发动机防盗系统无通信",
        "related_ecu": ["IMMO", "BCM", "ECM"],
        "related_signals": ["KeyValidSt", "Flag_BLE", "NFCKeyValidSt"],
        "possible_causes": [
            "Immobilizer module failure",
            "CAN communication issue",
            "Key transponder issue",
            "ECM immobilizer function fault",
        ],
        "scenarios": ["ble_auth", "key_timeout", "forced_off"],
    },
    "B2945": {
        "code": "B2945",
        "category": "body",
        "severity": "high",
        "description": "Security Indicator Circuit Short to Battery",
        "description_zh": "安全指示灯电路对电池短路",
        "related_ecu": ["BCM", "IMMO"],
        "related_signals": ["AlarmSt"],
        "possible_causes": [
            "Security indicator LED failure",
            "Wiring short to power",
            "BCM output driver fault",
        ],
        "scenarios": [],
    },
}


# =============================================================================
# DTC to Scenario Mapping
# =============================================================================

DTC_TO_SCENARIO_MAP: Dict[str, List[str]] = {
    # Network codes
    "U0100": ["remote_on", "forced_off"],
    "U0101": ["forced_off"],
    "U0140": ["ble_auth", "key_timeout", "forced_off"],
    "U0167": ["ble_auth", "key_timeout"],
    "U0214": ["ble_auth", "key_timeout", "remote_on"],
    "U0300": ["remote_on"],
    "U0415": ["ble_auth", "forced_off"],
    "U1000": ["forced_off"],
    "U1201": ["forced_off", "ble_auth"],
    "U1300": ["forced_off"],
    "U1301": ["forced_off"],
    # Powertrain codes
    "P0562": ["forced_off", "auto_poweroff"],
    "P0A1F": ["auto_poweroff", "forced_off"],
    "P0A7F": ["bms_charging"],
    "P0A80": ["bms_charging"],
    "P0AA6": ["forced_off"],
    "P0C73": ["bms_charging"],
    # Chassis codes
    "C121C": ["ble_auth", "forced_off"],
    # Body codes
    "B1000": ["forced_off"],
    "B10C2": ["key_timeout", "ble_auth"],
    "B10D4": ["ble_auth", "key_timeout"],
    "B10E0": ["ble_auth", "forced_off"],
    "B1670": ["forced_off", "auto_poweroff"],
    "B2723": ["ble_auth", "forced_off"],
    "B2799": ["ble_auth", "key_timeout", "forced_off"],
}


# =============================================================================
# DTC Hypothesis Templates
# =============================================================================

DTC_HYPOTHESIS_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "U0100": [
        {"name": "ECM/PCM CAN通信中断", "pct": 65, "cls": "p"},
        {"name": "ECM/PCM供电异常", "pct": 25, "cls": "s"},
        {"name": "CAN总线物理层故障", "pct": 10, "cls": "t"},
    ],
    "U0140": [
        {"name": "BCM CAN通信失败", "pct": 70, "cls": "p"},
        {"name": "BCM供电/接地问题", "pct": 20, "cls": "s"},
        {"name": "CAN总线线束损坏", "pct": 10, "cls": "t"},
    ],
    "U0167": [
        {"name": "防盗模块通信故障", "pct": 60, "cls": "p"},
        {"name": "钥匙认证系统异常", "pct": 30, "cls": "s"},
        {"name": "IMMO-BCM CAN链路问题", "pct": 10, "cls": "t"},
    ],
    "P0562": [
        {"name": "12V蓄电池亏电", "pct": 75, "cls": "p"},
        {"name": "DC-DC转换器故障", "pct": 15, "cls": "s"},
        {"name": "寄生电流过大", "pct": 10, "cls": "t"},
    ],
    "P0C73": [
        {"name": "电池热管理系统故障", "pct": 70, "cls": "p"},
        {"name": "冷却系统工作异常", "pct": 20, "cls": "s"},
        {"name": "环境温度过高", "pct": 10, "cls": "t"},
    ],
    "B10C2": [
        {"name": "遥控钥匙电池电量耗尽", "pct": 90, "cls": "p"},
        {"name": "钥匙电池接触不良", "pct": 10, "cls": "s"},
    ],
    "B10E0": [
        {"name": "启动按钮开关故障", "pct": 60, "cls": "p"},
        {"name": "PEPS模块故障", "pct": 30, "cls": "s"},
        {"name": "启动按钮线束问题", "pct": 10, "cls": "t"},
    ],
    "B2799": [
        {"name": "防盗模块无通信", "pct": 55, "cls": "p"},
        {"name": "钥匙转发器问题", "pct": 30, "cls": "s"},
        {"name": "ECM防盗功能故障", "pct": 15, "cls": "t"},
    ],
    "U1201": [
        {"name": "CAN总线物理层故障", "pct": 70, "cls": "p"},
        {"name": "CAN收发器故障", "pct": 20, "cls": "s"},
        {"name": "总线冲突或短路", "pct": 10, "cls": "t"},
    ],
    "U0214": [
        {"name": "RFA模块通信故障", "pct": 60, "cls": "p"},
        {"name": "遥控无钥匙进入系统故障", "pct": 30, "cls": "s"},
        {"name": "CAN总线线束问题", "pct": 10, "cls": "t"},
    ],
}


# =============================================================================
# DTC Output Templates (Role-adapted HTML)
# =============================================================================

DTC_OUTPUT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "U0100": {
        "owner": """<div class="conc">⚠️ ECM/PCM通信丢失，车辆无法正常上电</div>
<p style="margin-top:8px">车辆检测到与发动机控制模块(ECM)或动力控制模块(PCM)失去通信，这是一个严重的通信故障。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>尝试重启车辆：完全关闭电源，等待30秒后重新上电</div>
  <div class="ai"><div class="an">2</div>检查仪表盘是否有其他故障灯亮起</div>
  <div class="ai"><div class="an">3</div>如问题持续，请立即联系：<span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】U0100 - ECM/PCM CAN通信丢失 (CRITICAL)</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: U0100 | Category: Network | Related: ECM, PCM, TBOX</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>OBD读取ECM/PCM DTC快照，确认通信丢失时间戳</div>
  <div class="ai"><div class="an">P2</div>测量CAN-H/CAN-L电压，确认物理层正常</div>
  <div class="ai"><div class="an">P3</div>检查ECM/PCM供电熔丝和接地连接</div>
  <div class="ai"><div class="an">P4</div>CAN总线终端电阻测量（应为60Ω）</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】车辆检测到发动机控制模块通信异常</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆检测到发动机控制系统通信故障，这是一个需要尽快检查的问题。建议先尝试重启车辆，如果问题持续存在需要到店检测。"</p>""",
    },
    "U0140": {
        "owner": """<div class="conc">⚠️ 车身控制模块(BCM)通信丢失</div>
<p style="margin-top:8px">车辆与车身控制模块失去通信，可能影响钥匙识别、车门控制和上电功能。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>尝试用NFC钥匙卡应急上电</div>
  <div class="ai"><div class="an">2</div>检查车门是否能正常解锁/锁定</div>
  <div class="ai"><div class="an">3</div>如无法上电，请联系救援：<span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】U0140 - BCM CAN通信丢失 (CRITICAL)</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: U0140 | Related Signals: LDCU_PowerMode, KeyValidSt, DriverDoorAjarSt</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>检查BCM供电熔丝和接地</div>
  <div class="ai"><div class="an">P2</div>OBD读取BCM DTC，确认通信丢失模式</div>
  <div class="ai"><div class="an">P3</div>CAN示波器检查BCM节点波形</div>
  <div class="ai"><div class="an">P4</div>检查BCM连接器针脚是否腐蚀/松动</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】车身控制模块通信异常</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆车身控制系统通信出现异常，可能影响上电和门锁功能。建议用NFC钥匙卡尝试上电，如无法解决需要到店检测。"</p>""",
    },
    "P0562": {
        "owner": """<div class="conc">🔋 系统电压过低</div>
<p style="margin-top:8px">车辆检测到12V蓄电池电压不足，可能导致上电困难或自动下电保护。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>尝试启动车辆并行驶20-30分钟为蓄电池充电</div>
  <div class="ai"><div class="an">2</div>如车辆无法上电，需要外接电源辅助</div>
  <div class="ai"><div class="an">3</div>建议到店检测蓄电池健康状况</div>
</div>""",
        "technician": """<div class="conc">【诊断结论】P0562 - 系统电压过低 (HIGH)</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: P0562 | Related ECU: BCM, BMS, ECM | Signals: LDCU_PowerMode</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>测量12V蓄电池电压（静态应>12.4V）</div>
  <div class="ai"><div class="an">P2</div>检查蓄电池CCA容量</div>
  <div class="ai"><div class="an">P3</div>测量DC-DC输出电压（Ready状态应13.5-14.5V）</div>
  <div class="ai"><div class="an">P4</div>检查寄生电流（应<50mA）</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】12V蓄电池电压不足</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆检测到12V蓄电池电压偏低，可能导致上电困难。建议先尝试启动车辆行驶充电，如果车辆无法启动需要联系救援搭电。"</p>""",
    },
    "B10C2": {
        "owner": """<div class="conc">🔑 遥控钥匙电池电量低</div>
<p style="margin-top:8px">检测到遥控钥匙电池电量不足，可能导致无钥匙进入功能失效或钥匙识别困难。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>更换钥匙电池（CR2032型号）</div>
  <div class="ai"><div class="an">2</div>应急时可使用手机App或NFC钥匙卡</div>
  <div class="ai"><div class="an">3</div>将钥匙贴近启动按钮尝试上电</div>
</div>""",
        "technician": """<div class="conc">【诊断结论】B10C2 - 遥控钥匙电池电量低</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: B10C2 | Related ECU: RFA, BCM, TBOX | Signals: KeyValidSt, RKEKeyValidSt</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>检查钥匙电池电压（应>3V）</div>
  <div class="ai"><div class="an">P2</div>测试钥匙RSSI信号强度</div>
  <div class="ai"><div class="an">P3</div>检查是否有备用钥匙可用</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】遥控钥匙电池电量低</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，检测到您的遥控钥匙电池电量不足，建议尽快更换电池（型号CR2032）。临时可以用手机App或NFC钥匙卡应急上电。"</p>""",
    },
    "B2799": {
        "owner": """<div class="conc">🔒 防盗系统通信故障，车辆无法上电</div>
<p style="margin-top:8px">车辆防盗系统检测到通信异常，安全起见阻止了上电操作。这是防盗保护功能正常工作的表现。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>使用备用钥匙尝试上电</div>
  <div class="ai"><div class="an">2</div>尝试用NFC钥匙卡或手机App上电</div>
  <div class="ai"><div class="an">3</div>如仍无法上电，请联系：<span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】B2799 - 防盗系统无通信 (CRITICAL)</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: B2799 | Related ECU: IMMO, BCM, ECM | Signals: KeyValidSt, Flag_BLE, NFCKeyValidSt</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>检查IMMO模块供电和接地</div>
  <div class="ai"><div class="an">P2</div>OBD读取IMMO和ECM防盗状态</div>
  <div class="ai"><div class="an">P3</div>检查钥匙转发器信号</div>
  <div class="ai"><div class="an">P4</div>CAN总线IMMO节点通信测试</div>
  <div class="ai"><div class="an">P5</div>如需重新匹配钥匙，执行IMMO学习程序</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】防盗系统通信异常</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆防盗系统检测到异常，这是安全保护机制。请尝试用备用钥匙或手机App上电，如果问题持续需要到店检测。"</p>""",
    },
    "P0C73": {
        "owner": """<div class="conc">🌡️ 电池温度过高警告</div>
<p style="margin-top:8px">车辆检测到高压电池温度过高，系统已启动保护措施，可能限制充电功率或禁止上电。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>将车辆停在阴凉通风处</div>
  <div class="ai"><div class="an">2</div>等待30分钟让电池自然冷却</div>
  <div class="ai"><div class="an">3</div>避免在高温环境下长时间快充</div>
  <div class="ai"><div class="an">4</div>如反复出现此警告，请联系：<span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】P0C73 - 高压电池温度过高 (HIGH)</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: P0C73 | Related ECU: BMS, TMS | Signals: cellTempMax, packSOPCharge</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>OBD读取BMS所有电芯温度数据</div>
  <div class="ai"><div class="an">P2</div>检查电池冷却系统工作状态</div>
  <div class="ai"><div class="an">P3</div>检查冷却液液位和流量</div>
  <div class="ai"><div class="an">P4</div>检查环境温度和充电条件</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】高压电池温度过高</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆检测到电池温度偏高，系统已启动保护。建议将车停在阴凉处冷却30分钟后再使用。如果问题反复出现，建议预约检测。"</p>""",
    },
    "U1201": {
        "owner": """<div class="conc">⚠️ CAN总线故障，车辆通信系统异常</div>
<p style="margin-top:8px">车辆CAN通信网络出现故障，可能影响多个系统的正常工作。</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>尝试重启车辆系统</div>
  <div class="ai"><div class="an">2</div>注意仪表盘是否有多个故障灯</div>
  <div class="ai"><div class="an">3</div>如车辆无法正常工作，请立即联系：<span class="hi">400-XXX-XXXX</span></div>
</div>""",
        "technician": """<div class="conc">【诊断结论】U1201 - CAN总线关闭 (CRITICAL)</div>
<p style="margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--txd)">DTC: U1201 | Category: Network | All ECU affected</p>
<div class="action-list" style="margin-top:8px">
  <div class="ai"><div class="an">P1</div>CAN-H/CAN-L电压测量（正常2.5V左右）</div>
  <div class="ai"><div class="an">P2</div>终端电阻测量（应为60Ω）</div>
  <div class="ai"><div class="an">P3</div>逐个断开ECU定位故障节点</div>
  <div class="ai"><div class="an">P4</div>示波器检查CAN波形</div>
</div>""",
        "customer_service": """<div class="conc">【系统诊断】车辆通信网络故障</div>
<p style="margin-top:8px;font-style:italic;color:var(--txd)">"您好，车辆检测到通信网络故障，这是一个需要尽快检测的问题。建议尝试重启车辆，如果问题持续需要到店检测。"</p>""",
    },
}
