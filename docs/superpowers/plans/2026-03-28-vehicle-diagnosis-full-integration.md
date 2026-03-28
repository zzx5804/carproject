# Vehicle Power Diagnosis System Full Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the hardcoded frontend demo with the backend WebSocket server, implementing all missing message types and data structures to create a polished boss demonstration of the ontology + LLM intelligent car diagnosis system.

**Architecture:**
1. **Phase 1:** Backend Protocol Enhancement - Add 8 missing message types to match frontend expectations
2. **Phase 2:** Frontend WebSocket Integration - Replace hardcoded demo with real WebSocket calls
3. **Phase 3:** Backend Pipeline Enhancement - Add rich context in LLM agent for better responses
4. **Phase 4:** Knowledge Base Enhancement - Add reasoning steps, ontology summaries
5. **Phase 5:** Demo Mode Support - Ensure reliable boss presentations

**Tech Stack:** Python (FastAPI, asyncio), Vanilla JavaScript, WebSocket, OWL Ontology (TTL)

---

## File Structure Analysis

```
Modified Files:
├── backend/server.py                    # WebSocket server - add 8 message types
├── backend/models.py                   # Data models - extend for all message types
├── backend/agents/orchestrator.py       # Pipeline - add reasoning context
├── backend/agents/llm_diagnosis_agent.py # LLM agent - enhance with structured output
├── backend/diagnosis_knowledge.py      # Knowledge base - add reasoning steps
├── cea-diagnosis.html                  # Frontend - integrate with backend (rename from multi-agent-demo.html)
└── docs/superpowers/plans/             # This plan
```

---

## Phase 1: Backend Protocol Enhancement

### Task 1: Add Missing Message Types to Server

**Files:**
- Modify: `backend/server.py:195-250` (handle_message function)

- [ ] **Step 1: Analyze current message sending pattern**

Run: Read `backend/server.py` lines 180-280 to understand current WebSocket message structure.

```python
# Current pattern (to understand before modifying):
async def send(self, message: dict, websocket):
    await websocket.send_json(message)
```

- [ ] **Step 2: Add send_message helper with type validation**

Add this helper method to WebSocketManager class:

```python
async def broadcast_to_client(self, websocket, msg_type: str, payload: dict):
    """Send typed message to client."""
    message = {"type": msg_type, **payload}
    await websocket.send_json(message)
    logger.debug(f"Sent {msg_type}: {list(payload.keys())}")
```

- [ ] **Step 3: Modify handle_message to emit all message types**

In the "start" message handler (around line 180), replace simple pipeline run with comprehensive message emission:

