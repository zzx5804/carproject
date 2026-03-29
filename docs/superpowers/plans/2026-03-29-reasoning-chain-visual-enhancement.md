# Reasoning Chain Visual Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Ontology+LLM 与纯 LLM 两种模式的推理链有明显视觉差异，并在页面底部提供全宽对比面板，缓存两种模式最近一次运行结果供并排比较。

**Architecture:** 后端在 LLM-only 运行后对每个推理步骤自动填充 `deficit_note` 字段（纯后处理，不改 prompt）；前端 `addChain()` 按模式切换点/线颜色并渲染 `deficit_note`；全宽对比面板用 `sessionStorage` 缓存两侧数据，`pipeline_done` 时触发渲染。

**Tech Stack:** Python 3.13 / Pydantic v2 / pytest · 原生 JavaScript / sessionStorage · 无新依赖

---

## 文件结构

| 文件 | 变更 |
|------|------|
| `backend/llm/schemas.py` | `ReasoningStep` 新增 `deficit_note: Optional[str]` 字段 |
| `backend/llm/service.py` | `generate_diagnosis()` 末尾新增 `_fill_deficit_notes()` 后处理 |
| `backend/tests/test_reasoning_step_schema.py` | 新增 2 个测试 |
| `cea-diagnosis.html` | `addChain()` 彩色增强 + `deficit_note` 渲染 + 新增对比面板 HTML/CSS/JS |

---

## Task 1: 后端 schema — 新增 `deficit_note` 字段

**Files:**
- Modify: `backend/llm/schemas.py:102-122` (在 `rules_matched` 之后、`elapsed_ms` 之前插入字段)
- Test: `backend/tests/test_reasoning_step_schema.py`

- [ ] **Step 1: 写两个失败测试**

打开 `backend/tests/test_reasoning_step_schema.py`，在文件末尾追加：

```python
def test_reasoning_step_deficit_note_default():
    """deficit_note defaults to None when not provided."""
    step = ReasoningStep(step_number=1, title="t", body="b")
    assert step.deficit_note is None


def test_reasoning_step_deficit_note_string():
    """deficit_note accepts any string value."""
    step = ReasoningStep(
        step_number=1, title="t", body="b",
        deficit_note="识别到信号异常，但未通过本体规则链验证"
    )
    assert step.deficit_note == "识别到信号异常，但未通过本体规则链验证"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd D:/work/carproject/backend
pytest tests/test_reasoning_step_schema.py::test_reasoning_step_deficit_note_default tests/test_reasoning_step_schema.py::test_reasoning_step_deficit_note_string -v
```

预期：`FAILED` — `ReasoningStep` 无 `deficit_note` 属性。

- [ ] **Step 3: 在 `ReasoningStep` 中添加字段**

打开 `backend/llm/schemas.py`，在 `rules_matched` 字段（第 102-105 行）和 `@field_validator` 之间插入：

```python
    deficit_note: Optional[str] = Field(
        default=None,
        description="LLM-only 模式下说明本步骤缺失内容的注释，Ontology 模式为 None"
    )
```

完整的字段顺序应为：
`step_number → title → body → agent → confidence → confidence_delta → signals_referenced → rules_matched → deficit_note → @field_validator → elapsed_ms`

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd D:/work/carproject/backend
pytest tests/test_reasoning_step_schema.py -v
```

预期：全部 12 个测试 `PASSED`。

- [ ] **Step 5: 提交**

```bash
cd D:/work/carproject
git add backend/llm/schemas.py backend/tests/test_reasoning_step_schema.py
git commit -m "feat: add deficit_note field to ReasoningStep schema"
```

---

## Task 2: 后端逻辑 — `_fill_deficit_notes()` 后处理

**Files:**
- Modify: `backend/llm/service.py` — `generate_diagnosis()` 方法，在构建 `DiagnosisResponse` 之后、`return` 之前调用新方法

- [ ] **Step 1: 写测试（集成）**

在 `backend/tests/test_reasoning_step_schema.py` 末尾追加：

```python
def test_fill_deficit_notes_no_ontology():
    """_fill_deficit_notes sets notes when activated_knowledge is None."""
    from llm.service import LLMTools
    from llm.config import get_llm_config

    tools = LLMTools(get_llm_config())

    steps = [
        ReasoningStep(step_number=1, title="分析", body="b"),  # 兜底
        ReasoningStep(
            step_number=2, title="验证", body="b",
            signals_referenced=[{"key": "K", "value": "V", "level": "ok"}]
        ),  # 有信号无规则
        ReasoningStep(
            step_number=3, title="结论", body="b",
            agent="output"
        ),  # output → None
    ]

    result = tools._fill_deficit_notes(steps, activated_knowledge=None)

    assert result[0].deficit_note == "无信号引用与规则依据，推理基于语义理解"
    assert result[1].deficit_note == "识别到信号异常，但未通过本体规则链验证"
    assert result[2].deficit_note is None


