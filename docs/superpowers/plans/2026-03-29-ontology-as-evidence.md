# Ontology-as-Evidence 架构升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 OntologyFetcher 从硬编码 HTML 升级为真实 SPARQL 查询，让 LLM 推理步骤显式引用 Ontology 规则 ID，并在前端展示激活节点面板和 With/Without 对比切换。

**Architecture:** OntologyFetcher 执行三类 SPARQL 查询，组装 `ActivatedKnowledge` 对象写入 `DiagnosisContext`，下游 `LLMDiagnosisAgent` 从 context 中取出并注入结构化规则知识到 prompt，LLM 被强制引用 `[T_x_x]` 规则 ID，前端接收新 `onto_activated` WebSocket 事件并渲染激活面板。

**Tech Stack:** Python 3.11, rdflib 7.x (SPARQL), Pydantic v2, FastAPI WebSocket, Vanilla JS

---

## File Map

| 文件 | 改动 |
|------|------|
| `backend/models.py` | 新增 `ActivatedNode`、`ActivatedKnowledge` Pydantic 模型；`DiagnosisContext` 新增 `activated_knowledge` 字段；新增 `OntoActivatedMessage` |
| `backend/ontology/parser.py` | 新增三个 SPARQL 查询方法：`query_matching_rules`、`query_signal_individuals`、`query_rule_chain` |
| `backend/agents/ontology_fetcher.py` | 重构 `process()`：替换硬编码 HTML，调用新 SPARQL 方法，发送 `onto_activated` 事件 |
| `backend/llm/prompts.py` | 修改 `build_diagnosis_prompt()` 接收 `ActivatedKnowledge`，注入结构化规则块，新增强制引用指令 |
| `backend/server.py` | `start_diagnosis()` 解析 `use_ontology` 参数，写入 context |
| `cea-diagnosis.html` | 新增 `onto_activated` 事件处理、激活面板渲染、`[T_x_x]` 标签高亮、With/Without 切换开关 |
| `backend/tests/test_ontology_activated.py` | 新建：覆盖 SPARQL 查询方法和 ActivatedKnowledge 组装 |

---

## Task 1: 新增数据模型

**Files:**
- Modify: `backend/models.py`
- Test: `backend/tests/test_ontology_activated.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_ontology_activated.py`：

```python
"""Tests for ActivatedKnowledge models."""
import pytest
from models import ActivatedNode, ActivatedKnowledge, DiagnosisContext, Role


def test_activated_node_creation():
    node = ActivatedNode(
        node_id="T_1_2",
        node_type="rule",
        label_zh="Disable跳转至Enable",
        confidence=0.92,
        source_triple="rules_model.ttl#ruleT_1_2",
    )
    assert node.node_id == "T_1_2"
    assert node.node_type == "rule"
    assert node.confidence == 0.92


def test_activated_knowledge_creation():
    rule = ActivatedNode(
        node_id="T_1_2",
        node_type="rule",
        label_zh="Disable跳转至Enable",
        confidence=0.92,
        source_triple="rules_model.ttl#ruleT_1_2",
    )
    knowledge = ActivatedKnowledge(
        activated_rules=[rule],
        activated_classes=[],
        signal_mappings={"sv-kv": ":ReadyEnableDisable"},
        sparql_queries=["SELECT ?rule WHERE { ?rule rdf:type :TransitionRule }"],
    )
    assert len(knowledge.activated_rules) == 1
    assert knowledge.signal_mappings["sv-kv"] == ":ReadyEnableDisable"


def test_diagnosis_context_has_activated_knowledge(sample_context):
    assert sample_context.activated_knowledge is None


def test_onto_activated_message():
    from models import OntoActivatedMessage, ActivatedNode
    node = ActivatedNode(
        node_id="T_1_2", node_type="rule", label_zh="测试", confidence=0.9,
        source_triple="rules_model.ttl#ruleT_1_2"
    )
    msg = OntoActivatedMessage(
        nodes=[node],
        signal_mappings={"sv-kv": ":ReadyEnableDisable"},
    )
    assert msg.type == "onto_activated"
    assert len(msg.nodes) == 1
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py -v
```

期望：`ImportError: cannot import name 'ActivatedNode' from 'models'`

- [ ] **Step 3: 在 models.py 新增模型**

在 `backend/models.py` 末尾（`DiagnosisContext` 类定义之前）添加：

```python
# =============================================================================
# Ontology Activation Models
# =============================================================================


class ActivatedNode(BaseModel):
    """An ontology node activated during diagnosis."""

    node_id: str          # e.g. "T_1_2"
    node_type: str        # "rule" | "class" | "individual"
    label_zh: str         # e.g. "Disable跳转至Enable"
    confidence: float     # 0.0–1.0
    source_triple: str    # e.g. "rules_model.ttl#ruleT_1_2"


class ActivatedKnowledge(BaseModel):
    """Structured ontology knowledge activated for this diagnosis."""

    activated_rules: List[ActivatedNode] = Field(default_factory=list)
    activated_classes: List[ActivatedNode] = Field(default_factory=list)
    signal_mappings: Dict[str, str] = Field(default_factory=dict)
    sparql_queries: List[str] = Field(default_factory=list)


class OntoActivatedMessage(BaseModel):
    """WebSocket message: ontology nodes activated."""

    type: Literal["onto_activated"] = "onto_activated"
    nodes: List[ActivatedNode] = Field(default_factory=list)
    signal_mappings: Dict[str, str] = Field(default_factory=dict)
```