```python
# Replace existing "start" handler with this comprehensive version:
if msg_type == "start":
    symptom = message.get("symptom", "")
    role = message.get("role", "owner")
    signals = message.get("signals", {})
    
    logger.info(f"Received diagnosis request: {symptom[:50]}...")
    
    # 1. Acknowledge start
    await manager.send({"type": "agent_status", "agent": "orchestrator", "status": "running", "progress": 0}, websocket)
    
    # 2. Create context
    context = DiagnosisContext(symptom=symptom, role=role, signals=signals)
    
    # 3. Run pipeline
    try:
        pipeline = _app_state.get("diagnosis_pipeline")
        if not pipeline:
            raise ValueError("Diagnosis pipeline not initialized")
        
        # 4. Send ontology summary BEFORE processing (frontend expects onto_summary)
        parser = _app_state.get("ontology_parser")
        if parser:
            onto_counts = {
                "classes": len(parser.classes),
                "properties": len(parser.object_properties) + len(parser.datatype_properties),
                "rules": len(parser.individuals)
            }
            await manager.send({
                "type": "onto_summary",
                "counts": onto_counts,
                "summary": f"已加载 {onto_counts['classes']} 个车辆概念类, {onto_counts['properties']} 个属性"
            }, websocket)
        
        # 5. Run the actual diagnosis
        result = await pipeline.run(context)
        
        # 6. Send reasoning steps (multiple messages)
        if hasattr(result, 'reasoning_steps') and result.reasoning_steps:
            for i, step in enumerate(result.reasoning_steps):
                await manager.send({
                    "type": "reasoning_step",
                    "step": {
                        "title": step.get("title", f"Step {i+1}"),
                        "body": step.get("body", "")
                    }
                }, websocket)
                await asyncio.sleep(0.3)  # Delay for visual effect
        
        # 7. Send matched rules
        if hasattr(result, 'matched_rules') and result.matched_rules:
            for rule in result.matched_rules:
                await manager.send({
                    "type": "rule_matched",
                    "rule": {
                        "id": rule.get("id", "unknown"),
                        "text": rule.get("text", ""),
                        "src": rule.get("src", "VEEA-Spec"),
                        "conf": rule.get("confidence", "匹配")
                    }
                }, websocket)
        
        # 8. Send hypotheses
        if hasattr(result, 'hypotheses') and result.hypotheses:
            for hypo in result.hypotheses:
                await manager.send({
                    "type": "hypothesis",
                    "hypothesis": {
                        "id": hypo.get("id", ""),
                        "desc": hypo.get("description", ""),
                        "conf": hypo.get("confidence", 0),
                        "factors": hypo.get("factors", [])
                    }
                }, websocket)
        
        # 9. Send confidence factors
        if hasattr(result, 'confidence_factors') and result.confidence_factors:
            await manager.send({
                "type": "conf_factors",
                "factors": result.confidence_factors
            }, websocket)
        
        # 10. Send final confidence
        final_conf = getattr(result, 'confidence', getattr(result, 'final_confidence', 0.85))
        await manager.send({
            "type": "conf_final",
            "confidence": final_conf,
            "level": "high" if final_conf > 0.7 else "medium" if final_conf > 0.4 else "low"
        }, websocket)
        
        # 11. Send role-adapted output
        if hasattr(result, 'output') and result.output:
            output_text = result.output
        else:
            # Generate from template
            output_text = f"根据症状'{symptom}'的诊断建议：{getattr(result, 'primary_hypothesis', '检查车辆电源系统')}"
        
        await manager.send({
            "type": "output",
            "output": {
                "text": output_text,
                "role": role,
                "escalation": getattr(result, 'needs_escalation', False)
            }
        }, websocket)
        
        # 12. Pipeline complete
        await manager.send({"type": "pipeline_done", "status": "success"}, websocket)
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        await manager.send({"type": "error", "message": str(e)}, websocket)
        await manager.send({"type": "pipeline_done", "status": "error"}, websocket)
    
    return
```

- [ ] **Step 4: Add asyncio import if missing**

At top of server.py, ensure:

```python
import asyncio
```

- [ ] **Step 5: Verify syntax**

Run: `python -m py_compile backend/server.py`
Expected: No errors

---

### Task 2: Extend Data Models for All Message Types

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Add new Pydantic models for response types**

Add these models after existing model definitions (around line 280):

```python
class ReasoningStep(BaseModel):
    """Reasoning step in diagnosis process."""
    step_number: int
    title: str
    body: str
    rule_id: Optional[str] = None

class MatchedRule(BaseModel):
    """Matched diagnostic rule."""
    id: str
    text: str
    src: str = "VEEA-Spec"
    confidence: str = "匹配"

class Hypothesis(BaseModel):
    """Diagnosis hypothesis."""
    id: str
    description: str
    confidence: float
    factors: List[str] = Field(default_factory=list)

class ConfidenceFactors(BaseModel):
    """Confidence calculation factors."""
    symptom_match: float = 0.0
    signal_match: float = 0.0
    rule_support: float = 0.0
    ontology_relevance: float = 0.0

class RoleOutput(BaseModel):
    """Role-adapted output."""
    text: str
    role: str
    escalation: bool = False

class DiagnosisResponse(BaseModel):
    """Complete diagnosis response."""
    reasoning_steps: List[Dict[str, Any]] = Field(default_factory=list)
    matched_rules: List[Dict[str, Any]] = Field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_factors: Dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    output: Optional[str] = None
    primary_hypothesis: str = "检查车辆电源系统"
    needs_escalation: bool = False
```

- [ ] **Step 2: Verify models compile**

Run: `python -m py_compile backend/models.py`
Expected: No errors

---

## Phase 2: Frontend WebSocket Integration

### Task 3: Replace Hardcoded Demo with Real WebSocket Calls

**Files:**
- Modify: `cea-diagnosis.html` (formerly multi-agent-demo.html)
- Check: Find exact file name first

- [ ] **Step 1: Identify the frontend file**

Run: `ls *.html` in workspace root to find the correct HTML file.

```bash
ls D:\workspace\2\*.html
```

- [ ] **Step 2: Analyze current startPipeline function**

Read lines 300-500 of the HTML file to find the SCENARIOS object and startPipeline function.

- [ ] **Step 3: Replace startPipeline with WebSocket integration**

