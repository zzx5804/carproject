"""
Application Configuration Module.

Centralized configuration management using pydantic-settings.
Supports environment variables, .env files, and programmatic configuration.
"""

import sys
from pathlib import Path
from typing import Optional, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    All settings can be overridden via environment variables with APP_ prefix.
    Example: APP_SERVER_PORT=9000 to change the server port.
    
    Configuration priority (highest to lowest):
    1. Environment variables (APP_*)
    2. .env file in backend/ directory
    3. Default values defined here
    """
    
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # =========================================================================
    # Server Configuration
    # =========================================================================
    
    server_host: str = Field(
        default="0.0.0.0",
        description="Server host address"
    )
    server_port: int = Field(
        default=8765,
        ge=1,
        le=65535,
        description="Server port"
    )
    server_reload: bool = Field(
        default=False,
        description="Enable auto-reload for development"
    )
    
    # =========================================================================
    # Diagnosis Mode Configuration
    # =========================================================================
    
    use_llm_mode: bool = Field(
        default=True,
        description="Use LLM-powered diagnosis mode (True) or legacy rule-based mode (False)"
    )
    
    # =========================================================================
    # Ontology Configuration
    # =========================================================================
    
    ontology_path: Optional[str] = Field(
        default=None,
        description="Path to ontology TTL file. If not set, auto-detection is used."
    )
    ontology_folder: Optional[str] = Field(
        default=None,
        description="Path to ontology folder containing TTL files. If not set, auto-detection is used."
    )
    
    # =========================================================================
    # Logging Configuration
    # =========================================================================
    
    log_level: str = Field(
        default="INFO",
        description="Console logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_file: str = Field(
        default="backend.log",
        description="Log file path"
    )
    log_rotation: str = Field(
        default="10 MB",
        description="Log rotation size"
    )
    log_retention: str = Field(
        default="7 days",
        description="Log retention period"
    )
    log_format: str = Field(
        default="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        description="Log format string"
    )
    
    # =========================================================================
    # WebSocket Configuration
    # =========================================================================
    
    ws_heartbeat_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="WebSocket heartbeat interval in seconds"
    )
    ws_max_connections: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum concurrent WebSocket connections"
    )
    ws_endpoint: str = Field(
        default="/ws",
        description="WebSocket endpoint path"
    )
    
    # =========================================================================
    # Application Metadata
    # =========================================================================
    
    app_name: str = Field(
        default="Vehicle Power Diagnosis System",
        description="Application name"
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    
    # =========================================================================
    # Validators
    # =========================================================================
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate and normalize log level."""
        valid_levels = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            logger.warning(f"Invalid log level '{v}', using INFO")
            return "INFO"
        return v_upper
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def get_ontology_path(self) -> Path:
        """
        Get ontology file path with fallback search.
        
        Search order:
        1. User-specified ontology_path setting
        2. Project root directory (parent of backend/)
        3. Backend directory
        
        Returns:
            Path: Path to the ontology file (may not exist)
        """
        # Check user-specified path first
        if self.ontology_path:
            user_path = Path(self.ontology_path)
            if user_path.exists():
                return user_path
            logger.warning(f"Specified ontology path not found: {self.ontology_path}")
        
        # Define fallback search paths
        backend_dir = Path(__file__).parent
        project_root = backend_dir.parent
        
        fallback_paths: List[Path] = [
            # Project root
            project_root / "vehicle_power_mode_ontology.ttl",
            # Backend directory
            backend_dir / "vehicle_power_mode_ontology.ttl",
            # Legacy filenames (if they exist)
            project_root / "vehicle_power_ontology_GLM_Minimax_Merged.ttl",
            backend_dir / "vehicle_power_ontology_GLM_Minimax_Merged.ttl",
        ]
        
        # Search for existing file
        for path in fallback_paths:
            if path.exists():
                return path
        
        # Return default path even if not found
        # (will trigger warning during loading)
        return fallback_paths[0]
    
    def get_ontology_folder(self) -> Path:
        """
        Get ontology folder path with fallback search.
        
        Search order:
        1. User-specified ontology_folder setting
        2. Project root / "ontology files" directory
        
        Returns:
            Path: Path to the ontology folder (may not exist)
        """
        # Check user-specified path first
        if self.ontology_folder:
            user_path = Path(self.ontology_folder)
            if user_path.exists() and user_path.is_dir():
                return user_path
            logger.warning(f"Specified ontology folder not found: {self.ontology_folder}")
        
        # Default to project root / "ontology files"
        backend_dir = Path(__file__).parent
        project_root = backend_dir.parent
        default_folder = project_root / "ontology files"
        
        return default_folder
    
    def get_all_ontology_search_paths(self) -> List[Path]:
        """
        Get all possible ontology search paths.
        
        Returns:
            List[Path]: All paths to search for ontology files
        """
        backend_dir = Path(__file__).parent
        project_root = backend_dir.parent
        
        paths = []
        
        if self.ontology_path:
            paths.append(Path(self.ontology_path))
        
        paths.extend([
            project_root / "vehicle_power_mode_ontology.ttl",
            backend_dir / "vehicle_power_mode_ontology.ttl",
            project_root / "vehicle_power_ontology_GLM_Minimax_Merged.ttl",
            backend_dir / "vehicle_power_ontology_GLM_Minimax_Merged.ttl",
        ])
        
        return paths
    
    def get_server_url(self) -> str:
        """Get the WebSocket server URL."""
        return f"ws://localhost:{self.server_port}"
    
    def get_http_url(self) -> str:
        """Get the HTTP server URL."""
        return f"http://localhost:{self.server_port}"


# =============================================================================
# Global Settings Instance
# =============================================================================

_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create the global settings instance.
    
    Settings are loaded from:
    1. Environment variables (APP_* prefix)
    2. .env file in backend/ directory
    3. Default values
    
    Returns:
        Settings: The global settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment and .env file.
    
    This clears the cached settings and creates a new instance,
    picking up any changes to environment variables or .env file.
    
    Returns:
        Settings: Fresh settings instance
    """
    global _settings
    _settings = Settings()
    logger.info("Settings reloaded from environment")
    return _settings


def reset_settings() -> None:
    """
    Reset the global settings instance.
    
    Used primarily for testing to ensure clean state.
    """
    global _settings
    _settings = None


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging(settings: Optional[Settings] = None) -> None:
    """
    Configure logging based on settings.
    
    Sets up:
    - Console output with color formatting
    - File output with rotation and retention
    
    Args:
        settings: Settings instance to use. If None, uses global settings.
    """
    settings = settings or get_settings()
    
    # Remove existing handlers
    logger.remove()
    
    # Console handler
    logger.add(
        sys.stdout,
        format=settings.log_format,
        level=settings.log_level,
        colorize=True
    )
    
    # File handler
    logger.add(
        settings.log_file,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        level="DEBUG",
        encoding="utf-8"
    )
    
    logger.debug(f"Logging configured: level={settings.log_level}, file={settings.log_file}")


# =============================================================================
# Convenience Functions
# =============================================================================

def is_llm_mode() -> bool:
    """Check if LLM diagnosis mode is enabled."""
    return get_settings().use_llm_mode


def get_server_config() -> dict:
    """
    Get server configuration for uvicorn.
    
    Returns:
        dict: Configuration dict suitable for uvicorn.Config
    """
    settings = get_settings()
    return {
        "host": settings.server_host,
        "port": settings.server_port,
        "reload": settings.server_reload,
        "log_level": settings.log_level.lower()
    }