def test_fill_deficit_notes_with_ontology():
    """_fill_deficit_notes does nothing when activated_knowledge is present."""
    from llm.service import LLMTools
    from llm.config import get_llm_config

    tools = LLMTools(get_llm_config())

    steps = [
        ReasoningStep(step_number=1, title="t", body="b"),
    ]

    class FakeKnowledge:
        pass

    result = tools._fill_deficit_notes(steps, activated_knowledge=FakeKnowledge())
    assert result[0].deficit_note is None
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd D:/work/carproject/backend
pytest tests/test_reasoning_step_schema.py::test_fill_deficit_notes_no_ontology tests/test_reasoning_step_schema.py::test_fill_deficit_notes_with_ontology -v
```

预期：`FAILED` — `LLMTools` 无 `_fill_deficit_notes` 方法。

- [ ] **Step 3: 在 `LLMTools` 中实现 `_fill_deficit_notes()`**

找到 `backend/llm/service.py` 中 `class LLMTools` 的末尾（`generate_diagnosis` 方法结束处），在其后追加：

```python
    def _fill_deficit_notes(
        self,
        steps: List[ReasoningStep],
        activated_knowledge: Optional[Any],
    ) -> List[ReasoningStep]:
        """
        Fill deficit_note on each step for LLM-only runs.

        Only called when activated_knowledge is None (pure LLM mode).
        Returns the same list with deficit_note set in-place.
        """
        if activated_knowledge is not None:
            return steps

        for step in steps:
            # Priority 1: output step — no note
            if step.agent == "output":
                step.deficit_note = None
                continue

            has_rules = bool(step.rules_matched)
            has_signals = bool(step.signals_referenced)

            # Priority 2: hallucinated rules
            if has_rules:
                step.deficit_note = "规则引用来自 LLM 推测，未经 SPARQL 验证"
            # Priority 3: signals but no rules
            elif has_signals:
                step.deficit_note = "识别到信号异常，但未通过本体规则链验证"
            # Priority 4: fallback
            else:
                step.deficit_note = "无信号引用与规则依据，推理基于语义理解"

        return steps
```

- [ ] **Step 4: 在 `generate_diagnosis()` 中调用**

找到 `generate_diagnosis()` 方法中构建 `DiagnosisResponse` 的位置（约第 726-750 行），在 `return DiagnosisResponse(...)` 调用完成后，`return` 语句之前插入后处理调用。

将现有的：
```python
            # Build DiagnosisResponse
            return DiagnosisResponse(
                diagnosis_id=f"diag_{int(time.time() * 1000)}",
                ...
                escalation_hint=data.get("escalation_hint"),
            )
```

改为：
```python
            # Build DiagnosisResponse
            response = DiagnosisResponse(
                diagnosis_id=f"diag_{int(time.time() * 1000)}",
                summary=data.get("summary", "诊断完成"),
                reasoning_steps=[
                    ReasoningStep(**step) if isinstance(step, dict) else step
                    for step in data.get("reasoning_steps", [])
                ],
                primary_hypothesis=DiagnosticHypothesis(**data["primary_hypothesis"])
                if "primary_hypothesis" in data and data["primary_hypothesis"]
                else None,
                secondary_hypotheses=[
                    DiagnosticHypothesis(**h) if isinstance(h, dict) else h
                    for h in data.get("secondary_hypotheses", [])
                ],
                final_confidence=data.get("final_confidence", 0.75),
                confidence_factors=[
                    ConfidenceFactor(**f) if isinstance(f, dict) else f
                    for f in data.get("confidence_factors", [])
                ],
                output_for_owner=data.get("output_for_owner"),
                output_for_technician=data.get("output_for_technician"),
                output_for_customer_service=data.get("output_for_customer_service"),
                model_used=self.config.model,
                escalation_hint=data.get("escalation_hint"),
            )
            # Fill deficit notes for LLM-only runs
            self._fill_deficit_notes(
                response.reasoning_steps,
                activated_knowledge=activated_knowledge,
            )
            return response
