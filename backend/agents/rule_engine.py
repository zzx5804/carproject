"""
RuleEngine Agent - Matches and executes diagnostic rules.
"""

from typing import List, Dict, Any
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, Rule, Hypothesis, ReasoningStep, AgentState
from diagnosis_knowledge import RULES, HYPOTHESIS_TEMPLATES, SCENARIO_RULES_MAP
from scenario_detector import get_scenario_detector


class RuleEngineAgent(BaseAgent):
    """
    Rule Engine Agent.
    
    Responsibilities:
    - Match symptoms to diagnostic rules
    - Generate hypotheses
    - Execute rule chains
    """
    
    def __init__(self, agent_id: AgentID = AgentID.RULE):
        super().__init__(agent_id)
        self._scenario_detector = get_scenario_detector()
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Match rules and generate hypotheses."""
        logger.info("RuleEngine processing...")
        
        await self.update_status(AgentState.RUNNING, 0)
        
        # Determine which rules to apply based on scenario
        scenario = self._detect_scenario_from_context(context)
        
        # Get applicable rules
        applicable_rules = self._get_applicable_rules(scenario)
        
        # Send rule matches to frontend
        total_rules = len(applicable_rules)
        for i, rule_def in enumerate(applicable_rules):
            await self.delay(280)
            rule = Rule(**rule_def)
            context.matched_rules.append(rule)
            
            await self.send({
                "type": "rule_matched",
                "rule": rule_def
            })
            
            await self.update_status(AgentState.RUNNING, int((i + 1) / total_rules * 60))
        
        # Generate hypotheses
        hypotheses = self._get_hypotheses(scenario)
        
        # Send hypotheses to frontend
        for hypo in hypotheses:
            await self.delay(250)
            context.hypotheses.append(Hypothesis(**hypo))
            
            await self.send({
                "type": "hypothesis",
                "hypo": hypo
            })
        
        # Update context
        await self.send_msg_bus("conf", [
            {"k": "结果", "v": "规则匹配完成", "cls": "g"},
            {"k": "规则数", "v": f"{len(applicable_rules)}条"},
            {"k": "假设", "v": f"{len(hypotheses)}个"}
        ])
        
        await self.animate_wire("conf")
        
        await self.update_status(AgentState.DONE, 100)
        
        return context
    
    def _detect_scenario_from_context(self, context: DiagnosisContext) -> str:
        """Detect scenario from context using ScenarioDetector."""
        return self._scenario_detector.detect(context.symptom)
    
    def _get_applicable_rules(self, scenario: str) -> List[Dict]:
        """Get applicable rules for the scenario."""
        rule_ids = SCENARIO_RULES_MAP.get(scenario, ["T_1_2"])
        return [RULES[rid] for rid in rule_ids if rid in RULES]
    
    def _get_hypotheses(self, scenario: str) -> List[Dict]:
        """Get hypotheses for the scenario."""
        return HYPOTHESIS_TEMPLATES.get(scenario, [
            {"name": "待进一步诊断", "pct": 50, "cls": "p"},
            {"name": "需现场检测", "pct": 50, "cls": "s"}
        ])
