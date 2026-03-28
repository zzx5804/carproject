# Vehicle Power Diagnosis System Demo Enhancements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the Web Demo to visually showcase Ontology loading stats, multi-agent invocation chains, and LLM reasoning steps to make the system's underlying complexity visible to stakeholders.

**Architecture:** 
1. The backend will transmit real-time Ontology metrics (classes, properties, rules) to the frontend upon connection.
2. The frontend will feature a new "Knowledge Base" telemetry panel to display these stats.
3. To preserve the impressive 6-agent visual topology while running in LLM Mode, we will map the LLM's internal thinking phases (`parse_symptom`, `rule_matching`, etc.) to the UI's individual agent nodes, triggering SVG wire animations and active states just like the legacy multi-agent mode.

**Tech Stack:** Python (FastAPI), Vanilla JavaScript, HTML/CSS.

---

### Task 1: Expose Ontology Statistics in Backend

**Files:**
- Modify: `backend/server.py`

- [ ] **Step 1: Modify `handle_message` to include ontology stats on `client_ready`**
We need to read the parser's internal lists to show the scale of the knowledge base.

```python
# Replace the existing `client_ready` block (around line 195-207) with this:
    if msg_type == "client_ready":
        client_version = message.get("client_version", "unknown")
        logger.info(f"Client ready, version: {client_version}")
        
        parser = _app_state.get("ontology_parser")
        stats = {
            "classes": len(parser.classes) if parser else 0,
            "obj_props": len(parser.object_properties) if parser else 0,
            "data_props": len(parser.datatype_properties) if parser else 0,
            "individuals": len(parser.individuals) if parser else 0
        }
        
        await manager.send({
            "type": "backend_status",
            "status": "ready",
            "ontology_loaded": parser is not None,
            "pipeline_ready": _app_state.get("diagnosis_pipeline") is not None,
            "ontology_stats": stats,
            "mode": "llm" if get_app_state().get("diagnosis_pipeline", object()).use_llm else "legacy"
        }, websocket)
        return
```

- [ ] **Step 2: Verify `get_app_state` works**
Note that `get_app_state()` returns a dict, so the above code `get_app_state().get("diagnosis_pipeline", object()).use_llm` might throw if `use_llm` is not an attribute of `object`. Let's fix the snippet to be safer.

```python
# Use this refined snippet for Step 1
    if msg_type == "client_ready":
        client_version = message.get("client_version", "unknown")
        logger.info(f"Client ready, version: {client_version}")
        
        parser = _app_state.get("ontology_parser")
        pipeline = _app_state.get("diagnosis_pipeline")
        
        stats = {
            "classes": len(parser.classes) if parser else 0,
            "obj_props": len(parser.object_properties) if parser else 0,
            "data_props": len(parser.datatype_properties) if parser else 0,
            "individuals": len(parser.individuals) if parser else 0
        }
        
        await manager.send({
            "type": "backend_status",
            "status": "ready",
            "ontology_loaded": parser is not None,
            "pipeline_ready": pipeline is not None,
            "ontology_stats": stats,
            "mode": "llm" if pipeline and pipeline.use_llm else "legacy"
        }, websocket)
        return
```

### Task 2: Visualize Knowledge Base Stats in Frontend

**Files:**
- Modify: `multi-agent-demo.html`

- [ ] **Step 1: Add the Knowledge Base UI Panel**
Add a small statistics bar right below the backend connection bar in the HTML. Find the `div` containing `Backend connection bar` and append this right after it.

