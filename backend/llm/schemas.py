"""
Pydantic schemas for LLM-based diagnosis.

Defines request/response structures for LLM-powered diagnosis.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import re


class Role(str, Enum):
    """User role for output adaptation."""
    OWNER = "owner"
    TECHNICIAN = "technician"
    CUSTOMER_SERVICE = "customer_service"


class SignalInfo(BaseModel):
    """Vehicle signal information."""
    key: str = Field(description="Signal key (e.g., 'LDCU_PowerMode')")
    value: str = Field(description="Signal value (e.g., '0:Off')")
    label: Optional[str] = Field(default=None, description="Human-readable label")


class DiagnosisRequest(BaseModel):
    """
    Request for LLM-based diagnosis.

    This is the input format passed to the LLM for semantic analysis.
    """
    symptom: str = Field(description="User's symptom description in natural language")
    role: Role = Field(default=Role.OWNER, description="User role for output adaptation")
    signals: List[SignalInfo] = Field(
        default_factory=list,
        description="Vehicle signal values from ECU"
    )
    context: Optional[str] = Field(
        default=None,
        description="Additional context (e.g., vehicle model, weather conditions)"
    )
    dtc_codes: Optional[List[str]] = Field(
        default=None,
        description="DTC (Diagnostic Trouble Code) codes if available"
    )
    activated_knowledge: Optional[Any] = Field(
        default=None,
        description="ActivatedKnowledge from OntologyFetcher for structured prompt injection"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "symptom": "踩刹车按启动按钮，车辆无法上电",
                "role": "owner",
                "signals": [
                    {"key": "LDCU_PowerMode", "value": "0:Off"},
                    {"key": "KeyValidSt", "value": "INVALID"},
                    {"key": "Flag_BLE", "value": "0"}
                ]
            }
        }


class SignalRef(BaseModel):
    """A signal referenced in a reasoning step."""
    key: str = Field(description="Signal key, e.g. 'BLE_Auth_Error'")
    value: str = Field(description="Signal value, e.g. 'AUTH_ERR(0x05)'")
    level: str = Field(
        default="ok",
        pattern=r"^(error|warn|ok)$",
        description="Anomaly level: error | warn | ok"
    )


class ReasoningStep(BaseModel):
    """A single reasoning step in the diagnosis chain."""
    step_number: int = Field(description="Step number (1, 2, 3, ...)")
    title: str = Field(description="Step title")
    body: str = Field(description="Step content/details")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in this step's conclusion"
    )
    confidence_delta: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Change in confidence vs previous step (can be negative)"
    )
    signals_referenced: Optional[List[SignalRef]] = Field(
        default=None,
        description="Signals referenced in this step."
    )
    rules_matched: Optional[List[str]] = Field(
        default=None,
        description="Ontology rule IDs matched in this step, e.g. ['T_1_3', 'T_2_1']"
    )

    @field_validator("rules_matched")
    @classmethod
    def validate_rule_ids(cls, v):
        if v is None:
            return v
        pattern = re.compile(r'^T_\d+_\d+$')
        for rid in v:
            if not pattern.match(rid):
                raise ValueError(f"Invalid rule ID format: {rid!r}. Expected T_N_N")
        return v
    elapsed_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Time spent on this reasoning step in milliseconds (injected by backend)"
    )
    agent: Optional[str] = Field(
        default="llm",
        description="Step source agent: 'llm' | 'ont' | 'output'"
    )


class ConfidenceFactor(BaseModel):
    """A factor contributing to the final confidence score."""
    label: str = Field(description="Factor name (e.g., '症状匹配度')")
    value: float = Field(ge=0.0, le=1.0, description="Factor value (0-1)")
    weight: float = Field(ge=0.0, le=1.0, description="Factor weight in final score")
    explanation: Optional[str] = Field(
        default=None,
        description="Explanation of how this factor was calculated"
    )


class DiagnosticHypothesis(BaseModel):
    """
    A diagnostic hypothesis with root cause and confidence.
    """
    hypothesis_id: str = Field(description="Unique hypothesis identifier")
    rank: int = Field(description="Rank (1 = most likely)")
    root_cause: str = Field(description="Root cause description")
    description: str = Field(description="Detailed explanation")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1)"
    )
    affected_components: List[str] = Field(
        default_factory=list,
        description="List of vehicle components likely affected"
    )
    verification_steps: List[str] = Field(
        default_factory=list,
        description="Recommended verification steps"
    )
    priority: str = Field(
        default="medium",
        description="Priority: 'high', 'medium', 'low'"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "hypothesis_id": "hypo_001",
                "rank": 1,
                "root_cause": "BLE认证失败 - 手机蓝牙钥匙未授权",
                "description": "车辆检测到手机但蓝牙认证失败，KeyValidSt=INVALID，导致无法从Off模式转移到LocalOn模式",
                "confidence": 0.85,
                "affected_components": ["TBOX", "BLE模块", "手机App"],
                "verification_steps": [
                    "检查手机蓝牙是否开启",
                    "确认手机App蓝牙权限",
                    "检查TBOX BLE错误码"
                ],
                "priority": "high"
            }
        }


class DiagnosisResponse(BaseModel):
    """
    Response from LLM-based diagnosis.
    
    This is the structured output format returned by the LLM.
    """
    diagnosis_id: str = Field(description="Unique diagnosis identifier")
    summary: str = Field(description="Brief diagnosis summary")
    
    # Reasoning chain
    reasoning_steps: List[ReasoningStep] = Field(
        default_factory=list,
        description="Chain of reasoning from symptom to conclusion"
    )
    
    # Hypotheses
    primary_hypothesis: Optional[DiagnosticHypothesis] = Field(
        default=None,
        description="Most likely diagnosis"
    )
    secondary_hypotheses: List[DiagnosticHypothesis] = Field(
        default_factory=list,
        description="Alternative hypotheses"
    )
    
    # Confidence
    final_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Final confidence score (0-1)"
    )
    confidence_factors: List[ConfidenceFactor] = Field(
        default_factory=list,
        description="Breakdown of confidence factors"
    )
    
    # Output text (role-adapted)
    output_for_owner: Optional[str] = Field(
        default=None,
        description="User-friendly output for vehicle owner"
    )
    output_for_technician: Optional[str] = Field(
        default=None,
        description="Technical output for service technician"
    )
    output_for_customer_service: Optional[str] = Field(
        default=None,
        description="Output for customer service representative"
    )
    
    # Metadata
    model_used: str = Field(description="LLM model used for diagnosis")
    tokens_used: Optional[int] = Field(
        default=None,
        description="Total tokens used"
    )
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="Processing time in milliseconds"
    )
    
    # Escalation
    escalation_hint: Optional[str] = Field(
        default=None,
        description="Hint for when to escalate to higher support"
    )
    
    def get_output_for_role(self, role: Role) -> str:
        """Get the appropriate output text for the given role."""
        if role == Role.OWNER:
            return self.output_for_owner or self.summary
        elif role == Role.TECHNICIAN:
            return self.output_for_technician or self.summary
        elif role == Role.CUSTOMER_SERVICE:
            return self.output_for_customer_service or self.summary
        return self.summary
    
    def to_html(self, role: Role) -> str:
        """
        Convert diagnosis response to HTML for frontend display.
        
        Args:
            role: Target user role
            
        Returns:
            str: HTML-formatted diagnosis output
        """
        output = self.get_output_for_role(role)
        
        html_parts = [
            f'<div class="conc">{self.summary}</div>',
            f'<p style="margin-top:8px">{output}</p>'
        ]
        
        # Add reasoning steps if available
        if self.reasoning_steps:
            html_parts.append('<div class="reasoning-chain">')
            for step in self.reasoning_steps:
                html_parts.append(
                    f'<div class="rs-step">'
                    f'<div class="rs-title">[{step.step_number}] {step.title}</div>'
                    f'<div class="rs-body">{step.body}</div>'
                    f'</div>'
                )
            html_parts.append('</div>')
        
        # Add verification steps from primary hypothesis
        if self.primary_hypothesis and self.primary_hypothesis.verification_steps:
            html_parts.append('<div class="action-list">')
            for i, step in enumerate(self.primary_hypothesis.verification_steps, 1):
                html_parts.append(f'<div class="ai"><div class="an">{i}</div>{step}</div>')
            html_parts.append('</div>')
        
        # Add confidence display
        conf_pct = int(self.final_confidence * 100)
        conf_color = "var(--grn)" if conf_pct >= 80 else "var(--ylw)" if conf_pct >= 60 else "var(--red)"
        html_parts.append(
            f'<div class="confidence" style="margin-top:12px;color:{conf_color}">'
            f'置信度: {conf_pct}%'
            f'</div>'
        )
        
        # Add escalation hint if available
        if self.escalation_hint:
            html_parts.append(
                f'<div class="escalation" style="margin-top:8px;color:var(--txd);font-size:11px">'
                f'{self.escalation_hint}'
                f'</div>'
            )
        
        return "".join(html_parts)
    
    class Config:
        json_schema_extra = {
            "example": {
                "diagnosis_id": "diag_20240315_001",
                "summary": "BLE认证失败导致无法上电",
                "reasoning_steps": [
                    {
                        "step_number": 1,
                        "title": "症状解析",
                        "body": "用户描述：踩刹车按启动按钮，车辆无法上电。当前电源模式：Off",
                        "confidence": 0.95
                    },
                    {
                        "step_number": 2,
                        "title": "信号分析",
                        "body": "KeyValidSt=INVALID, Flag_BLE=0, 表明蓝牙钥匙未通过认证",
                        "confidence": 0.90
                    },
                    {
                        "step_number": 3,
                        "title": "规则匹配",
                        "body": "符合SWRL Rule R-2: 有效钥匙+刹车按下 → LocalOn，但KeyValidSt=INVALID阻断此路径",
                        "confidence": 0.88
                    }
                ],
                "primary_hypothesis": {
                    "hypothesis_id": "hypo_001",
                    "rank": 1,
                    "root_cause": "BLE认证失败 - 手机蓝牙钥匙未授权",
                    "confidence": 0.85,
                    "verification_steps": [
                        "检查手机蓝牙是否开启",
                        "确认手机App蓝牙权限",
                        "重新配对蓝牙钥匙"
                    ],
                    "priority": "high"
                },
                "final_confidence": 0.85,
                "output_for_owner": "手机蓝牙钥匙认证失败，请检查手机蓝牙设置并确保App已授权蓝牙权限。",
                "model_used": "internal-llm-v1"
            }
        }


# Backward compatibility with existing code
class Hypothesis(BaseModel):
    """Backward-compatible hypothesis model."""
    name: str
    pct: int
    cls: str  # "p" (primary), "s" (secondary), "t" (tertiary)


class ConfFactor(BaseModel):
    """Backward-compatible confidence factor."""
    label: str
    val: float
    display: str


class Rule(BaseModel):
    """Backward-compatible rule model."""
    id: str
    text: str
    src: str
    conf: str