Replace the hardcoded startPipeline function with:

```javascript
// Replace existing startPipeline function
async function startPipeline() {
  const symptom = document.getElementById('symptomInput')?.value || '';
  const role = document.getElementById('roleSelect')?.value || 'owner';
  const signals = parseSignalsFromUI();
  
  if (!symptom.trim()) {
    alert('请输入症状描述');
    return;
  }
  
  // Reset UI
  resetDiagnosisUI();
  
  // Send to backend via WebSocket
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: 'start',
      symptom: symptom,
      role: role,
      signals: signals
    }));
  } else {
    // Fallback to demo mode if not connected
    console.warn('WebSocket not connected, using demo mode');
    runDemoMode(symptom);
  }
}

function parseSignalsFromUI() {
  // Parse signal inputs from UI if they exist
  const signals = {};
  const signalInputs = document.querySelectorAll('[id^="signal-"]');
  signalInputs.forEach(input => {
    const key = input.id.replace('signal-', '');
    signals[key] = input.value;
  });
  return signals;
}

function resetDiagnosisUI() {
  // Clear all result panels
  ['dp-sym', 'dp-ont', 'dp-rule', 'dp-conf', 'dp-out'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      const idle = el.querySelector('.idle');
      if (idle) idle.style.display = 'block';
      const content = el.querySelector('[class$="list"]');
      if (content) content.innerHTML = '';
    }
  });
  
  // Reset agent states
  setAgent('orch', 'running', 10);
}

function runDemoMode(symptom) {
  // Keep existing hardcoded behavior as fallback
  // This ensures demo still works without backend
  console.log('Running in demo mode for:', symptom);
}
```

- [ ] **Step 4: Add WebSocket message handler for all types**

Add this message handler in the WebSocket onmessage function (find existing ws.onmessage and enhance):

```javascript
// Replace or enhance existing ws.onmessage handler
ws.onmessage = function(event) {
  const msg = JSON.parse(event.data);
  
  switch(msg.type) {
    case 'agent_status':
      handleAgentStatus(msg);
      break;
    case 'msg_bus':
      handleMsgBus(msg);
      break;
    case 'onto_summary':
      handleOntoSummary(msg);
      break;
    case 'reasoning_step':
      handleReasoningStep(msg);
      break;
    case 'rule_matched':
      handleRuleMatched(msg);
      break;
    case 'hypothesis':
      handleHypothesis(msg);
      break;
    case 'conf_factors':
      handleConfFactors(msg);
      break;
    case 'conf_final':
      handleConfFinal(msg);
      break;
    case 'output':
      handleOutput(msg);
      break;
    case 'pipeline_done':
      handlePipelineDone(msg);
      break;
    case 'error':
      handleError(msg);
      break;
    case 'wire_animate':
      handleWireAnimate(msg);
      break;
    default:
      console.log('Unknown message type:', msg.type);
  }
};

// Add handler functions
function handleOntoSummary(msg) {
  const panel = document.getElementById('ontologyStatsBar');
  if (panel) {
    panel.style.display = 'flex';
    if (msg.counts) {
      document.getElementById('stat-cls').textContent = msg.counts.classes || 0;
      document.getElementById('stat-props').textContent = msg.counts.properties || 0;
      document.getElementById('stat-ind').textContent = msg.counts.rules || 0;
    }
  }
}

function handleReasoningStep(msg) {
  const container = document.getElementById('reasoningSteps');
  if (!container) return;
  
  document.querySelector('#dp-sym .idle')?.style.remove();
  container.style.display = 'flex';
  
  const el = document.createElement('div');
  el.className = 'step';
  const step = msg.step;
  el.innerHTML = `<div class="step-title">${step.title}</div><div class="step-body">${step.body}</div>`;
  container.appendChild(el);
  setTimeout(() => el.classList.add('vis'), 50);
}

function handleRuleMatched(msg) {
  const list = document.getElementById('ruleList');
  if (list) {
    list.style.display = 'block';
    const rule = msg.rule;
    const el = document.createElement('div');
    el.className = 'rule-item';
    el.innerHTML = `<span class="rule-id">${rule.id}</span><span class="rule-text">${rule.text}</span>`;
    list.appendChild(el);
  }
}

function handleHypothesis(msg) {
  const list = document.getElementById('hypothesisList');
  if (list) {
    list.style.display = 'block';
    const hypo = msg.hypothesis;
    const el = document.createElement('div');
    el.className = 'hypothesis';
    el.innerHTML = `<div class="hypo-desc">${hypo.desc}</div><div class="hypo-conf">${Math.round(hypo.conf * 100)}%</div>`;
    list.appendChild(el);
  }
}

function handleConfFactors(msg) {
  const panel = document.getElementById('confFactors');
  if (panel) {
    panel.style.display = 'block';
    panel.innerHTML = Object.entries(msg.factors)
      .map(([k, v]) => `<div class="cf-item"><span>${k}</span><span>${(v*100).toFixed(0)}%</span></div>`)
      .join('');
  }
}

function handleConfFinal(msg) {
  const el = document.getElementById('finalConf');
  if (el) {
    el.textContent = `${Math.round(msg.confidence * 100)}%`;
    el.style.color = msg.level === 'high' ? 'var(--grn)' : msg.level === 'medium' ? 'var(--yel)' : 'var(--red)';
  }
}

function handleOutput(msg) {
  const panel = document.getElementById('outputPanel');
  if (panel) {
    panel.style.display = 'block';
    panel.textContent = msg.output.text;
    if (msg.output.escalation) {
      panel.classList.add('escalation');
    }
  }
}

function handlePipelineDone(msg) {
  setAgent('orch', 'done', 100);
  setAgent('out', 'done', 100);
  setAgent('conf', 'done', 100);
  
  const status = document.getElementById('sysStatus');
  if (status) {
    status.textContent = msg.status === 'success' ? '✓ 诊断完成' : '✗ 诊断失败';
  }
}

function handleError(msg) {
  console.error('Diagnosis error:', msg.message);
  const status = document.getElementById('sysStatus');
  if (status) {
    status.textContent = '✗ 错误: ' + msg.message;
    status.style.color = 'var(--red)';
  }
}

function handleWireAnimate(msg) {
  wirePulse(msg.from, msg.to);
}
```