在 `DiagnosisContext` 类的 `# Ontology data` 注释块下添加一行：

```python
    # Activated ontology knowledge (populated by OntologyFetcher)
    activated_knowledge: Optional[ActivatedKnowledge] = None
```

将 `ActivatedKnowledge` 和 `OntoActivatedMessage` 加入 `ResponseMessage` 联合类型：

```python
ResponseMessage = (
    AgentStatusMessage
    | MsgBusMessage
    | WireAnimateMessage
    | ReasoningStepMessage
    | OntoSummaryMessage
    | OntoActivatedMessage      # ← 新增
    | RuleMatchedMessage
    | HypothesisMessage
    | ConfFactorsMessage
    | ConfFinalMessage
    | OutputMessage
    | BackendStatusMessage
    | PipelineDoneMessage
    | SignalRecommendationMessage
    | ErrorMessage
)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py -v
```

期望：4 tests PASSED

- [ ] **Step 5: Commit**

```bash
cd backend && git add models.py tests/test_ontology_activated.py
git commit -m "feat: add ActivatedNode, ActivatedKnowledge models and OntoActivatedMessage"
```

---

## Task 2: SPARQL 查询层

**Files:**
- Modify: `backend/ontology/parser.py`
- Test: `backend/tests/test_ontology_activated.py`（追加）

- [ ] **Step 1: 在测试文件追加 SPARQL 测试**

在 `backend/tests/test_ontology_activated.py` 末尾追加：

```python
# ── SPARQL query tests ────────────────────────────────────────────────────────

@pytest.fixture
def real_parser():
    """OntologyParser loaded from the project ontology folder."""
    from pathlib import Path
    from ontology.parser import OntologyParser
    folder = Path(__file__).parent.parent.parent / "ontology files"
    if not folder.exists():
        pytest.skip(f"Ontology folder not found: {folder}")
    parser = OntologyParser(str(folder))
    if not parser.load():
        pytest.skip("Failed to load ontology")
    return parser


def test_query_matching_rules_returns_list(real_parser):
    results = real_parser.query_matching_rules(["上电", "BLE"])
    assert isinstance(results, list)


def test_query_matching_rules_finds_t12(real_parser):
    """T_1_2 covers the Disable→Enable transition relevant to startup failure."""
    results = real_parser.query_matching_rules(["上电", "Enable", "Disable"])
    rule_ids = [n.node_id for n in results]
    assert "T_1_2" in rule_ids


def test_query_matching_rules_returns_activated_nodes(real_parser):
    results = real_parser.query_matching_rules(["上电"])
    for node in results:
        assert isinstance(node.node_id, str)
        assert node.node_type == "rule"
        assert 0.0 <= node.confidence <= 1.0
        assert "rules_model.ttl" in node.source_triple or node.source_triple != ""


def test_query_signal_individuals_off_mode(real_parser):
    signals = {"sv-pm": "0:Off", "sv-kv": "INVALID"}
    mappings = real_parser.query_signal_individuals(signals)
    assert isinstance(mappings, dict)
    # sv-pm=0:Off should map to OffMode or similar
    assert "sv-pm" in mappings


def test_query_rule_chain_returns_string(real_parser):
    chain = real_parser.query_rule_chain("T_1_2")
    assert isinstance(chain, str)
    assert len(chain) > 0
    assert "T_1_2" in chain
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py::test_query_matching_rules_returns_list -v
```

期望：`AttributeError: 'OntologyParser' object has no attribute 'query_matching_rules'`

- [ ] **Step 3: 在 parser.py 新增三个 SPARQL 方法**

在 `backend/ontology/parser.py` 末尾（文件最后），在最后一个方法之后添加：

