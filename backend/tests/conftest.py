"""
Shared pytest fixtures for all tests.
"""
import pytest
import asyncio
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock

# Configure asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_symptom() -> str:
    """Sample symptom text for testing."""
    return "踩刹车按启动按钮，车辆无法上电"


@pytest.fixture
def sample_signals() -> Dict[str, str]:
    """Sample signal values for testing."""
    return {
        "sv-pm": "0:Off",
        "sv-kv": "INVALID",
        "sv-ble": "0",
        "sv-brk": "PRESSED",
        "sv-zat": "PRESSED"
    }


@pytest.fixture
def sample_context(sample_symptom, sample_signals):
    """Sample DiagnosisContext for testing."""
    from models import DiagnosisContext, Role
    return DiagnosisContext(
        symptom=sample_symptom,
        role=Role.OWNER,
        signals=sample_signals
    )


@pytest.fixture
def mock_message_sender():
    """Mock message sender for agent testing."""
    messages = []
    
    async def sender(msg: Dict[str, Any]):
        messages.append(msg)
    
    sender.messages = messages  # type: ignore
    return sender


@pytest.fixture
def mock_websocket():
    """Mock WebSocket for server testing."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


@pytest.fixture
def ontology_path() -> Path:
    """Path to test ontology file."""
    # Use the project's ontology file
    path = Path(__file__).parent.parent.parent / "vehicle_power_mode_ontology.ttl"
    if not path.exists():
        pytest.skip(f"Ontology file not found: {path}")
    return path


@pytest.fixture
def ontology_parser(ontology_path):
    """Initialized ontology parser for testing."""
    from ontology.parser import OntologyParser
    parser = OntologyParser(str(ontology_path))
    if not parser.load():
        pytest.skip("Failed to load ontology")
    return parser