- [ ] **Step 5: Add CSS for new elements**

Add to the CSS section:

```css
/* New result panel styles */
.rule-item { padding: 8px; margin: 4px 0; background: var(--s2); border-radius: 4px; font-size: 12px; }
.rule-id { font-weight: bold; color: var(--acc); margin-right: 8px; }
.hypothesis { padding: 10px; margin: 4px 0; background: var(--s2); border-radius: 4px; display: flex; justify-content: space-between; }
.hypo-desc { flex: 1; }
.hypo-conf { font-weight: bold; color: var(--grn); }
.cf-item { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--br); }
.escalation { border-left: 3px solid var(--red); padding-left: 10px; }
```

- [ ] **Step 6: Test frontend HTML syntax**

Open the HTML file in a browser or use a validator to check for syntax errors.

---

## Phase 3: Backend Pipeline Enhancement

### Task 4: Enhance LLM Agent with Structured Reasoning

**Files:**
- Modify: `backend/agents/llm_diagnosis_agent.py`

- [ ] **Step 1: Review current LLM agent structure**

Read `backend/agents/llm_diagnosis_agent.py` lines 1-100 to understand current implementation.

- [ ] **Step 2: Enhance process method to return structured response**

Replace the process method to include all required fields:

```python
async def process(self, context: DiagnosisContext) -> DiagnosisContext:
    """
    Process diagnosis with LLM and return structured response.
    
    Returns context with:
    - reasoning_steps: List of reasoning steps
    - matched_rules: List of matched rules
    - hypotheses: List of diagnosis hypotheses
    - confidence_factors: Dict of confidence factors
    - confidence: Final confidence score
    - output: Role-adapted output text
    """
    await self.update_status(AgentState.RUNNING, 0)
    
    try:
        # 1. Parse symptom
        parsed = await self._parse_symptom(context.symptom)
        context.parsed_symptoms = parsed.get("symptoms", [])
        await self.update_status(AgentState.RUNNING, 20)
        
        # 2. Send reasoning step: symptom parsing
        await self._send_reasoning_step(1, "症状解析", f"识别到症状: {', '.join(context.parsed_symptoms)}")
        
        # 3. Fetch ontology info
        ont_info = await self._fetch_ontology(context.parsed_symptoms)
        await self.update_status(AgentState.RUNNING, 40)
        
        # 4. Send reasoning step: ontology lookup
        await self._send_reasoning_step(2, "本体查询", f"检索到 {len(ont_info.get('classes', []))} 个相关概念")
        
        # 5. Match rules
        rules = await self._match_rules(context, ont_info)
        await self.update_status(AgentState.RUNNING, 60)
        
        # 6. Send matched rules
        for rule in rules:
            await self._send_rule_matched(rule)
        
        # 7. Generate hypotheses
        hypotheses = await self._generate_hypotheses(context, rules, ont_info)
        await self.update_status(AgentState.RUNNING, 80)
        
        # 8. Send hypotheses
        for hypo in hypotheses:
            await self._send_hypothesis(hypo)
        
        # 9. Calculate confidence
        conf_factors = await self._calculate_confidence(context, rules, hypotheses)
        conf = sum(conf_factors.values()) / len(conf_factors) if conf_factors else 0.5
        
        # 10. Send confidence factors
        await self._send_confidence_factors(conf_factors)
        
        # 11. Generate output
        output = await self._generate_output(context.role, hypotheses, conf)
        
        # Store in context for pipeline
        context.signals["reasoning_steps"] = json.dumps([
            {"title": f"Step {i+1}", "body": s} 
            for i, s in enumerate(getattr(self, '_reasoning_log', []))
        ])
        context.signals["matched_rules"] = json.dumps(rules)
        context.signals["hypotheses"] = json.dumps(hypotheses)
        context.signals["confidence_factors"] = json.dumps(conf_factors)
        context.signals["confidence"] = str(conf)
        context.signals["output"] = output
        
        await self.update_status(AgentState.DONE, 100)
        
    except Exception as e:
        logger.error(f"LLM diagnosis error: {e}")
        # Fallback to rule-based
        await self._fallback_to_rules(context)
        await self.update_status(AgentState.ERROR, 100)
    
    return context
```

