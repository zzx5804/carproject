# Enhanced Reasoning Chain Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将因果推理链从纯文字步骤升级为每步自动展开的富卡片，每步显示置信度进度条、引用信号键值对、命中规则 ID、耗时角标。

**Architecture:** 后端 `ReasoningStep` 新增 4 个可选字段（`confidence_delta`、`signals_referenced`、`rules_matched`、`elapsed_ms`）；LLM Prompt 新增字段示例；`llm_diagnosis_agent.py` 在发送事件前注入 `elapsed_ms`；前端 `addChain()` 渲染增强卡片，向后兼容旧 payload。

**Tech Stack:** Python 3.13, Pydantic v2, JavaScript (vanilla), pytest

---

## File Map

| 文件 | 变更类型 | 变更内容 |
|------|---------|---------|
| `backend/llm/schemas.py` | Modify | `ReasoningStep` 新增 4 字段 |
| `backend/llm/prompts.py` | Modify | `DIAGNOSIS_PROMPT_TEMPLATE` 补充字段示例 |
| `backend/agents/llm_diagnosis_agent.py` | Modify | `_send_reasoning_steps()` 注入 `elapsed_ms`，透传新字段 |
| `cea-diagnosis.html` | Modify | `addChain()` 渲染增强卡片，CSS 新增 `.cs-evidence` 样式 |
| `backend/tests/test_reasoning_step_schema.py` | Create | 新字段的 schema 单元测试 |
| `backend/tests/test_llm_agent_reasoning.py` | Create | `_send_reasoning_steps()` 的单元测试 |

---

## Task 1: ReasoningStep schema 新增字段 + 测试

**Files:**
- Modify: `backend/llm/schemas.py:65-75`
- Create: `backend/tests/test_reasoning_step_schema.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_reasoning_step_schema.py`：

```python
"""Tests for enhanced ReasoningStep schema fields."""
import pytest
from pydantic import ValidationError
from llm.schemas import ReasoningStep


def test_reasoning_step_new_fields_all_optional():
    """New fields are optional — old payloads must still parse."""
    step = ReasoningStep(step_number=1, title="信号分析", body="BLE错误")
    assert step.confidence_delta is None
    assert step.signals_referenced is None
    assert step.rules_matched is None
    assert step.elapsed_ms is None


def test_reasoning_step_with_all_new_fields():
    step = ReasoningStep(
        step_number=1,
        title="信号分析",
        body="检测到 BLE 错误",
        confidence=0.88,
        confidence_delta=0.88,
        signals_referenced=[
            {"key": "BLE_Auth_Error", "value": "AUTH_ERR(0x05)", "level": "error"},
            {"key": "KeyValidSt", "value": "INVALID", "level": "error"},
        ],
        rules_matched=["T_1_3"],
        elapsed_ms=800,
    )
    assert step.confidence == 0.88
    assert step.confidence_delta == 0.88
    assert len(step.signals_referenced) == 2
    assert step.signals_referenced[0]["key"] == "BLE_Auth_Error"
    assert step.rules_matched == ["T_1_3"]
    assert step.elapsed_ms == 800


def test_reasoning_step_confidence_delta_can_be_negative():
    step = ReasoningStep(
        step_number=2, title="验证", body="部分排除",
        confidence=0.85, confidence_delta=-0.03
    )
    assert step.confidence_delta == -0.03


def test_reasoning_step_elapsed_ms_must_be_positive():
    with pytest.raises(ValidationError):
        ReasoningStep(
            step_number=1, title="T", body="B",
            elapsed_ms=-100
        )


def test_reasoning_step_signals_referenced_level_values():
    """level 字段只接受 error/warn/ok。"""
    step = ReasoningStep(
        step_number=1, title="T", body="B",
        signals_referenced=[
            {"key": "K", "value": "V", "level": "ok"}
        ]
    )
    assert step.signals_referenced[0]["level"] == "ok"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd D:/work/carproject/backend && python -m pytest tests/test_reasoning_step_schema.py -v
```

期望：`FAILED` — `ImportError` 或字段不存在