```python
    # =========================================================================
    # SPARQL Query Methods (Ontology-as-Evidence)
    # =========================================================================

    def query_matching_rules(self, keywords: List[str]) -> List["ActivatedNode"]:
        """
        Query TransitionRule individuals whose labels or comments match keywords.

        Returns ActivatedNode list sorted by confidence descending.
        Confidence is computed as: matched_keywords / total_keywords, floored at 0.5
        if the rule has any match at all.
        """
        from models import ActivatedNode

        graph = self._require_graph()
        ns = self.ns

        # SPARQL: fetch all TransitionRule individuals with their metadata
        sparql = """
        SELECT ?rule ?ruleId ?labelZh ?commentZh ?fromState ?toState
        WHERE {
            ?rule rdf:type :TransitionRule .
            OPTIONAL { ?rule :ruleId ?ruleId . }
            OPTIONAL { ?rule rdfs:label ?labelZh FILTER(lang(?labelZh) = "zh") . }
            OPTIONAL { ?rule rdfs:comment ?commentZh FILTER(lang(?commentZh) = "zh") . }
            OPTIONAL { ?rule :fromState ?fromState . }
            OPTIONAL { ?rule :toState ?toState . }
        }
        """
        results = graph.query(
            sparql,
            initNs={"rdf": RDF, "rdfs": RDFS, "": ns},
        )

        activated: List[ActivatedNode] = []
        keywords_lower = [k.lower() for k in keywords]

        for row in results:
            rule_uri = str(row.rule) if row.rule else ""
            rule_id = str(row.ruleId) if row.ruleId else rule_uri.split("#")[-1]
            label_zh = str(row.labelZh) if row.labelZh else rule_id
            comment_zh = str(row.commentZh) if row.commentZh else ""
            from_state = str(row.fromState).split("#")[-1] if row.fromState else ""
            to_state = str(row.toState).split("#")[-1] if row.toState else ""

            # Score: count keyword hits across label + comment + state names
            searchable = f"{label_zh} {comment_zh} {from_state} {to_state}".lower()
            hits = sum(1 for kw in keywords_lower if kw in searchable)

            if hits == 0:
                continue

            confidence = min(0.5 + (hits / max(len(keywords_lower), 1)) * 0.5, 1.0)

            # Build source_triple reference
            local_name = rule_uri.split("#")[-1] if "#" in rule_uri else rule_id
            source = f"rules_model.ttl#{local_name}"

            activated.append(
                ActivatedNode(
                    node_id=rule_id,
                    node_type="rule",
                    label_zh=label_zh,
                    confidence=round(confidence, 2),
                    source_triple=source,
                )
            )

        # Sort by confidence descending, limit to top 5
        activated.sort(key=lambda n: n.confidence, reverse=True)
        return activated[:5]

    def query_signal_individuals(self, signals: Dict[str, str]) -> Dict[str, str]:
        """
        Map frontend signal key-values to Ontology individual local names.

        Mapping table:
        - sv-pm with "Off"    → ":OffMode"
        - sv-pm with "Remote" → ":RemoteOnMode"
        - sv-pm with "Local"  → ":LocalOnMode"
        - sv-pm with "Conv"   → ":ConvenienceMode"
        - sv-kv "VALID"       → ":ReadyEnableEnable"
        - sv-kv "INVALID"     → ":ReadyEnableDisable"
        """
        mappings: Dict[str, str] = {}

        sv_pm = signals.get("sv-pm", "")
        if "Off" in sv_pm:
            mappings["sv-pm"] = ":OffMode"
        elif "Remote" in sv_pm:
            mappings["sv-pm"] = ":RemoteOnMode"
        elif "Local" in sv_pm or "On" in sv_pm:
            mappings["sv-pm"] = ":LocalOnMode"
        elif "Conv" in sv_pm:
            mappings["sv-pm"] = ":ConvenienceMode"

        sv_kv = signals.get("sv-kv", "")
        if "VALID" in sv_kv and "INVALID" not in sv_kv:
            mappings["sv-kv"] = ":ReadyEnableEnable"
        elif "INVALID" in sv_kv:
            mappings["sv-kv"] = ":ReadyEnableDisable"

        sv_ble = signals.get("sv-ble", "")
        if sv_ble == "1":
            mappings["sv-ble"] = ":BLEKeyDetected"
        elif sv_ble == "0":
            mappings["sv-ble"] = ":BLEKeyNotDetected"

        return mappings

    def query_rule_chain(self, rule_id: str) -> str:
        """
        Return a human-readable rule chain string for the given ruleId.

        Format:
            [T_1_2] Disable跳转至Enable
              前提: :ReadyEnableDisable
              结论: → :ReadyEnableEnable
              来源: rules_model.ttl#ruleT_1_2
        """
        graph = self._require_graph()
        ns = self.ns

        sparql = """
        SELECT ?rule ?labelZh ?commentZh ?fromState ?toState
        WHERE {
            ?rule rdf:type :TransitionRule .
            ?rule :ruleId ?id .
            FILTER(str(?id) = ?targetId)
            OPTIONAL { ?rule rdfs:label ?labelZh FILTER(lang(?labelZh) = "zh") . }
            OPTIONAL { ?rule rdfs:comment ?commentZh FILTER(lang(?commentZh) = "zh") . }
            OPTIONAL { ?rule :fromState ?fromState . }
            OPTIONAL { ?rule :toState ?toState . }
        }
        """
        from rdflib import Literal as RDFLiteral
        results = list(graph.query(
            sparql,
            initNs={"rdf": RDF, "rdfs": RDFS, "": ns},
            initBindings={"targetId": RDFLiteral(rule_id)},
        ))

        if not results:
            return f"[{rule_id}] 规则未找到"

        row = results[0]
        label_zh = str(row.labelZh) if row.labelZh else rule_id
        comment_zh = str(row.commentZh) if row.commentZh else ""
        from_state = str(row.fromState).split("#")[-1] if row.fromState else "?"
        to_state = str(row.toState).split("#")[-1] if row.toState else "?"
        rule_uri = str(row.rule) if row.rule else ""
        local_name = rule_uri.split("#")[-1] if "#" in rule_uri else f"rule{rule_id}"

        lines = [
            f"[{rule_id}] {label_zh}",
            f"  前提: :{from_state}",
            f"  结论: → :{to_state}",
        ]
        if comment_zh:
            lines.append(f"  说明: {comment_zh}")
        lines.append(f"  来源: rules_model.ttl#{local_name}")
        return "\n".join(lines)
```