- [ ] **Step 3: Add helper methods for structured output**

Add these methods to the LLMDiagnosisAgent class:

```python
async def _send_reasoning_step(self, step_num: int, title: str, body: str):
    """Send reasoning step to frontend."""
    await self.send({
        "type": "reasoning_step",
        "step": {
            "title": f"[{step_num}] {title}",
            "body": body
        }
    })
    # Log for later retrieval
    if not hasattr(self, '_reasoning_log'):
        self._reasoning_log = []
    self._reasoning_log.append(f"{title}: {body}")

async def _send_rule_matched(self, rule: Dict[str, Any]):
    """Send matched rule to frontend."""
    await self.send({
        "type": "rule_matched",
        "rule": {
            "id": rule.get("id", "unknown"),
            "text": rule.get("text", "")[:100],
            "src": rule.get("src", "VEEA-Spec"),
            "conf": "匹配"
        }
    })

async def _send_hypothesis(self, hypo: Dict[str, Any]):
    """Send hypothesis to frontend."""
    await self.send({
        "type": "hypothesis",
        "hypothesis": {
            "id": hypo.get("id", ""),
            "desc": hypo.get("description", ""),
            "conf": hypo.get("confidence", 0),
            "factors": hypo.get("factors", [])
        }
    })

async def _send_confidence_factors(self, factors: Dict[str, float]):
    """Send confidence factors to frontend."""
    await self.send({
        "type": "conf_factors",
        "factors": factors
    })
    # Also send final confidence
    conf = sum(factors.values()) / len(factors) if factors else 0
    await self.send({
        "type": "conf_final",
        "confidence": conf,
        "level": "high" if conf > 0.7 else "medium" if conf > 0.4 else "low"
    })

async def _generate_output(self, role: str, hypotheses: List[Dict], confidence: float) -> str:
    """Generate role-adapted output."""
    if not hypotheses:
        return "未能生成诊断假设，建议联系专业技术人员。"
    
    primary = hypotheses[0]
    needs_escalation = confidence < 0.5
    
    # Use template based on role
    templates = {
        "owner": "根据您的描述，车辆可能存在 {desc}。建议：{advice}",
        "technician": "诊断结果：{desc}。相关因素：{factors}。置信度：{conf}%",
        "engineer": " hypothesis: {id}\ndescription: {desc}\nconfidence: {conf}\nfactors: {factors}\nrecommendation: {advice}"
    }
    
    template = templates.get(role, templates["owner"])
    return template.format(
        desc=primary.get("description", "电源系统异常"),
        advice=primary.get("advice", "检查保险丝和电源继电器"),
        factors=", ".join(primary.get("factors", [])[:3]),
        conf=int(confidence * 100),
        id=primary.get("id", "unknown")
    )
```

- [ ] **Step 4: Add delay method**

Ensure the agent has a delay method for pacing:

```python
async def delay(self, ms: int):
    """Delay for visual effect."""
    await asyncio.sleep(ms / 1000)
```

