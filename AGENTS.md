# AGENTS.md - Vehicle Power Diagnosis System

Guidelines for AI coding agents working in this repository.

## Project Overview

A Python-based multi-agent diagnosis system for vehicle power mode management. Uses OWL ontology (TTL format) for domain knowledge, FastAPI + WebSocket for real-time communication, and a multi-agent pipeline architecture for reasoning.

---

## Build / Lint / Test Commands

### Setup
```bash
cd backend
pip install -r requirements.txt
```

### Run Server
```bash
cd backend
python main.py
# Server starts on http://localhost:8765
# WebSocket endpoint: ws://localhost:8765/ws
```

### Run Tests
```bash
cd backend
python -m pytest tests/ -v     # Run all unit tests (recommended)
python test_backend.py         # Run component tests (legacy)
```

### Run Single Test (with pytest)
```bash
cd backend
python -m pytest tests/test_models.py -v
python -m pytest tests/test_diagnosis_knowledge.py -v
```

### Type Checking (if mypy installed)
```bash
cd backend
mypy *.py agents/*.py ontology/*.py
```

---

## Project Structure

```
ontology/
├── backend/
│   ├── main.py              # Entry point, initializes pipeline
│   ├── server.py            # FastAPI + WebSocket server
│   ├── models.py            # Pydantic models for API
│   ├── config.py            # Centralized configuration (pydantic-settings)
│   ├── dependencies.py      # DI container with Protocol interfaces
│   ├── diagnosis_knowledge.py  # Centralized constants (patterns, rules, templates)
│   ├── scenario_detector.py # Centralized scenario detection
│   ├── test_backend.py      # Component tests (legacy)
│   ├── requirements.txt     # Python dependencies
│   ├── pytest.ini           # pytest configuration
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseAgent abstract class + AgentFactory
│   │   ├── orchestrator.py  # Pipeline coordinator
│   │   ├── symptom_parser.py
│   │   ├── ontology_fetcher.py
│   │   ├── rule_engine.py
│   │   ├── confidence_calc.py
│   │   ├── output_adapter.py
│   │   └── llm_diagnosis_agent.py
│   ├── ontology/
│   │   ├── __init__.py
│   │   └── parser.py        # TTL/RDF ontology parser
│   ├── llm/                 # LLM integration
│   │   ├── service.py
│   │   ├── config.py
│   │   ├── fallback.py      # Rule-based fallback (uses shared knowledge)
│   │   ├── prompts.py
│   │   └── schemas.py
│   └── tests/               # pytest test suite
│       ├── __init__.py
│       ├── conftest.py      # Shared fixtures
│       ├── test_models.py
│       ├── test_diagnosis_knowledge.py
│       ├── test_dependencies.py
│       └── test_config.py
├── vehicle_power_mode_ontology.ttl  # OWL ontology file
└── multi-agent-demo.html    # Frontend (single HTML file)
```

---

## Code Style Guidelines

### Imports

Order imports in three groups, separated by blank lines:

```python
# 1. Standard library
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any

# 2. Third-party
from fastapi import FastAPI, WebSocket
from loguru import logger
from pydantic import BaseModel
from rdflib import Graph, Namespace

# 3. Local modules
from models import DiagnosisContext, AgentID
from agents.base import BaseAgent
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Modules | snake_case | `symptom_parser.py` |
| Classes | PascalCase | `OrchestratorAgent` |
| Functions | snake_case | `parse_symptom()` |
| Variables | snake_case | `power_mode_value` |
| Constants | UPPER_SNAKE | `DEFAULT_TIMEOUT` |
| Enums | PascalCase (class), UPPER for values | `AgentState.RUNNING` |
| Private attributes | _leading_underscore | `self._send_message` |

### Type Hints

Always use type hints for function parameters and return values:

```python
async def process(self, context: DiagnosisContext) -> DiagnosisContext:
    ...

def get_class(self, name: str) -> Optional[OntologyClass]:
    ...

def search_by_keyword(self, keyword: str) -> Dict[str, List[str]]:
    ...
```

### Docstrings

Use triple-quoted docstrings for modules, classes, and public methods:

```python
"""
Module-level docstring describing the file's purpose.
"""

class BaseAgent(ABC):
    """
    Abstract base class for all diagnosis agents.
    
    Each agent:
    - Has a unique ID
    - Can send messages to the WebSocket client
    - Can update its status
    - Processes the diagnosis context
    """
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """
        Process the diagnosis context.
        
        Args:
            context: The diagnosis context to process
            
        Returns:
            Updated diagnosis context
        """
        pass
```

### Data Classes & Pydantic Models

Use `@dataclass` for internal data structures:

```python
@dataclass
class OntologyClass:
    uri: str
    label: str
    label_zh: str = ""
    parent_classes: List[str] = field(default_factory=list)
```

Use Pydantic `BaseModel` for API data validation:

```python
class DiagnosisContext(BaseModel):
    symptom: str
    role: Role
    signals: Dict[str, str]
    parsed_symptoms: List[str] = Field(default_factory=list)
```

### Async Patterns

All I/O operations should be async:

```python
async def run(self, context: DiagnosisContext) -> DiagnosisContext:
    await self.update_status(AgentState.RUNNING, 0)
    result = await self.process(context)
    await self.update_status(AgentState.DONE, 100)
    return result
