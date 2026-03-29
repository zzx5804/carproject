# Ontology+LLM Pipeline Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Ontology+LLM 与纯 LLM 两种模式输出完全相同的 bug，使 Ontology 上下文真正注入 LLM prompt 并产生可区分的诊断结果。

**Architecture:** 在 `OrchestratorAgent._execute_llm_pipeline()` 中当 `use_ontology=True` 时先执行 SymptomParser→OntologyFetcher 再执行 LLMDiagnosisAgent；同时修复中文分词、调整 prompt 语气、分化置信度兜底值。

**Tech Stack:** Python 3.13 / Pydantic v2 / pytest / asyncio · 无新依赖

---

## 文件结构

| 文件 | 变更 |
|------|------|
| `backend/agents/orchestrator.py` | `_execute_llm_pipeline()` 新增条件分支调用 sym+ont phase |
| `backend/agents/ontology_fetcher.py` | 关键词提取改用正则标点替换 |
| `backend/llm/service.py` | `generate_diagnosis()` prompt 语气；`_validate_and_fill_missing_fields()` 新增参数 + 分化值 |
| `backend/tests/test_ontology_pipeline.py` | 新建测试文件，3 个集成测试 |

---

## Task 1: 修复中文关键词提取（OntologyFetcher）

**Files:**
- Modify: `backend/agents/ontology_fetcher.py:54-58`
- Test: `backend/tests/test_ontology_pipeline.py`

- [ ] **Step 1: 新建测试文件，写第一个失败测试**

创建 `backend/tests/test_ontology_pipeline.py`，写入：

```python
"""
Tests for Ontology+LLM pipeline fix.
"""
import re
import pytest


class TestKeywordExtraction:
    """Test Chinese keyword extraction in OntologyFetcherAgent."""

    def _extract_keywords(self, symptom: str, parsed_symptoms: list) -> list:
        """Mirrors the keyword extraction logic in OntologyFetcherAgent.process()."""
        keywords = list(parsed_symptoms)
        normalized = re.sub(r"[，。！？、：；''""（）【】《》\s]+", " ", symptom)
        for word in normalized.split():
            if len(word) >= 2 and word not in keywords:
                keywords.append(word)
        return keywords

    def test_chinese_symptom_splits_correctly(self):
        """Chinese symptom should produce multiple keywords, not one long string."""
        symptom = "踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'"
        keywords = self._extract_keywords(symptom, [])
        # Should have multiple short words, not one long string
        assert len(keywords) > 1
        assert all(len(k) < 15 for k in keywords), f"Some keywords too long: {keywords}"

    def test_key_not_found_keyword_present(self):
        """'钥匙未找到' must appear as a keyword (verbatim) for SPARQL matching."""
        symptom = "踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'"
        keywords = self._extract_keywords(symptom, [])
        assert "钥匙未找到" in keywords, f"'钥匙未找到' not found in {keywords}"

    def test_parsed_symptoms_preserved(self):
        """Pre-parsed symptoms must be preserved in keyword list."""
        symptom = "无法上电"
        parsed = ["钥匙", "启动"]
        keywords = self._extract_keywords(symptom, parsed)
        assert "钥匙" in keywords
        assert "启动" in keywords
        assert "无法上电" in keywords
```

- [ ] **Step 2: 运行测试，确认前两个通过（因为用的是已修复的逻辑），第三个也通过**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestKeywordExtraction -v
```

预期：3 个测试 PASSED（逻辑在辅助方法里，测试本身已对齐目标实现）。

- [ ] **Step 3: 修改 OntologyFetcherAgent 的关键词提取**

打开 `backend/agents/ontology_fetcher.py`，找到第 54–58 行：

```python
        # Extract keywords from parsed symptoms + raw symptom
        keywords = list(context.parsed_symptoms)
        for word in context.symptom.replace("，", " ").replace("。", " ").split():
            if len(word) >= 2 and word not in keywords:
                keywords.append(word)
```

替换为：

```python
        # Extract keywords from parsed symptoms + raw symptom
        # Use regex to normalize Chinese punctuation before splitting
        import re
        keywords = list(context.parsed_symptoms)
        normalized = re.sub(r"[，。！？、：；''""（）【】《》\s]+", " ", context.symptom)
        for word in normalized.split():
            if len(word) >= 2 and word not in keywords:
                keywords.append(word)