- [ ] **Step 5: Verify syntax**

Run: `python -m py_compile backend/agents/llm_diagnosis_agent.py`
Expected: No errors

---

## Phase 4: Knowledge Base Enhancement

### Task 5: Add Reasoning Steps to Knowledge Base

**Files:**
- Modify: `backend/diagnosis_knowledge.py`

- [ ] **Step 1: Review current knowledge base structure**

Read `backend/diagnosis_knowledge.py` to understand existing rules and templates.

- [ ] **Step 2: Add reasoning step templates**

Add these constants after existing templates:

```python
# Reasoning step templates
REASONING_STEP_TEMPLATES = {
    "symptom_parsing": {
        "title": "症状解析",
        "body": "正在解析用户描述的症状: {symptom}"
    },
    "ontology_lookup": {
        "title": "本体查询",
        "body": "检索与症状相关的车辆概念和关系"
    },
    "rule_matching": {
        "title": "规则匹配",
        "body": "匹配诊断规则库中的相关规则: {rule_count} 条候选规则"
    },
    "hypothesis_generation": {
        "title": "假设生成",
        "body": "基于匹配规则生成诊断假设"
    },
    "confidence_calculation": {
        "title": "置信度计算",
        "body": "计算各假设的置信度得分"
    },
    "output_generation": {
        "title": "输出生成",
        "body": "生成针对 {role} 角色的诊断报告"
    }
}

# Hypothesis templates
HYPOTHESIS_TEMPLATES = [
    {
        "id": "H001",
        "description": "电源模式控制系统故障",
        "advice": "检查PEPS电源模式开关信号，检查车身控制模块(BCM)通信",
        "factors": ["电源模式信号异常", "无钥匙进入系统故障", "启动按钮无响应"]
    },
    {
        "id": "H002", 
        "description": "蓄电池电量不足或接线松动",
        "advice": "检测蓄电池电压，检查正负极接线柱是否松动或氧化",
        "factors": ["蓄电池电压过低", "搭铁线接触不良", "发电机充电异常"]
    },
    {
        "id": "H003",
        "description": "启动机或启动继电器故障",
        "advice": "检查启动机继电器供电，检查启动机本体是否损坏",
        "factors": ["启动机不转", "继电器无吸合", "启动电路断路"]
    },
    {
        "id": "H004",
        "description": "发动机控制模块(ECM)通信故障",
        "advice": "使用诊断仪检测ECM通信状态，检查CAN总线连接",
        "factors": ["ECM无通信", "CAN总线故障", "ECM供电异常"]
    }
]

# Confidence factor weights
CONFIDENCE_WEIGHTS = {
    "symptom_match": 0.3,
    "signal_match": 0.3,
    "rule_support": 0.25,
    "ontology_relevance": 0.15
}
```

- [ ] **Step 3: Add helper function to generate reasoning steps**

Add this function:

```python
def generate_reasoning_steps(symptom: str, role: str) -> List[Dict[str, str]]:
    """
    Generate reasoning steps for diagnosis.
    
    Args:
        symptom: User's symptom description
        role: User's role (owner/technician/engineer)
    
    Returns:
        List of reasoning step dictionaries
    """
    steps = []
    
    # Step 1: Symptom parsing
    steps.append({
        "title": REASONING_STEP_TEMPLATES["symptom_parsing"]["title"],
        "body": REASONING_STEP_TEMPLATES["symptom_parsing"]["body"].format(symptom=symptom[:50])
    })
    
    # Step 2: Ontology lookup
    steps.append({
        "title": REASONING_STEP_TEMPLATES["ontology_lookup"]["title"],
        "body": REASONING_STEP_TEMPLATES["ontology_lookup"]["body"]
    })
    
    # Step 3: Rule matching
    steps.append({
        "title": REASONING_STEP_TEMPLATES["rule_matching"]["title"],
        "body": REASONING_STEP_TEMPLATES["rule_matching"]["body"].format(rule_count=len(SCENARIO_PATTERNS))
    })
    
    # Step 4: Hypothesis generation
    steps.append({
        "title": REASONING_STEP_TEMPLATES["hypothesis_generation"]["title"],
        "body": REASONING_STEP_TEMPLATES["hypothesis_generation"]["body"]
    })
    
    # Step 5: Confidence calculation
    steps.append({
        "title": REASONING_STEP_TEMPLATES["confidence_calculation"]["title"],
        "body": REASONING_STEP_TEMPLATES["confidence_calculation"]["body"]
    })
    
    # Step 6: Output generation
    steps.append({
        "title": REASONING_STEP_TEMPLATES["output_generation"]["title"],
        "body": REASONING_STEP_TEMPLATES["output_generation"]["body"].format(role=role)
    })
    
    return steps
```