```html
      <!-- Backend connection bar -->
      <div style="display:flex;gap:6px;align-items:center;margin-bottom:10px;padding:8px;background:var(--s2);border-radius:6px;border:1px solid var(--br)">
        <div style="font-size:10px;color:var(--txd);font-family:var(--mono);white-space:nowrap">后端 WS</div>
        <input type="text" id="backendUrl" value="ws://localhost:8765/ws"
          style="flex:1;background:var(--bg);border:1px solid var(--br);color:var(--tx);padding:4px 7px;border-radius:4px;font-family:var(--mono);font-size:10px;outline:none"/>
        <button id="connectBtn" onclick="toggleConnect()"
          style="background:transparent;border:1px solid var(--br);color:var(--txd);padding:3px 8px;border-radius:4px;cursor:pointer;font-size:10px;white-space:nowrap">连接</button>
        <span id="connStatus" style="font-size:10px;color:var(--txd);white-space:nowrap;font-family:var(--mono)">● 离线</span>
      </div>
      
      <!-- NEW: Ontology Stats Bar -->
      <div id="ontologyStatsBar" style="display:none;gap:10px;align-items:center;margin-bottom:10px;padding:8px;background:rgba(5, 150, 105, 0.05);border-radius:6px;border:1px solid rgba(5, 150, 105, 0.2);">
        <div style="font-size:10px;color:var(--grn);font-family:var(--mono);font-weight:600;white-space:nowrap">🗄️ 知识库已挂载</div>
        <div style="display:flex;gap:12px;flex:1;justify-content:flex-end;">
            <div style="font-size:9px;color:var(--txd);font-family:var(--mono)"><span id="stat-cls" style="color:var(--txb);font-weight:bold">0</span> Classes</div>
            <div style="font-size:9px;color:var(--txd);font-family:var(--mono)"><span id="stat-props" style="color:var(--txb);font-weight:bold">0</span> Properties</div>
            <div style="font-size:9px;color:var(--txd);font-family:var(--mono)"><span id="stat-ind" style="color:var(--txb);font-weight:bold">0</span> Individuals</div>
        </div>
      </div>
```

- [ ] **Step 2: Update `updateBackendStatus` JS function to populate stats**

```javascript
// Replace the existing updateBackendStatus function
function updateBackendStatus(msg) {
  const statusEl = document.getElementById('sysStatus');
  if (statusEl && msg.status) {
    const statusMap = {
      'ready': '⬤ 系统就绪',
      'loading_ontology': '⬤ 加载本体...',
      'processing': '⬤ 处理中...',
      'error': '⬤ 系统错误'
    };
    statusEl.textContent = (statusMap[msg.status] || msg.status) + (msg.mode === 'llm' ? ' (LLM)' : ' (Rule)');
    
    if (msg.status === 'error') {
      statusEl.style.color = 'var(--red)';
    } else if (msg.status === 'ready') {
      statusEl.style.color = 'var(--grn)';
    }
  }

  if (msg.ontology_stats) {
      document.getElementById('ontologyStatsBar').style.display = 'flex';
      
      // Animate numbers for impact
      animateValue('stat-cls', 0, msg.ontology_stats.classes, 1000);
      animateValue('stat-props', 0, msg.ontology_stats.obj_props + msg.ontology_stats.data_props, 1200);
      animateValue('stat-ind', 0, msg.ontology_stats.individuals, 1500);
  }
}

// Add the number animation helper function right after updateBackendStatus
function animateValue(id, start, end, duration) {
    if (start === end) return;
    const obj = document.getElementById(id);
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            obj.innerHTML = end;
        }
    };
    window.requestAnimationFrame(step);
}
```

### Task 3: Map LLM Phases to Multi-Agent Topology Visuals

In LLM mode, the orchestrator only uses `LLMDiagnosisAgent`, leaving the 6-node SVG topology idle. We will map the `llm_thinking` events to visually trigger the legacy nodes so the demo maintains its visual impact.

**Files:**
- Modify: `multi-agent-demo.html`

- [ ] **Step 1: Enhance `showLLMThinking` to trigger wire animations**

Find the `showLLMThinking` function (around the bottom of the script) and modify it to map phases to agent activations.

