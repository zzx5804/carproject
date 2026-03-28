"""
Tests for config module.
"""
import pytest
import os
from pathlib import Path


class TestSettings:
    def test_settings_defaults(self):
        from config import Settings
        s = Settings()
        assert s.server_host == "0.0.0.0"
        assert s.server_port == 8765
        assert s.use_llm_mode is True
    
    def test_settings_env_override(self, monkeypatch):
        from config import Settings, reset_settings
        reset_settings()
        monkeypatch.setenv("APP_SERVER_PORT", "9000")
        monkeypatch.setenv("APP_USE_LLM_MODE", "false")
        
        s = Settings()
        assert s.server_port == 9000
        assert s.use_llm_mode is False
        reset_settings()
    
    def test_settings_log_config(self):
        from config import Settings
        s = Settings()
        assert s.log_level == "INFO"
        assert s.log_file == "backend.log"
    
    def test_settings_log_level_validation(self, monkeypatch):
        from config import Settings, reset_settings
        reset_settings()
        monkeypatch.setenv("APP_LOG_LEVEL", "debug")
        
        s = Settings()
        assert s.log_level == "DEBUG"
        reset_settings()
    
    def test_settings_invalid_log_level_fallback(self, monkeypatch):
        from config import Settings, reset_settings
        reset_settings()
        monkeypatch.setenv("APP_LOG_LEVEL", "INVALID_LEVEL")
        
        s = Settings()
        # Invalid level should fallback to INFO
        assert s.log_level == "INFO"
        reset_settings()
    
    def test_settings_app_metadata(self):
        from config import Settings
        s = Settings()
        assert s.app_name == "Vehicle Power Diagnosis System"
        assert s.app_version == "1.0.0"
    
    def test_settings_websocket_config(self):
        from config import Settings
        s = Settings()
        assert s.ws_heartbeat_interval == 30
        assert s.ws_max_connections == 100
        assert s.ws_endpoint == "/ws"


class TestGetSettings:
    def test_get_settings_singleton(self):
        from config import get_settings, reset_settings
        reset_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        reset_settings()
    
    def test_reload_settings(self):
        from config import get_settings, reload_settings, reset_settings
        reset_settings()
        s1 = get_settings()
        s2 = reload_settings()
        # After reload, should be a new instance
        s3 = get_settings()
        assert s2 is s3
        reset_settings()
    
    def test_reset_settings(self):
        from config import get_settings, reset_settings
        
        s1 = get_settings()
        reset_settings()
        s2 = get_settings()
        # After reset, should be a new instance
        assert s1 is not s2
        reset_settings()


class TestGetOntologyPath:
    def test_get_ontology_path_returns_path(self):
        from config import Settings
        s = Settings()
        path = s.get_ontology_path()
        assert isinstance(path, Path)
    
    def test_get_ontology_path_with_custom_path(self, monkeypatch, tmp_path):
        from config import Settings, reset_settings
        reset_settings()
        
        # Create a temp ontology file
        ontology_file = tmp_path / "custom_ontology.ttl"
        ontology_file.write_text("# test ontology")
        
        monkeypatch.setenv("APP_ONTOLOGY_PATH", str(ontology_file))
        
        s = Settings()
        path = s.get_ontology_path()
        assert path == ontology_file
        reset_settings()
    
    def test_get_all_ontology_search_paths(self):
        from config import Settings
        s = Settings()
        paths = s.get_all_ontology_search_paths()
        assert isinstance(paths, list)
        assert len(paths) > 0
        for p in paths:
            assert isinstance(p, Path)


class TestServerUrls:
    def test_get_server_url(self):
        from config import Settings
        s = Settings()
        url = s.get_server_url()
        assert url == f"ws://localhost:{s.server_port}"
    
    def test_get_http_url(self):
        from config import Settings
        s = Settings()
        url = s.get_http_url()
        assert url == f"http://localhost:{s.server_port}"


class TestSetupLogging:
    def test_setup_logging_runs(self):
        from config import Settings, setup_logging
        s = Settings()
        # Should not raise
        setup_logging(s)
    
    def test_setup_logging_with_none_uses_global(self):
        from config import setup_logging, get_settings, reset_settings
        reset_settings()
        get_settings()  # Initialize
        # Should not raise when None is passed
        setup_logging(None)
        reset_settings()


class TestConvenienceFunctions:
    def test_is_llm_mode(self):
        from config import is_llm_mode, reset_settings
        reset_settings()
        assert is_llm_mode() is True
        reset_settings()
    
    def test_get_server_config(self):
        from config import get_server_config, reset_settings
        reset_settings()
        config = get_server_config()
        assert "host" in config
        assert "port" in config
        assert "reload" in config
        assert "log_level" in config
        reset_settings()


class TestSettingsValidation:
    def test_server_port_validation_valid(self, monkeypatch):
        from config import Settings, reset_settings
        reset_settings()
        monkeypatch.setenv("APP_SERVER_PORT", "8080")
        
        s = Settings()
        assert s.server_port == 8080
        reset_settings()
    
    def test_server_port_out_of_range_high(self, monkeypatch):
        from config import Settings, reset_settings
        from pydantic import ValidationError
        reset_settings()
        
        monkeypatch.setenv("APP_SERVER_PORT", "70000")
        
        with pytest.raises(ValidationError):
            Settings()
        reset_settings()
    
    def test_server_port_out_of_range_low(self, monkeypatch):
        from config import Settings, reset_settings
        from pydantic import ValidationError
        reset_settings()
        
        monkeypatch.setenv("APP_SERVER_PORT", "0")
        
        with pytest.raises(ValidationError):
            Settings()
        reset_settings()


class TestSettingsFieldDefaults:
    def test_ontology_path_default_none(self):
        from config import Settings
        s = Settings()
        assert s.ontology_path is None
    
    def test_server_reload_default_false(self):
        from config import Settings
        s = Settings()
        assert s.server_reload is False
    
    def test_log_rotation_default(self):
        from config import Settings
        s = Settings()
        assert s.log_rotation == "10 MB"
    
    def test_log_retention_default(self):
        from config import Settings
        s = Settings()
        assert s.log_retention == "7 days"
