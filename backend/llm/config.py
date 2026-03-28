"""
LLM Configuration Module.

Manages LLM endpoint configuration, authentication, and model parameters.
Only supports local model deployment (custom REST API endpoint).
"""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


class LLMProviderEnum(str, Enum):
    """LLM provider selection."""

    LOCAL = "local"
    OPENROUTER = "openrouter"


class LLMConfig(BaseSettings):
    """
    Configuration for LLM service.

    Supports both local LLM deployment and OpenRouter.
    All sensitive values can be set via environment variables.
    """

    model_config = SettingsConfigDict(
        env_prefix="LLM_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Provider selection
    provider: LLMProviderEnum = Field(
        default=LLMProviderEnum.LOCAL,
        description="LLM provider: 'local' or 'openrouter'",
    )

    # OpenRouter specific configuration
    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter API key (LLM_OPENROUTER_API_KEY env var)"
    )
    openrouter_model: str = Field(
        default="openai/gpt-3.5-turbo", description="OpenRouter model name"
    )

    # Local model REST API endpoint
    endpoint: str = Field(
        default="https://llm-gateway.dev.cn-vwa.volkswagen-cea.com",
        description="Local LLM REST API endpoint",
    )
    api_key: Optional[str] = Field(default=None, description="API key for LLM endpoint")
    auth_header: str = Field(
        default="Authorization",
        description="Auth header name (e.g., 'Authorization', 'X-API-Key')",
    )
    auth_prefix: str = Field(
        default="Bearer",
        description="Prefix for auth header (e.g., 'Bearer', empty for API key only)",
    )

    # Model configuration
    model: str = Field(default="GLM-5-FP8", description="Model name to use")
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=2048, ge=1, le=32000, description="Maximum tokens in response"
    )

    # Request configuration
    timeout: int = Field(
        default=60, ge=1, le=300, description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum retry attempts"
    )
    retry_delay: float = Field(
        default=1.0, ge=0.1, description="Base delay between retries (seconds)"
    )

    # Streaming configuration
    enable_streaming: bool = Field(
        default=False, description="Enable streaming responses"
    )

    # Feature flags
    enable_fallback: bool = Field(
        default=True, description="Enable fallback to hardcoded rules on LLM failure"
    )
    log_requests: bool = Field(
        default=True, description="Log LLM requests and responses"
    )

    @field_validator("auth_prefix")
    @classmethod
    def validate_auth_prefix(cls, v: str) -> str:
        # Bearer, Token, or empty string
        return v if v else ""

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API."""
        headers = {}

        if self.api_key:
            if self.auth_prefix:
                headers[self.auth_header] = f"{self.auth_prefix} {self.api_key}"
            else:
                headers[self.auth_header] = self.api_key

        return headers

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive values)."""
        return {
            "provider": self.provider.value,
            "endpoint": self.endpoint,
            "model": self.model,
            "openrouter_model": self.openrouter_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "enable_streaming": self.enable_streaming,
            "enable_fallback": self.enable_fallback,
        }


# Global configuration instance
_llm_config: Optional[LLMConfig] = None


def get_llm_config() -> LLMConfig:
    """
    Get or create global LLM configuration.

    Configuration is loaded from:
    1. Environment variables (LLM_* prefix)
    2. llm_config.yaml file
    3. Default values

    Returns:
        LLMConfig: Configuration instance
    """
    global _llm_config

    if _llm_config is None:
        # Try to load from YAML file first
        # Check multiple locations: CLI, llm/, backend/ directories
        yaml_paths = [
            Path(__file__).parent.parent
            / "cli"
            / "llm_config.yaml",  # CLI config (priority)
            Path(__file__).parent / "llm_config.yaml",  # llm/ directory
            Path(__file__).parent.parent / "llm_config.yaml",  # backend/ directory
        ]

        # Check for environment variable override
        env_config_path = os.environ.get("LLM_CONFIG_PATH")
        if env_config_path:
            yaml_paths.insert(0, Path(env_config_path))

        yaml_path = None
        for path in yaml_paths:
            if path.exists():
                yaml_path = path
                break

        # Try to load .env file from CLI directory
        cli_env_path = Path(__file__).parent.parent / "cli" / ".env"
        if cli_env_path.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(cli_env_path)
                logger.info(f"Loaded .env from: {cli_env_path}")
            except ImportError:
                # dotenv not installed, manually load .env
                with open(cli_env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            if key not in os.environ:  # Don't override existing
                                os.environ[key] = value
                logger.info(f"Loaded .env manually from: {cli_env_path}")

        config_dict = {}

        if yaml_path and yaml_path.exists():
            try:
                import yaml

                with open(yaml_path, "r", encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        # Map YAML keys to config fields
                        # Only include non-empty values so env vars can override
                        yaml_mappings = [
                            (
                                "endpoint",
                                "endpoint",
                                "https://llm-gateway.dev.cn-vwa.volkswagen-cea.com",
                            ),
                            ("api_key", "api_key", None),  # Use env var preferentially
                            ("model", "model", "GLM-5-FP8"),
                            ("temperature", "temperature", 0.7),
                            ("max_tokens", "max_tokens", 2048),
                            ("timeout", "timeout", 60),
                            ("max_retries", "max_retries", 3),
                            ("retry_delay", "retry_delay", 1.0),
                            ("enable_streaming", "enable_streaming", False),
                            ("enable_fallback", "enable_fallback", True),
                            ("log_requests", "log_requests", True),
                        ]

                        for yaml_key, config_key, default in yaml_mappings:
                            val = yaml_config.get(yaml_key, default)
                            # For API key: skip if empty - environment variable should be used
                            if config_key == "api_key":
                                if val and val.strip():  # Only set if non-empty
                                    config_dict[config_key] = val
                                # If empty, skip - Pydantic will use env var from load_dotenv
                            elif val is not None and val != "":
                                config_dict[config_key] = val

                        logger.info(f"Loaded config from YAML: {yaml_path}")
            except ImportError:
                logger.warning("PyYAML not installed, using default config")
            except Exception as e:
                logger.warning(f"Failed to load YAML config: {e}")

        # Create config (environment variables will override YAML)
        _llm_config = LLMConfig(**config_dict)

        logger.info(
            f"LLM Config loaded: endpoint={_llm_config.endpoint}, "
            f"model={_llm_config.model}"
        )

    return _llm_config


def reload_llm_config() -> LLMConfig:
    """Reload configuration from sources."""
    global _llm_config
    _llm_config = None  # Reset to force reload
    return get_llm_config()  # Use the same logic as get_llm_config


# Backward compatibility
LLMSettings = LLMConfig
get_llm_settings = get_llm_config