```

- [ ] **Step 5: 运行全部测试，确认通过**

```bash
cd D:/work/carproject/backend
pytest tests/test_reasoning_step_schema.py -v
```

预期：全部 14 个测试 `PASSED`。

- [ ] **Step 6: 提交**

```bash
cd D:/work/carproject
git add backend/llm/service.py backend/tests/test_reasoning_step_schema.py
git commit -m "feat: fill deficit_note for LLM-only reasoning steps"
```

---

## Task 3: 前端 A — `addChain()` 彩色渐变增强

**Files:**
- Modify: `cea-diagnosis.html` — `addChain()` 函数（约第 584-638 行）及 `<style>` 块

**背景知识：** 当前 `addChain()` 用固定的 `.cs-dot`/`.cs-conn` 样式。点和线的颜色在 CSS 中写死，不区分模式。`_useOntology` 全局变量控制当前模式。

- [ ] **Step 1: 在 `<style>` 块中添加 `.cs-deficit` CSS**

找到现有 `<style>` 块（文件顶部附近），搜索 `.chain-step` 相关的 CSS，在其附近追加：

```css
.cs-deficit{color:var(--orange);font-size:8px;font-family:var(--mono);margin-top:4px;opacity:0.85}
```

- [ ] **Step 2: 修改 `addChain()` 函数**

找到 `addChain(step, i)` 函数（约第 584 行），将函数开头到 `el.innerHTML=...` 这一行替换为如下内容（完整替换，保留函数签名和后续 setTimeout 逻辑不变）：

在 `const effectiveAgent = ...` 那行**之后**，`const tag = ...` **之前**，插入点颜色计算：

```javascript
  const DOT_COLORS = ['#00b4ff','#a78bfa','#ffc53d','#ff4d6a','#00e68a'];
  const dotColor = _useOntology ? DOT_COLORS[i % DOT_COLORS.length] : '#2a3a60';
  const dotShadow = _useOntology ? `0 0 8px ${dotColor}66` : 'none';
  const nextColor = _useOntology ? DOT_COLORS[(i + 1) % DOT_COLORS.length] : '#253050';
  const connStyle = _useOntology
      ? `background:linear-gradient(${dotColor},${nextColor})`
      : 'background:#253050';
```

在 `const deficitHtml` 行（在 `evidenceHtml` 构建之前）插入：

```javascript
  const deficitHtml = step.deficit_note
      ? `<div class="cs-deficit">※ ${step.deficit_note}</div>`
      : '';
```

将 `el.innerHTML=...` 那行的模板字符串中：

1. `.cs-dot` 的 style 由固定样式改为动态：将原来的
   ```
   <div class="cs-dot">${i+1}</div><div class="cs-conn"></div>
   ```
   改为：
   ```
   <div class="cs-dot" style="background:${dotColor};box-shadow:${dotShadow};color:${_useOntology?'#000':'#7a8ba8'}">${i+1}</div><div class="cs-conn" style="${connStyle}"></div>
   ```

2. 最终步骤边框：将原来的
   ```javascript
   const cardBorder=isLast?'border:1px solid var(--red);box-shadow:0 0 12px rgba(255,77,106,0.08)':'';
   ```
   改为：
   ```javascript
   const cardBorder=isLast
       ? (_useOntology
           ? 'border:1px solid var(--red);box-shadow:0 0 12px rgba(255,77,106,0.08)'
           : 'border:1px solid rgba(0,180,255,0.3);box-shadow:0 0 8px rgba(0,180,255,0.06)')
       : '';
   ```

3. 在 `<div class="cs-content">${step.body}</div>` 之后、`${evidenceHtml}` 之前插入 `${deficitHtml}`：
   ```
   ...<div class="cs-content">${step.body}</div>${deficitHtml}${evidenceHtml}...
   ```

- [ ] **Step 3: 手动验证**

启动后端，打开 `cea-diagnosis.html`，运行 Ontology+LLM 模式：
- 步骤点应显示渐变色（蓝→紫→黄→红→绿循环）
- 连接线应有渐变
- 最终步骤边框为红色

切换纯 LLM 模式运行：
- 步骤点应为灰色 `#2a3a60`
- 连接线应为灰色 `#253050`
- 每个非 output 步骤下方应出现橙色 `※` 注释
- 最终步骤边框为蓝色（`rgba(0,180,255,0.3)`）

