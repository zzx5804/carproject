# 增强因果推理链展示 — 设计文档

**日期**: 2026-03-29
**状态**: 待实施
**目标**: 将推理链从纯文字步骤升级为带证据面板的富卡片，提升汇报可解释性与数据说服力

---

## 1. 背景与目标

### 现状

`cea-diagnosis.html` 中的因果推理链（`#reasonChain`）目前每步只展示：
- 步骤编号 + 标题
- 纯文字 body（含高亮规则 tag）
- LLM / Ontology 来源标签

`ReasoningStep` schema 中的 `confidence` 字段已定义但**前端未渲染**；`details[]` 数组始终为空。

### 目标

给老板汇报时，推理链需要同时体现：

| 维度 | 具体内容 |
|------|---------|
| 可解释性 | 每步明确说明依据了哪条本体规则、引用了哪些信号 |
| 量化证据 | 每步置信度数值 + 较上步变化量 + 进度条 |
| 实时感 | 步骤流式出现动画、置信度数字计数动画、耗时角标 |
| 可追溯性 | 规则 tag 可点击跳转至本体激活节点 |

---

## 2. 架构变更范围

```
backend/llm/schemas.py          ← ReasoningStep 新增字段
backend/llm/prompts.py          ← 要求 LLM 填充新字段
backend/agents/llm_diagnosis_agent.py  ← 事件 payload 透传新字段
cea-diagnosis.html              ← addChain() 渲染增强卡片
```

无新文件，无新 WebSocket 消息类型，改动范围最小化。

---

## 3. 数据模型变更

### ReasoningStep（`backend/llm/schemas.py`）

新增 3 个可选字段：

```python
class ReasoningStep(BaseModel):
    step_number: int
    title: str
    body: str
    confidence: Optional[float] = None          # 已有，本步骤绝对置信度 (0-1)

    # 新增
    confidence_delta: Optional[float] = None    # 较上一步的变化量，可为负
    signals_referenced: Optional[List[Dict[str, str]]] = None
    # 格式: [{"key": "BLE_Auth_Error", "value": "AUTH_ERR(0x05)", "level": "error"}]
    # level 取值: "error" | "warn" | "ok"

    rules_matched: Optional[List[str]] = None
    # 格式: ["T_1_3", "T_2_1"]

    elapsed_ms: Optional[int] = None            # 本步骤推理耗时（毫秒）
```

**向后兼容**：所有新字段均为 `Optional`，旧 payload 不受影响。

---

## 4. LLM Prompt 变更（`backend/llm/prompts.py`）

在 `reasoning_steps` 的 JSON schema 示例中补充新字段说明：

```json
{
  "step_number": 1,
  "title": "信号异常识别",
  "body": "检测到 BLE 认证错误...",
  "confidence": 0.88,
  "confidence_delta": 0.88,
  "signals_referenced": [
    {"key": "BLE_Auth_Error", "value": "AUTH_ERR(0x05)", "level": "error"},
    {"key": "KeyValidSt",     "value": "INVALID",        "level": "error"}
  ],
  "rules_matched": ["T_1_3"],
  "elapsed_ms": null
}
```

Prompt 说明：
- `signals_referenced`：仅列出**本步骤实际引用**的信号，不要列全部信号
- `confidence_delta`：第一步等于 `confidence`，后续步骤为本步减上步
- `elapsed_ms`：LLM 无法测量，填 `null`，由后端在发送事件前注入

---

## 5. 后端事件发送变更（`backend/agents/llm_diagnosis_agent.py`）

在发送 `reasoning_step` 事件前：
1. 记录每步开始时间戳
2. 完成后计算 `elapsed_ms` 并注入到 step dict
3. 将完整 step（含新字段）透传给前端，不做裁剪

```python
step_dict = step.model_dump()
step_dict["elapsed_ms"] = elapsed_ms  # 后端注入
await self.emit("reasoning_step", {"step": step_dict})
```

---

## 6. 前端渲染变更（`cea-diagnosis.html`）

### 6.1 卡片结构

`addChain()` 函数生成的 HTML 结构升级为：

```
┌─────────────────────────────────────────────────┐
│ [S1] 步骤标题         [LLM tag]  [⏱ 0.8s badge] │
│ body 文字（含 [T_x_x] ↗ 可点击规则 tag）         │
│ ┌──────────────┬──────────────┬──────────────┐   │
│ │ 步骤置信度    │ 引用信号      │ 命中规则      │   │
│ │ [进度条]      │ KEY: VALUE   │ [T_1_3]      │   │
│ │ ↑ 88%        │ KEY: VALUE   │ 规则描述      │   │
│ └──────────────┴──────────────┴──────────────┘   │
└─────────────────────────────────────────────────┘
```

证据面板（3列grid）仅在对应数据存在时渲染，任一列数据缺失则该列不显示（不渲染空格）。

### 6.2 置信度颜色规则

| 数值范围 | 颜色 |
|---------|------|
| ≥ 85%   | `var(--green)` |
| 70–84%  | `var(--yellow)` |
| < 70%   | `var(--orange)` |

`confidence_delta` 前缀：正值显示 `↑`，负值显示 `↓`，零显示 `→`。

### 6.3 信号值颜色规则

按 `level` 字段：
- `"error"` → `var(--red)`
- `"warn"` → `var(--yellow)`
- `"ok"` → `var(--green)`
- 无 level → `var(--tx)`

### 6.4 动画

- 卡片整体：保持现有 `slideIn` 动画（`opacity: 0 → 1` + `translateX`）
- 置信度数字：`animateNum()` 从 0 计数到目标值（600ms）
- 计时角标：卡片出现后 200ms 淡入
- 步骤连接线：颜色随步骤渐变（蓝→紫→黄→红），与步骤圆点颜色对应

### 6.5 最终步骤特殊样式

最后一个推理步骤（`[S4]` 根因确认）：
- 整个卡片边框颜色改为 `var(--red)`，带微光 box-shadow
- `Output` tag 使用红色配色
- 证据面板第一列显示"最终置信度"而非"步骤置信度"

---

## 7. 不在范围内

- 横向因果流程图（方案 B）：本次不实施，待后续迭代
- 推理链折叠/展开交互（方案 B 手风琴）：本次不实施
- 后端实时 streaming body 文字（逐字输出）：需要独立后端改造，本次不做

---

## 8. 验收标准

1. 运行诊断后，每个推理步骤卡片自动展开，无需任何点击
2. 有 `confidence` 数据时，置信度进度条+数字出现，并有计数动画
3. 有 `signals_referenced` 时，信号列显示键值对，颜色按 level 区分
4. 有 `rules_matched` 时，规则列显示规则 ID，可点击高亮本体节点
5. 有 `elapsed_ms` 时，右上角显示耗时角标
6. 无新字段的旧 payload 下，卡片退化为原有纯文字样式，不报错
7. 最后一步边框红色高亮
