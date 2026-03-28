"""
Prompt Templates for LLM-based Vehicle Diagnosis.

Contains structured prompts for different diagnosis tasks.
"""

from typing import Dict, Any, Optional, List
from string import Template


# =============================================================================
# System Prompts
# =============================================================================

DIAGNOSIS_SYSTEM_PROMPT = """你是一个专业的汽车故障诊断专家系统。你的职责是根据用户的症状描述、车辆信号数据和诊断规则知识库，提供准确、专业的故障诊断结果。

## 核心能力

1. **症状解析**: 从自然语言中提取故障特征、涉及组件、触发条件
2. **规则推理**: 应用知识库中的诊断规则进行推理
3. **假设生成**: 基于证据生成多个可能的故障假设
4. **置信度评估**: 综合多个因素评估诊断可信度
5. **输出适配**: 根据用户角色调整输出风格

## 诊断原则

- 始终基于证据推理，不做无根据的猜测
- 优先考虑安全性相关的故障
- 对于不确定的情况，明确说明并提供验证建议
- 遵循汽车诊断的标准流程和规范

## 输出要求

返回结构化的JSON格式结果，包含推理链、假设、置信度等信息。"""


SYMPTOM_PARSING_PROMPT = """分析以下车辆故障描述，提取关键诊断信息。

## 输入
- 症状描述: $symptom
- 车辆信号: $signals

## 任务
1. 识别故障类型（上电失败/下电异常/认证失败/充电异常/其他）
2. 提取涉及的车辆组件
3. 分析相关信号状态
4. 判断故障严重程度

## 输出格式
返回JSON:
{
  "fault_type": "故障类型",
  "components": ["组件1", "组件2"],
  "relevant_signals": ["信号1", "信号2"],
  "severity": "high/medium/low",
  "keywords": ["关键词"],
  "scenario": "场景分类"
}"""


DIAGNOSIS_PROMPT_TEMPLATE = """## 诊断请求

### 用户症状
$symptom

### 用户角色
$role

### 车辆信号状态
$signals

### Ontology知识库上下文
$ontology_context

### 匹配的诊断规则
$matched_rules

## 诊断任务

请按照以下步骤进行诊断：

1. **症状解析**: 分析用户的症状描述，识别故障特征
2. **信号分析**: 结合车辆信号，评估当前状态
3. **规则推理**: 应用匹配的诊断规则进行推理
4. **假设生成**: 生成可能的故障假设，按可能性排序
5. **置信度计算**: 综合评估诊断的可信程度

## 输出要求

返回以下JSON格式：

```json
{
  "summary": "一句话诊断结论",
  "reasoning_steps": [
    {
      "step_number": 1,
      "title": "步骤标题",
      "body": "详细分析内容",
      "confidence": 0.95
    }
  ],
  "primary_hypothesis": {
    "hypothesis_id": "hypo_001",
    "rank": 1,
    "root_cause": "根本原因",
    "description": "详细描述",
    "confidence": 0.85,
    "affected_components": ["组件1", "组件2"],
    "verification_steps": ["验证步骤1", "验证步骤2"],
    "priority": "high"
  },
  "secondary_hypotheses": [],
  "final_confidence": 0.85,
  "confidence_factors": [
    {
      "label": "症状匹配度",
      "value": 0.9,
      "weight": 0.3,
      "explanation": "说明"
    }
  ],
  "output_for_owner": "给车主的通俗解释",
  "output_for_technician": "给技师的技术分析",
  "output_for_customer_service": "给客服的处理建议",
  "escalation_hint": "升级条件说明"
}
```"""


# =============================================================================
# Role-specific Output Templates
# =============================================================================

ROLE_OUTPUT_GUIDELINES = {
    "owner": """
## 车主输出风格

- 使用通俗易懂的语言，避免专业术语
- 提供清晰的操作步骤
- 给出简单的问题排查建议
- 如需专业帮助，提供明确的联系方式
- 语气友好、耐心、专业

示例格式：
<div class="conc">📱 手机蓝牙钥匙认证失败，无法上电</div>
<p>踩刹车按启动键时，车辆检测到手机但无法完成蓝牙认证...</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>操作步骤一</div>
  <div class="ai"><div class="an">2</div>操作步骤二</div>
</div>
""",
    
    "technician": """
## 技师输出风格

- 使用专业术语和标准化描述
- 提供详细的诊断流程和信号分析
- 包含OBD诊断建议和故障码参考
- 参考技术规范编号（如VEEA-SysR-xxxx）
- 提供可能的维修方案

示例格式：
<div class="conc">【诊断结论】T_1_2 转移失败 — BLE认证失败</div>
<p style="font-family:var(--mono);font-size:11px">
链路: T_1_2 → KeySearchingSt=Initial Search → tKeyValid超时
</p>
<div class="action-list">
  <div class="ai"><div class="an">P1</div>OBD读取 TBOX_ECU: BLE_ErrorCode</div>
  <div class="ai"><div class="an">P2</div>检查信号状态</div>
</div>
""",
    
    "customer_service": """
## 客服输出风格

- 使用友好专业的语言
- 提供明确的指导步骤
- 标注升级条件
- 包含安抚性的表达
- 准备好常见问题解答

示例格式：
<div class="conc">【系统诊断】车辆蓝牙钥匙认证异常</div>
<p style="font-style:italic">"您好，车辆检测到您的手机但认证失败..."</p>
<div class="action-list">
  <div class="ai"><div class="an">1</div>指导步骤</div>
</div>
<p style="color:var(--txd);font-size:11px">
升级条件：操作3次仍失败 → 升级技术支持
</p>
"""
}