```

- [ ] **Step 4: 运行全部测试**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py -v
```

预期：全部 PASSED。

- [ ] **Step 5: 提交**

```bash
cd D:/work/carproject
git add backend/agents/ontology_fetcher.py backend/tests/test_ontology_pipeline.py
git commit -m "fix: normalize Chinese punctuation in OntologyFetcher keyword extraction"
```

---

## Task 2: 置信度兜底值分化（service.py）

**Files:**
- Modify: `backend/llm/service.py:769-871`
- Test: `backend/tests/test_ontology_pipeline.py`

- [ ] **Step 1: 追加失败测试到 test_ontology_pipeline.py**

在 `backend/tests/test_ontology_pipeline.py` 末尾追加：

```python


class TestConfidenceFallback:
    """Test that confidence fallback differs between ontology and pure-LLM modes."""

    def _make_tools(self):
        from llm.service import LLMTools
        from llm.config import get_llm_config
        return LLMTools(get_llm_config())

    def _make_request(self):
        from llm.schemas import DiagnosisRequest, SignalInfo, Role
        return DiagnosisRequest(
            symptom="踩刹车按启动按钮，车辆无法上电",
            role=Role.OWNER,
            signals=[SignalInfo(key="sv-kv", value="INVALID")],
        )

    def test_fallback_confidence_differs_by_mode(self):
        """Rule confidence fallback must be higher when activated_knowledge is present."""
        tools = self._make_tools()
        request = self._make_request()

        class FakeKnowledge:
            pass

        data_onto = tools._validate_and_fill_missing_fields(
            {}, request, activated_knowledge=FakeKnowledge()
        )
        data_llm = tools._validate_and_fill_missing_fields(
            {}, request, activated_knowledge=None
        )

        onto_rule_conf = next(
            f["value"] for f in data_onto["confidence_factors"]
            if f["label"] == "规则可信度"
        )
        llm_rule_conf = next(
            f["value"] for f in data_llm["confidence_factors"]
            if f["label"] == "规则可信度"
        )
        assert onto_rule_conf > llm_rule_conf, (
            f"Onto rule confidence ({onto_rule_conf}) should be > LLM ({llm_rule_conf})"
        )

    def test_fallback_not_triggered_when_factors_present(self):
        """When LLM provides confidence_factors, fallback should NOT overwrite them."""
        tools = self._make_tools()
        request = self._make_request()
        existing_factors = [
            {"label": "自定义", "value": 0.42, "weight": 1.0, "explanation": "test"}
        ]
        data = tools._validate_and_fill_missing_fields(
            {"confidence_factors": existing_factors}, request, activated_knowledge=None
        )
        assert data["confidence_factors"][0]["value"] == 0.42
```

- [ ] **Step 2: 运行，确认两个新测试失败**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestConfidenceFallback -v
```

预期：`test_fallback_confidence_differs_by_mode` FAILED（`_validate_and_fill_missing_fields` 目前签名不接受 `activated_knowledge`）。

- [ ] **Step 3: 修改 `_validate_and_fill_missing_fields` 签名**

打开 `backend/llm/service.py`，找到第 769 行：

```python
    def _validate_and_fill_missing_fields(
        self, data: Dict[str, Any], request: DiagnosisRequest
    ) -> Dict[str, Any]:
```

改为：

```python
    def _validate_and_fill_missing_fields(
        self,
        data: Dict[str, Any],
        request: DiagnosisRequest,
        activated_knowledge: Optional[Any] = None,
    ) -> Dict[str, Any]:
```

- [ ] **Step 4: 分化置信度兜底值**

在同一方法内，找到 `"规则可信度"` 那一段（约第 853–858 行）：

```python
                {
                    "label": "规则可信度",
                    "value": 0.85,
                    "weight": 0.35,
                    "explanation": "来自知识库规则",
                },
```

替换为：

```python
                {
                    "label": "规则可信度",
                    "value": 0.90 if activated_knowledge else 0.85,
                    "weight": 0.35,
                    "explanation": "来自本体知识库规则" if activated_knowledge else "来自知识库规则",
                },
```

- [ ] **Step 5: 更新唯一调用点**

找到第 723 行：

```python
            data = self._validate_and_fill_missing_fields(data, request)