**注意**：`ActivatedNode` 是在 models.py 中定义的，需要在方法内 import 以避免循环引用（parser.py 不能在顶层 import models.py）。

- [ ] **Step 4: 运行 SPARQL 测试**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py -v -k "query"
```

期望：5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/ontology/parser.py backend/tests/test_ontology_activated.py
git commit -m "feat: add SPARQL query methods to OntologyParser (query_matching_rules, query_signal_individuals, query_rule_chain)"
```

---

## Task 3: 重构 OntologyFetcher

**Files:**
- Modify: `backend/agents/ontology_fetcher.py`
- Test: `backend/tests/test_ontology_activated.py`（追加）

- [ ] **Step 1: 追加 OntologyFetcher 集成测试**

在测试文件末尾追加：

```python
# ── OntologyFetcher integration tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ontology_fetcher_populates_activated_knowledge(
    real_parser, mock_message_sender, sample_context
):
    """After process(), context.activated_knowledge should be populated."""
    from agents.ontology_fetcher import OntologyFetcherAgent
    from models import AgentID

    sent_messages = []

    agent = OntologyFetcherAgent()
    agent.set_ontology_parser(real_parser)
    agent._send = AsyncMock(side_effect=lambda msg: sent_messages.append(msg))

    result = await agent.process(sample_context)

    assert result.activated_knowledge is not None
    assert isinstance(result.activated_knowledge.activated_rules, list)
    assert isinstance(result.activated_knowledge.signal_mappings, dict)


@pytest.mark.asyncio
async def test_ontology_fetcher_sends_onto_activated_event(
    real_parser, sample_context
):
    """OntologyFetcher must emit onto_activated WebSocket event."""
    from agents.ontology_fetcher import OntologyFetcherAgent
    from unittest.mock import AsyncMock

    sent_messages = []
    agent = OntologyFetcherAgent()
    agent.set_ontology_parser(real_parser)
    agent._send = AsyncMock(side_effect=lambda msg: sent_messages.append(msg))

    await agent.process(sample_context)

    types = [m.get("type") for m in sent_messages]
    assert "onto_activated" in types
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py::test_ontology_fetcher_populates_activated_knowledge -v
```

期望：FAILED — context.activated_knowledge is None

- [ ] **Step 3: 重构 ontology_fetcher.py**

将 `backend/agents/ontology_fetcher.py` 的 `process()` 方法替换为：

```python
    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Fetch ontology information based on context using SPARQL queries."""
        logger.info("OntologyFetcher processing...")

        await self.update_status(AgentState.RUNNING, 0)

        if not self._ontology_parser:
            logger.warning("No ontology parser set, skipping ontology fetch")
            return context

        # Extract keywords from parsed symptoms + raw symptom
        keywords = list(context.parsed_symptoms)
        for word in context.symptom.replace("，", " ").replace("。", " ").split():
            if len(word) >= 2 and word not in keywords:
                keywords.append(word)

        await self.delay(150)
        await self.update_status(AgentState.RUNNING, 25)

        # ① Query matching rules via SPARQL
        activated_rules = self._ontology_parser.query_matching_rules(keywords)
        sparql_query_log = [
            f"SELECT ?rule WHERE {{ ?rule rdf:type :TransitionRule }} "
            f"(keywords: {keywords[:3]})"
        ]
        await self.delay(150)
        await self.update_status(AgentState.RUNNING, 50)

        # ② Map signals to ontology individuals
        signal_mappings = self._ontology_parser.query_signal_individuals(
            context.signals
        )
        await self.delay(150)
        await self.update_status(AgentState.RUNNING, 70)

        # ③ Assemble ActivatedKnowledge
        from models import ActivatedKnowledge
        knowledge = ActivatedKnowledge(
            activated_rules=activated_rules,
            activated_classes=[],
            signal_mappings=signal_mappings,
            sparql_queries=sparql_query_log,
        )
        context.activated_knowledge = knowledge

        # ④ Send onto_activated event to frontend
        await self.send({
            "type": "onto_activated",
            "nodes": [
                {
                    "id": n.node_id,
                    "type": n.node_type,
                    "label_zh": n.label_zh,
                    "confidence": n.confidence,
                    "source": n.source_triple,
                }
                for n in activated_rules
            ],
            "signal_mappings": signal_mappings,
        })

        # ⑤ Generate HTML summary from real query results
        html = self._generate_ontology_summary(context, signal_mappings, activated_rules)
        await self.send({"type": "onto_summary", "html": html})

        # ⑥ Notify message bus
        rule_ids = ", ".join(n.node_id for n in activated_rules[:3]) or "无"
        await self.send_msg_bus("rule", [
            {"k": "激活规则", "v": rule_ids, "cls": "g"},
            {"k": "信号映射", "v": f"{len(signal_mappings)} 条", "cls": "g"},
        ])
        await self.animate_wire("rule")
        await self.update_status(AgentState.DONE, 100)

        return context
```

