"""
LLM Module for Vehicle Power Diagnosis System.

This module provides LLM integration for intelligent diagnosis,
replacing hardcoded rules with semantic reasoning.
"""

from llm.config import LLMConfig, get_llm_config, LLMProviderEnum
from llm.service import LLMService, LLMTools, get_llm_service
from llm.schemas import (
    DiagnosisRequest,
    DiagnosisResponse,
    DiagnosticHypothesis,
    ReasoningStep,
    ConfidenceFactor,
    Role,
    SignalInfo,
)
from llm.prompts import PromptBuilder, get_prompt_builder
from llm.fallback import FallbackHandler, get_fallback_handler

__all__ = [
    # Config
    "LLMConfig",
    "LLMProviderEnum",
    "get_llm_config",
    # Service
    "LLMService",
    "LLMTools",
    "get_llm_service",
    # Schemas
    "DiagnosisRequest",
    "DiagnosisResponse",
    "DiagnosticHypothesis",
    "ReasoningStep",
    "ConfidenceFactor",
    "Role",
    "SignalInfo",
    # Prompts
    "PromptBuilder",
    "get_prompt_builder",
    # Fallback
    "FallbackHandler",
    "get_fallback_handler",
]
