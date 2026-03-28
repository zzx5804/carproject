# Vehicle Power Diagnosis System - Technical Design Document

**Version:** 1.0.0  
**Date:** 2026-03-25  
**Status:** Implementation Complete

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Agent Pipeline](#3-agent-pipeline)
4. [WebSocket Communication](#4-websocket-communication)
5. [Ontology Integration](#5-ontology-integration)
6. [LLM Service Architecture](#6-llm-service-architecture)
7. [Configuration Management](#7-configuration-management)
8. [Data Models](#8-data-models)
9. [Error Handling & Fallback](#9-error-handling--fallback)
10. [Deployment](#10-deployment)

---

## 1. System Overview

### 1.1 Purpose

The Vehicle Power Diagnosis System is a multi-agent AI-powered diagnosis platform for vehicle power mode management. It analyzes vehicle symptoms and signals to provide intelligent diagnosis with role-adapted output for owners, technicians, and customer service representatives.

### 1.2 Key Features

- **Multi-Agent Pipeline**: 7 specialized agents orchestrated for diagnosis
- **Dual Execution Modes**: LLM-powered intelligent diagnosis or legacy rule-based diagnosis
- **Ontology-Driven**: OWL-compliant TTL ontology for domain knowledge
- **Real-Time Communication**: WebSocket-based bidirectional messaging
- **Role-Adapted Output**: Customized responses for different user roles
- **Graceful Fallback**: Automatic fallback from LLM to rule-based diagnosis

### 1.3 Technology Stack

| Layer | Technology |
|-------|------------|
| Backend Framework | FastAPI + Uvicorn |
| Communication | WebSocket (bidirectional) |
| Ontology Parsing | RDFLib + OWL-RL |
| LLM Integration | LiteLLM (multi-provider support) |
| Validation | Pydantic v2 |
| Configuration | Pydantic-Settings |
| Logging | Loguru |
| Testing | pytest + pytest-asyncio |

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VEHICLE POWER DIAGNOSIS SYSTEM                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │   Frontend   │     │                   BACKEND                         │  │
│  │  (HTML/JS)   │◄───►│                                                  │  │
│  └──────────────┘     │  ┌────────────┐    ┌─────────────────────────┐   │  │
│        │              │  │  FastAPI   │    │    WebSocket Server     │   │  │
│        │              │  │  Server    │────│    (ConnectionManager)  │   │  │
│        │              │  └─────┬──────┘    └───────────┬─────────────┘   │  │
│        │              │        │                       │                  │  │
│        │              │        ▼                       ▼                  │  │
│        │              │  ┌─────────────────────────────────────────────┐  │  │
│        │              │  │              DIAGNOSIS PIPELINE             │  │  │
│        │              │  │                                             │  │  │
│        │              │  │  ┌────────────┐    ┌───────────────────┐   │  │  │
│        │              │  │  │Orchestrator│───►│    Agent Pool     │   │  │  │
│        │              │  │  │   Agent    │    │ ┌───┐┌───┐┌───┐   │   │  │  │
│        │              │  │  └─────┬──────┘    │ │LLM││SYM││ONT│   │   │  │  │
│        │              │  │        │           │ │   ││   ││   │   │   │  │  │
│        │              │  │        ▼           │ └───┘└───┘└───┘   │   │  │  │
│        │              │  │  ┌────────────┐    │ ┌───┐┌───┐┌───┐   │   │  │  │
│        │              │  │  │    LLM     │    │ │RUL││CNF││OUT│   │   │  │  │
│        │              │  │  │  Service   │◄───┤ └───┘└───┘└───┘   │   │  │  │
│        │              │  │  └─────┬──────┘    └───────────────────┘   │  │  │
│        │              │  │        │                                     │  │  │
│        │              │  └────────│─────────────────────────────────────┘  │  │
│        │              │           │                                        │  │
│        │              │           ▼                                        │  │
│        │              │  ┌────────────────┐    ┌──────────────────────┐   │  │
│        │              │  │   Ontology     │    │     Knowledge        │   │  │
│        │              │  │   Parser       │    │     Constants        │   │  │
│        │              │  │  (TTL/RDF)     │    │ (diagnosis_knowledge)│   │  │
│        │              │  └────────────────┘    └──────────────────────┘   │  │
│        │              └──────────────────────────────────────────────────┘  │
│        │                                                                     │
│        ▼                                                                     │
│  ┌──────────────┐                                                           │
│  │   vehicle_   │                                                           │
│  │  power_mode  │                                                           │
│  │ _ontology.ttl│                                                           │
│  └──────────────┘                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Overview

| Component | File | Responsibility |
|-----------|------|----------------|
| Entry Point | `main.py` | Application bootstrap, pipeline initialization |
| Server | `server.py` | FastAPI app, WebSocket handling, routing |
| Orchestrator | `agents/orchestrator.py` | Pipeline coordination, agent dispatch |
| Agents | `agents/*.py` | Specialized diagnosis processing |
| Ontology Parser | `ontology/parser.py` | TTL parsing, domain knowledge queries |
| LLM Service | `llm/service.py` | LLM API integration, structured output |
| Models | `models.py` | Pydantic data models for API |
| Config | `config.py` | Centralized configuration management |
| Dependencies | `dependencies.py` | DI container, Protocol interfaces |
| Knowledge | `diagnosis_knowledge.py` | Centralized diagnosis constants |

---

## 3. Agent Pipeline

### 3.1 Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENT PIPELINE FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                         ┌─────────────────┐                                 │
│                         │   WebSocket     │                                 │
│                         │    Client       │                                 │
│                         └────────┬────────┘                                 │
│                                  │ DiagnosisRequest                          │
│                                  ▼                                          │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║                         ORCHESTRATOR AGENT                             ║  │
│  ║  [ORCH]                                                                ║  │
│  ║  ┌─────────────────────────────────────────────────────────────────┐  ║  │
│  ║  │ Mode Selection:                                                  │  ║  │
│  ║  │   use_llm_mode=True  ──► LLM Pipeline (Single Agent)            │  ║  │
│  ║  │   use_llm_mode=False ──► Legacy Pipeline (Multi-Agent)          │  ║  │
│  ║  └─────────────────────────────────────────────────────────────────┘  ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                  │                                          │
│              ┌───────────────────┴───────────────────┐                      │
│              │                                       │                      │
│              ▼                                       ▼                      │
│  ┌───────────────────────────┐      ┌────────────────────────────────────┐ │
│  │     LLM MODE (Default)    │      │        LEGACY MODE                 │ │
│  │                           │      │                                    │ │
│  │  ┌─────────────────────┐  │      │  ┌───────┐    ┌───────┐            │ │
│  │  │    LLM Agent        │  │      │  │  SYM  │───►│  ONT  │            │ │
│  │  │    [LLM]            │  │      │  │Parser │    │Fetcher│            │ │
│  │  │                     │  │      │  └───┬───┘    └───┬───┘            │ │
│  │  │  ┌───────────────┐  │  │      │      │            │                │ │
│  │  │  │ Parse Symptom │  │  │      │      │            │                │ │
│  │  │  │ Match Rules   │  │  │      │      ▼            ▼                │ │
│  │  │  │ Generate Hypo │  │  │      │  ┌───────────────────────┐         │ │
│  │  │  │ Calc Conf     │  │  │      │  │        RULE           │         │ │
│  │  │  │ Adapt Output  │  │  │      │  │      [RULE]           │         │ │
│  │  │  └───────────────┘  │  │      │  └───────────┬───────────┘         │ │
│  │  └─────────────────────┘  │      │              │                     │ │
│  │                           │      │              ▼                     │ │
│  │                           │      │  ┌───────┐  ┌───────┐  ┌───────┐  │ │
│  │                           │      │  │ CONF  │─►│  OUT  │─►│ DONE  │  │ │
│  │                           │      │  │Calc   │  │Adapt  │  │       │  │ │
│  │                           │      │  └───────┘  └───────┘  └───────┘  │ │
│  └───────────────────────────┘      └────────────────────────────────────┘ │
│              │                                       │                      │
│              └───────────────────┬───────────────────┘                      │
│                                  │                                          │
│                                  ▼                                          │
│                         ┌─────────────────┐                                 │
│                         │  DiagnosisContext│                                │
│                         │  (Result)        │                                │
│                         └────────┬────────┘                                 │
│                                  │                                          │
│                                  ▼                                          │
│                         ┌─────────────────┐                                 │
│                         │   WebSocket     │                                 │
│                         │    Response     │                                 │
│                         └─────────────────┘                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Agent Details

| Agent ID | Name | Responsibility |
|----------|------|----------------|
| `ORCH` | OrchestratorAgent | Pipeline coordination, mode selection, error recovery |
| `LLM` | LLMDiagnosisAgent | Complete LLM-powered diagnosis (replaces SYM+RULE+OUT) |
| `SYM` | SymptomParserAgent | Parse symptom text, extract keywords, classify scenario |
| `ONT` | OntologyFetcherAgent | Query ontology for relevant classes/properties/signals |
| `RULE` | RuleEngineAgent | Match diagnostic rules, generate hypotheses |
| `CONF` | ConfidenceCalcAgent | Calculate confidence scores based on factors |
| `OUT` | OutputAdapterAgent | Generate role-adapted HTML output |

### 3.3 Agent Communication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AGENT MESSAGE BUS FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ORCH ────────────────────────────────────────────────────────────────►    │
│     │                                                                        │
│     │ send_msg_bus("ALL", [...])                                            │
│     │ animate_wire("llm")                                                    │
│     ▼                                                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        MESSAGE BUS                                    │   │
│   │  ┌─────────────────────────────────────────────────────────────┐    │   │
│   │  │  {                                                          │    │   │
│   │  │    "type": "msg_bus",                                       │    │   │
│   │  │    "from": "orch",                                          │    │   │
│   │  │    "to": "llm",                                             │    │   │
│   │  │    "pairs": [                                               │    │   │
│   │  │      {"k": "指令", "v": "LLM_DIAGNOSIS"},                   │    │   │
│   │  │      {"k": "症状", "v": "踩刹车按启动按钮..."}              │    │   │
│   │  │    ]                                                        │    │   │
│   │  │  }                                                          │    │   │
│   │  └─────────────────────────────────────────────────────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│     │                                                                        │
│     │ Wire Animation                                                         │
│     ▼                                                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  { "type": "wire_animate", "from": "orch", "to": "llm" }             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   LLM ◄─────────────────────────────────────────────────────────────────    │
│     │                                                                        │
│     │ process(context)                                                       │
│     │                                                                        │
│     ├──► send({ "type": "reasoning_step", ... })                            │
│     ├──► send({ "type": "hypothesis", ... })                                │
│     ├──► send({ "type": "conf_factors", ... })                              │
│     └──► send({ "type": "output", ... })                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 BaseAgent Class Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT CLASS HIERARCHY                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                        ┌──────────────────────┐                             │
│                        │     BaseAgent        │                             │
│                        │    (Abstract)        │                             │
│                        ├──────────────────────┤                             │
│                        │ + agent_id: AgentID  │                             │
│                        │ + state: AgentState  │                             │
│                        │ + progress: int      │                             │
│                        ├──────────────────────┤                             │
│                        │ + set_sender()       │                             │
│                        │ + send()             │                             │
│                        │ + update_status()    │                             │
│                        │ + send_msg_bus()     │                             │
│                        │ + animate_wire()     │                             │
│                        │ + process() [abs]    │                             │
│                        │ + run()              │                             │
│                        └──────────┬───────────┘                             │
│                                   │                                          │
│           ┌───────────────────────┼───────────────────────┐                 │
│           │                       │                       │                 │
│           ▼                       ▼                       ▼                 │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐           │
│  │ OrchestratorAgent│   │ LLMDiagnosisAgent│   │ SymptomParserAgent│         │
│  ├─────────────────┤   ├─────────────────┤   ├─────────────────┤           │
│  │ + agents: Dict  │   │ + llm_service   │   │ + patterns      │           │
│  │ + use_llm: bool │   │ + fallback      │   └─────────────────┘           │
│  ├─────────────────┤   ├─────────────────┤                                 │
│  │ + register()    │   │ + diagnose()    │                                 │
│  │ + broadcast()   │   └─────────────────┘                                 │
│  └─────────────────┘                                                        │
│                                                                              │
│           ┌───────────────────────┼───────────────────────┐                 │
│           │                       │                       │                 │
│           ▼                       ▼                       ▼                 │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐           │
│  │OntologyFetcher  │   │  RuleEngineAgent │   │ConfidenceCalcAgent│         │
│  │     Agent       │   │                 │   │                 │           │
│  ├─────────────────┤   ├─────────────────┤   ├─────────────────┤           │
│  │ + parser        │   │ + rules         │   │ + factors       │           │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘           │
│                                                                              │
│                                  │                                           │
│                                  ▼                                           │
│                        ┌─────────────────┐                                  │
│                        │OutputAdapterAgent│                                  │
│                        ├─────────────────┤                                  │
│                        │ + templates     │                                  │
│                        │ + adapt()       │                                  │
│                        └─────────────────┘                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. WebSocket Communication

### 4.1 Connection Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     WEBSOCKET CONNECTION LIFECYCLE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CLIENT                                           SERVER                    │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  WebSocket Handshake         │             │                       │
│     │  │  ws://localhost:8765/ws      │────────────►│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │                                ┌──────────────┴──────────────┐        │
│     │                                │ ConnectionManager.connect() │        │
│     │                                │ - Check max connections     │        │
│     │                                │ - Accept connection         │        │
│     │                                └──────────────┬──────────────┘        │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Connection Accepted         │◄────────────│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Start Diagnosis Request     │             │                       │
│     │  │  {                           │             │                       │
│     │  │    "type": "start",          │────────────►│                       │
│     │  │    "symptom": "...",         │             │                       │
│     │  │    "role": "owner",          │             │                       │
│     │  │    "signals": {...}          │             │                       │
│     │  │  }                           │             │                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │                                ┌──────────────┴──────────────┐        │
│     │                                │ handle_message()            │        │
│     │                                │ start_diagnosis()           │        │
│     │                                │ pipeline.run(context)       │        │
│     │                                └──────────────┬──────────────┘        │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Agent Status Updates        │             │                       │
│     │  │  { "type": "agent_status" }  │◄────────────│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Reasoning Steps             │             │                       │
│     │  │  { "type": "reasoning_step"} │◄────────────│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Hypotheses                  │             │                       │
│     │  │  { "type": "hypothesis" }    │◄────────────│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Confidence & Output         │             │                       │
│     │  │  { "type": "conf_final" }    │◄────────────│                       │
│     │  │  { "type": "output" }        │◄────────────│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Pipeline Complete           │             │                       │
│     │  │  { "type": "pipeline_done" } │◄────────────│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │  ┌──────────────────────────────┐             │                       │
│     │  │  Disconnect / Close          │────────────►│                       │
│     │  └──────────────────────────────┘             │                       │
│     │                                                │                       │
│     │                                ┌──────────────┴──────────────┐        │
│     │                                │ ConnectionManager.disconnect()│       │
│     │                                └─────────────────────────────┘        │
│     │                                                │                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Message Types

#### 4.2.1 Client → Server Messages

```python
# Start Diagnosis Request
{
    "type": "start",
    "symptom": "踩刹车按启动按钮，车辆无法上电",
    "role": "owner",  # owner | technician | customer_service
    "signals": {
        "sv-pm": "0:Off",
        "sv-kv": "INVALID",
        "sv-brk": "VALID"
    }
}
```

#### 4.2.2 Server → Client Messages

| Message Type | Description | Fields |
|-------------|-------------|--------|
| `agent_status` | Agent state update | `agent`, `state`, `progress` |
| `msg_bus` | Agent communication | `from`, `to`, `pairs[]` |
| `wire_animate` | Wire animation trigger | `from`, `to` |
| `reasoning_step` | Reasoning step | `step.title`, `step.body` |
| `onto_summary` | Ontology summary HTML | `html` |
| `rule_matched` | Matched rule info | `rule.id`, `rule.text`, `rule.src`, `rule.conf` |
| `hypothesis` | Diagnosis hypothesis | `hypo.name`, `hypo.pct`, `hypo.cls` |
| `conf_factors` | Confidence factors | `factors[].label`, `factors[].val` |
| `conf_final` | Final confidence | `confidence` |
| `output` | Role-adapted output | `html`, `escalation` |
| `pipeline_done` | Pipeline completion | - |
| `error` | Error message | `message` |

### 4.3 Message Flow Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DIAGNOSIS MESSAGE SEQUENCE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Time ──────────────────────────────────────────────────────────────────►   │
│                                                                              │
│  Client        Server       ORCH        LLM         Message                │
│    │             │           │           │              │                  │
│    │──start──────►           │           │              │                  │
│    │             │───────────►           │              │                  │
│    │             │           │───────────►              │                  │
│    │◄────────────│◄──────────│           │              │ agent_status     │
│    │◄────────────│◄──────────│           │              │ msg_bus          │
│    │◄────────────│◄──────────│───────────│              │ wire_animate     │
│    │             │           │           │────┐         │                  │
│    │◄────────────│◄──────────│◄──────────│◄───┘         │ agent_status     │
│    │◄────────────│◄──────────│◄──────────│              │ reasoning_step   │
│    │◄────────────│◄──────────│◄──────────│              │ reasoning_step   │
│    │◄────────────│◄──────────│◄──────────│              │ hypothesis       │
│    │◄────────────│◄──────────│◄──────────│              │ conf_factors     │
│    │◄────────────│◄──────────│◄──────────│              │ conf_final       │
│    │◄────────────│◄──────────│◄──────────│              │ output           │
│    │◄────────────│◄──────────│           │              │ agent_status     │
│    │◄────────────│◄──────────│           │              │ msg_bus          │
│    │◄────────────│◄──────────│           │              │ pipeline_done    │
│    │             │           │           │              │                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Ontology Integration

### 5.1 Ontology Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ONTOLOGY INTEGRATION ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    vehicle_power_mode_ontology.ttl                    │   │
│  │                                                                       │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │   OWL Classes   │  │    Properties   │  │  Named Individuals  │  │   │
│  │  │                 │  │                 │  │                     │  │   │
│  │  │ • PowerMode     │  │ • hasSignal     │  │ • OffMode           │  │   │
│  │  │ • ECU           │  │ • hasState      │  │ • LocalOnMode       │  │   │
│  │  │ • KeyType       │  │ • triggers      │  │ • RemoteOnMode      │  │   │
│  │  │ • Signal        │  │ • dependsOn     │  │ • BLEKey            │  │   │
│  │  │ • Transition    │  │ • hasDomain     │  │ • NFCKey            │  │   │
│  │  │                 │  │ • hasRange      │  │ • LDCU              │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                     SWRL Rules (in comments)                    │ │   │
│  │  │                                                                  │ │   │
│  │  │  # Rule T_1_2: ZAT Power On Transition                          │ │   │
│  │  │  # BrkPedalStVD=VALID ^ GE_Fahrstufe=P/N ^ ZATPressed           │ │   │
│  │  │  #   -> KeySearchingSt=InitialSearch ^ tKeyValid(30s)           │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    │ parse()                                  │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          OntologyParser                               │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  + graph: rdflib.Graph                                          │ │   │
│  │  │  + classes: Dict[str, OntologyClass]                            │ │   │
│  │  │  + object_properties: Dict[str, OntologyProperty]               │ │   │
│  │  │  + datatype_properties: Dict[str, OntologyProperty]             │ │   │
│  │  │  + individuals: Dict[str, OntologyIndividual]                   │ │   │
│  │  │  + swrl_rules: List[SWRLRule]                                   │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  Query Methods:                                                  │ │   │
│  │  │  + get_class(name) -> OntologyClass                             │ │   │
│  │  │  + get_property(name) -> OntologyProperty                       │ │   │
│  │  │  + get_signal_info(signal_name) -> Dict                         │ │   │
│  │  │  + get_power_mode_info() -> Dict                                │ │   │
│  │  │  + get_key_types() -> Dict                                      │ │   │
│  │  │  + get_ecu_info() -> Dict                                       │ │   │
│  │  │  + search_by_keyword(keyword) -> Dict                           │ │   │
│  │  │  + get_transition_rules() -> List                               │ │   │
│  │  │  + get_ontology_summary_html(context) -> str                    │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                    ┌───────────────┼───────────────┐                        │
│                    │               │               │                        │
│                    ▼               ▼               ▼                        │
│           ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│           │OntologyFetch│  │     LLM     │  │  Scenario   │                 │
│           │    Agent    │  │   Service   │  │  Detector   │                 │
│           └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Ontology Data Structures

```python
@dataclass
class OntologyClass:
    uri: str
    label: str
    label_zh: str = ""
    comment: str = ""
    comment_zh: str = ""
    parent_classes: List[str] = field(default_factory=list)
    properties: List[str] = field(default_factory=list)

@dataclass
class OntologyProperty:
    uri: str
    label: str
    label_zh: str = ""
    comment: str = ""
    comment_zh: str = ""
    domain: List[str] = field(default_factory=list)
    range: List[str] = field(default_factory=list)
    property_type: str = "object"  # "object" or "datatype"

@dataclass
class OntologyIndividual:
    uri: str
    label: str
    label_zh: str = ""
    class_type: str = ""
    property_values: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SWRLRule:
    rule_id: str
    conditions: List[str]
    actions: List[str]
    source: str = ""
    confidence: float = 0.95
```

### 5.3 Domain Knowledge Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     VEHICLE POWER ONTOLOGY HIERARCHY                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌──────────────┐                                  │
│                           │  owl:Thing   │                                  │
│                           └──────┬───────┘                                  │
│                                  │                                          │
│         ┌────────────────────────┼────────────────────────┐                 │
│         │                        │                        │                 │
│         ▼                        ▼                        ▼                 │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐           │
│  │  PowerMode  │         │     ECU     │         │   KeyType   │           │
│  └──────┬──────┘         └──────┬──────┘         └──────┬──────┘           │
│         │                       │                       │                   │
│    ┌────┴────┐           ┌─────┴─────┐            ┌─────┴─────┐            │
│    │         │           │           │            │           │            │
│    ▼         ▼           ▼           ▼            ▼           ▼            │
│ ┌──────┐ ┌──────┐   ┌──────┐  ┌──────┐      ┌──────┐  ┌──────┐            │
│ │ Off  │ │ On   │   │ LDCU │  │ TBOX │      │ BLE  │  │ NFC  │            │
│ │ Mode │ │ Mode │   │      │  │      │      │ Key  │  │ Key  │            │
│ └──────┘ └──┬───┘   └──────┘  └──────┘      └──────┘  └──────┘            │
│             │                                                               │
│        ┌────┴────┐                                                          │
│        │         │                                                          │
│        ▼         ▼                                                          │
│   ┌─────────┐ ┌─────────┐                                                   │
│   │ LocalOn │ │RemoteOn │                                                   │
│   │  Mode   │ │  Mode   │                                                   │
│   └─────────┘ └─────────┘                                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Key Relationships                             │    │
│  │                                                                      │    │
│  │  PowerMode ──hasSignal──► Signal (LDCU_PowerMode, KeyValidSt, etc.) │    │
│  │  ECU ──hasComponent──► Sensor/Actuator                              │    │
│  │  KeyType ──authenticates──► PowerMode transition                    │    │
│  │  Transition ──triggers──► StateChange                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. LLM Service Architecture

### 6.1 LLM Service Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LLM SERVICE ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          LLMService                                  │   │
│  │                                                                       │   │
│  │  diagnose(request, ontology_parser, fallback_handler)                │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                 │                                            │
│                                 ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          LLMTools                                    │   │
│  │                                                                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │parse_symptom │  │ match_rules  │  │   generate_diagnosis     │   │   │
│  │  │              │  │              │  │                          │   │   │
│  │  │ Extract:     │  │ Match:       │  │ Generate:                │   │   │
│  │  │ - fault_type │  │ - rule_id    │  │ - reasoning_steps        │   │   │
│  │  │ - components │  │ - confidence │  │ - hypotheses             │   │   │
│  │  │ - scenario   │  │ - match_text │  │ - confidence_factors     │   │   │
│  │  │ - severity   │  │              │  │ - role_adapted_output    │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘   │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                 │                                            │
│                    ┌────────────┴────────────┐                              │
│                    │                         │                              │
│                    ▼                         ▼                              │
│         ┌──────────────────┐     ┌──────────────────┐                       │
│         │  LiteLLMClient   │     │ CustomLLMClient  │                       │
│         │                  │     │                  │                       │
│         │ • OpenAI         │     │ • REST API       │                       │
│         │ • Anthropic      │     │ • Custom headers │                       │
│         │ • Custom endpoint│     │ • Retry logic    │                       │
│         │ • Streaming      │     │ • Timeout config │                       │
│         └──────────────────┘     └──────────────────┘                       │
│                    │                         │                              │
│                    └────────────┬────────────┘                              │
│                                 │                                            │
│                                 ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      LLM Provider (External)                         │   │
│  │                                                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐    │   │
│  │  │  OpenAI  │ │ Claude   │ │ Gemini   │ │ Custom Internal LLM  │    │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Diagnosis Request/Response Models

```python
# Request
class SignalInfo(BaseModel):
    key: str           # Signal name (e.g., "LDCU_PowerMode")
    value: str         # Signal value (e.g., "0:Off")

class DiagnosisRequest(BaseModel):
    symptom: str       # User's symptom description
    role: Role         # owner | technician | customer_service
    signals: List[SignalInfo]

# Response
class ReasoningStep(BaseModel):
    step_number: int
    title: str
    body: str

class DiagnosticHypothesis(BaseModel):
    root_cause: str
    confidence: float
    rank: int
    verification_steps: List[str]

class ConfidenceFactor(BaseModel):
    label: str
    value: float
    category: str

class DiagnosisResponse(BaseModel):
    diagnosis_id: str
    summary: str
    reasoning_steps: List[ReasoningStep]
    primary_hypothesis: Optional[DiagnosticHypothesis]
    secondary_hypotheses: List[DiagnosticHypothesis]
    final_confidence: float
    confidence_factors: List[ConfidenceFactor]
    output_for_owner: Optional[str]
    output_for_technician: Optional[str]
    output_for_customer_service: Optional[str]
    model_used: str
    processing_time_ms: Optional[int]
    escalation_hint: Optional[str]
```

### 6.3 Fallback Mechanism

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FALLBACK MECHANISM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                    ┌─────────────────────┐                                  │
│                    │   Diagnosis Request │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                              │
│                               ▼                                              │
│              ┌────────────────────────────────┐                             │
│              │      LLMService.diagnose()     │                             │
│              └────────────────┬───────────────┘                             │
│                               │                                              │
│                               ▼                                              │
│                    ┌─────────────────────┐                                  │
│                    │   Try LLM Diagnosis │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                              │
│                    ┌──────────┴──────────┐                                  │
│                    │                     │                                  │
│                    ▼                     ▼                                  │
│            ┌─────────────┐       ┌─────────────┐                            │
│            │   SUCCESS   │       │   FAILURE   │                            │
│            │             │       │             │                            │
│            │ Return      │       │ Check       │                            │
│            │ Diagnosis   │       │ enable_     │                            │
│            │ Response    │       │ fallback    │                            │
│            └──────┬──────┘       └──────┬──────┘                            │
│                   │                     │                                    │
│                   │                     ▼                                    │
│                   │            ┌─────────────────┐                           │
│                   │            │ enable_fallback │                           │
│                   │            │     = True?     │                           │
│                   │            └────────┬────────┘                           │
│                   │                     │                                    │
│                   │            ┌────────┴────────┐                           │
│                   │            │                 │                           │
│                   │            ▼                 ▼                           │
│                   │    ┌─────────────┐   ┌─────────────┐                     │
│                   │    │    YES      │   │     NO      │                     │
│                   │    │             │   │             │                     │
│                   │    │ Fallback    │   │ Return      │                     │
│                   │    │ Handler     │   │ Error       │                     │
│                   │    │ .diagnose() │   │ Response    │                     │
│                   │    └──────┬──────┘   └──────┬──────┘                     │
│                   │           │                 │                            │
│                   │           ▼                 │                            │
│                   │  ┌─────────────────┐        │                            │
│                   │  │ Rule-based      │        │                            │
│                   │  │ Diagnosis       │        │                            │
│                   │  │                 │        │                            │
│                   │  │ • Pattern match │        │                            │
│                   │  │ • Rule lookup   │        │                            │
│                   │  │ • Template out  │        │                            │
│                   │  └────────┬────────┘        │                            │
│                   │           │                 │                            │
│                   └───────────┴─────────────────┘                            │
│                               │                                              │
│                               ▼                                              │
│                    ┌─────────────────────┐                                  │
│                    │ Diagnosis Response  │                                  │
│                    └─────────────────────┘                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Configuration Management

### 7.1 Configuration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONFIGURATION MANAGEMENT                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Configuration Sources                            │    │
│  │                                                                      │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐   │    │
│  │  │ Environment   │  │  .env File    │  │    Default Values     │   │    │
│  │  │ Variables     │  │               │  │                       │   │    │
│  │  │ (APP_*)       │  │ backend/.env  │  │ config.py Settings    │   │    │
│  │  │               │  │               │  │                       │   │    │
│  │  │ Priority: 1   │  │ Priority: 2   │  │ Priority: 3           │   │    │
│  │  └───────────────┘  └───────────────┘  └───────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                 │                                            │
│                                 │ pydantic-settings                          │
│                                 ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Settings Class                               │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │ Server Configuration                                             │ │    │
│  │  │ ────────────────────────────────────────────────────────────────│ │    │
│  │  │ server_host: str = "0.0.0.0"                                     │ │    │
│  │  │ server_port: int = 8765                                          │ │    │
│  │  │ server_reload: bool = False                                      │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │ Diagnosis Mode                                                   │ │    │
│  │  │ ────────────────────────────────────────────────────────────────│ │    │
│  │  │ use_llm_mode: bool = True                                        │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │ Ontology Configuration                                           │ │    │
│  │  │ ────────────────────────────────────────────────────────────────│ │    │
│  │  │ ontology_path: Optional[str] = None                              │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │ Logging Configuration                                            │ │    │
│  │  │ ────────────────────────────────────────────────────────────────│ │    │
│  │  │ log_level: str = "INFO"                                          │ │    │
│  │  │ log_file: str = "backend.log"                                    │ │    │
│  │  │ log_rotation: str = "10 MB"                                      │ │    │
│  │  │ log_retention: str = "7 days"                                    │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │ WebSocket Configuration                                          │ │    │
│  │  │ ────────────────────────────────────────────────────────────────│ │    │
│  │  │ ws_heartbeat_interval: int = 30                                  │ │    │
│  │  │ ws_max_connections: int = 100                                    │ │    │
│  │  │ ws_endpoint: str = "/ws"                                         │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                 │                                            │
│                                 ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Global Settings Instance                        │   │
│  │                                                                       │   │
│  │  get_settings() -> Settings                                          │   │
│  │  reload_settings() -> Settings                                       │   │
│  │  reset_settings() -> None                                            │   │
│  │  setup_logging(settings) -> None                                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `APP_SERVER_PORT` | `8765` | Server port |
| `APP_SERVER_RELOAD` | `false` | Enable auto-reload (dev) |
| `APP_USE_LLM_MODE` | `true` | Use LLM diagnosis mode |
| `APP_ONTOLOGY_PATH` | `None` | Custom ontology path |
| `APP_LOG_LEVEL` | `INFO` | Logging level |
| `APP_LOG_FILE` | `backend.log` | Log file path |
| `APP_WS_HEARTBEAT_INTERVAL` | `30` | WebSocket heartbeat (seconds) |
| `APP_WS_MAX_CONNECTIONS` | `100` | Max concurrent connections |

---

## 8. Data Models

### 8.1 Core Models

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA MODEL OVERVIEW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          ENUMS                                         │  │
│  │                                                                        │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │  │
│  │  │   AgentState    │  │    AgentID      │  │       Role          │   │  │
│  │  ├─────────────────┤  ├─────────────────┤  ├─────────────────────┤   │  │
│  │  │ IDLE            │  │ ORCH            │  │ OWNER               │   │  │
│  │  │ RUNNING         │  │ SYM             │  │ TECHNICIAN          │   │  │
│  │  │ DONE            │  │ ONT             │  │ CUSTOMER_SERVICE    │   │  │
│  │  │ ERROR           │  │ RULE            │  │                     │   │  │
│  │  │                 │  │ CONF            │  │                     │   │  │
│  │  │                 │  │ OUT             │  │                     │   │  │
│  │  │                 │  │ LLM             │  │                     │   │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      DIAGNOSIS CONTEXT                                 │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │ DiagnosisContext                                                 │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │ INPUT:                                                           │  │  │
│  │  │   symptom: str                                                   │  │  │
│  │  │   role: Role                                                     │  │  │
│  │  │   signals: Dict[str, str]                                        │  │  │
│  │  │   vehicle_signals: Optional[VehicleSignals]                      │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │ PROCESSED:                                                       │  │  │
│  │  │   parsed_symptoms: List[str]                                     │  │  │
│  │  │   relevant_signals: Dict[str, Any]                               │  │  │
│  │  │   reasoning_steps: List[ReasoningStep]                           │  │  │
│  │  │   matched_rules: List[Rule]                                      │  │  │
│  │  │   hypotheses: List[Hypothesis]                                   │  │  │
│  │  ├─────────────────────────────────────────────────────────────────┤  │  │
│  │  │ OUTPUT:                                                          │  │  │
│  │  │   confidence_factors: List[ConfFactor]                           │  │  │
│  │  │   final_confidence: int                                          │  │  │
│  │  │   output_html: str                                               │  │  │
│  │  │   escalation_hint: Optional[str]                                 │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      SUPPORTING MODELS                                 │  │
│  │                                                                        │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │  │
│  │  │  ReasoningStep  │  │   Hypothesis    │  │      Rule           │   │  │
│  │  ├─────────────────┤  ├─────────────────┤  ├─────────────────────┤   │  │
│  │  │ title: str      │  │ name: str       │  │ id: str             │   │  │
│  │  │ body: str       │  │ pct: int        │  │ text: str           │   │  │
│  │  │                 │  │ cls: str        │  │ src: str            │   │  │
│  │  │                 │  │                 │  │ conf: str           │   │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘   │  │
│  │                                                                        │  │
│  │  ┌─────────────────┐  ┌─────────────────┐                             │  │
│  │  │   ConfFactor    │  │ VehicleSignals  │                             │  │
│  │  ├─────────────────┤  ├─────────────────┤                             │  │
│  │  │ label: str      │  │ ldcu_power_mode │                             │  │
│  │  │ val: float      │  │ key_valid_st    │                             │  │
│  │  │ display: str    │  │ brk_pedal_st    │                             │  │
│  │  │                 │  │ ... (21 fields) │                             │  │
│  │  └─────────────────┘  └─────────────────┘                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Error Handling & Fallback

### 9.1 Error Categories

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ERROR HANDLING HIERARCHY                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                              Exception                                       │
│                                  │                                           │
│                                  ▼                                           │
│                         ┌────────────────┐                                  │
│                         │    LLMError    │                                  │
│                         └───────┬────────┘                                  │
│                                 │                                            │
│          ┌──────────────────────┼──────────────────────┐                    │
│          │                      │                      │                    │
│          ▼                      ▼                      ▼                    │
│  ┌───────────────┐     ┌───────────────┐     ┌───────────────┐             │
│  │LLMConnection  │     │ LLMTimeout    │     │ LLMResponse   │             │
│  │    Error      │     │    Error      │     │    Error      │             │
│  └───────────────┘     └───────────────┘     └───────────────┘             │
│          │                      │                      │                    │
│          ▼                      │                      ▼                    │
│  ┌───────────────┐              │             ┌───────────────┐             │
│  │LLMRateLimit   │              │             │LLMResponse    │             │
│  │    Error      │              │             │ParseError     │             │
│  └───────────────┘              │             └───────────────┘             │
│                                 │                                            │
│                                 ▼                                            │
│                    ┌────────────────────────┐                               │
│                    │   FallbackHandler      │                               │
│                    │                        │                               │
│                    │ • Rule-based diagnosis │                               │
│                    │ • Pattern matching     │                               │
│                    │ • Template output      │                               │
│                    └────────────────────────┘                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Fallback Handler Logic

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FALLBACK HANDLER FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Input: DiagnosisRequest                                                   │
│          │                                                                   │
│          ▼                                                                   │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    FallbackHandler.diagnose()                        │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │                                           │
│                                  ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  1. detect_scenario(symptom, signals)                                │  │
│   │     ┌────────────────────────────────────────────────────────────┐   │  │
│   │     │ Pattern matching against SYMPTOM_PATTERNS                  │   │  │
│   │     │                                                            │   │  │
│   │     │ "ble_auth"    → BLE authentication failure                 │   │  │
│   │     │ "key_timeout" → Key search timeout                         │   │  │
│   │     │ "bms_charging"→ Battery thermal protection                 │   │  │
│   │     │ "auto_poweroff" → Auto power-off trigger                   │   │  │
│   │     └────────────────────────────────────────────────────────────┘   │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │                                           │
│                                  ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  2. get_rules_for_scenario(scenario)                                 │  │
│   │     ┌────────────────────────────────────────────────────────────┐   │  │
│   │     │ Lookup SCENARIO_RULES_MAP                                   │   │  │
│   │     │                                                            │   │  │
│   │     │ ble_auth → ["T_1_2", "R-KEY001", "R-BLE001", "R-BLE002"]  │   │  │
│   │     │ bms_charging → ["R-BMS001-P2", "R-SAFE-003"]               │   │  │
│   │     └────────────────────────────────────────────────────────────┘   │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │                                           │
│                                  ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  3. get_hypotheses_for_scenario(scenario)                            │  │
│   │     ┌────────────────────────────────────────────────────────────┐   │  │
│   │     │ Lookup HYPOTHESIS_TEMPLATES                                 │   │  │
│   │     │                                                            │   │  │
│   │     │ ble_auth → [                                               │   │  │
│   │     │   {name: "手机BLE连接认证失败", pct: 55, cls: "p"},        │   │  │
│   │     │   {name: "BLE配对信息丢失需重新绑定", pct: 30, cls: "s"},   │   │  │
│   │     │   {name: "TBOX BLE模块固件/硬件异常", pct: 15, cls: "t"}   │   │  │
│   │     │ ]                                                          │   │  │
│   │     └────────────────────────────────────────────────────────────┘   │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │                                           │
│                                  ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  4. get_output_for_role(scenario, role)                              │  │
│   │     ┌────────────────────────────────────────────────────────────┐   │  │
│   │     │ Lookup OUTPUT_TEMPLATES[scenario][role]                     │   │  │
│   │     │                                                            │   │  │
│   │     │ ble_auth + owner → "手机蓝牙钥匙认证失败..."                │   │  │
│   │     │ ble_auth + technician → "T_1_2 转移失败 — BLE认证失败..."  │   │  │
│   │     │ ble_auth + customer_service → "车辆蓝牙钥匙认证异常..."    │   │  │
│   │     └────────────────────────────────────────────────────────────┘   │  │
│   └──────────────────────────────┬───────────────────────────────────────┘  │
│                                  │                                           │
│                                  ▼                                           │
│   Output: DiagnosisResponse                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Deployment

### 10.1 Directory Structure

```
ontology/
├── backend/
│   ├── main.py                    # Entry point
│   ├── server.py                  # FastAPI + WebSocket server
│   ├── models.py                  # Pydantic models
│   ├── config.py                  # Configuration management
│   ├── dependencies.py            # DI container
│   ├── diagnosis_knowledge.py     # Centralized constants
│   ├── scenario_detector.py       # Scenario detection
│   ├── requirements.txt           # Python dependencies
│   ├── pytest.ini                 # pytest configuration
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseAgent + AgentFactory
│   │   ├── orchestrator.py        # Pipeline coordinator
│   │   ├── symptom_parser.py      # Symptom parsing
│   │   ├── ontology_fetcher.py    # Ontology queries
│   │   ├── rule_engine.py         # Rule matching
│   │   ├── confidence_calc.py     # Confidence calculation
│   │   ├── output_adapter.py      # Output adaptation
│   │   └── llm_diagnosis_agent.py # LLM-powered diagnosis
│   │
│   ├── ontology/
│   │   ├── __init__.py
│   │   └── parser.py              # TTL/RDF parser
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── config.py              # LLM configuration
│   │   ├── service.py             # LLM service layer
│   │   ├── schemas.py             # Request/response schemas
│   │   ├── prompts.py             # Prompt templates
│   │   └── fallback.py            # Rule-based fallback
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                # CLI entry point
│   │   ├── diagnosis_service.py   # CLI diagnosis service
│   │   └── output_formatter.py    # CLI output formatting
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py            # Shared fixtures
│       ├── test_models.py
│       ├── test_config.py
│       ├── test_dependencies.py
│       └── test_diagnosis_knowledge.py
│
├── vehicle_power_mode_ontology.ttl  # OWL ontology file
├── multi-agent-demo.html           # Frontend (single HTML)
└── docs/
    └── TECHNICAL_DESIGN.md         # This document
```

### 10.2 Running the Server

```bash
# Setup
cd backend
pip install -r requirements.txt

# Run with default settings
python main.py

# Run with custom configuration
APP_SERVER_PORT=9000 APP_LOG_LEVEL=DEBUG python main.py

# Run in legacy mode (no LLM)
APP_USE_LLM_MODE=false python main.py
```

### 10.3 Testing

```bash
# Run all tests
cd backend
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_models.py -v

# Run with coverage
python -m pytest tests/ -v --cov=. --cov-report=html
```

### 10.4 Health Check

```bash
# HTTP health endpoint
curl http://localhost:8765/health

# Response
{
  "status": "healthy",
  "ontology_loaded": true,
  "pipeline_ready": true
}
```

---

## Appendix A: Quick Reference

### A.1 Agent IDs

| ID | Full Name | Description |
|----|-----------|-------------|
| `orch` | OrchestratorAgent | Pipeline coordination |
| `llm` | LLMDiagnosisAgent | LLM-powered diagnosis |
| `sym` | SymptomParserAgent | Symptom parsing |
| `ont` | OntologyFetcherAgent | Ontology queries |
| `rule` | RuleEngineAgent | Rule matching |
| `conf` | ConfidenceCalcAgent | Confidence calculation |
| `out` | OutputAdapterAgent | Output adaptation |

### A.2 Message Types Quick Reference

| Type | Direction | Purpose |
|------|-----------|---------|
| `start` | Client→Server | Start diagnosis |
| `agent_status` | Server→Client | Agent state update |
| `msg_bus` | Server→Client | Agent communication |
| `wire_animate` | Server→Client | Wire animation |
| `reasoning_step` | Server→Client | Reasoning step |
| `hypothesis` | Server→Client | Hypothesis |
| `conf_factors` | Server→Client | Confidence factors |
| `conf_final` | Server→Client | Final confidence |
| `output` | Server→Client | Final output |
| `pipeline_done` | Server→Client | Pipeline complete |
| `error` | Server→Client | Error message |

### A.3 Configuration Quick Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_SERVER_PORT` | 8765 | Server port |
| `APP_USE_LLM_MODE` | true | LLM mode toggle |
| `APP_LOG_LEVEL` | INFO | Log level |
| `APP_ONTOLOGY_PATH` | auto | Ontology file path |

---

**Document End**
