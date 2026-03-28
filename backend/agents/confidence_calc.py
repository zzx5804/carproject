"""
ConfidenceCalc Agent - Calculates diagnosis confidence.
"""

from typing import List, Dict
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, ConfFactor, AgentState


class ConfidenceCalcAgent(BaseAgent):
    """
    Confidence Calculator Agent.
    
    Responsibilities:
    - Calculate overall confidence based on multiple factors
    - Send confidence factors to frontend
    - Generate final confidence score
    """
    
    # Confidence factor weights
    FACTOR_WEIGHTS = {
        "symptom_match": 0.30,  # Symptom matching degree
        "rule_confidence": 0.35,  # Rule confidence
        "data_quality": 0.20,   # Signal data quality
        "hierarchy": 0.05,      # Ontology hierarchy completeness
        "evidence": 0.10        # Evidence/log support
    }
    
    def __init__(self, agent_id: AgentID = AgentID.CONF):
        super().__init__(agent_id)
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Calculate confidence factors."""
        logger.info("ConfidenceCalc processing...")
        
        await self.update_status(AgentState.RUNNING, 0)
        
        # Calculate factors
        factors = await self._calculate_factors(context)
        
        # Send factors to frontend
        total_factors = len(factors)
        for i, factor in enumerate(factors):
            await self.delay(180)
            await self.send({
                "type": "conf_factors",
                "factors": [factor]
            })
            await self.update_status(AgentState.RUNNING, int((i + 1) / total_factors * 70))
        
        # Calculate final confidence
        final_confidence = self._calculate_final_confidence(factors)
        context.final_confidence = final_confidence
        context.confidence_factors = factors
        
        # Send final confidence
        await self.send({
            "type": "conf_final",
            "confidence": final_confidence
        })
        
        # Notify
        level = "HIGH" if final_confidence >= 80 else "MEDIUM"
        await self.send_msg_bus("out", [
            {"k": "置信度", "v": f"{final_confidence}%", "cls": "g"},
            {"k": "等级", "v": level}
        ])
        
        await self.animate_wire("out")
        
        await self.update_status(AgentState.DONE, 100)
        
        return context
    
    async def _calculate_factors(self, context: DiagnosisContext) -> List[ConfFactor]:
        """Calculate confidence factors based on context."""
        
        # Factor 1: Symptom matching
        symptom_match = 0.90
        if len(context.parsed_symptoms) > 3:
            symptom_match = 0.95
        elif len(context.parsed_symptoms) > 1:
            symptom_match = 0.85
        
        # Factor 2: Rule confidence
        rule_conf = 0.90
        if context.matched_rules:
            rule_confs = [float(r.conf) for r in context.matched_rules]
            rule_conf = sum(rule_confs) / len(rule_confs)
        
        # Factor 3: Data quality
        data_quality = 0.85
        signal_count = len([v for v in context.signals.values() if v and v != "— N/A"])
        if signal_count > 10:
            data_quality = 0.92
        elif signal_count > 5:
            data_quality = 0.88
        
        # Factor 4: Hierarchy (ontology coverage)
        hierarchy = 0.95  # Good coverage from ontology parser
        
        # Factor 5: Evidence/log support
        evidence = 0.90
        if context.hypotheses:
            primary_count = sum(1 for h in context.hypotheses if h.cls == "p")
            if primary_count >= 1:
                evidence = 0.92
        
        return [
            ConfFactor(
                label="症状匹配度(NLP)",
                val=symptom_match,
                display=f"{symptom_match:.2f}"
            ),
            ConfFactor(
                label="规则可信度(FRS)",
                val=rule_conf,
                display=f"{rule_conf:.2f}"
            ),
            ConfFactor(
                label="数据质量(ECU)",
                val=data_quality,
                display=f"{data_quality:.2f}"
            ),
            ConfFactor(
                label="层级修正",
                val=hierarchy,
                display="+5%"
            ),
            ConfFactor(
                label="日志佐证",
                val=evidence,
                display="+3%"
            )
        ]
    
    def _calculate_final_confidence(self, factors: List[ConfFactor]) -> int:
        """Calculate final confidence score."""
        # Weighted sum
        total = 0
        for factor in factors:
            weight = self.FACTOR_WEIGHTS.get(factor.label, 0.1)
            total += factor.val * weight * 100
        
        # Round to nearest integer
        confidence = int(round(total))
        
        # Cap at 100
        return min(confidence, 100)