将 `_generate_ontology_summary` 方法签名和实现替换为：

```python
    def _generate_ontology_summary(
        self,
        context: DiagnosisContext,
        signal_mappings: Dict[str, Any],
        activated_rules: list,
    ) -> str:
        """Generate HTML summary from real SPARQL query results."""
        sv_pm = context.signals.get("sv-pm", "0:Off")
        sv_kv = context.signals.get("sv-kv", "INVALID")
        sv_ble = context.signals.get("sv-ble", "0")

        pm_color = "var(--red)" if "Off" in sv_pm else "var(--ylw)" if "Remote" in sv_pm else "var(--grn)"
        kv_color = "var(--grn)" if "VALID" in sv_kv and "INVALID" not in sv_kv else "var(--red)"

        pm_individual = signal_mappings.get("sv-pm", "?")
        kv_individual = signal_mappings.get("sv-kv", "?")

        rules_html = ""
        for node in activated_rules[:3]:
            conf_color = "var(--grn)" if node.confidence >= 0.8 else "var(--ylw)"
            rules_html += (
                f'<div style="margin-top:4px">'
                f'<span style="color:{conf_color};font-weight:600">[{node.node_id}]</span> '
                f'<span style="color:var(--txd);font-size:9px">{node.label_zh}</span>'
                f'<span style="color:var(--txd);font-size:8px;margin-left:4px">'
                f'({int(node.confidence*100)}%)</span>'
                f'</div>'
            )

        return f'''<div style="font-family:var(--mono);font-size:11px;line-height:2;color:var(--tx)">
  <div style="color:var(--txd);font-size:9px;margin-bottom:4px">// SPARQL查询结果 · 实时激活</div>
  <div style="color:var(--acc);margin-bottom:4px">// 信号 → 本体映射</div>
  <div><span style="color:var(--txd)">sv-pm</span> <span style="color:{pm_color}">{sv_pm}</span>
    <span style="color:var(--txd)"> → </span><span style="color:var(--purple)">{pm_individual}</span></div>
  <div><span style="color:var(--txd)">sv-kv</span> <span style="color:{kv_color}">{sv_kv}</span>
    <span style="color:var(--txd)"> → </span><span style="color:var(--purple)">{kv_individual}</span></div>
  <div style="color:var(--ylw);margin-top:6px">// 激活规则</div>
  {rules_html}
</div>'''
```

- [ ] **Step 4: 运行集成测试**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py -v -k "fetcher"
```

期望：2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/agents/ontology_fetcher.py backend/tests/test_ontology_activated.py
git commit -m "feat: refactor OntologyFetcher to use SPARQL queries and emit onto_activated event"
```

---

## Task 4: LLM Prompt 结构化注入

**Files:**
- Modify: `backend/llm/prompts.py`
- Modify: `backend/agents/llm_diagnosis_agent.py`
- Test: `backend/tests/test_ontology_activated.py`（追加）

- [ ] **Step 1: 追加 Prompt 注入测试**

```python
# ── Prompt injection tests ────────────────────────────────────────────────────

def test_build_diagnosis_prompt_includes_rule_ids():
    """Prompt must contain activated rule IDs in [T_x_x] format."""
    from llm.prompts import get_prompt_builder
    from models import ActivatedNode, ActivatedKnowledge

    builder = get_prompt_builder()
    knowledge = ActivatedKnowledge(
        activated_rules=[
            ActivatedNode(
                node_id="T_1_2",
                node_type="rule",
                label_zh="Disable跳转至Enable",
                confidence=0.92,
                source_triple="rules_model.ttl#ruleT_1_2",
            )
        ],
        signal_mappings={"sv-kv": ":ReadyEnableDisable"},
        sparql_queries=[],
    )
    prompt = builder.build_diagnosis_prompt(
        symptom="踩刹车无法上电",
        role="owner",
        signals={"sv-pm": "0:Off", "sv-kv": "INVALID"},
        ontology_context="",
        matched_rules=[],
        activated_knowledge=knowledge,
    )
    assert "[T_1_2]" in prompt
    assert "rules_model.ttl#ruleT_1_2" in prompt
    assert "推理要求" in prompt


def test_build_diagnosis_prompt_includes_signal_mappings():
    from llm.prompts import get_prompt_builder
    from models import ActivatedKnowledge

    builder = get_prompt_builder()
    knowledge = ActivatedKnowledge(
        signal_mappings={"sv-kv": ":ReadyEnableDisable", "sv-pm": ":OffMode"},
    )
    prompt = builder.build_diagnosis_prompt(
        symptom="无法上电",
        role="owner",
        signals={"sv-pm": "0:Off", "sv-kv": "INVALID"},
        ontology_context="",
        matched_rules=[],
        activated_knowledge=knowledge,
    )
    assert ":ReadyEnableDisable" in prompt
    assert ":OffMode" in prompt
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py::test_build_diagnosis_prompt_includes_rule_ids -v
```