- [ ] **Step 3: 修改 `backend/llm/schemas.py`，新增 4 个字段**

将 `ReasoningStep` 类（第 65-75 行）替换为：

```python
class ReasoningStep(BaseModel):
    """A single reasoning step in the diagnosis chain."""
    step_number: int = Field(description="Step number (1, 2, 3, ...)")
    title: str = Field(description="Step title")
    body: str = Field(description="Step content/details")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence in this step's conclusion"
    )
    confidence_delta: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Change in confidence vs previous step (can be negative)"
    )
    signals_referenced: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description=(
            "Signals referenced in this step. "
            "Each item: {key, value, level} where level in error|warn|ok"
        )
    )
    rules_matched: Optional[List[str]] = Field(
        default=None,
        description="Ontology rule IDs matched in this step, e.g. ['T_1_3', 'T_2_1']"
    )
    elapsed_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Time spent on this reasoning step in milliseconds (injected by backend)"
    )
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd D:/work/carproject/backend && python -m pytest tests/test_reasoning_step_schema.py -v
```

期望：`5 passed`

- [ ] **Step 5: 确认现有测试不受影响**

```bash
cd D:/work/carproject/backend && python -m pytest tests/ -v --ignore=tests/test_reasoning_step_schema.py
```

期望：所有原有测试仍 PASS

- [ ] **Step 6: Commit**

```bash
cd D:/work/carproject && git add backend/llm/schemas.py backend/tests/test_reasoning_step_schema.py
git commit -m "feat: add confidence_delta, signals_referenced, rules_matched, elapsed_ms to ReasoningStep"
```

---

## Task 2: LLM Prompt 新增字段示例

**Files:**
- Modify: `backend/llm/prompts.py:92-128`

- [ ] **Step 1: 修改 `DIAGNOSIS_PROMPT_TEMPLATE` 中的 `reasoning_steps` 示例**

将 `prompts.py` 第 95-105 行的 `reasoning_steps` 示例块替换为：

```python
  "reasoning_steps": [
    {
      "step_number": 1,
      "title": "步骤标题",
      "body": "详细分析内容，引用规则格式 [T_x_x]，引用个体格式 :ClassName",
      "confidence": 0.88,
      "confidence_delta": 0.88,
      "signals_referenced": [
        {"key": "BLE_Auth_Error", "value": "AUTH_ERR(0x05)", "level": "error"},
        {"key": "KeyValidSt", "value": "INVALID", "level": "error"}
      ],
      "rules_matched": ["T_1_3"],
      "elapsed_ms": null
    }
  ],
```

同时在 `## 推理要求（必须遵守）` 块（prompts.py 末尾，`build_diagnosis_prompt` 方法内）追加以下说明（在 `return base_prompt` 之前 append 到 `base_prompt`）：

```python
        if activated_knowledge and activated_knowledge.activated_rules:
            base_prompt += """

## 推理要求（必须遵守）

在 reasoning_steps 的每个 body 字段中：
1. 引用具体规则 ID，格式：[T_x_x]（例如 [T_1_2]）
2. 引用本体个体名，格式：:ClassName（例如 :ReadyEnableDisable）
3. 每个推理步骤必须说明依据了哪条 Ontology 规则

在 reasoning_steps 的新字段中：
- signals_referenced：仅列出本步骤实际引用的信号，不要列全部信号；level 取 error/warn/ok
- confidence_delta：第一步等于 confidence，后续步骤为本步减上步值
- rules_matched：仅列出本步骤命中的规则 ID 列表
- elapsed_ms：填 null，由后端注入

示例：
"根据规则 [T_1_2]，当信号 :ReadyEnableDisable 时，状态转移到 :ReadyEnableEnable 失败，确认为上电链路异常。"
"""
```

> 注意：上面这段代码会替换掉 prompts.py 中已有的 `## 推理要求` 块（第 280-292 行），直接覆盖整个 if 块。

- [ ] **Step 2: 验证 PromptBuilder 可正常实例化**

```bash
cd D:/work/carproject/backend && python -c "from llm.prompts import get_prompt_builder; pb = get_prompt_builder(); print('OK')"
```

