"""
Diagnosis Service for CLI.

Encapsulates ontology loading, LLM integration, and diagnosis logic.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from ontology.parser import OntologyParser
from diagnosis_knowledge import SIGNAL_RECOMMENDATIONS
from scenario_detector import ScenarioDetector


@dataclass
class DiagnosisResult:
    """Diagnosis result data structure."""

    symptom: str
    summary: str = ""
    analysis: List[str] = field(default_factory=list)
    possible_causes: List[Dict[str, Any]] = field(default_factory=list)
    troubleshooting_steps: List[str] = field(default_factory=list)
    confidence: float = 0.0
    confidence_factors: Dict[str, Any] = field(default_factory=dict)  # 置信度因素
    model_used: str = ""
    processing_time_ms: int = 0
    signal_recommendations: List[Dict[str, Any]] = field(
        default_factory=list
    )  # 信号读取建议


class DiagnosisService:
    """
    Main diagnosis service for CLI.

    Handles ontology loading, LLM calls, and diagnosis logic.
    """

    def __init__(
        self,
        ontology_path: str,
        config_path: Optional[str] = None,
        model: Optional[str] = None,
        load_ontology: bool = True,
    ):
        """
        Initialize diagnosis service.

        Args:
            ontology_path: Path to TTL ontology file OR folder containing TTL files
            config_path: Path to LLM config YAML (optional)
            model: Model name to use (optional, overrides config)
            load_ontology: Whether to load ontology file (default: True). Set to False to skip loading.
        """
        self.ontology_path = ontology_path
        self.config_path = config_path or str(Path(__file__).parent / "llm_config.yaml")

        # Load ontology (conditionally)
        self.ontology_parser: Optional[OntologyParser] = None
        if load_ontology:
            self._load_ontology()
        else:
            logger.info("Skipping ontology loading (load_ontology=False)")

        # Load LLM config
        self.llm_config: Dict[str, Any] = {}
        self._load_llm_config()

        # Override model if specified
        if model:
            self.llm_config["model"] = model

        # LLM client (lazy loaded)
        self._llm_client = None

    def _load_ontology(self) -> bool:
        """Load and parse the ontology file(s)."""
        try:
            source_path = Path(self.ontology_path)

            if not source_path.exists():
                logger.error(f"Ontology source not found: {self.ontology_path}")
                return False

            self.ontology_parser = OntologyParser(self.ontology_path)
            if self.ontology_parser.load():
                files_info = (
                    f"{len(self.ontology_parser.loaded_files)} file(s)"
                    if self.ontology_parser.loaded_files
                    else "0 files"
                )
                logger.info(
                    f"Ontology loaded: {files_info}, {len(self.ontology_parser.classes)} classes, "
                    f"{len(self.ontology_parser.object_properties)} properties"
                )
                return True
            else:
                logger.error("Failed to parse ontology")
                return False
        except Exception as e:
            logger.error(f"Error loading ontology: {e}")
            return False

    def _load_llm_config(self) -> None:
        """Load LLM configuration from YAML file."""
        try:
            import yaml

            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.llm_config = yaml.safe_load(f) or {}
                logger.info(f"LLM config loaded from: {self.config_path}")
            else:
                logger.warning(
                    f"LLM config not found: {self.config_path}, using defaults"
                )
                self.llm_config = {}
        except ImportError:
            logger.warning("PyYAML not installed, using environment variables")
            self.llm_config = {}
        except Exception as e:
            logger.warning(f"Failed to load LLM config: {e}")
            self.llm_config = {}

        # Set defaults
        self.llm_config.setdefault(
            "endpoint", "https://llm-gateway.dev.cn-vwa.volkswagen-cea.com"
        )
        self.llm_config.setdefault("model", "GLM-5-FP8")
        self.llm_config.setdefault("temperature", 0.7)
        self.llm_config.setdefault("max_tokens", 4096)
        self.llm_config.setdefault("timeout", 120)

        # Override provider from environment variable if set
        if os.environ.get("LLM_PROVIDER"):
            self.llm_config["provider"] = os.environ.get("LLM_PROVIDER")

        # Get API key from environment or config based on provider
        provider = self.llm_config.get("provider", "litellm")
        if provider == "openrouter":
            # OpenRouter API key
            openrouter_key = os.environ.get(
                "LLM_OPENROUTER_API_KEY"
            ) or self.llm_config.get("openrouter_api_key", "")
            self.llm_config["openrouter_api_key"] = openrouter_key
            # Set both environment variables for litellm
            if openrouter_key:
                os.environ["OPENROUTER_API_KEY"] = openrouter_key
                os.environ["OPENAI_API_KEY"] = openrouter_key  # LiteLLM needs this
        else:
            # Custom endpoint API key
            api_key = os.environ.get(
                "LLM_API_KEY", self.llm_config.get("custom_api_key", "")
            )
            self.llm_config["api_key"] = api_key

    def _get_llm_client(self):
        """Get or create LLM client based on provider configuration."""
        if self._llm_client is None:
            provider = self.llm_config.get("provider", "litellm")

            try:
                import litellm
                import os

                # 禁用远程model cost map获取，只使用本地
                os.environ["LITELLM_DROP_PARAMS"] = "True"
                os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

                litellm.drop_params = True
                setattr(
                    litellm, "set_verbose", self.llm_config.get("log_requests", False)
                )

                if provider == "openrouter":
                    # 使用 OpenRouter
                    api_key = os.environ.get("LLM_OPENROUTER_API_KEY", "")
                    if not api_key:
                        # 尝试从旧的环境变量获取
                        api_key = os.environ.get("LLM_API_KEY", "")
                    os.environ["OPENROUTER_API_KEY"] = api_key
                    logger.info(f"LiteLLM client initialized with OpenRouter")
                else:
                    # 使用自定义端点 (内部 LLM 网关)
                    logger.info(f"LiteLLM client initialized with custom endpoint")

                self._llm_client = litellm
            except ImportError:
                raise ImportError("litellm not installed. Run: pip install litellm")
        return self._llm_client

    def _build_ontology_context(self, symptom: str) -> str:
        """
        Build ontology context for LLM prompt.

        Extracts relevant classes and properties based on symptom keywords.
        """
        if not self.ontology_parser:
            return ""

        parts = []

        # Power modes
        power_modes = self.ontology_parser.get_power_mode_info()
        if power_modes:
            parts.append("## 电源模式 (Power Modes)")
            for name, info in power_modes.items():
                parts.append(
                    f"- {info.get('label_zh', name)}: {info.get('comment_zh', '')[:100]}"
                )

        # Key types
        key_types = self.ontology_parser.get_key_types()
        if key_types:
            parts.append("\n## 钥匙类型 (Key Types)")
            for name, info in key_types.items():
                parts.append(
                    f"- {info.get('label_zh', name)}: {info.get('comment_zh', '')[:100]}"
                )

        # Search for relevant classes based on keywords
        keywords = [
            "电源",
            "上电",
            "下电",
            "启动",
            "钥匙",
            "认证",
            "BLE",
            "刹车",
            "车门",
            "Ready",
        ]
        for keyword in keywords:
            if keyword in symptom:
                results = self.ontology_parser.search_by_keyword(keyword)
                if results["classes"]:
                    parts.append(f"\n## 相关组件: {keyword}")
                    for cls_name in results["classes"][:3]:
                        cls = self.ontology_parser.get_class(cls_name)
                        if cls:
                            parts.append(
                                f"- {cls.label_zh or cls.label}: {cls.comment_zh or cls.comment}"
                            )

        return "\n".join(parts)

    def _build_diagnosis_prompt(self, symptom: str) -> List[Dict[str, str]]:
        """
        Build the diagnosis prompt for LLM.

        Args:
            symptom: User's symptom description

        Returns:
            List of message dicts for LLM API
        """
        ontology_context = self._build_ontology_context(symptom)

        system_prompt = """你是一个专业的汽车故障诊断专家，专门负责车辆电源模式管理系统的故障诊断。

