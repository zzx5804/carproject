# Ontology+LLM Pipeline Fix Design Spec

**日期：** 2026-03-29
**状态：** 已审批

---

## 背景与问题

测试场景"踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'"，使用 Ontology+LLM 与纯 LLM 两种模式执行后，推理链内容完全一致、置信度均为 85%。

根本原因是 **Pipeline 编排缺陷**：`OrchestratorAgent._execute_llm_pipeline()` 仅调用 `LLMDiagnosisAgent`，不管 `context.use_ontology` 取何值，`OntologyFetcherAgent` 从不执行，导致 `context.activated_knowledge` 始终为 `None`，LLM 在两种模式下收到完全相同的 prompt，输出自然一致。

次要原因：`_validate_and_fill_missing_fields()` 中两种模式触发相同的硬编码兜底置信度；`OntologyFetcherAgent` 对中文句子的空格分词无效，即便 pipeline 修复后也可能无法提取有效 SPARQL 关键词。

---

## 目标

1. 修复 pipeline 编排：Ontology+LLM 模式下，`OntologyFetcher` 必须在 `LLMDiagnosisAgent` 之前执行并填充 `activated_knowledge`。
2. 调整 Ontology 规则在 prompt 中的语气：从强制引用改为参考建议。
3. 分化两种模式的置信度兜底值：有 Ontology 上下文时，兜底规则可信度略高于纯 LLM。
4. 修复中文症状的关键词提取：用正则替换标点后再分词，确保 SPARQL 查询能匹配到相关规则。

---

## 范围

| 层 | 文件 | 变更类型 |
|----|------|----------|
| 编排 | `backend/agents/orchestrator.py` | `_execute_llm_pipeline()` 新增条件阶段调用 |
| Prompt | `backend/llm/service.py` | `generate_diagnosis()` 语气修改；`_validate_and_fill_missing_fields()` 签名 + 内容 |
| 关键词 | `backend/agents/ontology_fetcher.py` | 中文标点正则替换 |
| 测试 | `backend/tests/test_ontology_pipeline.py` | 新建文件，覆盖 3 个集成测试 |

不在范围内：WebSocket 协议、OntologyParser SPARQL 逻辑、前端代码、LLMDiagnosisAgent 主流程。

---

## Section 1：Pipeline 编排修复

### 变更文件：`backend/agents/orchestrator.py`

**变更位置：** `_execute_llm_pipeline()` 方法。

**变更前（当前代码）：**
```python
async def _execute_llm_pipeline(self, context: DiagnosisContext) -> DiagnosisContext:
    if AgentID.LLM not in self.agents:
        logger.warning("LLM agent not registered, falling back to legacy pipeline")
        return await self._execute_legacy_pipeline(context)

    llm_agent = self.agents[AgentID.LLM]
    await self.send_msg_bus("llm", [...])
    await self.animate_wire("llm")

    try:
        context = await llm_agent.run(context)
    except Exception as e:
        ...
    return context
```

**变更后：**
```python
async def _execute_llm_pipeline(self, context: DiagnosisContext) -> DiagnosisContext:
    if AgentID.LLM not in self.agents:
        logger.warning("LLM agent not registered, falling back to legacy pipeline")
        return await self._execute_legacy_pipeline(context)

    # 当 use_ontology=True 时，先运行 SymptomParser 和 OntologyFetcher
    # SymptomParser 填充 context.parsed_symptoms，OntologyFetcher 依赖它
    if getattr(context, "use_ontology", False):
        await self._execute_phase("sym", context)
        await self._execute_phase("ont", context)

    llm_agent = self.agents[AgentID.LLM]
    await self.send_msg_bus("llm", [...])
    await self.animate_wire("llm")

    try:
        context = await llm_agent.run(context)
    except Exception as e:
        ...
    return context
```

**关键约束：**
- `AgentID.SYM`（SymptomParser）若未注册，`_execute_phase()` 已有 warning+return，不会崩溃。
- `AgentID.ONT`（OntologyFetcher）同上。
- `_execute_phase("sym", ...)` 和 `_execute_phase("ont", ...)` 已有 30s 超时保护（`AGENT_TIMEOUT_SECONDS`）。
- 纯 LLM 模式（`use_ontology=False`）完全不触碰 SymptomParser 和 OntologyFetcher，行为不变。

---

## Section 2：Prompt 语气调整

### 变更文件：`backend/llm/service.py`

**变更位置：** `LLMTools.generate_diagnosis()` 方法内，`reasoning_requirement` 字符串构建处（约第 668–681 行）和 `activated_block` 引导语（约第 656 行）。

**`activated_block` 引导语（在规则列表前增加一行）：**
```python
activated_block += "\n\n### 激活的 Ontology 规则（供参考）\n"
activated_block += "以下规则来自本体知识库，可作为推理背景，无需强制引用：\n\n"
activated_block += "\n\n".join(rule_lines)
```