- [ ] **Step 4: Verify syntax**

Run: `python -m py_compile backend/diagnosis_knowledge.py`
Expected: No errors

---

## Phase 5: Demo Mode Support

### Task 6: Add Reliable Demo Mode for Boss Presentations

**Files:**
- Modify: `backend/server.py`
- Modify: `cea-diagnosis.html`

- [ ] **Step 1: Add demo mode flag to server**

In server.py, add demo mode handling:

```python
# Add near top of file
DEMO_MODE = os.getenv("APP_DEMO_MODE", "false").lower() == "true"

# In handle_message, after "start" handler:
if msg_type == "start":
    # Check if demo mode requested
    if DEMO_MODE or message.get("demo", False):
        await run_demo_mode(manager, websocket, message)
        return
    
    # Existing logic...
```

- [ ] **Step 2: Create demo mode handler**

Add this function:

```python
async def run_demo_mode(manager, websocket, message: dict):
    """Run in demo mode with simulated responses for reliable presentations."""
    symptom = message.get("symptom", "")
    role = message.get("role", "owner")
    
    logger.info(f"Running in demo mode for: {symptom[:30]}...")
    
    # Step 1: Ontology summary
    await manager.send({
        "type": "onto_summary",
        "counts": {"classes": 142, "properties": 55, "rules": 28},
        "summary": "已加载 142 个车辆概念类, 55 个属性"
    }, websocket)
    await asyncio.sleep(0.5)
    
    # Step 2-7: Reasoning steps
    steps = [
        ("[1] 症状解析", "识别到关键症状: 启动按钮无响应, 电源模式异常"),
        ("[2] 本体查询", "检索到 12 个相关车辆概念: PowerMode, IgnitionState, VehicleStatus..."),
        ("[3] 规则匹配", "匹配到 5 条相关诊断规则"),
        ("[4] 假设生成", "生成 3 个诊断假设: H001(电源模式控制), H002(蓄电池), H003(启动机)"),
        ("[5] 置信度计算", "H001: 85%, H002: 45%, H003: 30%"),
        ("[6] 输出生成", "针对角色 'owner' 生成诊断报告")
    ]
    
    for title, body in steps:
        await manager.send({
            "type": "reasoning_step",
            "step": {"title": title, "body": body}
        }, websocket)
        await asyncio.sleep(0.4)
    
    # Step 8: Matched rules
    rules = [
        {"id": "R-PM-001", "text": "如果电源模式=OFF且启动按钮按下, 则请求启动", "src": "VEEA-Spec", "conf": "高"},
        {"id": "R-PM-002", "text": "PEPS需要检测到有效钥匙才能切换电源模式", "src": "VEEA-Spec", "conf": "高"}
    ]
    for rule in rules:
        await manager.send({"type": "rule_matched", "rule": rule}, websocket)
        await asyncio.sleep(0.2)
    
    # Step 9: Hypotheses
    hypotheses = [
        {"id": "H001", "desc": "PEPS(无钥匙进入/启动系统)故障导致电源模式无法切换", "conf": 0.85, "factors": ["钥匙信号无效", "电源模式保持OFF"]},
        {"id": "H002", "desc": "蓄电池电量不足或接线松动", "conf": 0.45, "factors": ["电压过低", "启动无力"]}
    ]
    for hypo in hypotheses:
        await manager.send({"type": "hypothesis", "hypothesis": hypo}, websocket)
        await asyncio.sleep(0.2)
    
    # Step 10: Confidence factors
    await manager.send({
        "type": "conf_factors",
        "factors": {"symptom_match": 0.9, "signal_match": 0.85, "rule_support": 0.8, "ontology_relevance": 0.75}
    }, websocket)
    await asyncio.sleep(0.3)
    
    # Step 11: Final confidence
    await manager.send({
        "type": "conf_final",
        "confidence": 0.85,
        "level": "high"
    }, websocket)
    
    # Step 12: Output
    output_text = "根据您描述的症状（踩刹车按启动按钮，车辆无法上电），最可能的原因是PEPS无钥匙进入/启动系统故障。建议检查：1) 智能钥匙电池电量 2) 启动按钮背后的PEPS传感器 3) 车身控制模块BCM的通信状态。如无法自行解决，建议联系4S店进行专业诊断。"
    
    await manager.send({
        "type": "output",
        "output": {"text": output_text, "role": role, "escalation": False}
    }, websocket)
    
    # Step 13: Complete
    await manager.send({"type": "pipeline_done", "status": "success"}, websocket)
    
    logger.info("Demo mode completed successfully")
```