- [ ] **Step 4: 提交**

```bash
cd D:/work/carproject
git add cea-diagnosis.html
git commit -m "feat: addChain colored dots/lines and deficit_note rendering"
```

---

## Task 4: 前端 C — 全宽对比面板

**Files:**
- Modify: `cea-diagnosis.html` — HTML 结构、`<script>` 块（新增全局变量、缓存逻辑、`renderComparePanel`、`renderCompareChain`）

**背景知识：** `handleBackendMessage()` 处理所有 WebSocket 消息。`pipeline_done` case 在约第 517 行的 switch 语句中。`resetAll()` 约在第 640 行。全局变量在约第 349 行。

- [ ] **Step 1: 在 `</div></div>` 主容器之后追加对比面板 HTML**

找到主网格容器的关闭标签（约第 346-347 行，`</div>\n</div>`），在其后追加对比面板 HTML：

```html
<!-- ═══ 全宽对比面板 ═══ -->
<div id="comparePanel" style="margin-top:20px;padding:0 14px 30px">
  <div class="panel">
    <div class="panel-head">
      <div class="ph-dot" style="background:var(--yellow);box-shadow:0 0 5px var(--yellow)"></div>
      诊断对比
      <span class="prov-tag" style="margin-left:6px;background:rgba(167,139,250,0.2);border:1px solid #a78bfa;color:#a78bfa">Ontology+LLM</span>
      <span style="color:var(--tx3);font-size:10px;margin:0 6px">vs</span>
      <span class="prov-tag llm">纯 LLM</span>
      <span id="cmp-ts" style="margin-left:auto;font-size:9px;color:var(--tx3);font-family:var(--mono)"></span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:14px">
      <div>
        <div style="font-family:var(--mono);font-size:9px;color:#a78bfa;letter-spacing:1px;margin-bottom:10px">// ONTOLOGY + LLM</div>
        <div id="cmp-onto"></div>
      </div>
      <div>
        <div style="font-family:var(--mono);font-size:9px;color:var(--accent);letter-spacing:1px;margin-bottom:10px">// 纯 LLM</div>
        <div id="cmp-llm"></div>
      </div>
    </div>
    <div id="cmp-diff" style="padding:0 14px 14px;display:none"></div>
  </div>
</div>
```

- [ ] **Step 2: 在全局变量声明行之后添加新变量**

找到（约第 349-350 行）：
```javascript
let role='owner',running=false,scenarioKey='ble_auth',ws=null,stepIndex=0;
let _useOntology = true;
```

在其后插入：
```javascript
let _cachedSteps = [];
let _lastFinalConf = 0;
```

- [ ] **Step 3: 在 `handleBackendMessage()` 中追加缓存逻辑**

找到 `handleBackendMessage` 函数（约第 517 行），在 switch 语句中找到以下两个 case 并修改：

**`conf_final` case**（已有，找到后在其中记录置信度）：

将原来的：
```javascript
case 'conf_final':updateFinalConfidence(msg.confidence,msg.level);break;
```
改为：
```javascript
case 'conf_final':updateFinalConfidence(msg.confidence,msg.level);_lastFinalConf=msg.confidence||0;break;
```

**`reasoning_step` case**（已有，找到后追加缓存）：

将原来的：
```javascript
case 'reasoning_step':addChain(Object.assign({agent:'llm'},msg.step,{body:highlightRuleRefs(msg.step.body)}),stepIndex++);break;
```
改为：
```javascript
case 'reasoning_step':{const s=Object.assign({agent:'llm'},msg.step,{body:highlightRuleRefs(msg.step.body)});addChain(s,stepIndex++);_cachedSteps.push(s);break;}
```

**`pipeline_done` case**（已有，在其中追加写入 sessionStorage）：

将原来的：
```javascript
case 'pipeline_done':document.getElementById('goBtn').disabled=false;document.getElementById('goBtn').innerHTML='⚡ 重新运行诊断';running=false;setAgent('master','done',100);break;
```
改为：
```javascript
case 'pipeline_done':{document.getElementById('goBtn').disabled=false;document.getElementById('goBtn').innerHTML='⚡ 重新运行诊断';running=false;setAgent('master','done',100);
  try{
    const runData={steps:_cachedSteps.slice(),confidence:_lastFinalConf,ts:Date.now(),scenario:scenarioKey,mode:_useOntology?'onto':'llm'};
    sessionStorage.setItem(_useOntology?'lastOntoRun':'lastLlmRun',JSON.stringify(runData));
  }catch(e){console.warn('sessionStorage write failed',e);}
  _cachedSteps=[];
  renderComparePanel();
  break;}
```