**`reasoning_requirement` 从强制改为建议：**
```python
reasoning_requirement = """

## 参考知识（可选引用）

上方已提供 Ontology 激活规则作为背景参考。在 reasoning_steps 中：
- 若某个推理步骤与某条规则相关，可在 body 中提及规则 ID（格式：[T_x_x]）
- 若规则前置条件与当前症状不符，说明原因即可
- 不强制每个步骤都引用规则，以诊断准确性为优先
"""
```

---

## Section 3：置信度兜底分化

### 变更文件：`backend/llm/service.py`

**变更位置：** `_validate_and_fill_missing_fields()` 方法。

**签名变更：**
```python
def _validate_and_fill_missing_fields(
    self,
    data: Dict[str, Any],
    request: DiagnosisRequest,
    activated_knowledge: Optional[Any] = None,   # 新增参数
) -> Dict[str, Any]:
```

**兜底值分化（`confidence_factors` 默认值构建处）：**
```python
# 有 Ontology 上下文时，规则可信度更高（本体提供了额外证据支持）
rule_confidence = 0.90 if activated_knowledge else 0.85

data["confidence_factors"] = [
    {"label": "症状匹配度", "value": 0.90, "weight": 0.30, "explanation": "基于场景匹配"},
    {"label": "规则可信度", "value": rule_confidence, "weight": 0.35,
     "explanation": "来自本体知识库规则" if activated_knowledge else "来自知识库规则"},
    {"label": "数据质量", "value": 0.80 if request.signals else 0.50,
     "weight": 0.20, "explanation": "信号数据完整性"},
    {"label": "假设一致性", "value": 0.85, "weight": 0.15, "explanation": "假设与证据一致性"},
]
```

**调用点更新（`generate_diagnosis()` 内，约第 723 行）：**
```python
data = self._validate_and_fill_missing_fields(
    data, request, activated_knowledge=activated_knowledge
)
```

---

## Section 4：中文关键词提取修复

### 变更文件：`backend/agents/ontology_fetcher.py`

**变更位置：** `process()` 方法，关键词提取段（第 55–58 行）。

**变更前：**
```python
keywords = list(context.parsed_symptoms)
for word in context.symptom.replace("，", " ").replace("。", " ").split():
    if len(word) >= 2 and word not in keywords:
        keywords.append(word)
```

**变更后：**
```python
import re

keywords = list(context.parsed_symptoms)
# 用正则将所有中文标点、全角符号、引号替换为空格，再按空格分词
normalized = re.sub(r"[，。！？、：；''""（）【】《》\s]+", " ", context.symptom)
for word in normalized.split():
    if len(word) >= 2 and word not in keywords:
        keywords.append(word)
```

此修改确保 `"踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'"` 被分解为：
`["踩刹车按启动按钮", "车辆无法上电", "屏幕弹出", "钥匙未找到"]`，
而非单个整句字符串。

---

## 测试验证

### 新增测试文件：`backend/tests/test_ontology_pipeline.py`

**Test 1：** `test_ontology_fetcher_runs_in_llm_mode`
- Mock `OntologyFetcherAgent.process()`
- 触发 orchestrator 在 `use_ontology=True` 时调用流程
- 断言 `context.activated_knowledge` 不为 `None`

**Test 2：** `test_keyword_extraction_chinese`
- 直接调用 `OntologyFetcherAgent` 的关键词提取逻辑（或提取为辅助方法测试）
- 输入：`"踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'"`
- 断言：关键词列表包含 `"钥匙未找到"` 且长度 > 1

**Test 3：** `test_confidence_fallback_differs_by_mode`
- 调用 `LLMTools._validate_and_fill_missing_fields()` 两次，分别传 `activated_knowledge=None` 和非 None
- 断言两次返回的 `"规则可信度"` value 不同

### 手动验证流程
1. 使用测试场景运行 Ontology+LLM → 推理链步骤中应出现规则 ID（`[T_x_x]`）引用
2. 切换纯 LLM 模式运行 → 推理链无规则引用，步骤体出现 `※` deficit 注释
3. 对比两次置信度 → 应不同（Ontology 模式略高）
4. 底部对比面板 → 两侧可见差异

---

## 错误处理

- `_execute_phase("sym", ...)` 或 `_execute_phase("ont", ...)` 抛出异常：`_execute_phase()` 内部已有 `try/except + AgentState.ERROR`，异常会向上传播，`_execute_llm_pipeline()` 中不额外捕获，保持现有行为一致。
- `OntologyFetcher` 未注册：`_execute_phase()` 第 197 行 `if not agent_id or agent_id not in self.agents: return`，静默跳过。
- `activated_knowledge` 有值但 `activated_rules` 为空：现有 `if activated_knowledge and activated_knowledge.activated_rules` 判断已处理，`activated_block` 留空，行为不变。