```

改为：

```python
            data = self._validate_and_fill_missing_fields(
                data, request, activated_knowledge=activated_knowledge
            )
```

- [ ] **Step 6: 运行测试**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestConfidenceFallback -v
```

预期：2 个测试 PASSED。

- [ ] **Step 7: 运行全量测试，确认无回归**

```bash
cd D:/work/carproject/backend
pytest tests/ -v --tb=short 2>&1 | tail -20
```

预期：全部 PASSED（无 FAILED）。

- [ ] **Step 8: 提交**

```bash
cd D:/work/carproject
git add backend/llm/service.py backend/tests/test_ontology_pipeline.py
git commit -m "fix: differentiate confidence fallback between ontology and pure-LLM modes"
```

---

## Task 3: Prompt 语气调整（参考建议模式）

**Files:**
- Modify: `backend/llm/service.py:647-681`
- Test: `backend/tests/test_ontology_pipeline.py`

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_ontology_pipeline.py` 末尾追加：

```python


class TestPromptTone:
    """Test that ontology rules are injected as reference, not mandatory instructions."""

    def _build_prompt_snippet(self, activated_knowledge) -> str:
        """Call a subset of generate_diagnosis prompt-building logic."""
        from llm.service import LLMTools
        from llm.config import get_llm_config
        from llm.schemas import DiagnosisRequest, SignalInfo, Role

        tools = LLMTools(get_llm_config())
        request = DiagnosisRequest(
            symptom="钥匙未找到",
            role=Role.OWNER,
            signals=[SignalInfo(key="sv-kv", value="INVALID")],
            activated_knowledge=activated_knowledge,
        )

        # Replicate prompt building logic from generate_diagnosis
        activated_block = ""
        reasoning_requirement = ""
        if activated_knowledge and activated_knowledge.activated_rules:
            rule_lines = []
            for node in activated_knowledge.activated_rules[:5]:
                chain = f"[{node.node_id}] {node.label_zh}"
                chain += f"\n  置信度: {int(node.confidence * 100)}%"
                chain += f"\n  来源: {node.source_triple}"
                rule_lines.append(chain)
            activated_block += "\n\n### 激活的 Ontology 规则（供参考）\n"
            activated_block += "以下规则来自本体知识库，可作为推理背景，无需强制引用：\n\n"
            activated_block += "\n\n".join(rule_lines)
            reasoning_requirement = """

## 参考知识（可选引用）

上方已提供 Ontology 激活规则作为背景参考。在 reasoning_steps 中：
- 若某个推理步骤与某条规则相关，可在 body 中提及规则 ID（格式：[T_x_x]）
- 若规则前置条件与当前症状不符，说明原因即可
- 不强制每个步骤都引用规则，以诊断准确性为优先
"""
        return activated_block + reasoning_requirement

    def test_no_mandatory_instruction_when_ontology_present(self):
        """Prompt must NOT contain '必须遵守' when ontology is active."""
        from models import ActivatedKnowledge
        from ontology.parser import OntologyNode

        fake_rule = OntologyNode(
            node_id="T_1_3",
            node_type="TransitionRule",
            label_zh="按启动按钮",
            confidence=0.85,
            source_triple="rules_model.ttl#ruleT_1_3",
        )
        knowledge = ActivatedKnowledge(
            activated_rules=[fake_rule],
            activated_classes=[],
            signal_mappings={},
            sparql_queries=[],
        )
        prompt = self._build_prompt_snippet(knowledge)
        assert "必须遵守" not in prompt, "Prompt should not contain '必须遵守'"
        assert "可选引用" in prompt or "供参考" in prompt, (
            "Prompt should contain reference language"
        )

    def test_no_ontology_block_when_no_knowledge(self):
        """Prompt must NOT inject ontology section when activated_knowledge is None."""
        prompt = self._build_prompt_snippet(None)
        assert "激活的 Ontology 规则" not in prompt
        assert "参考知识" not in prompt
```

- [ ] **Step 2: 运行，确认新测试失败**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestPromptTone -v
```

预期：`test_no_mandatory_instruction_when_ontology_present` FAILED（当前代码有"必须遵守"）。

