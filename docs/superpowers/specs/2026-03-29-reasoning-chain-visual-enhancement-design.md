# 推理链视觉增强 & 双模式对比面板 Design Spec

**日期：** 2026-03-29
**状态：** 已审批

---

## 目标

在 `cea-diagnosis.html` 的因果推理链中，让 Ontology+LLM 与纯 LLM 两种模式产生可感知的视觉差异；并在页面底部提供常驻的全宽对比面板，缓存两种模式最近一次运行结果，支持并排比较。

参考设计：`.superpowers/brainstorm/13446-1774778756/content/comparison.html`

---

## 范围

| 层 | 文件 | 变更类型 |
|----|------|----------|
| 后端 schema | `backend/llm/schemas.py` | 新增 `deficit_note` 字段 |
| 后端逻辑 | `backend/llm/service.py` | LLM-only 模式后处理填充 `deficit_note` |
| 后端测试 | `backend/tests/test_reasoning_step_schema.py` | 新增 2 个测试 |
| 前端增强 A | `cea-diagnosis.html` `addChain()` | 彩色渐变点/线 + `deficit_note` 渲染 |
| 前端面板 C | `cea-diagnosis.html` | 全宽对比面板 + sessionStorage 缓存 |

不在范围内：WebSocket 协议、OntologyFetcher、LLMDiagnosisAgent 主流程、现有步骤字段。

---

## 后端设计

### 1. `ReasoningStep.deficit_note` 字段

```python
# backend/llm/schemas.py
deficit_note: Optional[str] = Field(
    default=None,
    description="LLM-only 模式下说明本步骤缺失内容的注释，Ontology 模式为 None"
)
```

字段位置：在 `rules_matched` 之后、`elapsed_ms` 之前。

### 2. 后处理逻辑（`backend/llm/service.py`）

在 `generate_diagnosis()` 返回 `DiagnosisResponse` 之前，当 `activated_knowledge is None`（即 LLM-only 运行）时，对每个步骤自动填充 `deficit_note`：

| 优先级 | 条件 | deficit_note |
|--------|------|--------------|
| 1（最高） | `agent == "output"` | `None`（最终结论不加注释） |
| 2 | 有 `rules_matched`（LLM 幻觉规则） | `"规则引用来自 LLM 推测，未经 SPARQL 验证"` |
| 3 | 有 `signals_referenced` 但无 `rules_matched` | `"识别到信号异常，但未通过本体规则链验证"` |
| 4（兜底） | 无 `rules_matched` 且无 `signals_referenced` | `"无信号引用与规则依据，推理基于语义理解"` |

条件按优先级从高到低顺序判断，命中即停止。

### 3. 新增测试（`backend/tests/test_reasoning_step_schema.py`）

- `test_reasoning_step_deficit_note_default()` — 默认值为 `None`
- `test_reasoning_step_deficit_note_string()` — 接受任意字符串值

---

## 前端设计 A：推理链视觉增强

### 步骤点颜色

```javascript
const DOT_COLORS = ['#00b4ff', '#a78bfa', '#ffc53d', '#ff4d6a', '#00e68a'];

const dotColor = _useOntology
    ? DOT_COLORS[i % DOT_COLORS.length]
    : '#2a3a60';  // 灰色，LLM 模式
```

步骤点的 `background` 和 `box-shadow` 均根据 `dotColor` 动态设置。

### 连接线颜色

```javascript
const nextColor = _useOntology
    ? DOT_COLORS[(i + 1) % DOT_COLORS.length]
    : '#253050';
const connStyle = _useOntology
    ? `background:linear-gradient(${dotColor},${nextColor})`
    : `background:#253050`;
```

最后一步（无连接线）不渲染 `cs-conn` 元素。

### `deficit_note` 渲染

在 `cs-content` 正文 div 之后、`evidenceHtml` 之前插入：

```javascript
const deficitHtml = step.deficit_note
    ? `<div class="cs-deficit">※ ${step.deficit_note}</div>`
    : '';