```javascript
// Add this implementation of showLLMThinking to map LLM phases to UI nodes
function showLLMThinking(content, agent, phase) {
  // Update LLM Agent card (if exists)
  if (typeof updateLLMAgentCard === 'function') {
      updateLLMAgentCard(content, phase);
  }
  if (typeof appendToLLMPanel === 'function') {
      appendToLLMPanel(content, phase);
  }

  // Demo Hack: Map LLM phases to the visual 6-node topology to keep the UI looking active
  pushMsg('llm', 'ALL', `<div class="kv"><span class="k">推理[${phase}]:</span><span class="v">${content}</span></div>`);
  
  if (phase === 'init') {
      setAgent('orch', 'running', 20);
  } 
  else if (phase === 'build_request') {
      setAgent('orch', 'done', 100);
      wirePulse('orch', 'sym');
      setAgent('sym', 'running', 50);
  }
  else if (phase === 'parse_symptom') {
      setAgent('sym', 'done', 100);
      wirePulse('sym', 'ont');
      wirePulse('sym', 'rule');
      setAgent('ont', 'running', 60);
  }
  else if (phase === 'rule_matching') {
      setAgent('ont', 'done', 100);
      setAgent('rule', 'running', 80);
      setTimeout(() => wirePulse('rule', 'conf'), 800);
  }
  else if (phase === 'finalize') {
      setAgent('rule', 'done', 100);
      setAgent('conf', 'running', 90);
      setTimeout(() => wirePulse('conf', 'out'), 600);
  }
  else if (phase === 'fallback') {
      setAgent('rule', 'error', 100);
      pushMsg('sys', 'ALL', `<div class="kv"><span class="k">Fallback:</span><span class="v e">LLM Failed, routing to rules</span></div>`);
  }
  else if (phase === 'complete') {
      setAgent('conf', 'done', 100);
      setAgent('out', 'running', 100);
  }
}
```

- [ ] **Step 2: Modify `pushMsg` CSS styles to handle "llm" and "sys" sources**
Because we added messages from 'llm' and 'sys' in Step 1, ensure they have styles.
Find `.msg-from.c-orch` in the CSS and add styles for llm/sys right below it:

```css
.msg-from.c-llm  { background:rgba(15, 23, 42, 0.12); color:var(--txb); }
.msg-from.c-sys  { background:rgba(220, 38, 38, 0.12); color:var(--red); }
```

- [ ] **Step 3: Update SVG Wire Paths**
To make `wirePulse('orch', 'sym')` work, we need to ensure the JS `drawWires()` function creates these specific paths.

Find the `drawWires()` function. The application currently hardcodes paths like `p-orch-sym`. If it already exists, no change is needed. If not, verify the IDs.
*Self-correction: The `wirePulse(from, to)` function in the existing HTML uses `id="p-${from}-${to}"`. `multi-agent-demo.html` already draws `p-orch-sym`, `p-sym-ont`, `p-sym-rule`, `p-rule-conf`, `p-conf-out`. We mapped exactly to these existing wires.* 

### Task 4: Final Review & Test (Stage 1)

- [x] **Step 1: Test Server Start**
```bash
cd backend
python main.py
```
Expected: Server starts cleanly, ontology parses successfully.

- [x] **Step 2: Open multi-agent-demo.html in browser**
Expected: 
1. The WebSocket connects immediately.
2. The "🗄️ 知识库已挂载" banner appears with animated numbers (e.g., 142 Classes, 55 Properties).
3. Hitting "⚡ 启动诊断 Pipeline" triggers the LLM. 
4. Instead of sitting idle, the SVG wires pulse and nodes (SymptomParser -> OntologyFetcher -> RuleEngine...) light up sequentially mimicking the real pipeline!

---

## Stage 2: Explainability & Structured Reasoning UI

**Goal:** Enhance the reasoning visualization to make the AI's decision-making process more transparent and impressive for demo purposes. The current implementation already shows reasoning steps, hypotheses, and confidence factors, but they appear as scrolling text that's hard to follow during a live demo.

