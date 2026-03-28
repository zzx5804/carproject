"""
Data models for the multi-agent diagnosis system.
Defines Pydantic models for WebSocket messages and internal data structures.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# Enums
# =============================================================================


class AgentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class AgentID(str, Enum):
    ORCH = "orch"
    SYM = "sym"
    ONT = "ont"
    RULE = "rule"
    CONF = "conf"
    OUT = "out"
    LLM = "llm"  # LLM-powered diagnosis agent
    DTC = "dtc"  # DTC-based diagnosis agent
    SIG = "sig"  # Signal recommendation agent


class Role(str, Enum):
    OWNER = "owner"
    TECHNICIAN = "technician"
    CUSTOMER_SERVICE = "customer_service"


class SignalPriority(str, Enum):
    """Signal recommendation priority."""

    REQUIRED = "required"
    OPTIONAL = "optional"


# =============================================================================
# DTC Enums
# =============================================================================


class DTCCategory(str, Enum):
    """DTC category based on SAE J2012 / ISO 15031-6."""

    POWERTRAIN = "powertrain"  # P0xxx, P1xxx - Engine/Transmission/Emissions
    CHASSIS = "chassis"  # C0xxx, C1xxx - ABS/Steering/Suspension
    BODY = "body"  # B0xxx, B1xxx - Airbag/Climate/Lights
    NETWORK = "network"  # U0xxx, U1xxx - CAN/LIN Communication


class DTCSeverity(str, Enum):
    """DTC severity level."""

    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # Service soon
    MEDIUM = "medium"  # Attention needed
    LOW = "low"  # Informational


class DTCParsedInfo(BaseModel):
    """Parsed DTC information following SAE J2012 / ISO 15031-6."""

    code: str  # "U0100"
    category: DTCCategory  # powertrain/chassis/body/network
    severity: DTCSeverity  # critical/high/medium/low
    description: str  # "Lost Communication with ECM/PCM"
    description_zh: str  # Chinese description
    related_ecu: List[str] = Field(default_factory=list)  # ["ECM", "PCM"]
    related_signals: List[str] = Field(default_factory=list)  # ["LDCU_PowerMode", ...]
    possible_causes: List[str] = Field(
        default_factory=list
    )  # ["CAN bus failure", "ECM power issue"]
    hypothesis: List["Hypothesis"] = Field(default_factory=list)  # Forward reference


# =============================================================================
# WebSocket Request Models
# =============================================================================


class StartRequest(BaseModel):
    """Client request to start diagnosis pipeline."""

    type: Literal["start"] = "start"
    symptom: str = ""
    dtc_codes: List[str] = Field(
        default_factory=list, description="List of DTC codes, e.g., ['U0100', 'P0562']"
    )
    role: Role = Role.OWNER
    signals: Dict[str, str] = Field(default_factory=dict)


# =============================================================================
# WebSocket Response Models
# =============================================================================


class AgentStatusMessage(BaseModel):
    """Agent status update message."""

    type: Literal["agent_status"] = "agent_status"
    agent: str
    state: AgentState
    progress: Optional[int] = None


class MsgPair(BaseModel):
    """Key-value pair for message bus."""

    k: str
    v: str
    cls: Optional[str] = None  # CSS class: "g" (green), "e" (error), "w" (warning)


class MsgBusMessage(BaseModel):
    """Message bus update."""

    type: Literal["msg_bus"] = "msg_bus"
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    pairs: List[MsgPair]

    class Config:
        populate_by_name = True


class WireAnimateMessage(BaseModel):
    """Wire animation trigger."""

    type: Literal["wire_animate"] = "wire_animate"
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")

    class Config:
        populate_by_name = True


class ReasoningStep(BaseModel):
    """Single reasoning step."""

    title: str
    body: str


class ReasoningStepMessage(BaseModel):
    """Reasoning step update."""

    type: Literal["reasoning_step"] = "reasoning_step"
    step: ReasoningStep


class OntoSummaryMessage(BaseModel):
    """Ontology summary message."""

    type: Literal["onto_summary"] = "onto_summary"
    counts: Dict[str, int] = Field(default_factory=dict)
    summary: Optional[str] = None
    html: Optional[str] = None


class Rule(BaseModel):
    """Matched rule."""

    id: str
    text: str
    src: str
    conf: str


class RuleMatchedMessage(BaseModel):
    """Rule matched message."""

    type: Literal["rule_matched"] = "rule_matched"
    rule: Rule


class Hypothesis(BaseModel):
    """Diagnosis hypothesis."""

    name: Optional[str] = None
    pct: Optional[int] = None
    cls: str = "p"  # "p" (primary), "s" (secondary), "t" (tertiary)
    desc: Optional[str] = None
    conf: Optional[float] = None
    factors: List[str] = Field(default_factory=list)


class HypothesisMessage(BaseModel):
    """Hypothesis message."""

    type: Literal["hypothesis"] = "hypothesis"
    hypothesis: Optional[Hypothesis] = None
    hypo: Optional[Hypothesis] = None

    @property
    def payload(self) -> Optional[Hypothesis]:
        """Return hypothesis payload, supporting legacy field name."""

        return self.hypothesis or self.hypo


class ConfFactor(BaseModel):
    """Confidence factor."""

    label: str
    val: float
    display: str


class ConfFactorsMessage(BaseModel):
    """Confidence factors message."""

    type: Literal["conf_factors"] = "conf_factors"
    factors: List[ConfFactor]


class ConfFinalMessage(BaseModel):
    """Final confidence message."""

    type: Literal["conf_final"] = "conf_final"
    confidence: int
    level: Optional[str] = None


class RoleOutput(BaseModel):
    """Role-adapted diagnosis output."""

    text: str
    role: str
    escalation: Optional[bool] = None
    hint: Optional[str] = None


class OutputMessage(BaseModel):
    """Output message."""

    type: Literal["output"] = "output"
    html: Optional[str] = None
    output: Optional[RoleOutput] = None
    escalation: Optional[str] = None


class BackendStatusMessage(BaseModel):
    """Backend readiness status for frontend HUD."""

    type: Literal["backend_status"] = "backend_status"
    status: str
    ontology_loaded: bool = False
    pipeline_ready: bool = False
    ontology_stats: Dict[str, int] = Field(default_factory=dict)
    mode: Optional[str] = None


class PipelineDoneMessage(BaseModel):
    """Pipeline completion message."""

    type: Literal["pipeline_done"] = "pipeline_done"
    status: Optional[str] = None


class ErrorMessage(BaseModel):
    """Error message."""

    type: Literal["error"] = "error"
    message: str


class SignalRecommendation(BaseModel):
    """Signal recommendation for diagnosis."""

    signal_name: str  # e.g., "LDCU_PowerMode"
    description_zh: str  # Chinese description
    description_en: str  # English description
    reason: str  # Why this signal is needed
    priority: SignalPriority  # required or optional
    read_method: str  # How to read (OBD/诊断仪/仪表)


class SignalRecommendationMessage(BaseModel):
    """Signal recommendation message."""

    type: Literal["signal_recommendations"] = "signal_recommendations"
    recommendations: List[SignalRecommendation]
    scenario: str  # Which scenario this applies to


# =============================================================================
# Ontology Activation Models
# =============================================================================


class ActivatedNode(BaseModel):
    """An ontology node activated during diagnosis."""

    node_id: str          # e.g. "T_1_2"
    node_type: str        # "rule" | "class" | "individual"
    label_zh: str         # e.g. "Disable跳转至Enable"
    confidence: float     # 0.0–1.0
    source_triple: str    # e.g. "rules_model.ttl#ruleT_1_2"


class ActivatedKnowledge(BaseModel):
    """Structured ontology knowledge activated for this diagnosis."""

    activated_rules: List[ActivatedNode] = Field(default_factory=list)
    activated_classes: List[ActivatedNode] = Field(default_factory=list)
    signal_mappings: Dict[str, str] = Field(default_factory=dict)
    sparql_queries: List[str] = Field(default_factory=list)


class OntoActivatedMessage(BaseModel):
    """WebSocket message: ontology nodes activated."""

    type: Literal["onto_activated"] = "onto_activated"
    nodes: List[ActivatedNode] = Field(default_factory=list)
    signal_mappings: Dict[str, str] = Field(default_factory=dict)


# Union type for all response messages
ResponseMessage = (
    AgentStatusMessage
    | MsgBusMessage
    | WireAnimateMessage
    | ReasoningStepMessage
    | OntoSummaryMessage
    | RuleMatchedMessage
    | HypothesisMessage
    | ConfFactorsMessage
    | ConfFinalMessage
    | OutputMessage
    | BackendStatusMessage
    | PipelineDoneMessage
    | SignalRecommendationMessage
    | OntoActivatedMessage
    | ErrorMessage
)


# =============================================================================
# Internal Data Models
# =============================================================================


class VehicleSignals(BaseModel):
    """Vehicle signal values from frontend."""

    ldcu_power_mode: Optional[int] = Field(None, alias="LDCU_PowerMode")
    ldcu_power_on_source: Optional[int] = Field(None, alias="LDCU_PowerONSource")
    ldcu_power_off_source: Optional[int] = Field(None, alias="LDCU_PowerOFFSource")
    rdcu_power_st: Optional[int] = Field(None, alias="RDCU_PowerSt")
    key_valid_st: Optional[int] = Field(None, alias="KeyValidSt")
    alarm_st: Optional[int] = Field(None, alias="AlarmSt")
    brk_pedal_st: Optional[int] = Field(None, alias="BrkPedalSt")
    brk_pedal_st_vd: Optional[int] = Field(None, alias="BrkPedalStVD")
    driver_door_ajar_st: Optional[int] = Field(None, alias="DriverDoorAjarSt")
    drv_seat_occupancy_st: Optional[int] = Field(None, alias="DrvSeatOccupancySt")
    gearlev: Optional[int] = Field(None, alias="Gearlev")
    veh_spd: Optional[float] = Field(None, alias="VehSpd")
    flag_ble: Optional[int] = Field(None, alias="Flag_BLE")
    flag_4g_ready: Optional[int] = Field(None, alias="Flag_4GReady")
    flag_nfc: Optional[int] = Field(None, alias="Flag_NFC")
    ccu_diagnostic_st: Optional[int] = Field(None, alias="CCU_DiagnosticSt")
    xpu_power_req: Optional[int] = Field(None, alias="XPU_PowerReq")
    emergency_power_off_sw_st: Optional[int] = Field(
        None, alias="EmergencyPowerOffSwSt"
    )
    nfc_key_valid_st: Optional[int] = Field(None, alias="NFCKeyValidSt")
    ble_key_valid_st: Optional[int] = Field(None, alias="BLEKeyValidSt")
    rke_key_valid_st: Optional[int] = Field(None, alias="RKEKeyValidSt")
    uwb_key_valid_st: Optional[int] = Field(None, alias="UWBKeyValidSt")
    digital_key_valid_st: Optional[int] = Field(None, alias="DigitalKeyValidSt")
    key_searching_st: Optional[int] = Field(None, alias="KeySearchingSt")
    ota_power_on_valid: Optional[int] = Field(None, alias="OTAPowerOnValid")
    ev_sys_ready_st: Optional[int] = Field(None, alias="EVSysReadySt")

    class Config:
        populate_by_name = True


class DiagnosisContext(BaseModel):
    """Context for diagnosis pipeline."""

    symptom: str
    role: Role
    signals: Dict[str, str]
    vehicle_signals: Optional[VehicleSignals] = None

    # DTC information
    dtc_codes: List[str] = Field(default_factory=list, description="List of DTC codes")
    parsed_dtc_info: List[DTCParsedInfo] = Field(
        default_factory=list, description="Parsed DTC information"
    )

    # Parsed information
    parsed_symptoms: List[str] = Field(default_factory=list)
    relevant_signals: Dict[str, Any] = Field(default_factory=dict)
    signal_recommendations: List[SignalRecommendation] = Field(default_factory=list)

    # Reasoning results
    reasoning_steps: List[ReasoningStep] = Field(default_factory=list)
    matched_rules: List[Rule] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)

    # Confidence
    confidence_factors: List[ConfFactor] = Field(default_factory=list)
    final_confidence: int = 0

    # Output
    output_html: str = ""
    escalation_hint: Optional[str] = None

    # Ontology data
    ontology_classes: Dict[str, Any] = Field(default_factory=dict)
    ontology_properties: Dict[str, Any] = Field(default_factory=dict)
    ontology_individuals: Dict[str, Any] = Field(default_factory=dict)

    # Activated ontology knowledge (populated by OntologyFetcher)
    activated_knowledge: Optional[ActivatedKnowledge] = None