# =============================================================================
# Prompt Builder Class
# =============================================================================

class PromptBuilder:
    """
    Builder class for constructing LLM prompts.
    
    Provides methods to build prompts for different diagnosis tasks
    with proper context injection.
    """
    
    def __init__(self):
        self.system_prompt = DIAGNOSIS_SYSTEM_PROMPT
        self.diagnosis_template = Template(DIAGNOSIS_PROMPT_TEMPLATE)
        self.symptom_template = Template(SYMPTOM_PARSING_PROMPT)
    
    def build_diagnosis_prompt(
        self,
        symptom: str,
        role: str,
        signals: Dict[str, str],
        ontology_context: str,
        matched_rules: List[Dict[str, Any]],
        activated_knowledge: Optional[Any] = None,
    ) -> str:
        """
        Build complete diagnosis prompt.

        Args:
            symptom: User's symptom description
            role: User role (owner/technician/customer_service)
            signals: Vehicle signal values
            ontology_context: Ontology knowledge context
            matched_rules: List of matched diagnostic rules
            activated_knowledge: ActivatedKnowledge from OntologyFetcher (optional)

        Returns:
            str: Complete prompt for LLM
        """
        # Format signals
        signals_text = "\n".join([
            f"- {k}: {v}" for k, v in signals.items()
        ]) if signals else "无信号数据"

        # Format rules
        rules_text = "\n".join([
            f"- {r.get('rule_id', 'R')}: {r.get('rule_text', '')} "
            f"(置信度: {r.get('match_confidence', 0.9):.0%})"
            for r in matched_rules
        ]) if matched_rules else "暂无匹配规则"

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

        # Add role guidelines
        role_guidelines = ROLE_OUTPUT_GUIDELINES.get(role, "")

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
    
    def build_symptom_parsing_prompt(
        self,
        symptom: str,
        signals: Dict[str, str]
    ) -> str:
        """
        Build symptom parsing prompt.
        
        Args:
            symptom: User's symptom description
            signals: Vehicle signal values
            
        Returns:
            str: Prompt for symptom parsing
        """
        signals_text = "\n".join([
            f"- {k}: {v}" for k, v in signals.items()
        ]) if signals else "无信号数据"
        
        return self.symptom_template.substitute(
            symptom=symptom,
            signals=signals_text
        )
    
    def build_context_summary(
        self,
        ontology_parser: Any,
        keywords: List[str]
    ) -> str:
        """
        Build ontology context summary for relevant keywords.
        
        Args:
            ontology_parser: Ontology parser instance
            keywords: Keywords to search in ontology
            
        Returns:
            str: Formatted ontology context
        """
        parts = []
        
        for keyword in keywords[:5]:
            results = ontology_parser.search_by_keyword(keyword)
            
            # Add relevant classes
            for cls_name in results.get("classes", [])[:2]:
                cls = ontology_parser.get_class(cls_name)
                if cls:
                    parts.append(f"### {cls.label} ({cls.label_zh})")
                    if cls.comment_zh:
                        parts.append(cls.comment_zh)
                    elif cls.comment:
                        parts.append(cls.comment)
        
        # Add standard power mode info
        power_modes = ontology_parser.get_power_mode_info()
        if power_modes:
            parts.append("### 电源模式")
            for name, info in power_modes.items():
                parts.append(f"- {info.get('label_zh', name)}")
        
        return "\n\n".join(parts)
    
    def get_system_prompt(self, task_type: str = "diagnosis") -> str:
        """
        Get system prompt for specific task.
        
        Args:
            task_type: Type of task (diagnosis/parsing/output)
            
        Returns:
            str: System prompt
        """
        if task_type == "diagnosis":
            return DIAGNOSIS_SYSTEM_PROMPT
        elif task_type == "parsing":
            return "你是一个专业的汽车故障症状分析专家。"
        elif task_type == "output":
            return "你是一个汽车诊断报告生成器，擅长为不同用户角色生成合适的输出文本。"
        return DIAGNOSIS_SYSTEM_PROMPT


# Singleton instance
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Get or create prompt builder instance."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