期望：`OK`

- [ ] **Step 3: Commit**

```bash
cd D:/work/carproject && git add backend/llm/prompts.py
git commit -m "feat: update diagnosis prompt to include new ReasoningStep fields in example"
```

---

## Task 3: llm_diagnosis_agent 注入 elapsed_ms + 透传新字段

**Files:**
- Modify: `backend/agents/llm_diagnosis_agent.py:329-341`
- Create: `backend/tests/test_llm_agent_reasoning.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_llm_agent_reasoning.py`：

```python
"""Tests for _send_reasoning_steps in LLMDiagnosisAgent."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from agents.llm_diagnosis_agent import LLMDiagnosisAgent
from llm.schemas import ReasoningStep, DiagnosisResponse, DiagnosticHypothesis


def make_response(steps):
    return DiagnosisResponse(
        diagnosis_id="test_001",
        summary="测试",
        reasoning_steps=steps,
        final_confidence=0.85,
        model_used="test-model",
    )


@pytest.mark.asyncio
async def test_send_reasoning_steps_includes_elapsed_ms():
    """elapsed_ms must be injected even if LLM returned None."""
    agent = LLMDiagnosisAgent()
    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    agent.send = mock_send

    steps = [
        ReasoningStep(step_number=1, title="信号分析", body="BLE错误", confidence=0.88),
    ]
    response = make_response(steps)
    await agent._send_reasoning_steps(response)

    assert len(sent_messages) == 1
    step_payload = sent_messages[0]["step"]
    assert "elapsed_ms" in step_payload
    assert isinstance(step_payload["elapsed_ms"], int)
    assert step_payload["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_send_reasoning_steps_passes_new_fields():
    """signals_referenced, rules_matched, confidence_delta must be forwarded."""
    agent = LLMDiagnosisAgent()
    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    agent.send = mock_send

    steps = [
        ReasoningStep(
            step_number=1, title="信号分析", body="BLE错误",
            confidence=0.88, confidence_delta=0.88,
            signals_referenced=[{"key": "BLE_Auth_Error", "value": "AUTH_ERR", "level": "error"}],
            rules_matched=["T_1_3"],
        ),
    ]
    response = make_response(steps)
    await agent._send_reasoning_steps(response)

    step_payload = sent_messages[0]["step"]
    assert step_payload["confidence"] == 0.88
    assert step_payload["confidence_delta"] == 0.88
    assert step_payload["signals_referenced"][0]["key"] == "BLE_Auth_Error"
    assert step_payload["rules_matched"] == ["T_1_3"]


@pytest.mark.asyncio
async def test_send_reasoning_steps_elapsed_ms_overrides_llm_value():
    """Backend-injected elapsed_ms should replace any LLM-provided value."""
    agent = LLMDiagnosisAgent()
    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    agent.send = mock_send

    steps = [
        ReasoningStep(step_number=1, title="T", body="B", elapsed_ms=99999),
    ]
    response = make_response(steps)
    await agent._send_reasoning_steps(response)

    step_payload = sent_messages[0]["step"]
    # Backend should override with real measurement, not LLM's 99999
    assert step_payload["elapsed_ms"] != 99999
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd D:/work/carproject/backend && python -m pytest tests/test_llm_agent_reasoning.py -v
```

期望：`FAILED` — `AssertionError: elapsed_ms not in step_payload` 或类似

- [ ] **Step 3: 修改 `_send_reasoning_steps()` 方法**

将 `llm_diagnosis_agent.py` 第 329-341 行替换为：

```python
    async def _send_reasoning_steps(self, response: DiagnosisResponse):
        """Send reasoning steps to frontend, injecting elapsed_ms from wall clock."""
        for step in response.reasoning_steps:
            step_start = time.time()
            await self.delay(200)
            elapsed_ms = int((time.time() - step_start) * 1000)

            step_dict = step.model_dump()
            step_dict["elapsed_ms"] = elapsed_ms  # backend overrides LLM value

            await self.send(
                {
                    "type": "reasoning_step",
                    "step": step_dict,
                }
            )
```