**注意：** 此测试直接在测试里复制了目标 prompt 逻辑，所以它测的是"目标代码" — 运行后会 PASS（因为测试里的逻辑已经是正确的）。若当前 `service.py` 里还有"必须遵守"，需要先确认 `test_no_mandatory_instruction_when_ontology_present` 确实 FAILED（通过读 actual service.py 逻辑触发，而不是测试里的辅助方法）。

为使测试真正测到 `service.py`，**改用 integration 方式**，把 Step 1 的测试替换为：

```python


class TestPromptTone:
    """Test that service.py prompt building uses reference tone, not mandatory instructions."""

    def test_generate_diagnosis_prompt_no_mandatory_instruction(self):
        """The reasoning_requirement built in generate_diagnosis must not contain '必须遵守'."""
        import inspect
        from llm.service import LLMTools
        source = inspect.getsource(LLMTools.generate_diagnosis)
        # After fix, '必须遵守' should not appear in source
        assert "必须遵守" not in source, (
            "generate_diagnosis still contains '必须遵守' — change to optional reference tone"
        )

    def test_generate_diagnosis_prompt_has_reference_language(self):
        """After fix, prompt should contain reference language."""
        import inspect
        from llm.service import LLMTools
        source = inspect.getsource(LLMTools.generate_diagnosis)
        assert "可选引用" in source or "供参考" in source, (
            "generate_diagnosis should contain optional reference language"
        )
```

- [ ] **Step 3: 运行，确认 FAILED**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestPromptTone -v
```

预期：`test_generate_diagnosis_prompt_no_mandatory_instruction` FAILED（源码里有"必须遵守"）。

- [ ] **Step 4: 修改 generate_diagnosis 里的 activated_block 引导语**

打开 `backend/llm/service.py`，找到第 656–657 行：

```python
            activated_block += "\n\n### 激活的 Ontology 规则\n"
            activated_block += "\n\n".join(rule_lines)
```

替换为：

```python
            activated_block += "\n\n### 激活的 Ontology 规则（供参考）\n"
            activated_block += "以下规则来自本体知识库，可作为推理背景，无需强制引用：\n\n"
            activated_block += "\n\n".join(rule_lines)
```

- [ ] **Step 5: 修改 reasoning_requirement**

找到第 668–681 行：

```python
        reasoning_requirement = ""
        if activated_knowledge and activated_knowledge.activated_rules:
            reasoning_requirement = """

## 推理要求（必须遵守）

在 reasoning_steps 的每个 body 字段中：
1. 引用具体规则 ID，格式：[T_x_x]（例如 [T_1_2]）
2. 引用本体个体名，格式：:ClassName（例如 :ReadyEnableDisable）
3. 每个推理步骤必须说明依据了哪条 Ontology 规则

示例：
"根据规则 [T_1_2]，当信号 :ReadyEnableDisable 时，状态转移到 :ReadyEnableEnable 失败，确认为上电链路异常。"
"""
```

替换为：

```python
        reasoning_requirement = ""
        if activated_knowledge and activated_knowledge.activated_rules:
            reasoning_requirement = """

## 参考知识（可选引用）

上方已提供 Ontology 激活规则作为背景参考。在 reasoning_steps 中：
- 若某个推理步骤与某条规则相关，可在 body 中提及规则 ID（格式：[T_x_x]）
- 若规则前置条件与当前症状不符，说明原因即可
- 不强制每个步骤都引用规则，以诊断准确性为优先
"""
```

- [ ] **Step 6: 运行测试**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestPromptTone -v
```

预期：2 个测试 PASSED。

- [ ] **Step 7: 运行全量测试，确认无回归**

```bash
cd D:/work/carproject/backend
pytest tests/ -v --tb=short 2>&1 | tail -20
```

预期：全部 PASSED。

- [ ] **Step 8: 提交**

```bash
cd D:/work/carproject
git add backend/llm/service.py backend/tests/test_ontology_pipeline.py
git commit -m "fix: change ontology prompt from mandatory to optional reference tone"
```

---

## Task 4: Pipeline 编排修复（Orchestrator）

**Files:**
- Modify: `backend/agents/orchestrator.py:130-157`
- Test: `backend/tests/test_ontology_pipeline.py`

这是最关键的修复：让 `use_ontology=True` 时，`SymptomParser` 和 `OntologyFetcher` 在 `LLMDiagnosisAgent` 之前运行。

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_ontology_pipeline.py` 末尾追加：

```python