```

CSS（内联或追加到 `<style>`）：

```css
.cs-deficit {
    color: var(--orange);
    font-size: 8px;
    font-family: var(--mono);
    margin-top: 4px;
    opacity: 0.85;
}
```

### 最终步骤边框

Ontology 模式保持红色边框（`var(--red)`）。LLM 模式最终步骤改为蓝色边框（`rgba(0,180,255,0.3)`），以区分两种模式的输出感。

---

## 前端设计 C：全宽对比面板

### 位置

追加在现有 `.app-grid` 最外层 `</div>` 之后、`</div>` body 结束之前。

### HTML 骨架

```html
<div id="comparePanel" style="margin-top:20px;padding:0 14px 30px">
  <div class="panel">
    <div class="panel-head">
      <!-- 标题 + 两侧 badge -->
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:14px">
      <div id="cmp-onto"><!-- Ontology 侧 --></div>
      <div id="cmp-llm"><!-- LLM 侧 --></div>
    </div>
    <div id="cmp-diff" style="padding:0 14px 14px"><!-- 差异摘要 --></div>
  </div>
</div>
```

### 数据缓存

**追加时机：** 每次 `reasoning_step` 事件时将步骤 push 到 `_cachedSteps[]`。

**写入时机：** `pipeline_done` 事件时：

```javascript
const runData = {
    steps: _cachedSteps.slice(),
    confidence: _lastFinalConf,  // 由 conf_final 事件记录
    ts: Date.now(),
    scenario: scenarioKey,
    mode: _useOntology ? 'onto' : 'llm'
};
sessionStorage.setItem(
    _useOntology ? 'lastOntoRun' : 'lastLlmRun',
    JSON.stringify(runData)
);
_cachedSteps = [];
renderComparePanel();
```

**新增全局变量：**

```javascript
let _cachedSteps = [];
let _lastFinalConf = 0;  // 由 conf_final 事件设置
```

### `renderComparePanel()`

1. 从 `sessionStorage` 读取 `lastOntoRun` 和 `lastLlmRun`
2. 若某侧为 `null`，显示占位符：`// 尚未运行 [mode] 模式`
3. 若有数据，调用 `renderCompareChain(runData, isOnto)` 渲染静态链列表（无动画，复用相同 HTML 模板）
4. 若两侧均有数据，渲染差异摘要行：

| 指标 | 计算方式 |
|------|----------|
| 最终置信度 | `runData.confidence` |
| 规则命中总数 | 所有步骤 `rules_matched.length` 之和 |
| 信号引用总数 | 所有步骤 `signals_referenced.length` 之和 |
| 推理步骤数 | `runData.steps.length` |

### `renderCompareChain(runData, isOnto)`

复用 `addChain()` 相同 HTML 结构，但：
- 静态渲染（无 `setTimeout` 动画）
- 点颜色、连接线颜色逻辑与 `addChain()` 一致（根据 `isOnto` 参数）
- 渲染 `deficit_note` 同 `addChain()`

---

## 错误处理

- `sessionStorage` 读取失败（JSON 解析错）：捕获异常，该侧显示占位符，不中断其他功能
- 两侧模式相同（用户只跑了一种模式重复运行）：`lastOntoRun` / `lastLlmRun` 分开存储，不会覆盖另一侧
- `_cachedSteps` 在 `resetAll()` 中清空：确保新一轮诊断不会混入上一轮步骤

---

## 测试验证

1. 运行 Ontology+LLM → 对比面板左侧出现彩色链，右侧显示占位符
2. 切换纯 LLM → 运行 → 右侧出现灰色链 + `※` 注释，差异摘要行出现
3. 再次切换 Ontology+LLM → 运行 → 左侧更新为新结果，右侧保留上一次 LLM 结果
4. 刷新页面 → 两侧均显示占位符（sessionStorage 清空）
5. 后端测试：`pytest backend/tests/test_reasoning_step_schema.py -v` 全绿