- [ ] **Step 4: 在 `resetAll()` 中清空 `_cachedSteps`**

找到 `resetAll()` 函数（约第 640 行）开头，在 `['master','symptom'...` 的 `forEach` 之前插入：
```javascript
_cachedSteps=[];
```

- [ ] **Step 5: 实现 `renderCompareChain()` 函数**

在 `addChain` 函数之后（约第 638 行）、`resetAll` 函数之前，插入：

```javascript
function renderCompareChain(container, runData, isOnto) {
  const DOT_COLORS = ['#00b4ff','#a78bfa','#ffc53d','#ff4d6a','#00e68a'];
  let html = '';
  runData.steps.forEach(function(step, i) {
    const dotColor = isOnto ? DOT_COLORS[i % DOT_COLORS.length] : '#2a3a60';
    const dotShadow = isOnto ? `0 0 8px ${dotColor}66` : 'none';
    const nextColor = isOnto ? DOT_COLORS[(i+1) % DOT_COLORS.length] : '#253050';
    const connStyle = isOnto
        ? `background:linear-gradient(${dotColor},${nextColor})`
        : 'background:#253050';
    const effectiveAgent = (!isOnto && step.agent !== 'output') ? 'llm' : step.agent;
    const tag = effectiveAgent==='llm'
        ? '<span class="prov-tag llm">LLM</span>'
        : effectiveAgent==='ont'
            ? '<span class="prov-tag ont">Ontology</span>'
            : '<span class="prov-tag rule">Output</span>';
    const isLast = step.agent==='output' || (step.title && step.title.includes('根因'));
    const cardBorder = isLast
        ? (isOnto
            ? 'border:1px solid var(--red);box-shadow:0 0 12px rgba(255,77,106,0.08)'
            : 'border:1px solid rgba(0,180,255,0.3)')
        : '';
    const deficitHtml = step.deficit_note
        ? `<div class="cs-deficit">※ ${step.deficit_note}</div>`
        : '';
    const connHtml = isLast ? '' : `<div class="cs-conn" style="${connStyle}"></div>`;
    html += `<div class="chain-step vis">
      <div class="cs-line">
        <div class="cs-dot done" style="background:${dotColor};box-shadow:${dotShadow};color:${isOnto?'#000':'#7a8ba8'}">${i+1}</div>
        ${connHtml}
      </div>
      <div class="cs-body" style="${cardBorder};border-radius:8px;padding:8px 10px">
        <div class="cs-title" style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
          <span class="done">[S${i+1}] ${step.title} ${tag}</span>
        </div>
        <div class="cs-content">${step.body||''}</div>
        ${deficitHtml}
      </div>
    </div>`;
  });
  container.innerHTML = html || '<div style="font-size:10px;color:var(--tx3);font-family:var(--mono);padding:8px">// 暂无步骤数据</div>';
}
```

- [ ] **Step 6: 实现 `renderComparePanel()` 函数**

紧接 `renderCompareChain` 之后插入：