期望：FAILED — `build_diagnosis_prompt() got unexpected keyword argument 'activated_knowledge'`

- [ ] **Step 3: 修改 prompts.py 的 build_diagnosis_prompt()**

在 `backend/llm/prompts.py` 中修改 `PromptBuilder.build_diagnosis_prompt()` 方法签名：

```python
    def build_diagnosis_prompt(
        self,
        symptom: str,
        role: str,
        signals: Dict[str, str],
        ontology_context: str,
        matched_rules: List[Dict[str, Any]],
        activated_knowledge: Optional[Any] = None,   # ← 新增参数
    ) -> str:
```

在该方法的 `return self.diagnosis_template.substitute(...)` 之前，插入：

```python
        # Build activated knowledge block
        activated_block = ""
        if activated_knowledge and activated_knowledge.activated_rules:
            rule_lines = []
            for node in activated_knowledge.activated_rules[:5]:
                chain = f"[{node.node_id}] {node.label_zh}"
                chain += f"\n  置信度: {int(node.confidence * 100)}%"
                chain += f"\n  来源: {node.source_triple}"
                rule_lines.append(chain)
            activated_block += "\n### 激活的 Ontology 规则\n"
            activated_block += "\n\n".join(rule_lines)

        if activated_knowledge and activated_knowledge.signal_mappings:
            mapping_lines = [
                f'{k}="{signals.get(k, "?")}" → {v}'
                for k, v in activated_knowledge.signal_mappings.items()
            ]
            activated_block += "\n\n### 信号 → 本体映射\n"
            activated_block += "\n".join(mapping_lines)
```

在方法末尾的 `return` 语句后追加（即把 return 改成先拼装再 return）：

```python
        base_prompt = self.diagnosis_template.substitute(
            symptom=symptom,
            role=role,
            signals=signals_text,
            ontology_context=ontology_context + activated_block,
            matched_rules=rules_text
        ) + f"\n\n## 角色输出指南\n{role_guidelines}"

        if activated_knowledge and activated_knowledge.activated_rules:
            base_prompt += """

## 推理要求（必须遵守）

在 reasoning_steps 的每个 body 字段中：
1. 引用具体规则 ID，格式：[T_x_x]（例如 [T_1_2]）
2. 引用本体个体名，格式：:ClassName（例如 :ReadyEnableDisable）
3. 每个推理步骤必须说明依据了哪条 Ontology 规则

示例：
"根据规则 [T_1_2]，当信号 :ReadyEnableDisable 时，状态转移到 :ReadyEnableEnable 失败，确认为上电链路异常。"
"""
        return base_prompt
```

**同时删除原有的 `return self.diagnosis_template.substitute(...) + ...` 那行**（被上面的 `base_prompt` + return 替代）。

- [ ] **Step 4: 修改 LLMDiagnosisAgent 传递 activated_knowledge**

在 `backend/agents/llm_diagnosis_agent.py` 中，找到 `_build_request` 方法并在 `LLMService.diagnose()` 调用链上游，找到 `build_diagnosis_prompt` 被调用的位置。

实际上 prompt 构建在 `backend/llm/service.py` 内部。找到 service.py 中调用 `prompt_builder.build_diagnosis_prompt()` 的位置：

```bash
grep -n "build_diagnosis_prompt" backend/llm/service.py
```

在该调用处补充 `activated_knowledge` 参数，从 `ontology_parser` 或 context 中传入。

由于 `LLMService.diagnose()` 已接收 `ontology_parser`，最简单的方式是在 `LLMDiagnosisAgent.process()` 中，在调用 `self.llm_service.diagnose()` 之前，把 `context.activated_knowledge` 存到 request 的 extra 字段，或直接在 service.py 中从 ontology_parser 查询。

**更直接的方式**：在 `llm_diagnosis_agent.py` 的 `_build_request()` 方法中，把 `activated_knowledge` 附加到 `DiagnosisRequest`（需要先确认该模型是否有 extra 字段）。

先检查：

```bash
grep -n "class DiagnosisRequest\|activated" backend/llm/schemas.py
```

- [ ] **Step 5: 检查并修改 llm/schemas.py 和 service.py**

```bash
grep -n "build_diagnosis_prompt\|activated_knowledge\|class DiagnosisRequest" backend/llm/schemas.py backend/llm/service.py
```

根据实际结构，在 `DiagnosisRequest` 中新增可选字段：

```python
activated_knowledge: Optional[Any] = None
```

在 `service.py` 中找到 `build_diagnosis_prompt(...)` 调用处，加上：

```python
    activated_knowledge=request.activated_knowledge,
```

在 `llm_diagnosis_agent.py` 的 `_build_request()` 中：

