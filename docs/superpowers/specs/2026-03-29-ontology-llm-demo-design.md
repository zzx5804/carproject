# Ontology-as-Evidence 架构升级设计文档

**日期：** 2026-03-29
**状态：** 待实施
**目标：** 将 Ontology 从"展示装饰"升级为"推理引擎"，支撑老板汇报 demo

---

## 1. 背景与目标

### 1.1 问题陈述

当前系统存在一个核心矛盾：系统声称是"Ontology 驱动的 LLM 诊断"，但实际上：

- `OntologyFetcher` 生成的是**硬编码 HTML 字符串**，不读 TTL 文件，不执行任何查询
- `LLMDiagnosisAgent` 注入 LLM 的 ontology_context 是**无结构的描述性文字**，不含规则 ID
- LLM 推理步骤中**没有任何 Ontology 规则引用**，置信度是 LLM 自行估算的
- Ontology 面板是**静态展示**，与实际诊断过程无关联

面对技术专家级受众，这一问题会在追问中暴露。

### 1.2 汇报目标（四个高光时刻）

| # | 高光时刻 | 技术实现 |
|---|----------|----------|
| A | Ontology 节点被激活时的可视化动画 | `onto_activated` WebSocket 事件 + 前端高亮 |
| B | LLM 推理步骤显式引用规则 ID | Prompt 注入 + 正则渲染 `[R-xxx]` 标签 |
| C | With / Without Ontology 对比模式 | 前端切换开关 + 两种 pipeline 参数 |
| D | Agent 全链路数据流透明可见 | ActivatedKnowledge 对象在 context 中流转 |

### 1.3 受众

技术专家级领导，会追问：
- "Ontology 在诊断中具体起了什么作用？"
- "LLM 的结论是基于哪条规则推理出来的？"
- "Ontology 和 LLM 之间的接口是什么？"

---

## 2. 方案选择

选择**方案 A：Ontology-as-Evidence 架构升级**（3-5天，中等改造）。

放弃方案 C（纯前端透明度增强）：模拟数据会在追问中穿帮。
放弃全面引入 OWL-RL 推理器：时间风险高，可在后续迭代中加入。

---

## 3. 架构变化

### 3.1 数据流对比

**改造前：**
```
症状输入 → OntologyFetcher（硬编码HTML）→ LLMDiagnosisAgent（字符串拼接）→ LLM → 输出
```

**改造后：**
```
症状输入
  → OntologyFetcher（SPARQL查询 → ActivatedKnowledge → onto_activated事件）
  → LLMDiagnosisAgent（结构化规则注入 → LLM引用[R-xxx] → 输出带溯源链）
```

### 3.2 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/models.py` | 新增 | `ActivatedNode`、`ActivatedKnowledge` 数据模型 |
| `backend/ontology/parser.py` | 新增方法 | 三类 SPARQL 查询方法 |
| `backend/agents/ontology_fetcher.py` | 重构 | 替换硬编码逻辑为 SPARQL 查询 |
| `backend/llm/prompts.py` | 修改 | 结构化规则注入 + 强制引用指令 |
| `cea-diagnosis.html` | 新增功能 | 激活面板、规则标签、对比开关 |

**不动的文件：** `orchestrator.py`、`server.py`、`config.py`、其他 Agent 文件

---

## 4. 详细设计

### 4.1 新增数据模型（models.py）

```python
@dataclass
class ActivatedNode:
    node_id: str          # e.g. "R-BLE-001"
    node_type: str        # "rule" | "class" | "individual"
    label_zh: str         # "BLE认证失败规则"
    confidence: float     # 匹配置信度 0.0-1.0
    source_triple: str    # 来源文件 + 行号，e.g. "rules_model.ttl#L47"

@dataclass
class ActivatedKnowledge:
    activated_rules: List[ActivatedNode]    # 命中的诊断规则
    activated_classes: List[ActivatedNode]  # 涉及的本体类
    signal_mappings: Dict[str, str]         # 信号值 → Ontology 个体映射
    sparql_queries: List[str]               # 实际执行的查询语句（供展示）
```

### 4.2 SPARQL 查询层（ontology/parser.py）

新增三个方法：

**① `query_matching_rules(keywords: List[str]) -> List[ActivatedNode]`**
在 `rules_model.ttl` 中查找与症状关键词匹配的规则，返回规则 ID、中文描述、触发条件、置信度。

**② `query_signal_individuals(signals: Dict[str, str]) -> Dict[str, str]`**
将信号值精确映射到 Ontology 个体：
- `sv-pm="0:Off"` → `:PowerMode_Off`
- `sv-kv="INVALID"` → `:KeyValidStatus_Invalid`