```javascript
function renderComparePanel() {
  const ontoEl = document.getElementById('cmp-onto');
  const llmEl = document.getElementById('cmp-llm');
  const diffEl = document.getElementById('cmp-diff');
  const tsEl = document.getElementById('cmp-ts');
  if (!ontoEl || !llmEl) return;

  let ontoData = null, llmData = null;
  try { ontoData = JSON.parse(sessionStorage.getItem('lastOntoRun') || 'null'); } catch(e) {}
  try { llmData = JSON.parse(sessionStorage.getItem('lastLlmRun') || 'null'); } catch(e) {}

  if (ontoData) {
    renderCompareChain(ontoEl, ontoData, true);
  } else {
    ontoEl.innerHTML = '<div style="font-size:10px;color:var(--tx3);font-family:var(--mono);padding:16px 0">// 尚未运行 Ontology+LLM 模式</div>';
  }

  if (llmData) {
    renderCompareChain(llmEl, llmData, false);
  } else {
    llmEl.innerHTML = '<div style="font-size:10px;color:var(--tx3);font-family:var(--mono);padding:16px 0">// 尚未运行纯 LLM 模式</div>';
  }

  // Update timestamp
  const latest = [ontoData, llmData].filter(Boolean).sort((a,b) => b.ts - a.ts)[0];
  if (latest && tsEl) {
    tsEl.textContent = '最近更新 ' + new Date(latest.ts).toLocaleTimeString('zh-CN');
  }

  // Render diff summary only when both sides available
  if (ontoData && llmData) {
    const ontoRules = ontoData.steps.reduce((s,st) => s + (st.rules_matched ? st.rules_matched.length : 0), 0);
    const llmRules  = llmData.steps.reduce((s,st)  => s + (st.rules_matched  ? st.rules_matched.length  : 0), 0);
    const ontoSigs  = ontoData.steps.reduce((s,st) => s + (st.signals_referenced ? st.signals_referenced.length : 0), 0);
    const llmSigs   = llmData.steps.reduce((s,st)  => s + (st.signals_referenced  ? st.signals_referenced.length  : 0), 0);
    const ontoConf  = Math.round((ontoData.confidence || 0) * 100);
    const llmConf   = Math.round((llmData.confidence || 0) * 100);

    diffEl.innerHTML = `
      <div style="font-family:var(--mono);font-size:9px;color:var(--yellow);letter-spacing:1px;margin-bottom:8px">▎ 关键差异摘要</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 10px">
          <div style="font-family:var(--mono);font-size:8px;color:var(--tx3);margin-bottom:4px">最终置信度</div>
          <div style="font-size:13px;font-weight:700;color:${ontoConf>llmConf?'var(--green)':'var(--tx2)'}"><span style="color:#a78bfa">${ontoConf}%</span> vs <span style="color:var(--accent)">${llmConf}%</span></div>
        </div>
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 10px">
          <div style="font-family:var(--mono);font-size:8px;color:var(--tx3);margin-bottom:4px">规则命中</div>
          <div style="font-size:13px;font-weight:700"><span style="color:#a78bfa">${ontoRules}</span> vs <span style="color:var(--accent)">${llmRules}</span></div>
        </div>
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 10px">
          <div style="font-family:var(--mono);font-size:8px;color:var(--tx3);margin-bottom:4px">信号引用</div>
          <div style="font-size:13px;font-weight:700"><span style="color:#a78bfa">${ontoSigs}</span> vs <span style="color:var(--accent)">${llmSigs}</span></div>
        </div>
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 10px">
          <div style="font-family:var(--mono);font-size:8px;color:var(--tx3);margin-bottom:4px">推理步骤数</div>
          <div style="font-size:13px;font-weight:700"><span style="color:#a78bfa">${ontoData.steps.length}</span> vs <span style="color:var(--accent)">${llmData.steps.length}</span></div>
        </div>
      </div>`;
    diffEl.style.display = 'block';
  } else {
    diffEl.style.display = 'none';
  }
}
```

- [ ] **Step 7: 初始化时调用 `renderComparePanel()`**

找到 `window.addEventListener('load', ...)` 回调（约第 669 行），在 `loadScenario('ble_auth');` 之后追加：
```javascript
renderComparePanel();
```

- [ ] **Step 8: 手动验证完整流程**

1. 打开 `cea-diagnosis.html`，滚动到底部 → 对比面板两侧均显示占位符文字
2. 运行 Ontology+LLM → 左侧（`cmp-onto`）出现彩色链，右侧仍为占位符
3. 切换纯 LLM，运行 → 右侧出现灰色链 + `※` 注释，差异摘要行出现（4 个指标格子）
4. 再次切换 Ontology+LLM 并运行 → 左侧更新，右侧保留上次 LLM 结果
5. 刷新页面 → 两侧均显示占位符

- [ ] **Step 9: 提交**

```bash
cd D:/work/carproject
git add cea-diagnosis.html
git commit -m "feat: add full-width comparison panel with sessionStorage caching"
```

---

## 自审完成后的执行选项

**计划已保存到 `docs/superpowers/plans/2026-03-29-reasoning-chain-visual-enhancement.md`。两种执行选项：**

**1. Subagent-Driven（推荐）** — 每个 Task 派发独立 subagent，Task 间有 spec 合规性 + 代码质量双重审查，快速迭代

**2. Inline Execution** — 在本 session 中使用 executing-plans，分批执行并有检查点

**请选择哪种方式？**