```python
    def _build_request(self, context: DiagnosisContext) -> DiagnosisRequest:
        signals = [SignalInfo(key=k, value=v) for k, v in context.signals.items()]
        role = Role.OWNER
        if hasattr(context.role, "value"):
            role = Role(context.role.value)
        return DiagnosisRequest(
            symptom=context.symptom,
            role=role,
            signals=signals,
            activated_knowledge=context.activated_knowledge,  # ← 新增
        )
```

- [ ] **Step 6: 运行 Prompt 测试**

```bash
cd backend
python -m pytest tests/test_ontology_activated.py -v -k "prompt"
```

期望：2 tests PASSED

- [ ] **Step 7: Commit**

```bash
git add backend/llm/prompts.py backend/llm/schemas.py backend/llm/service.py backend/agents/llm_diagnosis_agent.py backend/tests/test_ontology_activated.py
git commit -m "feat: inject structured ontology rules into LLM prompt with mandatory [T_x_x] reference"
```

---

## Task 5: server.py 解析 use_ontology 参数

**Files:**
- Modify: `backend/server.py`

- [ ] **Step 1: 修改 start_diagnosis() 读取 use_ontology**

在 `backend/server.py` 的 `start_diagnosis()` 函数中，在 `demo_mode = message.get("demo", False)` 这行之后添加：

```python
    use_ontology = message.get("use_ontology", True)  # Default: ontology enabled
```

在 `context = DiagnosisContext(...)` 构建之后添加：

```python
    # Store use_ontology preference in context for pipeline agents
    # OntologyFetcher will skip SPARQL queries when use_ontology=False
    context.use_ontology = use_ontology
```

在 `DiagnosisContext` 模型（`backend/models.py`）中新增字段：

```python
    # Pipeline control
    use_ontology: bool = True  # When False, OntologyFetcher skips SPARQL queries
```

在 `backend/agents/ontology_fetcher.py` 的 `process()` 方法开头，在 `if not self._ontology_parser` 检查后添加：

```python
        # Respect use_ontology flag from context
        if not getattr(context, "use_ontology", True):
            logger.info("use_ontology=False, skipping SPARQL queries")
            return context
```

- [ ] **Step 2: 运行全量测试确认无回归**

```bash
cd backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

期望：所有原有测试继续 PASS，新测试 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/server.py backend/models.py backend/agents/ontology_fetcher.py
git commit -m "feat: support use_ontology flag in WebSocket start message"
```

---

## Task 6: 前端可视化改造

**Files:**
- Modify: `cea-diagnosis.html`

- [ ] **Step 1: 新增 onto_activated 事件处理**

在 `cea-diagnosis.html` 的 WebSocket `onmessage` 处理器中（找到 `case "onto_summary":` 附近），新增：

```javascript
case "onto_activated":
    renderOntologyActivated(data);
    break;
```

新增函数（放在 `<script>` 块中）：

```javascript
function renderOntologyActivated(data) {
    const panel = document.getElementById("onto-activated-panel");
    if (!panel) return;

    const nodes = data.nodes || [];
    const mappings = data.signal_mappings || {};

    // Render activated rule nodes
    const rulesHtml = nodes.map(node => {
        const confPct = Math.round(node.confidence * 100);
        const confColor = confPct >= 80 ? "var(--green)" : "var(--yellow)";
        return `<div class="onto-node" id="onto-node-${node.id}" style="
            border:1px solid ${confColor};border-radius:6px;padding:6px 10px;
            margin-bottom:5px;background:rgba(0,0,0,0.2);
            animation:nodeActivate 0.5s ease-out;
        ">
            <div style="display:flex;justify-content:space-between">
                <span style="color:${confColor};font-family:var(--mono);font-weight:600">${node.id}</span>
                <span style="color:${confColor};font-size:9px">${confPct}%</span>
            </div>
            <div style="color:var(--tx2);font-size:10px;margin-top:2px">${node.label_zh}</div>
            <div style="color:var(--tx3);font-size:8px">${node.source}</div>
        </div>`;
    }).join("");

    // Render signal mappings
    const mappingsHtml = Object.entries(mappings).map(([k, v]) =>
        `<div style="font-size:10px;font-family:var(--mono)">
            <span style="color:var(--yellow)">${k}</span>
            <span style="color:var(--tx3)"> → </span>
            <span style="color:var(--accent)">${v}</span>
        </div>`
    ).join("");

    panel.innerHTML = `
        <div style="color:var(--accent);font-size:9px;letter-spacing:1px;margin-bottom:6px">
            SPARQL 激活节点 · ${nodes.length} 条规则
        </div>
        ${rulesHtml}
        ${mappingsHtml ? `<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:6px">${mappingsHtml}</div>` : ""}
    `;
}
```

在页面 `<style>` 块中新增动画：

```css
@keyframes nodeActivate {
    from { opacity: 0; transform: translateX(-8px); }
    to   { opacity: 1; transform: translateX(0); }
}
```

- [ ] **Step 2: 在现有 Ontology 面板区域添加激活面板容器**

找到页面中展示 ontology HTML 的元素（id 为 `onto-content` 或类似），在其上方或下方添加：

```html
<div id="onto-activated-panel" style="padding:8px 12px;min-height:40px;"></div>
```