**Key Improvements:**
1. Add a collapsible "命中工程规范" (Matched Engineering Specs) panel
2. Enhance reasoning steps with visual icons and collapsible details
3. Add a "Reasoning Timeline" that shows the diagnostic flow visually
4. Highlight key decision points with color coding

---

### Task 5: Add "命中工程规范" (Matched Engineering Specs) Panel

**Files:**
- Modify: `multi-agent-demo.html`
- Modify: `backend/agents/llm_diagnosis_agent.py`

- [ ] **Step 1: Add engineering specs panel to HTML**

Find the `dp-rule` section in the HTML (around where rule_matched is handled) and enhance it:

```html
<!-- Replace or enhance the #dp-rule section -->
<div id="dp-rule" class="dp" style="grid-column:span 2">
  <div class="dp-hdr"><span class="dp-ic">📐</span> 工程规范匹配</div>
  <div class="idle">等待规则匹配...</div>
  <div id="ruleList" class="rule-list" style="display:none"></div>
  <!-- NEW: Engineering Specs Summary Panel -->
  <div id="engSpecsPanel" style="display:none;margin-top:12px;padding:10px;background:rgba(99,102,241,0.05);border-radius:6px;border:1px solid rgba(99,102,241,0.15)">
    <div style="font-size:10px;color:var(--acc);font-family:var(--mono);margin-bottom:8px">✓ 已匹配工程规范</div>
    <div id="engSpecsList" style="display:flex;flex-wrap:wrap;gap:6px"></div>
  </div>
</div>
```

- [ ] **Step 2: Add CSS for engineering spec badges**

Add to the CSS section:

```css
/* Engineering Spec Badges */
.eng-spec-badge {
  display:inline-flex;align-items:center;gap:4px;
  padding:4px 8px;background:rgba(99,102,241,0.1);
  border:1px solid rgba(99,102,241,0.25);border-radius:4px;
  font-size:10px;font-family:var(--mono);color:#818cf8;
  transition:all .2s;
}
.eng-spec-badge:hover { background:rgba(99,102,241,0.2); }
.eng-spec-badge .spec-id { font-weight:600; }
.eng-spec-badge .spec-src { color:var(--txd);font-size:9px; }
```

- [ ] **Step 3: Modify LLM agent to send matched specs**

In `llm_diagnosis_agent.py`, enhance `_send_reasoning_steps` to also emit `rule_matched` events when specific rules are identified:

```python
async def _send_reasoning_steps(self, response: DiagnosisResponse):
    """Send reasoning steps to frontend with rule highlighting."""
    for step in response.reasoning_steps:
        await self.delay(200)
        await self.send({
            "type": "reasoning_step",
            "step": {
                "title": f"[{step.step_number}] {step.title}",
                "body": step.body
            }
        })
        
        # NEW: If step references a rule, emit rule_matched
        if hasattr(step, 'rule_id') and step.rule_id:
            await self.send({
                "type": "rule_matched",
                "rule": {
                    "id": step.rule_id,
                    "text": step.body[:100] + "..." if len(step.body) > 100 else step.body,
                    "src": "VEEA-Spec",
                    "conf": "匹配"
                }
            })
```

---

### Task 6: Enhance Reasoning Steps with Visual Hierarchy

**Files:**
- Modify: `multi-agent-demo.html`

- [ ] **Step 1: Add icons and visual enhancements to reasoning steps**

Modify the `reasoning_step` case in the message handler:

```javascript
case 'reasoning_step': {
  const sc2 = document.getElementById('reasoningSteps');
  document.querySelector('#dp-sym .idle').style.display = 'none';
  sc2.style.display = 'flex';
  const i = sc2.children.length;
  const el = document.createElement('div');
  el.className = 'step';
  const s = msg.step;
  
  // NEW: Add icon based on step type
  const icon = getStepIcon(s.title);
  
  el.innerHTML = `<div class="step-line"><div class="step-dot">${icon}</div></div>`
    + `<div class="step-cnt"><div class="step-title">${s.title}</div>`
    + `<div class="step-body">${s.body}</div></div>`;
  sc2.appendChild(el);
  setTimeout(() => el.classList.add('vis','active'), 30);
  setTimeout(() => { el.classList.remove('active'); el.classList.add('done'); }, 700);
  break;
}

// NEW: Helper function for step icons
function getStepIcon(title) {
  if (title.includes('症状')) return '🔍';
  if (title.includes('规则') || title.includes('匹配')) return '📐';
  if (title.includes('置信') || title.includes('计算')) return '📊';
  if (title.includes('假设')) return '💡';
  if (title.includes('信号')) return '📡';
  return (i+1).toString();
}
```

