"""
Orchestrator Agent - Coordinates the diagnosis pipeline.

Supports two execution modes:
1. LLM Mode (default): Single LLM agent handles entire diagnosis
2. Legacy Mode: Multi-agent pipeline with separate agents for each phase

DTC Integration:
- If DTC codes are provided, DTCAgent runs first to analyze fault codes
- DTC analysis enriches context with related scenarios and hypotheses
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, AgentState

# Agent execution timeout in seconds
AGENT_TIMEOUT_SECONDS = 30


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent.
    
    Responsibilities:
    - Initialize and coordinate the diagnosis pipeline
    - Manage agent execution order
    - Handle error recovery
    - Send final pipeline completion message
    
    Execution Modes:
    - LLM Mode: Uses single LLMDiagnosisAgent for entire diagnosis
    - Legacy Mode: Uses traditional multi-agent pipeline
    
    DTC Support:
    - If DTC codes are provided, runs DTCAgent first
    - DTC analysis can trigger scenario detection
    """
    
    def __init__(self, agent_id: AgentID = AgentID.ORCH, use_llm: bool = True):
        super().__init__(agent_id)
        self.agents: Dict[AgentID, BaseAgent] = {}
        self.use_llm = use_llm  # Default to LLM mode
    
    def register_agent(self, agent: BaseAgent):
        """Register another agent for orchestration."""
        self.agents[agent.agent_id] = agent
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Orchestrate the diagnosis pipeline."""
        logger.info(f"Orchestrator starting pipeline (LLM mode: {self.use_llm})...")
        
        await self.update_status(AgentState.RUNNING, 0)
        
        # Build initial message with DTC info if present
        initial_msg = [
            {"k": "任务", "v": "启动诊断 Pipeline"},
            {"k": "模式", "v": "LLM智能诊断" if self.use_llm else "规则推理"},
            {"k": "症状", "v": context.symptom[:30] + "..." if len(context.symptom) > 30 else context.symptom},
            {"k": "角色", "v": context.role.value if hasattr(context.role, 'value') else str(context.role)}
        ]
        
        # Add DTC info if present
        if context.dtc_codes:
            dtc_summary = ", ".join(context.dtc_codes[:3])
            if len(context.dtc_codes) > 3:
                dtc_summary += f" (+{len(context.dtc_codes) - 3})"
            initial_msg.append({"k": "DTC故障码", "v": dtc_summary, "cls": "e"})
        
        # Send initial message
        await self.send_msg_bus("ALL", initial_msg)
        
        await self.delay(500)
        await self.update_status(AgentState.RUNNING, 10)
        
        # Phase 0: DTC Analysis (if DTC codes provided)
        if context.dtc_codes:
            await self._execute_dtc_phase(context)
            await self.update_status(AgentState.RUNNING, 25)
        
        if self.use_llm:
            # LLM Mode: Single agent handles entire diagnosis
            context = await self._execute_llm_pipeline(context)
        else:
            # Legacy Mode: Multi-agent pipeline
            context = await self._execute_legacy_pipeline(context)
        
        # Pipeline complete
        await self.send({
            "type": "pipeline_done"
        })
        
        # Final status
        await self.send_msg_bus("ALL", [
            {"k": "状态", "v": "Pipeline 执行完成 ✓", "cls": "g"},
            {"k": "置信度", "v": f"{context.final_confidence}%", "cls": "g"}
        ])
        
        await self.update_status(AgentState.DONE, 100)
        
        logger.info(f"Pipeline complete. Final confidence: {context.final_confidence}%")
        
        return context
    
    async def _execute_dtc_phase(self, context: DiagnosisContext) -> None:
        """Execute DTC analysis phase if DTC codes are provided."""
        if AgentID.DTC not in self.agents:
            logger.warning("DTC agent not registered, skipping DTC phase")
            return
        
        dtc_agent = self.agents[AgentID.DTC]
        
        await self.send_msg_bus("dtc", [
            {"k": "指令", "v": "PARSE_DTC"},
            {"k": "DTC数量", "v": str(len(context.dtc_codes))}
        ])
        
        await self.animate_wire("dtc")
        
        try:
            await dtc_agent.run(context)
        except Exception as e:
            logger.warning(f"DTC agent failed ({type(e).__name__}): {e}")
            await dtc_agent.update_status(AgentState.ERROR)
            # Continue with pipeline even if DTC fails
    
    async def _execute_llm_pipeline(self, context: DiagnosisContext) -> DiagnosisContext:
        """Execute LLM-based diagnosis pipeline."""
        
        # Check if LLM agent is registered
        if AgentID.LLM not in self.agents:
            logger.warning("LLM agent not registered, falling back to legacy pipeline")
            return await self._execute_legacy_pipeline(context)
        
        # When use_ontology=True, run SymptomParser then OntologyFetcher first so that
        # context.activated_knowledge is populated before the LLM agent runs.
        if getattr(context, "use_ontology", False):
            await self._execute_phase("sym", context)
            await self._execute_phase("ont", context)

        llm_agent = self.agents[AgentID.LLM]

        # Execute LLM agent (handles entire diagnosis)
        await self.send_msg_bus("llm", [
            {"k": "指令", "v": "LLM_DIAGNOSIS"},
            {"k": "输入", "v": context.symptom[:50] + "..."}
        ])
        
        await self.animate_wire("llm")
        
        try:
            context = await llm_agent.run(context)
        except Exception as e:
            logger.warning(f"LLM agent failed ({type(e).__name__}): {e}")
            await llm_agent.update_status(AgentState.ERROR)
            # Fall back to legacy pipeline
            logger.info("Falling back to legacy pipeline")
            return await self._execute_legacy_pipeline(context)
        
        return context
    
    async def _execute_legacy_pipeline(self, context: DiagnosisContext) -> DiagnosisContext:
        """Execute legacy multi-agent pipeline."""
        
        # Phase 1: SymptomParser
        await self._execute_phase("sym", context)
        
        # Phase 2: OntologyFetcher (parallel with RuleEngine)
        await self._execute_phase("ont", context)
        
        # Phase 3: RuleEngine (includes hypothesis generation)
        await self._execute_phase("rule", context)
        
        # Phase 3.5: SignalRecommender (after rule engine, before confidence)
        await self._execute_phase("sig", context)
        
        # Phase 4: ConfidenceCalc
        await self._execute_phase("conf", context)
        
        # Phase 5: OutputAdapter
        await self._execute_phase("out", context)
        
        return context
    
    async def _execute_phase(self, phase: str, context: DiagnosisContext):
        """Execute a specific pipeline phase."""
        
        # Map phase to agent
        phase_map = {
            "dtc": AgentID.DTC,
            "sym": AgentID.SYM,
            "ont": AgentID.ONT,
            "rule": AgentID.RULE,
            "sig": AgentID.SIG,
            "conf": AgentID.CONF,
            "out": AgentID.OUT
        }
        
        agent_id = phase_map.get(phase)
        if not agent_id or agent_id not in self.agents:
            logger.warning(f"No agent registered for phase: {phase}")
            return
        
        agent = self.agents[agent_id]
        
        # Send instruction to agent
        instruction_map = {
            "dtc": [{"k": "指令", "v": "PARSE_DTC"}, {"k": "DTC数量", "v": str(len(context.dtc_codes)) if context.dtc_codes else "0"}],
            "sym": [{"k": "指令", "v": "PARSE_SYMPTOM"}, {"k": "payload", "v": context.symptom[:40] + "..."}],
            "ont": [{"k": "指令", "v": "FETCH_SIGNALS"}, {"k": "层级", "v": "L1:LDCU / L2:TBOX / L3:ECU"}],
            "rule": [{"k": "指令", "v": "MATCH_RULES"}, {"k": "输入", "v": "症状+信号"}],
            "sig": [{"k": "指令", "v": "RECOMMEND_SIGNALS"}, {"k": "场景", "v": "检测场景"}],
            "conf": [{"k": "指令", "v": "CALCULATE_CONFIDENCE"}, {"k": "输入", "v": "规则+假设"}],
            "out": [{"k": "指令", "v": "ADAPT_OUTPUT"}, {"k": "角色", "v": context.role.value if hasattr(context.role, 'value') else str(context.role)}]
        }
        
        await self.send_msg_bus(phase, instruction_map.get(phase, []))
        
        # Animate wire to agent
        await self.animate_wire(phase)
        
        # Execute agent with timeout
        try:
            context = await asyncio.wait_for(
                agent.run(context),
                timeout=AGENT_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"Agent {phase} timed out after {AGENT_TIMEOUT_SECONDS}s")
            await agent.update_status(AgentState.ERROR)
            raise TimeoutError(f"Agent {phase} execution timed out after {AGENT_TIMEOUT_SECONDS}s")
        except Exception as e:
            logger.error(f"Agent {phase} failed ({type(e).__name__}): {e}")
            await agent.update_status(AgentState.ERROR)
            raise
        
        # Update progress
        progress_map = {
            "dtc": 25,  # DTC phase runs before symptom parser
            "sym": 40,
            "ont": 55,
            "rule": 70,
            "sig": 77,  # After rule (70), before conf (85)
            "conf": 85,
            "out": 95
        }
        await self.update_status(AgentState.RUNNING, progress_map.get(phase, 50))
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all registered agents."""
        for agent in self.agents.values():
            await agent.send(message)