**③ `query_rule_chain(rule_id: str) -> str`**
给定规则 ID，返回该规则的完整前提-结论三元组链，供 LLM prompt 和前端溯源展示使用。

### 4.3 OntologyFetcher 新逻辑（agents/ontology_fetcher.py）

```
process():
  1. 从 context.parsed_symptoms 提取关键词
  2. 调用 query_matching_rules(keywords) → 激活规则节点
  3. 调用 query_signal_individuals(signals) → 信号映射
  4. 组装 ActivatedKnowledge 对象
  5. 发送 onto_activated WebSocket 事件到前端
  6. 基于真实查询结果动态生成 HTML 展示
  7. 将 ActivatedKnowledge 写入 context（传递给下游）
```

### 4.4 LLM Prompt 注入改造（llm/prompts.py）

**`build_diagnosis_prompt()` 新增参数：** `activated_knowledge: ActivatedKnowledge`

**注入内容格式：**
```
### 激活的 Ontology 规则
[R-BLE-001] BLE认证失败诊断规则
  前提: KeyValidSt=INVALID ∧ BLE_ErrorCode=0x05
  结论: → T_1_2转移失败，置信度 0.92
  来源: rules_model.ttl#L47

### 信号 → 本体映射
sv-kv="INVALID" → :KeyValidStatus_Invalid
sv-pm="0:Off"   → :PowerMode_Off
```

**新增 Prompt 指令：**
```
## 推理要求
在 reasoning_steps 的每个 body 字段中：
1. 引用具体规则 ID，格式：[R-xxx]
2. 引用本体类名，格式：:ClassName
3. 说明该步骤依据了哪条 Ontology 规则
```

### 4.5 新增 WebSocket 消息类型

```json
{
  "type": "onto_activated",
  "nodes": [
    {"id": "R-BLE-001", "type": "rule", "confidence": 0.92, "label_zh": "BLE认证失败规则", "source": "rules_model.ttl#L47"},
    {"id": "R-PM-003",  "type": "rule", "confidence": 0.78, "label_zh": "上电失败规则",    "source": "rules_model.ttl#L89"}
  ],
  "signal_mappings": {
    "sv-kv": ":KeyValidStatus_Invalid",
    "sv-pm": ":PowerMode_Off"
  }
}
```

### 4.6 前端改造（cea-diagnosis.html）

**① Ontology 激活面板（替换现有静态展示区）**
- 接收 `onto_activated` 事件，动态渲染激活节点列表
- 每个节点显示：规则 ID、中文描述、匹配置信度、来源文件行号
- 节点首次出现时有发光动画效果

**② 推理步骤规则引用高亮**
- 正则匹配 LLM 输出中的 `[R-xxx]` 标签
- 渲染为可点击的高亮标签，点击后在 Ontology 面板中高亮对应节点

**③ With / Without Ontology 对比切换**
- 头部新增模式切换开关：`Ontology + LLM` ↔ `纯 LLM`
- 切换时发送不同参数（`use_ontology: true/false`）触发两种 pipeline
- 两种模式诊断结果可并排对比

---

## 5. 实施路线图

| 天 | 目标 | 文件 | 验收标准 |
|----|------|---------|----------|
| Day 1 | Ontology 查询层 | `ontology/parser.py`、`models.py` | 命令行跑 SPARQL，返回正确规则节点 |
| Day 2 | OntologyFetcher 改造 | `agents/ontology_fetcher.py` | Pipeline 日志可见 SPARQL 查询和激活节点 |
| Day 3 | LLM Prompt 注入 | `llm/prompts.py` | LLM 输出中出现 `[R-BLE-001]` 等显式引用 |
| Day 4-5 | 前端可视化 | `cea-diagnosis.html` | 完整 demo 4个高光时刻全部出现 |

---

## 6. 汇报演示脚本

1. **先跑"纯 LLM 模式"** — 让老板看到无 Ontology 时输出模糊、无依据
2. **切换到"Ontology + LLM 模式"** — Ontology 面板激活，节点逐一点亮
3. **指向 LLM 推理步骤中的 `[R-BLE-001]`** — 点击跳转，面板高亮对应节点
4. **指向"来源：rules_model.ttl · L47"** — 说明推理有本体依据，可追溯

**关键台词：**
> "Ontology 在这里不是配角，它是整个推理过程的知识约束层。LLM 的每一步结论都必须有本体规则作为依据，这保证了诊断结果的可解释性和可追溯性。"

---

## 7. 不在范围内

- 引入 OWL-RL 推理器（owlrl）全量推理——可在后续迭代加入
- 修改 SPARQL 端点为独立服务——维持现有 rdflib 内嵌方式
- 改动 `orchestrator.py`、`server.py`、`config.py` 及除上述之外的 Agent 文件