- [ ] **Step 2: Add collapsible detail sections**

Enhance the step CSS:

```css
.step { position:relative;padding-left:28px;margin-bottom:4px;opacity:0;transform:translateX(-10px);transition:all .3s; }
.step.vis { opacity:1;transform:translateX(0); }
.step-body { font-size:12px;line-height:1.6;color:var(--tx);max-height:60px;overflow:hidden;transition:max-height .3s;cursor:pointer; }
.step-body:hover { max-height:500px;background:var(--s2);padding:8px;border-radius:4px;margin-top:4px; }
.step-dot { width:22px;height:22px;border-radius:50%;border:2px solid var(--br);display:flex;align-items:center;justify-content:center;font-size:10px;color:var(--txd);background:var(--bg); }
```

---

### Task 7: Add Reasoning Timeline Summary

**Files:**
- Modify: `multi-agent-demo.html`

- [ ] **Step 1: Add a mini timeline above the reasoning panel**

Add to HTML, before `#dp-sym`:

```html
<!-- NEW: Reasoning Timeline Summary -->
<div id="reasoningTimeline" style="display:none;grid-column:span 4;padding:12px;background:var(--s2);border-radius:8px;margin-bottom:12px;">
  <div style="font-size:10px;color:var(--txd);font-family:var(--mono);margin-bottom:8px">推理时间线</div>
  <div id="timelineBar" style="display:flex;gap:4px;height:6px;"></div>
  <div id="timelineLabels" style="display:flex;gap:4px;margin-top:6px;font-size:9px;color:var(--txd);font-family:var(--mono);"></div>
</div>
```

- [ ] **Step 2: Update timeline on each reasoning step**

Add to `reasoning_step` case:

```javascript
// NEW: Update timeline
updateReasoningTimeline(s.title, i);
```

Add the helper function:

```javascript
function updateReasoningTimeline(title, index) {
  const tl = document.getElementById('reasoningTimeline');
  const bar = document.getElementById('timelineBar');
  const labels = document.getElementById('timelineLabels');
  
  tl.style.display = 'block';
  
  // Add segment to bar
  const seg = document.createElement('div');
  seg.className = 'tl-seg';
  seg.style.cssText = `flex:1;background:var(--acc);border-radius:3px;opacity:0.3;transition:opacity .3s;`;
  setTimeout(() => seg.style.opacity = '1', 50);
  bar.appendChild(seg);
  
  // Add label (every 3rd step to avoid crowding)
  if (index % 3 === 0) {
    const lbl = document.createElement('div');
    lbl.style.cssText = `flex:1;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;`;
    lbl.textContent = title.replace(/\[\d+\]\s*/, '').substring(0, 8);
    labels.appendChild(lbl);
  }
}
```

---

### Task 8: Final Review & Test (Stage 2)

- [ ] **Step 1: Verify Python syntax**
```bash
cd backend
python -m compileall agents/llm_diagnosis_agent.py
```

- [ ] **Step 2: Test in browser**
Expected:
1. Reasoning steps appear with icons
2. Timeline bar fills progressively
3. Hovering on a step expands the body
4. Matched rules appear in the "工程规范匹配" panel

- [ ] **Step 3: Demo flow verification**
1. Enter a symptom
2. Watch the timeline fill
3. See matched specs appear as badges
4. Verify confidence factors update smoothly