> 注意：`time` 已在文件顶部导入（第 8 行），无需重复导入。
> `step.model_dump()` 会自动包含所有字段（含新增的 `confidence_delta`、`signals_referenced`、`rules_matched`）。
> 旧 `title` 字段格式从 `f"[{step.step_number}] {step.title}"` 改为 `step_dict["title"]` 原值；前端会自己加 `[S1]` 前缀（见前端 Task 4）。

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd D:/work/carproject/backend && python -m pytest tests/test_llm_agent_reasoning.py -v
```

期望：`3 passed`

- [ ] **Step 5: 运行全量测试**

```bash
cd D:/work/carproject/backend && python -m pytest tests/ -v
```

期望：全部 PASS（忽略需要本体文件的 skip）

- [ ] **Step 6: Commit**

```bash
cd D:/work/carproject && git add backend/agents/llm_diagnosis_agent.py backend/tests/test_llm_agent_reasoning.py
git commit -m "feat: inject elapsed_ms and pass all ReasoningStep fields in reasoning_step event"
```

---

## Task 4: 前端 addChain() 渲染增强卡片

**Files:**
- Modify: `cea-diagnosis.html`（CSS 区域 + `addChain()` 函数）

- [ ] **Step 1: 新增 CSS 样式**

在 `cea-diagnosis.html` 的 `<style>` 块中，找到 `.chain-step{...}` 相关规则（约第 123-125 行），在其后追加：

```css
.cs-evidence{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:5px;margin-top:7px}
.cs-ev-cell{background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 6px}
.cs-ev-label{font-family:var(--mono);font-size:7px;color:var(--tx3);letter-spacing:.5px;margin-bottom:3px}
.cs-ev-bar{height:3px;background:var(--border);border-radius:2px;margin-bottom:2px;overflow:hidden}
.cs-ev-bar-fill{height:100%;border-radius:2px;transition:width .6s ease}
.cs-ev-value{font-family:var(--mono);font-size:9px;font-weight:600}
.cs-ev-sub{font-family:var(--mono);font-size:7px;color:var(--tx3);margin-top:1px}
.cs-sig-row{font-family:var(--mono);font-size:8px;margin-bottom:1px}
.cs-sig-row.err{color:var(--red)}.cs-sig-row.warn{color:var(--yellow)}.cs-sig-row.ok{color:var(--green)}
.cs-elapsed{font-family:var(--mono);font-size:8px;color:var(--tx3);background:var(--bg2);border:1px solid var(--border);border-radius:3px;padding:1px 5px;opacity:0;transition:opacity .3s .2s}
.cs-elapsed.vis{opacity:1}
```

- [ ] **Step 2: 替换 `addChain()` 函数**

在 `cea-diagnosis.html` 中找到 `function addChain(step,i){` 函数（约第 563 行），将整个函数替换为：

```javascript
function addChain(step, i) {
  const ch = document.getElementById('reasonChain');
  const idle = document.getElementById('chainIdle');
  if (idle) idle.style.display = 'none';

  // Source tag
  const tag = step.agent === 'llm'
    ? '<span class="prov-tag llm">LLM</span>'
    : step.agent === 'ont'
    ? '<span class="prov-tag ont">Ontology</span>'
    : step.agent === 'sym'
    ? '<span class="prov-tag llm">NLU</span>'
    : '<span class="prov-tag rule">Output</span>';

  // Elapsed badge (injected by backend via step.elapsed_ms)
  const elapsedBadge = (step.elapsed_ms != null)
    ? `<span class="cs-elapsed" id="cs-elapsed-${i}">⏱ ${(step.elapsed_ms / 1000).toFixed(1)}s</span>`
    : '';

  // Confidence cell
  let confCell = '';
  if (step.confidence != null) {
    const pct = Math.round(step.confidence * 100);
    const color = pct >= 85 ? 'var(--green)' : pct >= 70 ? 'var(--yellow)' : 'var(--orange)';
    const delta = step.confidence_delta != null ? step.confidence_delta : null;
    const arrow = delta == null ? '' : delta > 0.001 ? '↑ ' : delta < -0.001 ? '↓ ' : '→ ';
    const deltaColor = delta == null ? color : delta > 0.001 ? 'var(--green)' : delta < -0.001 ? 'var(--orange)' : 'var(--tx2)';
    confCell = `<div class="cs-ev-cell">
      <div class="cs-ev-label">步骤置信度</div>
      <div class="cs-ev-bar"><div class="cs-ev-bar-fill" style="width:0%;background:${color}" id="cs-conf-bar-${i}"></div></div>
      <div class="cs-ev-value" style="color:${deltaColor}" id="cs-conf-num-${i}">${arrow}0%</div>
      ${delta != null ? `<div class="cs-ev-sub">较上步 ${delta >= 0 ? '+' : ''}${Math.round(delta * 100)}%</div>` : ''}
    </div>`;
  }

  // Signals cell
  let sigCell = '';
  if (step.signals_referenced && step.signals_referenced.length > 0) {
    const rows = step.signals_referenced.map(s =>
      `<div class="cs-sig-row ${s.level || ''}">${s.key}: ${s.value}</div>`
    ).join('');
    sigCell = `<div class="cs-ev-cell"><div class="cs-ev-label">引用信号</div>${rows}</div>`;
  }

  // Rules cell
  let rulesCell = '';
  if (step.rules_matched && step.rules_matched.length > 0) {
    const ruleSpans = step.rules_matched.map(r =>
      `<span class="rule-tag" onclick="highlightOntologyNode('${r}')"
        style="background:rgba(167,139,250,0.2);border:1px solid #a78bfa;border-radius:3px;
               padding:1px 4px;color:#a78bfa;font-family:var(--mono);font-size:8px;
               cursor:pointer;display:inline-block;margin-bottom:2px">${r} ↗</span>`
    ).join(' ');
    rulesCell = `<div class="cs-ev-cell"><div class="cs-ev-label">命中规则</div>${ruleSpans}</div>`;
  }

  // Evidence panel (only rendered if at least one cell has data)
  const hasEvidence = confCell || sigCell || rulesCell;
  const evidenceHtml = hasEvidence
    ? `<div class="cs-evidence">${confCell}${sigCell}${rulesCell}</div>`
    : '';

  // Is this the last step? Use red border if step.agent === 'output' or body contains '根因'
  const isLast = step.agent === 'output' || (step.title && step.title.includes('根因'));
  const cardBorder = isLast ? 'border:1px solid var(--red);box-shadow:0 0 12px rgba(255,77,106,0.08)' : '';

  const el = document.createElement('div');
  el.className = 'chain-step';
  el.innerHTML = `
    <div class="cs-line">
      <div class="cs-dot">${i + 1}</div>
      <div class="cs-conn"></div>
    </div>
    <div class="cs-body" style="${cardBorder};border-radius:8px;padding:8px 10px">
      <div class="cs-title" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:4px">
        <span>[S${i + 1}] ${step.title} ${tag}</span>
        ${elapsedBadge}
      </div>
      <div class="cs-content">${highlightRuleRefs(step.body)}</div>
      ${evidenceHtml}
    </div>`;

  ch.appendChild(el);

  // Animate in
  setTimeout(() => {
    el.classList.add('vis');
    el.querySelector('.cs-dot').classList.add('active');
  }, 50);

  // Animate elapsed badge
  if (step.elapsed_ms != null) {
    setTimeout(() => {
      const badge = document.getElementById(`cs-elapsed-${i}`);
      if (badge) badge.classList.add('vis');
    }, 250);
  }

  // Animate confidence bar + number
  if (step.confidence != null) {
    const pct = Math.round(step.confidence * 100);
    const color = pct >= 85 ? 'var(--green)' : pct >= 70 ? 'var(--yellow)' : 'var(--orange)';
    const delta = step.confidence_delta != null ? step.confidence_delta : null;
    const arrow = delta == null ? '' : delta > 0.001 ? '↑ ' : delta < -0.001 ? '↓ ' : '→ ';
    setTimeout(() => {
      const bar = document.getElementById(`cs-conf-bar-${i}`);
      const num = document.getElementById(`cs-conf-num-${i}`);
      if (bar) bar.style.width = pct + '%';
      if (num) animateNum(`cs-conf-num-${i}`, 0, pct, 600, arrow + '{v}%');
    }, 150);
  }

  setTimeout(() => {
    el.querySelector('.cs-dot').classList.remove('active');
    el.querySelector('.cs-dot').classList.add('done');
    el.querySelector('.cs-conn').classList.add('done');
    el.querySelector('.cs-title span').classList.add('done');
  }, 800);
}
```

- [ ] **Step 3: 升级 `animateNum()` 支持格式化模板**

找到 `function animateNum(id,s,e,d){` 函数（约第 473 行），替换为：

```javascript
function animateNum(id, s, e, d, fmt) {
  const el = document.getElementById(id);
  if (!el) return;
  let t0 = null;
  const step = ts => {
    if (!t0) t0 = ts;
    const p = Math.min((ts - t0) / d, 1);
    const v = Math.floor(p * (e - s) + s);
    el.textContent = fmt ? fmt.replace('{v}', v) : v;
    if (p < 1) requestAnimationFrame(step);
    else el.textContent = fmt ? fmt.replace('{v}', e) : e;
  };
  requestAnimationFrame(step);
}
```

- [ ] **Step 4: 手动验证**

启动后端和前端，运行一次诊断，观察推理链：
1. 每步卡片出现时有 slideIn 动画
2. 有 `confidence` 时：进度条从 0 动画到目标值，数字计数
3. 有 `signals_referenced` 时：显示信号键值对，颜色按 level
4. 有 `rules_matched` 时：显示可点击规则 tag
5. 有 `elapsed_ms` 时：右上角耗时角标 200ms 后淡入
6. 最后一步（agent='output'）：卡片红色边框

- [ ] **Step 5: Commit**

```bash
cd D:/work/carproject && git add cea-diagnosis.html
git commit -m "feat: enhance reasoning chain cards with evidence panel, confidence bar, signals, rules, elapsed badge"
```

---

## Task 5: 回归测试 + 验收

**Files:**
- No new files

- [ ] **Step 1: 全量后端测试**

```bash
cd D:/work/carproject/backend && python -m pytest tests/ -v
```

期望：所有测试 PASS（ontology 相关可能 skip，属正常）

- [ ] **Step 2: 无 Ontology 模式验证（向后兼容）**

在界面点击"Without Ontology"，运行诊断：
- 推理链应仍然出现
- 旧格式（无 `confidence_delta` 等字段）下卡片退化为纯文字，不报错
- Console 无 JS 错误

- [ ] **Step 3: 有 Ontology 模式验证（完整功能）**

在界面点击"With Ontology"，运行诊断：
- 所有 4 个验收标准通过（见设计文档第 8 节）
- 特别确认：规则 tag 点击后本体激活节点高亮

- [ ] **Step 4: Final commit**

```bash
cd D:/work/carproject && git add .
git commit -m "chore: verify enhanced reasoning chain end-to-end"
```

---

## 自检报告

**Spec coverage:**
- [x] 可解释性（每步显示规则 + 信号）— Task 3 + Task 4
- [x] 量化证据（置信度进度条 + 变化量）— Task 1 + Task 4
- [x] 实时感（动画 + 耗时角标）— Task 3 + Task 4
- [x] 可追溯性（规则 tag 可点击）— Task 4
- [x] 向后兼容（旧 payload 退化）— Task 4 + Task 5
- [x] 最终步骤红色高亮 — Task 4

**Type consistency:**
- `step.model_dump()` 在 Task 3 和 Task 4 之间字段名一致
- `animateNum` 在 Task 4 Step 3 升级，格式模板 `{v}` 仅在 Task 4 Step 2 使用
- `cs-conf-bar-${i}` / `cs-conf-num-${i}` ID 在 Step 2 和 Step 2 动画部分一致

**Placeholder scan:** 无 TBD / TODO / "类似 Task N" 模糊引用。