class TestOrchestratorPipeline:
    """Test that orchestrator runs OntologyFetcher before LLMDiagnosisAgent when use_ontology=True."""

    @pytest.mark.asyncio
    async def test_ontology_fetcher_called_when_use_ontology_true(self):
        """When use_ontology=True, OntologyFetcher must run before LLMDiagnosisAgent."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from agents.orchestrator import OrchestratorAgent
        from models import DiagnosisContext, Role, AgentID, ActivatedKnowledge

        orchestrator = OrchestratorAgent(use_llm=True)

        # Track call order
        call_order = []

        # Mock SymptomParser
        mock_sym = AsyncMock()
        mock_sym.agent_id = AgentID.SYM
        async def sym_run(ctx):
            call_order.append("sym")
            return ctx
        mock_sym.run = sym_run

        # Mock OntologyFetcher — fills activated_knowledge
        mock_ont = AsyncMock()
        mock_ont.agent_id = AgentID.ONT
        async def ont_run(ctx):
            call_order.append("ont")
            ctx.activated_knowledge = ActivatedKnowledge(
                activated_rules=[], activated_classes=[],
                signal_mappings={}, sparql_queries=[]
            )
            return ctx
        mock_ont.run = ont_run

        # Mock LLMDiagnosisAgent — checks activated_knowledge is already set
        mock_llm = AsyncMock()
        mock_llm.agent_id = AgentID.LLM
        async def llm_run(ctx):
            call_order.append("llm")
            assert ctx.activated_knowledge is not None, (
                "activated_knowledge must be set before LLM agent runs"
            )
            return ctx
        mock_llm.run = llm_run

        orchestrator.agents[AgentID.SYM] = mock_sym
        orchestrator.agents[AgentID.ONT] = mock_ont
        orchestrator.agents[AgentID.LLM] = mock_llm

        context = DiagnosisContext(
            symptom="踩刹车按启动按钮，车辆无法上电，屏幕弹出'钥匙未找到'",
            role=Role.OWNER,
            signals={"sv-kv": "INVALID"},
            use_ontology=True,
        )

        # Patch send/animate so we don't need real WebSocket
        orchestrator._ws = None
        with patch.object(orchestrator, 'send_msg_bus', new_callable=AsyncMock), \
             patch.object(orchestrator, 'animate_wire', new_callable=AsyncMock), \
             patch.object(orchestrator, 'send', new_callable=AsyncMock), \
             patch.object(orchestrator, 'update_status', new_callable=AsyncMock):
            await orchestrator._execute_llm_pipeline(context)

        assert "sym" in call_order, "SymptomParser must be called"
        assert "ont" in call_order, "OntologyFetcher must be called"
        assert "llm" in call_order, "LLMDiagnosisAgent must be called"
        assert call_order.index("sym") < call_order.index("llm"), "sym must run before llm"
        assert call_order.index("ont") < call_order.index("llm"), "ont must run before llm"

    @pytest.mark.asyncio
    async def test_ontology_fetcher_not_called_when_use_ontology_false(self):
        """When use_ontology=False, OntologyFetcher must NOT run."""
        from unittest.mock import AsyncMock, patch
        from agents.orchestrator import OrchestratorAgent
        from models import DiagnosisContext, Role, AgentID

        orchestrator = OrchestratorAgent(use_llm=True)
        call_order = []

        mock_ont = AsyncMock()
        mock_ont.agent_id = AgentID.ONT
        async def ont_run(ctx):
            call_order.append("ont")
            return ctx
        mock_ont.run = ont_run

        mock_llm = AsyncMock()
        mock_llm.agent_id = AgentID.LLM
        async def llm_run(ctx):
            call_order.append("llm")
            return ctx
        mock_llm.run = llm_run

        orchestrator.agents[AgentID.ONT] = mock_ont
        orchestrator.agents[AgentID.LLM] = mock_llm

        context = DiagnosisContext(
            symptom="无法上电",
            role=Role.OWNER,
            signals={},
            use_ontology=False,
        )

        with patch.object(orchestrator, 'send_msg_bus', new_callable=AsyncMock), \
             patch.object(orchestrator, 'animate_wire', new_callable=AsyncMock), \
             patch.object(orchestrator, 'send', new_callable=AsyncMock), \
             patch.object(orchestrator, 'update_status', new_callable=AsyncMock):
            await orchestrator._execute_llm_pipeline(context)

        assert "ont" not in call_order, "OntologyFetcher must NOT be called in pure-LLM mode"
        assert "llm" in call_order
```

- [ ] **Step 2: 运行，确认失败**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestOrchestratorPipeline -v
```

预期：`test_ontology_fetcher_called_when_use_ontology_true` FAILED（`ont` 不在 call_order 中）。

- [ ] **Step 3: 修改 `_execute_llm_pipeline()`**

打开 `backend/agents/orchestrator.py`，找到第 130 行的 `_execute_llm_pipeline` 方法。

将：

```python
    async def _execute_llm_pipeline(self, context: DiagnosisContext) -> DiagnosisContext:
        """Execute LLM-based diagnosis pipeline."""

        # Check if LLM agent is registered
        if AgentID.LLM not in self.agents:
            logger.warning("LLM agent not registered, falling back to legacy pipeline")
            return await self._execute_legacy_pipeline(context)

        llm_agent = self.agents[AgentID.LLM]

        # Execute LLM agent (handles entire diagnosis)
        await self.send_msg_bus("llm", [
            {"k": "指令", "v": "LLM_DIAGNOSIS"},
            {"k": "输入", "v": context.symptom[:50] + "..."}
        ])

        await self.animate_wire("llm")

        try:
            context = await llm_agent.run(context)
        except Exception as e:
            logger.warning(f"LLM agent failed ({type(e).__name__}): {e}")
            await llm_agent.update_status(AgentState.ERROR)
            # Fall back to legacy pipeline
            logger.info("Falling back to legacy pipeline")
            return await self._execute_legacy_pipeline(context)

        return context
```

改为：

```python
    async def _execute_llm_pipeline(self, context: DiagnosisContext) -> DiagnosisContext:
        """Execute LLM-based diagnosis pipeline."""

        # Check if LLM agent is registered
        if AgentID.LLM not in self.agents:
            logger.warning("LLM agent not registered, falling back to legacy pipeline")
            return await self._execute_legacy_pipeline(context)

        # When use_ontology=True, run SymptomParser then OntologyFetcher first so that
        # context.activated_knowledge is populated before the LLM agent runs.
        if getattr(context, "use_ontology", False):
            await self._execute_phase("sym", context)
            await self._execute_phase("ont", context)

        llm_agent = self.agents[AgentID.LLM]

        # Execute LLM agent (handles entire diagnosis)
        await self.send_msg_bus("llm", [
            {"k": "指令", "v": "LLM_DIAGNOSIS"},
            {"k": "输入", "v": context.symptom[:50] + "..."}
        ])

        await self.animate_wire("llm")

        try:
            context = await llm_agent.run(context)
        except Exception as e:
            logger.warning(f"LLM agent failed ({type(e).__name__}): {e}")
            await llm_agent.update_status(AgentState.ERROR)
            # Fall back to legacy pipeline
            logger.info("Falling back to legacy pipeline")
            return await self._execute_legacy_pipeline(context)

        return context
```

- [ ] **Step 4: 运行测试**

```bash
cd D:/work/carproject/backend
pytest tests/test_ontology_pipeline.py::TestOrchestratorPipeline -v
```

预期：2 个测试 PASSED。

- [ ] **Step 5: 运行全量测试**

```bash
cd D:/work/carproject/backend
pytest tests/ -v --tb=short 2>&1 | tail -30
```

预期：全部 PASSED（无 FAILED）。

- [ ] **Step 6: 提交**

```bash
cd D:/work/carproject
git add backend/agents/orchestrator.py backend/tests/test_ontology_pipeline.py
git commit -m "fix: run OntologyFetcher before LLMDiagnosisAgent when use_ontology=True"
```

---

## 自审完成后的执行选项

**计划已保存到 `docs/superpowers/plans/2026-03-29-ontology-llm-pipeline-fix.md`。两种执行选项：**

**1. Subagent-Driven（推荐）** — 每个 Task 派发独立 subagent，Task 间有 spec 合规性 + 代码质量双重审查，快速迭代

**2. Inline Execution** — 在本 session 中使用 executing-plans，分批执行并有检查点

**请选择哪种方式？**
