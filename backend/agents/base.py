"""
Base agent class for the multi-agent diagnosis system.
Provides common functionality and interface for all agents.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional, Any, Dict
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from models import DiagnosisContext, AgentState, AgentID


# =============================================================================
# Message Sender Type
# =============================================================================

MessageSender = Callable[[Dict[str, Any]], Awaitable[None]]


# =============================================================================
# Base Agent
# =============================================================================

class BaseAgent(ABC):
    """
    Abstract base class for all diagnosis agents.
    
    Each agent:
    - Has a unique ID
    - Can send messages to the WebSocket client
    - Can update its status
    - Processes the diagnosis context
    """
    
    def __init__(self, agent_id: AgentID):
        self.agent_id = agent_id
        self.state = AgentState.IDLE
        self.progress = 0
        self._send_message: Optional[MessageSender] = None
        self._context: Optional[DiagnosisContext] = None
    
    def set_sender(self, sender: MessageSender):
        """Set the message sender function."""
        self._send_message = sender
    
    def set_context(self, context: DiagnosisContext):
        """Set the diagnosis context."""
        self._context = context
    
    async def send(self, message: Dict[str, Any]):
        """Send a message to the WebSocket client."""
        if self._send_message:
            await self._send_message(message)
    
    async def update_status(self, state: AgentState, progress: Optional[int] = None):
        """Update agent status and notify client."""
        self.state = state
        if progress is not None:
            self.progress = progress
        
        await self.send({
            "type": "agent_status",
            "agent": self.agent_id.value,
            "state": state.value,
            "progress": progress
        })
    
    async def send_msg_bus(self, to_agent: str, pairs: list):
        """Send a message to the message bus."""
        await self.send({
            "type": "msg_bus",
            "from": self.agent_id.value,
            "to": to_agent,
            "pairs": pairs
        })
    
    async def animate_wire(self, to_agent: str):
        """Trigger wire animation to another agent."""
        await self.send({
            "type": "wire_animate",
            "from": self.agent_id.value,
            "to": to_agent
        })
    
    async def delay(self, ms: int):
        """Async delay helper."""
        await asyncio.sleep(ms / 1000)
    
    @abstractmethod
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """
        Process the diagnosis context.
        
        Args:
            context: The diagnosis context to process
            
        Returns:
            Updated diagnosis context
        """
        pass
    
    async def run(self, context: DiagnosisContext) -> DiagnosisContext:
        """
        Run the agent with error handling.
        
        Args:
            context: The diagnosis context
            
        Returns:
            Updated diagnosis context
        """
        self._context = context
        
        try:
            await self.update_status(AgentState.RUNNING, 0)
            result = await self.process(context)
            await self.update_status(AgentState.DONE, 100)
            return result
            
        except asyncio.CancelledError:
            # Handle task cancellation - this is normal during shutdown
            logger.info(f"Agent {self.agent_id.value} was cancelled")
            await self.update_status(AgentState.ERROR)
            raise
        except Exception as e:
            logger.error(f"Agent {self.agent_id.value} error ({type(e).__name__}): {e}")
            await self.update_status(AgentState.ERROR)
            await self.send({
                "type": "error",
                "message": f"Agent {self.agent_id.value} error: {type(e).__name__}: {str(e)}"
            })
            raise


# =============================================================================
# Agent Factory
# =============================================================================

class AgentFactory:
    """Factory for creating agent instances."""
    
    _agents: Dict[AgentID, type] = {}
    
    @classmethod
    def register(cls, agent_id: AgentID, agent_class: type):
        """Register an agent class."""
        cls._agents[agent_id] = agent_class
    
    @classmethod
    def create(cls, agent_id: AgentID) -> BaseAgent:
        """Create an agent instance."""
        if agent_id not in cls._agents:
            raise ValueError(f"Unknown agent ID: {agent_id}")
        return cls._agents[agent_id](agent_id)
    
    @classmethod
    def create_all(cls) -> Dict[AgentID, BaseAgent]:
        """Create all registered agents."""
        return {agent_id: cls.create(agent_id) for agent_id in cls._agents}