- [ ] **Step 3: 新增推理步骤 [T_x_x] 标签高亮**

找到处理 `reasoning_step` 消息的渲染函数，在渲染 `step.body` 之前对文本做正则替换：

```javascript
function highlightRuleRefs(text) {
    return text.replace(/\[([T][_\d]+)\]/g, (match, ruleId) =>
        `<span class="rule-tag" onclick="highlightOntologyNode('${ruleId}')"
            style="background:rgba(167,139,250,0.2);border:1px solid #a78bfa;
                   border-radius:3px;padding:1px 5px;color:#a78bfa;
                   font-family:var(--mono);font-size:9px;cursor:pointer"
            title="点击高亮本体规则">${match} ↗</span>`
    );
}

function highlightOntologyNode(ruleId) {
    // Remove previous highlight
    document.querySelectorAll(".onto-node.highlighted").forEach(el => {
        el.classList.remove("highlighted");
        el.style.boxShadow = "";
    });
    // Highlight target node
    const node = document.getElementById(`onto-node-${ruleId}`);
    if (node) {
        node.classList.add("highlighted");
        node.style.boxShadow = "0 0 12px rgba(167,139,250,0.6)";
        node.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
}
```

在渲染 reasoning_step body 时调用：

```javascript
stepBodyElement.innerHTML = highlightRuleRefs(step.body);
```

- [ ] **Step 4: 新增 With/Without Ontology 切换开关**

在页面头部（找到角色切换按钮 `.role-sel` 区域附近），添加：

```html
<div id="ontology-toggle" style="
    display:flex;align-items:center;gap:8px;
    padding:4px 8px;background:var(--bg);border-radius:6px;
    border:1px solid var(--border);margin:8px 14px 0;
">
    <span style="font-size:10px;color:var(--tx3);font-family:var(--mono)">模式：</span>
    <button onclick="setOntologyMode(true)"  id="btn-with-onto"
        style="padding:3px 10px;border-radius:4px;border:none;cursor:pointer;
               font-size:9px;background:var(--accent);color:#000;font-weight:600">
        Ontology + LLM
    </button>
    <button onclick="setOntologyMode(false)" id="btn-without-onto"
        style="padding:3px 10px;border-radius:4px;border:none;cursor:pointer;
               font-size:9px;background:var(--surface2);color:var(--tx3)">
        纯 LLM
    </button>
</div>
```

在 `<script>` 中添加：

```javascript
let _useOntology = true;

function setOntologyMode(enabled) {
    _useOntology = enabled;
    document.getElementById("btn-with-onto").style.background =
        enabled ? "var(--accent)" : "var(--surface2)";
    document.getElementById("btn-with-onto").style.color =
        enabled ? "#000" : "var(--tx3)";
    document.getElementById("btn-without-onto").style.background =
        enabled ? "var(--surface2)" : "var(--orange)";
    document.getElementById("btn-without-onto").style.color =
        enabled ? "var(--tx3)" : "#000";

    if (!enabled) {
        document.getElementById("onto-activated-panel").innerHTML =
            `<div style="color:var(--tx3);font-size:10px;font-family:var(--mono)">
                // 纯 LLM 模式 — Ontology 未激活
            </div>`;
    }
}
```

在发送 WebSocket `start` 消息的地方，加入 `use_ontology` 参数：

```javascript
ws.send(JSON.stringify({
    type: "start",
    symptom: symptom,
    role: currentRole,
    signals: getSignals(),
    use_ontology: _useOntology,   // ← 新增
}));
```

- [ ] **Step 5: 手动验证完整流程**

```bash
cd backend && python main.py
# 在浏览器打开 cea-diagnosis.html
# 输入症状: "踩刹车按启动按钮，车辆无法上电"
# 观察：
# 1. Ontology 激活面板出现规则节点（带 T_x_x 编号）
# 2. LLM 推理步骤中出现 [T_1_2] 等高亮标签
# 3. 点击标签，面板中对应节点发光
# 4. 切换"纯 LLM"模式，再次诊断，对比输出差异
```

- [ ] **Step 6: Commit**

```bash
git add cea-diagnosis.html
git commit -m "feat: add ontology activation panel, rule tag highlighting, and With/Without toggle to frontend"
```

---

## 自审结果

**Spec 覆盖检查：**
- ✅ 高光 A（节点激活动画）→ Task 3 + Task 6 Step 1
- ✅ 高光 B（LLM 引用规则 ID）→ Task 4
- ✅ 高光 C（对比模式）→ Task 5 + Task 6 Step 4
- ✅ 高光 D（全链路透明）→ Task 1 ActivatedKnowledge 在 context 流转
- ✅ 六个文件全覆盖

**类型一致性：**
- `ActivatedNode` / `ActivatedKnowledge` 在 Task 1 定义，Task 2/3/4 均通过 `from models import` 引用，无命名分叉

**Placeholder 扫描：**
- Task 4 Step 4/5 描述了"根据实际结构"的检查步骤，因 `llm/service.py` 未在计划前读取全文。Step 4 给出了明确的 grep 命令让执行者自行定位，不构成 TBD。