```

Use `asyncio.sleep()` for delays, wrapped in helper methods:

```python
async def delay(self, ms: int):
    await asyncio.sleep(ms / 1000)
```

### Error Handling

Handle exceptions explicitly with logging:

```python
try:
    result = await agent.run(context)
except Exception as e:
    logger.error(f"Agent {self.agent_id.value} error: {e}")
    await self.update_status(AgentState.ERROR)
    raise
```

Never use bare `except:` - always specify the exception type.

### Logging

Use `loguru` logger:

```python
from loguru import logger

logger.info(f"Loaded ontology with {len(self.graph)} triples")
logger.warning(f"Ontology not found, using default path: {path}")
logger.error(f"Failed to load ontology: {e}")
```

Logging format is configured in `main.py`.

---

## Agent Development Patterns

### Creating a New Agent

1. Inherit from `BaseAgent`
2. Implement `process()` method
3. Register in `main.py` pipeline

```python
from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, AgentState

class MyNewAgent(BaseAgent):
    def __init__(self, agent_id: AgentID = AgentID.MY_AGENT):
        super().__init__(agent_id)
    
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        await self.update_status(AgentState.RUNNING, 0)
        
        # Send message to message bus
        await self.send_msg_bus("target_agent", [
            {"k": "key", "v": "value"}
        ])
        
        # Animate wire to another agent
        await self.animate_wire("target_agent")
        
        # ... processing logic ...
        
        await self.update_status(AgentState.DONE, 100)
        return context
```

### Agent Communication

Agents communicate via the message bus:

```python
# Send key-value pairs to message bus
await self.send_msg_bus("target_agent", [
    {"k": "指令", "v": "PARSE_SYMPTOM"},
    {"k": "payload", "v": context.symptom}
])

# Trigger wire animation
await self.animate_wire("target_agent")

# Send arbitrary message to WebSocket client
await self.send({
    "type": "reasoning_step",
    "step": {"title": "...", "body": "..."}
})
```

---

## Ontology Integration

### Querying the Ontology

```python
parser = OntologyParser("path/to/ontology.ttl")
parser.load()

# Get class info
cls = parser.get_class("PowerMode")

# Search by keyword
results = parser.search_by_keyword("brake")

# Get specific info
power_modes = parser.get_power_mode_info()
key_types = parser.get_key_types()
```

### Ontology File Format

The ontology uses Turtle (TTL) format with:
- OWL classes for domain entities
- Object properties for relationships
- Datatype properties for signals
- Named individuals for enum-like values
- SWRL rules documented in comments

---

## WebSocket Protocol

### Client → Server

```json
{
  "type": "start",
  "symptom": "踩刹车按启动按钮，车辆无法上电",
  "role": "owner",
  "signals": {"sv-pm": "0:Off", "sv-kv": "INVALID"}
}
```

### Server → Client Message Types

| Type | Description |
|------|-------------|
| `agent_status` | Agent state update |
| `msg_bus` | Agent communication |
| `wire_animate` | Wire animation trigger |
| `reasoning_step` | Reasoning step update |
| `onto_summary` | Ontology summary HTML |
| `rule_matched` | Matched rule info |
| `hypothesis` | Diagnosis hypothesis |
| `conf_factors` | Confidence factors |
| `conf_final` | Final confidence score |
| `output` | Role-adapted output |
| `pipeline_done` | Pipeline completion |
| `error` | Error message |

---

## Dependencies

Key packages (from `requirements.txt`):

- `fastapi>=0.109.0` - Web framework
- `uvicorn[standard]>=0.27.0` - ASGI server
- `websockets>=12.0` - WebSocket support
- `rdflib>=7.0.0` - RDF/OWL parsing
- `owlrl>=6.0.0` - OWL reasoning
- `pydantic>=2.5.0` - Data validation
- `pydantic-settings>=2.0.0` - Configuration management
- `loguru>=0.7.2` - Logging
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support

---

## Configuration

All configuration is centralized in `backend/config.py` using pydantic-settings. Override via environment variables:

```bash
# Server configuration
APP_SERVER_PORT=9000          # Default: 8765
APP_SERVER_HOST=127.0.0.1     # Default: 0.0.0.0

# Diagnosis mode
APP_USE_LLM_MODE=false        # Default: true

# Ontology
APP_ONTOLOGY_PATH=/path/to/ontology.ttl

# Logging
APP_LOG_LEVEL=DEBUG           # Default: INFO

# WebSocket
APP_WS_HEARTBEAT_INTERVAL=60  # Default: 30
APP_WS_MAX_CONNECTIONS=50     # Default: 100
```

Or create a `.env` file in the `backend` directory:

```env
APP_SERVER_PORT=9000
APP_USE_LLM_MODE=false
APP_LOG_LEVEL=DEBUG
```

---

## Frontend

Single HTML file (`multi-agent-demo.html`) with vanilla JS. Connects to WebSocket backend. No build step required - open directly in browser.

---

## Notes

- The project follows EEA 3.5 / SSTS-CEA automotive architecture patterns
- Ontology contains bilingual labels (English + Chinese)
- Agents use a pipeline execution model orchestrated by `OrchestratorAgent`
- All file I/O and network operations should be async
