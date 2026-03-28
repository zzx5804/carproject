"""Agents module for the multi-agent diagnosis system."""
from models import AgentID
from agents.base import BaseAgent, AgentFactory
from agents.orchestrator import OrchestratorAgent
from agents.symptom_parser import SymptomParserAgent
from agents.ontology_fetcher import OntologyFetcherAgent
from agents.rule_engine import RuleEngineAgent
from agents.confidence_calc import ConfidenceCalcAgent
from agents.output_adapter import OutputAdapterAgent
from agents.signal_recommender import SignalRecommenderAgent

# Register all agents
AgentFactory.register(AgentID.ORCH, OrchestratorAgent)
AgentFactory.register(AgentID.SYM, SymptomParserAgent)
AgentFactory.register(AgentID.ONT, OntologyFetcherAgent)
AgentFactory.register(AgentID.RULE, RuleEngineAgent)
AgentFactory.register(AgentID.CONF, ConfidenceCalcAgent)
AgentFactory.register(AgentID.OUT, OutputAdapterAgent)
AgentFactory.register(AgentID.SIG, SignalRecommenderAgent)

__all__ = [
    "BaseAgent",
    "AgentFactory",
    "OrchestratorAgent",
    "SymptomParserAgent",
    "OntologyFetcherAgent",
    "RuleEngineAgent",
    "ConfidenceCalcAgent",
    "OutputAdapterAgent",
    "SignalRecommenderAgent",
]