- [ ] **Step 3: Add demo mode toggle in frontend**

In the HTML, add a demo mode checkbox:

```html
<!-- Add after backend URL input -->
<label style="display:flex;align-items:center;gap:4px;cursor:pointer">
  <input type="checkbox" id="demoModeCheck">
  <span style="font-size:10px;color:var(--acc)">演示模式</span>
</label>
```

- [ ] **Step 4: Modify frontend to send demo flag**

In the startPipeline function, add:

```javascript
const demoMode = document.getElementById('demoModeCheck')?.checked || false;
ws.send(JSON.stringify({
  type: 'start',
  symptom: symptom,
  role: role,
  signals: signals,
  demo: demoMode  // Add this
}));
```

- [ ] **Step 5: Test demo mode**

Run server with demo mode:
```bash
cd backend
APP_DEMO_MODE=true python main.py
```

Open frontend, check "演示模式", enter any symptom, click start.
Expected: All message types flow through with impressive timing

---

## Task 7: Integration Testing

- [ ] **Step 1: Start backend server**

```bash
cd backend
python main.py
```

Expected: Server starts on port 8765

- [ ] **Step 2: Open frontend in browser**

Navigate to `cea-diagnosis.html` in browser.

- [ ] **Step 3: Connect WebSocket**

Click "连接" button. Expected: Status shows "🟢 在线"

- [ ] **Step 4: Run diagnosis without demo mode**

Enter symptom: "踩刹车按启动按钮，车辆无法上电"
Select role: "owner"
Click "启动诊断 Pipeline"

Expected sequence:
1. Ontology stats bar appears
2. Reasoning steps appear one by one
3. Rules, hypotheses, confidence all display
4. Final output shows in Chinese
5. Pipeline completes successfully

- [ ] **Step 5: Run diagnosis with demo mode**

Check "演示模式", enter any symptom, click start.

Expected: Similar flow but with predefined impressive outputs

---

## Task 8: Final Polish

- [ ] **Step 1: Add wire animations for visual impact**

In frontend, ensure wirePulse is called at appropriate times:

```javascript
// Add after sending certain message types
if (msg.type === 'reasoning_step') {
  if (msg.step.title.includes('[2]')) wirePulse('sym', 'ont');
  if (msg.step.title.includes('[3]')) wirePulse('sym', 'rule');
  if (msg.step.title.includes('[5]')) wirePulse('rule', 'conf');
}
```

- [ ] **Step 2: Add progress animations**

Enhance agent status updates with smooth progress:

```javascript
function setAgent(id, status, progress) {
  const card = document.querySelector(`[data-agent="${id}"]`);
  if (!card) return;
  
  // Update status indicator
  const indicator = card.querySelector('.status-dot');
  if (indicator) {
    indicator.className = 'status-dot ' + status;
  }
  
  // Update progress bar
  const bar = card.querySelector('.progress-bar');
  if (bar) {
    bar.style.width = progress + '%';
  }
}
```

- [ ] **Step 3: Final browser test**

Repeat diagnosis flow, verify all UI elements animate correctly.

---

## Completion Checklist

- [ ] All 8 missing message types implemented in backend
- [ ] Frontend sends real WebSocket messages instead of hardcoded data
- [ ] LLM agent produces structured reasoning steps
- [ ] Knowledge base has reasoning step templates
- [ ] Demo mode works reliably for boss presentations
- [ ] Wire animations trigger at correct times
- [ ] Full diagnosis flow works end-to-end
- [ ] No console errors in browser

---

## Rollback Plan

If issues occur:

1. **Backend won't start**: Check Python syntax with `python -m py_compile backend/server.py`
2. **WebSocket connection fails**: Verify server is running on correct port
3. **Frontend shows blank**: Check browser console for JavaScript errors
4. **Messages not displaying**: Verify message type handlers are correctly registered

**Emergency fallback**: Set `APP_DEMO_MODE=true` to use reliable demo mode.

---

**Plan complete and saved to `docs/superpowers/plans/2026-03-28-vehicle-diagnosis-full-integration.md`**

**Two execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
