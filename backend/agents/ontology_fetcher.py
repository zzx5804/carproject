"""
OntologyFetcher Agent - Fetches relevant ontology information using SPARQL queries.
"""

from typing import Dict, Any
from loguru import logger

from agents.base import BaseAgent
from models import DiagnosisContext, AgentID, AgentState


class OntologyFetcherAgent(BaseAgent):
    """
    Ontology Fetcher Agent.

    Responsibilities:
    - Query matching rules via SPARQL based on symptoms/keywords
    - Map signals to ontology individuals
    - Populate context.activated_knowledge
    - Emit onto_activated WebSocket event to frontend
    """

    def __init__(self, agent_id: AgentID = AgentID.ONT):
        super().__init__(agent_id)
        self._ontology_parser = None
        self._send = None  # Allows tests to inject a mock sender directly

    def set_ontology_parser(self, parser) -> None:
        """Set the ontology parser for SPARQL queries."""
        self._ontology_parser = parser

    async def send(self, message: Dict[str, Any]):
        """Send a message; delegates to _send mock if injected, else base class."""
        if self._send is not None:
            await self._send(message)
        else:
            await super().send(message)

    async def process(self, context: DiagnosisContext) -> DiagnosisContext:
        """Fetch ontology information based on context using SPARQL queries."""
        logger.info("OntologyFetcher processing...")

        await self.update_status(AgentState.RUNNING, 0)

        if not self._ontology_parser:
            logger.warning("No ontology parser set, skipping ontology fetch")
            return context

        # Respect use_ontology flag from context
        if not getattr(context, "use_ontology", True):
            logger.info("use_ontology=False, skipping SPARQL queries")
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

    def _generate_ontology_summary(
        self,
        context: DiagnosisContext,
        signal_mappings: Dict[str, Any],
        activated_rules: list,
    ) -> str:
        """Generate HTML summary from real SPARQL query results."""
        sv_pm = context.signals.get("sv-pm", "0:Off")
        sv_kv = context.signals.get("sv-kv", "INVALID")

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