你的职责是：
1. 分析用户描述的故障症状
2. 基于车辆本体知识理解故障场景
3. 提供可能的故障原因分析
4. 给出详细的排查步骤

诊断输出格式要求：
- 故障摘要：一句话概括故障
- 故障分析：逐步分析推理过程
- 可能原因：列出可能的原因，每项包含置信度（高/中/低）
- 排查步骤：具体的检查步骤，按优先级排序
- 诊断置信度：整体诊断的置信度百分比

请用中文回答，语言简洁专业。"""

        user_prompt = f"""## 故障描述
{symptom}

## 车辆电源模式本体知识
{ontology_context}

请基于以上信息进行故障诊断，给出诊断结果和排查步骤。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    async def diagnose_async(self, symptom: str) -> DiagnosisResult:
        """
        Perform diagnosis asynchronously.

        Args:
            symptom: User's symptom description

        Returns:
            DiagnosisResult with diagnosis and troubleshooting steps
        """
        start_time = time.time()

        result = DiagnosisResult(symptom=symptom)

        try:
            client = self._get_llm_client()
            messages = self._build_diagnosis_prompt(symptom)

            provider = self.llm_config.get("provider", "litellm")

            # Build model name based on provider
            if provider == "openrouter":
                # OpenRouter: use model with openrouter/ prefix (e.g., openrouter/openai/gpt-3.5-turbo)
                model = self.llm_config.get(
                    "openrouter_model",
                    self.llm_config.get("model", "openai/gpt-3.5-turbo"),
                )
                # Add openrouter/ prefix if not present
                if "/" in model and not model.startswith("openrouter/"):
                    model_name = f"openrouter/{model}"
                elif not model.startswith("openrouter/"):
                    model_name = f"openrouter/openai/{model}"
                else:
                    model_name = model

                # Set OpenRouter-specific environment variables for LiteLLM
                import os

                os.environ["OPENROUTER_API_KEY"] = os.environ.get(
                    "LLM_OPENROUTER_API_KEY", ""
                )
                os.environ["OPENROUTER_BASE_URL"] = "https://openrouter.ai/api/v1"
                api_key = "os.environ/OPENROUTER_API_KEY"  # LiteLLM reads from env
                api_base = None
                logger.info(f"Calling OpenRouter: model={model_name}")
            else:
                # Custom endpoint (internal LLM gateway)
                model = self.llm_config.get("model", "GLM-5-FP8")
                model_name = f"openai/{model}" if "/" not in model else model
                api_base = self.llm_config.get("custom_endpoint", "")
                import os

                api_key = os.environ.get(
                    "LLM_API_KEY", self.llm_config.get("custom_api_key", "")
                )
                logger.info(
                    f"Calling custom endpoint: model={model_name}, base={api_base}"
                )

            # Call LLM
            completion_kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": self.llm_config.get("temperature", 0.7),
                "max_tokens": self.llm_config.get("max_tokens", 4096),
            }

            # Add base_url only for custom endpoint, not for OpenRouter
            if provider == "openrouter":
                completion_kwargs["base_url"] = "https://openrouter.ai/api/v1"
            elif api_base:
                completion_kwargs["api_base"] = api_base

            response = await client.acompletion(**completion_kwargs)

            # Extract content from response (ModelResponse for non-streaming)
            # response.choices is available on ModelResponse, not CustomStreamWrapper
            choices = getattr(response, "choices", None)  # type: ignore
            if choices:
                content = choices[0].message.content  # type: ignore
            else:
                content = None

            result.model_used = model

            # Parse the response
            if content:
                self._parse_llm_response(content, result)
            else:
                result.summary = "LLM返回内容为空"

            # Generate signal recommendations
            self._generate_signal_recommendations(symptom, result)

        except Exception as e:
            logger.error(f"LLM diagnosis failed: {e}")
            result.summary = f"诊断失败: {str(e)}"

        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result

    def diagnose(self, symptom: str) -> DiagnosisResult:
        """
        Perform diagnosis synchronously.

        Args:
            symptom: User's symptom description

        Returns:
            DiagnosisResult with diagnosis and troubleshooting steps
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        try:
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.diagnose_async(symptom))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.diagnose_async(symptom))

    def _parse_llm_response(self, content: str, result: DiagnosisResult) -> None:
        """
        Parse LLM response into structured result.

        Args:
            content: Raw LLM response text
            result: DiagnosisResult to populate
        """
        import re

        lines = content.strip().split("\n")
        current_section = ""
        summary_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 去除Markdown粗体格式 **text**
            line_clean = line.replace("**", "").strip()

            # Detect section headers - must check if this is a header line (not content)
            # Headers typically are standalone lines like "## 可能原因" or "**可能原因**"
            is_header_line = (
                line_clean
                in ["故障摘要", "可能原因", "排查步骤", "故障分析", "诊断置信度"]
                or line_clean.startswith("故障摘要")
                or line_clean.startswith("可能原因")
                or line_clean.startswith("排查步骤")
                or line_clean.startswith("故障分析")
                or line_clean.startswith("诊断置信度")
                or "## 故障摘要" in line
                or "## 可能原因" in line
                or "## 排查步骤" in line
                or "## 故障分析" in line
            )

            if is_header_line:
                if "故障摘要" in line_clean or "摘要" in line_clean:
                    current_section = "summary"
                    continue
                elif "故障分析" in line_clean or line_clean == "分析":
                    current_section = "analysis"
                    continue
                elif "可能原因" in line_clean:
                    current_section = "causes"
                    continue
                elif "排查步骤" in line_clean:
                    current_section = "steps"
                    continue
                elif "诊断置信度" in line_clean or "整体置信度" in line_clean:
                    current_section = "confidence"
                    continue

            # Parse content based on section
            if current_section == "summary":
                summary_parts.append(line_clean)

            elif current_section == "analysis":
                # 匹配分析项
                if (
                    line_clean.startswith(
                        ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")
                    )
                    or line.startswith("*")
                    or (line_clean and line_clean[0].isdigit() and len(line_clean) > 10)
                ):
                    result.analysis.append(line_clean.lstrip("0123456789. "))

            elif current_section == "causes":
                # 匹配可能原因：1. 标题（置信度：高）
                # LLM返回格式可能是 "1. 标题" 或 "1.标题"（有空格）
                line_stripped = line.strip()
                line_clean = line_stripped.replace("**", "")

                # 检查是否以数字.开头（可能有空格）
                import re

                match = re.match(r"^(\d+)\.?\s*(.+)$", line_clean)

                if match and current_section == "causes":
                    cause_text = match.group(2).strip()

                    # 提取置信度
                    confidence = "中"
                    if "高" in cause_text or "高" in line_clean:
                        confidence = "高"
                    elif "低" in cause_text or "低" in line_clean:
                        confidence = "低"

                    if cause_text and len(cause_text) > 2:
                        result.possible_causes.append(
                            {"description": cause_text, "confidence": confidence}
                        )
                elif line.startswith("    *") and "原因" in line_clean:
                    # 补充原因说明
                    cause_text = line_clean.lstrip("* ").strip()
                    if result.possible_causes:
                        last_cause = result.possible_causes[-1]
                        last_cause["description"] = (
                            last_cause["description"] + " " + cause_text
                        )

            elif current_section == "steps":
                # 匹配排查步骤：1.  **标题** 或 * 操作：
                if line_clean.startswith(
                    ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.")
                ):
                    step_text = line_clean.lstrip("0123456789. ").strip()
                    if step_text and len(step_text) > 2:
                        result.troubleshooting_steps.append(step_text)
                elif "* 操作：" in line_clean or "* 分析：" in line_clean:
                    # 补充步骤说明
                    step_text = line_clean.lstrip("* ").strip()
                    if result.troubleshooting_steps:
                        last_step = result.troubleshooting_steps[-1]
                        result.troubleshooting_steps[-1] = last_step + " " + step_text

            elif current_section == "confidence":
                match = re.search(r"(\d+)%", line_clean)
                if match:
                    result.confidence = int(match.group(1)) / 100.0

        # Set summary from collected parts
        if summary_parts:
            result.summary = " ".join(summary_parts)
        elif not result.summary:
            sentences = content.split("。")
            if sentences:
                result.summary = sentences[0].strip()

        # Default confidence if not found
        if result.confidence == 0:
            result.confidence = 0.75

        # 计算置信度因素
        result.confidence_factors = self._calculate_confidence_factors(result, content)

        # 基于因素重新计算置信度
        calculated_confidence = self._compute_confidence(result.confidence_factors)

        # 取LLM置信度和计算置信度的加权平均
        if result.confidence > 0:
            # LLM置信度权重60%，计算置信度权重40%
            result.confidence = result.confidence * 0.6 + calculated_confidence * 0.4
        else:
            result.confidence = calculated_confidence

    def _calculate_confidence_factors(
        self, result: "DiagnosisResult", content: str
    ) -> Dict[str, Any]:
        """
        计算置信度相关因素

        Returns:
            包含各项评分因子的字典
        """
        factors = {
            "cause_count": len(result.possible_causes),
            "cause_confidence_score": 0.0,
            "step_count": len(result.troubleshooting_steps),
            "analysis_length": len(result.analysis),
            "has_summary": len(result.summary) > 10,
            "keyword_match_score": 0.0,
        }

        # 1. 可能原因置信度评分
        if result.possible_causes:
            cause_scores = []
            for cause in result.possible_causes:
                conf = cause.get("confidence", "中")
                if conf == "高":
                    cause_scores.append(0.9)
                elif conf == "中":
                    cause_scores.append(0.6)
                elif conf == "低":
                    cause_scores.append(0.3)
                else:
                    cause_scores.append(0.5)
            factors["cause_confidence_score"] = sum(cause_scores) / len(cause_scores)

        # 2. 关键词匹配度（基于本体知识）
        symptom_keywords = [
            "上电",
            "下电",
            "启动",
            "钥匙",
            "刹车",
            "车门",
            "电源",
            "认证",
            "BLE",
            "NFC",
            "电压",
            "故障",
            "无法",
            "无响应",
        ]
        matched = sum(1 for kw in symptom_keywords if kw in result.symptom)
        factors["keyword_match_score"] = min(matched / 5, 1.0)  # 最多5个关键词匹配

        return factors

    def _compute_confidence(self, factors: Dict[str, Any]) -> float:
        """
        基于因素计算置信度

        评分标准:
        - 可能原因数量: 2-4个最佳 (0.9), 1个 (0.7), >4个 (0.5)
        - 原因置信度: 取平均
        - 排查步骤数量: >=6个 (0.9), 3-5个 (0.7), <3个 (0.5)
        - 分析长度: >3行 (0.8), 1-3行 (0.6), 0行 (0.4)
        - 有摘要: +0.1
        - 关键词匹配: 匹配越多分数越高
        """
        score = 0.5  # 基础分

        # 原因数量评分
        cause_count = factors.get("cause_count", 0)
        if 2 <= cause_count <= 4:
            score += 0.15
        elif cause_count == 1:
            score += 0.05
        elif cause_count > 4:
            score += 0.0  # 原因太多，可信度降低

        # 原因置信度评分
        cause_conf = factors.get("cause_confidence_score", 0.5)
        score += cause_conf * 0.2

        # 步骤数量评分
        step_count = factors.get("step_count", 0)
        if step_count >= 6:
            score += 0.15
        elif 3 <= step_count < 6:
            score += 0.1
        elif step_count > 0:
            score += 0.05

        # 分析长度评分
        analysis_len = factors.get("analysis_length", 0)
        if analysis_len >= 3:
            score += 0.1
        elif analysis_len > 0:
            score += 0.05

        # 摘要加分
        if factors.get("has_summary", False):
            score += 0.05

        # 关键词匹配加分
        kw_score = factors.get("keyword_match_score", 0)
        score += kw_score * 0.1

        return min(max(score, 0.1), 0.99)  # 限制在10%-99%之间

    def _generate_signal_recommendations(
        self, symptom: str, result: DiagnosisResult
    ) -> None:
        """
        Generate signal reading recommendations based on the detected scenario.

        Args:
            symptom: The symptom text to analyze
            result: DiagnosisResult to populate with signal recommendations
        """
        try:
            # Detect scenario from symptom
            detector = ScenarioDetector()
            scenario = detector.detect(symptom)

            logger.info(f"Detected scenario for signal recommendations: {scenario}")

            # Get recommendations for the scenario
            recommendations = SIGNAL_RECOMMENDATIONS.get(scenario, [])

            if recommendations:
                # Convert to list of dicts for the result
                result.signal_recommendations = [
                    {
                        "name": rec["name"],
                        "description_zh": rec["description_zh"],
                        "description_en": rec["description_en"],
                        "reason": rec["reason"],
                        "priority": rec["priority"],
                        "read_method": rec["read_method"],
                    }
                    for rec in recommendations
                ]
                logger.info(
                    f"Generated {len(result.signal_recommendations)} signal recommendations"
                )
            else:
                logger.warning(
                    f"No signal recommendations found for scenario: {scenario}"
                )

        except Exception as e:
            logger.error(f"Failed to generate signal recommendations: {e}")
            result.signal_recommendations = []

    def get_ontology_stats(self) -> str:
        """Get ontology loading statistics."""
        if self.ontology_parser:
            return f"{len(self.ontology_parser.classes)} classes, {len(self.ontology_parser.object_properties)} properties"
        return "not loaded"

    def get_llm_info(self) -> Dict[str, str]:
        """Get LLM configuration info based on provider."""
        provider = self.llm_config.get("provider", "litellm")

        if provider == "openrouter":
            # OpenRouter configuration
            endpoint = "https://openrouter.ai/api/v1"
            model = self.llm_config.get(
                "openrouter_model", self.llm_config.get("model", "openai/gpt-3.5-turbo")
            )
            # Add openrouter/ prefix for display if not present
            if not model.startswith("openrouter/"):
                model = f"openrouter/{model}"
        else:
            # Custom endpoint (internal LLM gateway)
            endpoint = self.llm_config.get(
                "custom_endpoint", self.llm_config.get("endpoint", "N/A")
            )
            model = self.llm_config.get("model", "N/A")

        return {
            "endpoint": endpoint,
            "model": model,
            "provider": provider,
        }

    def set_model(self, model: str) -> bool:
        """
        Set the model to use for diagnosis.

        Args:
            model: Model name (e.g., "GLM-5-FP8", "MiniMax", "MiniMax-M2.5")

        Returns:
            True if model is valid, False otherwise
        """
        available = self.get_available_models()
        model_names = [m["name"] for m in available]

        if model in model_names:
            self.llm_config["model"] = model
            self._llm_client = None  # Reset client to use new model
            logger.info(f"Model set to: {model}")
            return True
        else:
            logger.warning(f"Unknown model: {model}. Available: {model_names}")
            return False

    def get_available_models(self) -> List[Dict[str, str]]:
        """Get list of available models."""
        # Default models if not in config
        default_models = [
            {"name": "GLM-5-FP8", "description": "GLM-5 FP8 模型 - 平衡性能与速度"},
            {"name": "MiniMax", "description": "MiniMax 模型 - 快速响应"},
            {"name": "MiniMax-M2.5", "description": "MiniMax M2.5 - 增强版"},
            {"name": "MiniMax-M2.1", "description": "MiniMax M2.1 - 稳定版"},
        ]

        return self.llm_config.get("available_models", default_models)

    def load_ontology(self) -> bool:
        """Public method to load ontology."""
        return self._load_ontology()
