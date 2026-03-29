"""
LLM Service Layer.

Provides abstraction for local LLM API calls with retry logic,
streaming support, and fallback mechanisms.
Only supports local model deployment (custom REST API endpoint).
"""

import os
import json
import time
import asyncio
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator, Union, Callable
from abc import ABC, abstractmethod
from loguru import logger
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from llm.config import LLMConfig, get_llm_config, LLMProviderEnum
from llm.schemas import (
    DiagnosisRequest,
    DiagnosisResponse,
    DiagnosticHypothesis,
    ReasoningStep,
    ConfidenceFactor,
)


# =============================================================================
# Exceptions
# =============================================================================


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMConnectionError(LLMError):
    """Failed to connect to LLM service."""

    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    pass


class LLMResponseError(LLMError):
    """Invalid response from LLM."""

    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""

    pass


# =============================================================================
# LLM Client Protocol
# =============================================================================


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send completion request and return response text."""
        pass

    @abstractmethod
    async def complete_with_structure(
        self, messages: List[Dict[str, str]], response_model: type, **kwargs
    ) -> Any:
        """Send completion request and parse structured response."""
        pass

    @abstractmethod
    def stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion response."""
        pass

    async def close(self) -> None:
        """Close client resources. Override in subclasses if needed."""
        pass


# =============================================================================
# Local LLM Client (REST API)
# =============================================================================


class LocalLLMClient(LLMClient):
    """
    Client for local LLM REST API.

    Supports any REST API that follows OpenAI-compatible format.
    or custom request/response format.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers={
                    "Content-Type": "application/json",
                    **self.config.get_auth_headers(),
                },
            )
        return self._client

    def _build_request_body(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> Dict[str, Any]:
        """Build request body for the API."""
        return {
            "model": kwargs.get("model", self.config.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": kwargs.get("stream", False),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (LLMConnectionError, LLMTimeoutError, LLMRateLimitError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),  # Use logging level int
        reraise=True,
    )
    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send completion request."""
        client = await self._get_client()
        body = self._build_request_body(messages, **kwargs)

        if self.config.log_requests:
            logger.debug(f"LLM Request: {json.dumps(body, ensure_ascii=False)[:500]}")

        try:
            response = await client.post(self.config.endpoint, json=body)

            if response.status_code == 429:
                raise LLMRateLimitError("Rate limit exceeded")

            if response.status_code >= 500:
                raise LLMConnectionError(f"Server error: {response.status_code}")

            if response.status_code >= 400:
                raise LLMResponseError(
                    f"Request error: {response.status_code} - {response.text}"
                )

            data = response.json()

            # Parse OpenAI-compatible response
            if "choices" in data:
                content = data["choices"][0]["message"]["content"]
            elif "response" in data:
                content = data["response"]
            elif "text" in data:
                content = data["text"]
            else:
                raise LLMResponseError(f"Unknown response format: {list(data.keys())}")

            if self.config.log_requests:
                logger.debug(f"LLM Response: {content[:500]}")

            return content

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Request timed out after {self.config.timeout}s")
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect: {e}")
        except json.JSONDecodeError as e:
            raise LLMResponseError(f"Invalid JSON response: {e}")

    async def complete_with_structure(
        self, messages: List[Dict[str, str]], response_model: type, **kwargs
    ) -> Any:
        """Send completion request and parse as Pydantic model."""
        # Add JSON format instruction
        schema = response_model.model_json_schema()
        format_instruction = f"""
请以JSON格式返回结果，严格遵循以下schema：
{json.dumps(schema, ensure_ascii=False, indent=2)}

不要包含任何markdown代码块标记，直接返回JSON。
"""

        # Add to last user message or create new one
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += f"\n\n{format_instruction}"
        else:
            messages.append({"role": "user", "content": format_instruction})

        response_text = await self.complete(messages, **kwargs)

        # Clean up response
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        try:
            data = json.loads(response_text)
            return response_model.model_validate(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\nResponse: {response_text[:500]}")
            raise LLMResponseError(f"Failed to parse structured response: {e}")

    async def stream(  # type: ignore[override]
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion response."""
        client = await self._get_client()
        body = self._build_request_body(messages, stream=True, **kwargs)

        try:
            async with client.stream(
                "POST", self.config.endpoint, json=body
            ) as response:
                if response.status_code >= 400:
                    error_text = await response.aread()
                    raise LLMResponseError(f"Stream error: {response.status_code}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"Stream timed out")

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# OpenRouter LLM Client
# =============================================================================

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient(LLMClient):
    """
    Client for OpenRouter API.

    OpenRouter provides OpenAI-compatible API with access to multiple models.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._api_key = config.openrouter_api_key
        self._model = config.openrouter_model

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": "https://github.com/vehicle-diagnosis",
                "X-Title": "Vehicle Power Diagnosis System",
            }
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout), headers=headers
            )
        return self._client

    def _build_request_body(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> Dict[str, Any]:
        """Build request body for OpenRouter API."""
        return {
            "model": kwargs.get("model", self._model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": kwargs.get("stream", False),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (LLMConnectionError, LLMTimeoutError, LLMRateLimitError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send completion request to OpenRouter."""
        client = await self._get_client()
        body = self._build_request_body(messages, **kwargs)

        if self.config.log_requests:
            logger.debug(
                f"OpenRouter request: model={body['model']}, messages={len(messages)}"
            )

        try:
            response = await client.post(OPENROUTER_API_URL, json=body)
            response.raise_for_status()

            data = response.json()

            # OpenAI-compatible response format
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0].get("message", {}).get("content", "")
                if self.config.log_requests:
                    logger.debug(f"OpenRouter response: {len(content)} chars")
                return content
            else:
                raise LLMResponseError(f"Invalid OpenRouter response: {data}")

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"OpenRouter request timed out")
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to OpenRouter: {e}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise LLMRateLimitError("OpenRouter rate limit exceeded")
            elif e.response.status_code == 401:
                raise LLMConnectionError(
                    "OpenRouter authentication failed - check API key"
                )
            else:
                raise LLMResponseError(
                    f"OpenRouter HTTP error: {e.response.status_code}"
                )
        except httpx.HTTPError as e:
            raise LLMConnectionError(f"OpenRouter request failed: {e}")

    async def complete_with_structure(
        self, messages: List[Dict[str, str]], response_model: type, **kwargs
    ) -> Any:
        """Send completion request and parse structured response."""
        response = await self.complete(messages, **kwargs)

        # Try to parse JSON from response
        response = response.strip()
        if response.startswith("```"):
            parts = response.split("```")
            if len(parts) >= 2:
                response = parts[1]
                if response.startswith("json"):
                    response = response[4:]

        try:
            data = json.loads(response)
            return response_model(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse structured response: {e}")
            raise LLMResponseError(f"Failed to parse structured response: {e}")

    async def stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream completion response from OpenRouter."""
        client = await self._get_client()
        body = self._build_request_body(messages, stream=True, **kwargs)

        try:
            async with client.stream("POST", OPENROUTER_API_URL, json=body) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException:
            raise LLMTimeoutError(f"OpenRouter stream timed out")
        except httpx.HTTPError as e:
            raise LLMConnectionError(f"OpenRouter stream failed: {e}")

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# LLM Tools for Diagnosis
# =============================================================================


class LLMTools:
    """
    High-level LLM tools for vehicle diagnosis.

    Provides domain-specific methods that combine prompts,
    ontology context, and structured output parsing.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_llm_config()
        self._client: Optional[LLMClient] = None

    @property
    def client(self) -> LLMClient:
        """Get the LLM client based on provider configuration."""
        if self._client is None:
            if self.config.provider == LLMProviderEnum.OPENROUTER:
                self._client = OpenRouterClient(self.config)
                logger.info(f"Using OpenRouter client: {self.config.openrouter_model}")
            else:
                self._client = LocalLLMClient(self.config)
                logger.info(f"Using Local LLM client: {self.config.endpoint}")
        return self._client

    async def parse_symptom(
        self,
        symptom: str,
        signals: Dict[str, str],
        ontology_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parse symptom using LLM and extract structured information.

        Args:
            symptom: User's symptom description
            signals: Vehicle signal values
            ontology_context: Relevant ontology information

        Returns:
            Dict with parsed entities, intent, and relevant signals
        """
        system_prompt = """你是一个专业的汽车诊断专家。你的任务是解析用户的故障描述，提取关键信息。

请分析用户的症状描述，识别：
1. 故障类型（上电失败、下电异常、认证失败等）
2. 涉及的车辆组件（BLE钥匙、刹车踏板、电源模式等）
3. 相关的车辆信号状态
4. 可能的场景分类

返回JSON格式的结果。"""

        user_message = f"""用户症状：{symptom}

车辆信号：
{json.dumps(signals, ensure_ascii=False, indent=2)}
{f"\n\nOntology上下文：\n{ontology_context}" if ontology_context else ""}

请解析并返回以下JSON格式：
{{
  "fault_type": "故障类型",
  "components": ["涉及的组件列表"],
  "relevant_signals": ["相关信号列表"],
  "scenario": "场景分类",
  "keywords": ["关键词列表"],
  "severity": "严重程度(low/medium/high)"
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.client.complete(messages)

            # Parse JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            return json.loads(response)

        except (LLMError, json.JSONDecodeError, httpx.HTTPError) as e:
            logger.warning(f"Symptom parsing failed ({type(e).__name__}): {e}")
            # Return basic parsed info as fallback
            return {
                "fault_type": "unknown",
                "components": [],
                "relevant_signals": list(signals.keys()),
                "scenario": "unknown",
                "keywords": [],
                "severity": "medium",
            }

    async def match_diagnostic_rules(
        self,
        parsed_symptom: Dict[str, Any],
        ontology_rules: List[Dict[str, Any]],
        signals: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Match symptoms to diagnostic rules from ontology.

        Args:
            parsed_symptom: Parsed symptom information
            ontology_rules: Rules from ontology (SWRL rules)
            signals: Vehicle signal values

        Returns:
            List of matched rules with confidence
        """
        system_prompt = """你是一个汽车诊断规则引擎。根据用户的症状和信号状态，匹配最相关的诊断规则。

对于每个匹配的规则，评估其适用性和置信度。"""

        rules_text = "\n".join(
            [
                f"- {rule.get('id', 'R')}: {rule.get('text', rule.get('conditions', ''))}"
                for rule in ontology_rules
            ]
        )

        user_message = f"""症状分析：{json.dumps(parsed_symptom, ensure_ascii=False)}

可用规则：
{rules_text}

当前信号：
{json.dumps(signals, ensure_ascii=False, indent=2)}

请匹配相关规则并返回JSON数组：
[
  {{
    "rule_id": "规则ID",
    "rule_text": "规则文本",
    "match_confidence": 0.95,
    "match_reason": "匹配原因"
  }}
]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.client.complete(messages)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            return json.loads(response)

        except (LLMError, json.JSONDecodeError, httpx.HTTPError) as e:
            logger.warning(f"Rule matching failed ({type(e).__name__}): {e}")
            return []

    async def generate_diagnosis(
        self,
        request: DiagnosisRequest,
        ontology_context: str,
        matched_rules: List[Dict[str, Any]],
        activated_knowledge: Optional[Any] = None,
    ) -> DiagnosisResponse:
        """
        Generate complete diagnosis using LLM.

        This is the main diagnosis method that combines all information
        and produces a structured diagnosis response.

        Args:
            request: Diagnosis request with symptom and signals
            ontology_context: Relevant ontology information
            matched_rules: Matched diagnostic rules

        Returns:
            DiagnosisResponse with complete diagnosis
        """
        system_prompt = """你是一个专业的汽车故障诊断专家。你的任务是根据用户的症状描述、车辆信号和诊断规则，提供全面的诊断结果。

诊断要求：
1. 提供清晰的推理链，从症状到结论
2. 生成多个可能的假设，按可能性排序
3. 为每个假设提供验证步骤
4. 计算诊断置信度
5. 根据用户角色调整输出语言风格"""

        signals_text = (
            "\n".join([f"- {s.key}: {s.value}" for s in request.signals])
            if request.signals
            else "无信号数据"
        )

        rules_text = (
            "\n".join(
                [
                    f"- {r.get('rule_id', 'R')}: {r.get('rule_text', '')} (置信度: {r.get('match_confidence', 0.9):.0%})"
                    for r in matched_rules
                ]
            )
            if matched_rules
            else "无匹配规则"
        )

        # Build activated knowledge block for prompt injection
        activated_block = ""
        if activated_knowledge and activated_knowledge.activated_rules:
            rule_lines = []
            for node in activated_knowledge.activated_rules[:5]:
                chain = f"[{node.node_id}] {node.label_zh}"
                chain += f"\n  置信度: {int(node.confidence * 100)}%"
                chain += f"\n  来源: {node.source_triple}"
                rule_lines.append(chain)
            activated_block += "\n\n### 激活的 Ontology 规则\n"
            activated_block += "\n\n".join(rule_lines)

        if activated_knowledge and activated_knowledge.signal_mappings:
            signals_dict = {s.key: s.value for s in request.signals}
            mapping_lines = [
                f'{k}="{signals_dict.get(k, "?")}" → {v}'
                for k, v in activated_knowledge.signal_mappings.items()
            ]
            activated_block += "\n\n### 信号 → 本体映射\n"
            activated_block += "\n".join(mapping_lines)

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

        user_message = f"""## 诊断任务

### 用户症状
{request.symptom}

### 用户角色
{request.role.value}

### 车辆信号
{signals_text}

### Ontology上下文
{ontology_context}{activated_block}

### 匹配的诊断规则
{rules_text}
{reasoning_requirement}
请提供完整的诊断结果，返回JSON格式。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response_text = ""  # Initialize to avoid unbound error
        try:
            response_text = await self.client.complete(messages, max_tokens=4096)

            # Try to parse as JSON
            response_text = response_text.strip()
            if response_text.startswith("```"):
                parts = response_text.split("```")
                if len(parts) >= 2:
                    response_text = parts[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]

            data = json.loads(response_text)

            # ✨ 验证必要字段，如果缺失则使用 fallback 数据填充
            data = self._validate_and_fill_missing_fields(
                data, request, activated_knowledge=activated_knowledge
            )

            # Build DiagnosisResponse
            response = DiagnosisResponse(
                diagnosis_id=f"diag_{int(time.time() * 1000)}",
                summary=data.get("summary", "诊断完成"),
                reasoning_steps=[
                    ReasoningStep(**step) if isinstance(step, dict) else step
                    for step in data.get("reasoning_steps", [])
                ],
                primary_hypothesis=DiagnosticHypothesis(**data["primary_hypothesis"])
                if "primary_hypothesis" in data and data["primary_hypothesis"]
                else None,
                secondary_hypotheses=[
                    DiagnosticHypothesis(**h) if isinstance(h, dict) else h
                    for h in data.get("secondary_hypotheses", [])
                ],
                final_confidence=data.get("final_confidence", 0.75),
                confidence_factors=[
                    ConfidenceFactor(**f) if isinstance(f, dict) else f
                    for f in data.get("confidence_factors", [])
                ],
                output_for_owner=data.get("output_for_owner"),
                output_for_technician=data.get("output_for_technician"),
                output_for_customer_service=data.get("output_for_customer_service"),
                model_used=self.config.model,
                escalation_hint=data.get("escalation_hint"),
            )
            # Fill deficit notes for LLM-only runs
            response.reasoning_steps = self._fill_deficit_notes(
                response.reasoning_steps,
                activated_knowledge=activated_knowledge,
            )
            return response

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse diagnosis response JSON: {e}")
            # Return a basic response with the raw text
            return self._generate_fallback_response(request, response_text)
        except LLMError as e:
            logger.error(f"LLM error during diagnosis generation: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during diagnosis generation: {e}")
            raise LLMResponseError(f"Diagnosis generation failed: {e}") from e

    def _validate_and_fill_missing_fields(
        self,
        data: Dict[str, Any],
        request: DiagnosisRequest,
        activated_knowledge: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        验证 LLM 返回的数据并填充缺失的必要字段。

        当 LLM 返回的数据缺少 reasoning_steps、primary_hypothesis、
        confidence_factors 等字段时，使用默认值填充。

        Args:
            data: LLM 返回的 JSON 数据
            request: 原始诊断请求
            activated_knowledge: 可选的激活本体知识对象（包含 activated_rules 和 signal_mappings）。
                                如果提供且包含非空规则列表，置信度兜底值会提升到 0.90；
                                否则降至 0.85。

        Returns:
            填充后的数据字典
        """
        from diagnosis_knowledge import HYPOTHESIS_TEMPLATES, OUTPUT_TEMPLATES
        from scenario_detector import get_scenario_detector

        scenario_detector = get_scenario_detector()
        scenario = scenario_detector.detect(request.symptom)

        # 验证并填充 reasoning_steps
        if not data.get("reasoning_steps"):
            logger.warning("LLM response missing reasoning_steps, generating defaults")
            data["reasoning_steps"] = [
                {
                    "step_number": 1,
                    "title": "症状解析",
                    "body": f"用户症状: {request.symptom[:100]}\n场景分类: {scenario}",
                    "confidence": 0.90,
                },
                {
                    "step_number": 2,
                    "title": "信号分析",
                    "body": f"当前信号状态: {len(request.signals)} 个信号",
                    "confidence": 0.85,
                },
                {
                    "step_number": 3,
                    "title": "规则匹配",
                    "body": f"匹配场景: {scenario}",
                    "confidence": 0.88,
                },
            ]

        # 验证并填充 primary_hypothesis
        if not data.get("primary_hypothesis"):
            logger.warning(
                "LLM response missing primary_hypothesis, generating defaults"
            )
            hypotheses = HYPOTHESIS_TEMPLATES.get(
                scenario,
                [
                    {"name": "待进一步诊断", "pct": 50, "cls": "p"},
                ],
            )
            primary_hyp = (
                hypotheses[0] if hypotheses else {"name": "待进一步诊断", "pct": 50}
            )

            data["primary_hypothesis"] = {
                "hypothesis_id": "hypo_001",
                "rank": 1,
                "root_cause": primary_hyp.get("name", "待进一步诊断"),
                "description": f"基于场景 {scenario} 的诊断假设",
                "confidence": primary_hyp.get("pct", 50) / 100.0,
                "affected_components": [],
                "verification_steps": [],
                "priority": "high" if primary_hyp.get("pct", 50) > 70 else "medium",
            }

        # 验证并填充 confidence_factors
        if not data.get("confidence_factors"):
            logger.warning(
                "LLM response missing confidence_factors, generating defaults"
            )
            data["confidence_factors"] = [
                {
                    "label": "症状匹配度",
                    "value": 0.90,
                    "weight": 0.30,
                    "explanation": "基于场景匹配",
                },
                {
                    "label": "规则可信度",
                    "value": 0.90 if (activated_knowledge and activated_knowledge.activated_rules) else 0.85,
                    "weight": 0.35,
                    "explanation": "来自本体知识库规则" if (activated_knowledge and activated_knowledge.activated_rules) else "来自知识库规则",
                },
                {
                    "label": "数据质量",
                    "value": 0.80 if request.signals else 0.50,
                    "weight": 0.20,
                    "explanation": "信号数据完整性",
                },
                {
                    "label": "假设一致性",
                    "value": 0.85,
                    "weight": 0.15,
                    "explanation": "假设与证据一致性",
                },
            ]

        # 验证并填充 final_confidence
        if not data.get("final_confidence"):
            # 从 confidence_factors 计算
            factors = data.get("confidence_factors", [])
            if factors:
                total_weight = sum(f.get("weight", 0) for f in factors)
                weighted_sum = sum(
                    f.get("value", 0) * f.get("weight", 0) for f in factors
                )
                data["final_confidence"] = (
                    weighted_sum / total_weight if total_weight > 0 else 0.75
                )
            else:
                data["final_confidence"] = 0.75

        # 验证并填充 output_for_*
        role_str = (
            request.role.value if hasattr(request.role, "value") else str(request.role)
        )
        output_key = f"output_for_{role_str}"

        if not data.get(output_key) and not data.get("output_for_owner"):
            logger.warning(
                f"LLM response missing output for {role_str}, generating defaults"
            )
            templates = OUTPUT_TEMPLATES.get(scenario, {})
            if role_str in templates:
                data[output_key] = templates[role_str]
            elif "owner" in templates:
                data[output_key] = templates["owner"]

        return data

    def _generate_fallback_response(
        self, request: DiagnosisRequest, raw_text: str = ""
    ) -> DiagnosisResponse:
        """
        生成 fallback 诊断响应。

        当 LLM 完全失败或返回无效 JSON 时使用。

        Args:
            request: 原始诊断请求
            raw_text: LLM 返回的原始文本（如果有）

        Returns:
            DiagnosisResponse with fallback diagnosis
        """
        from diagnosis_knowledge import HYPOTHESIS_TEMPLATES, OUTPUT_TEMPLATES
        from scenario_detector import get_scenario_detector

        scenario_detector = get_scenario_detector()
        scenario = scenario_detector.detect(request.symptom)
        role_str = (
            request.role.value if hasattr(request.role, "value") else str(request.role)
        )

        # 获取假设模板
        hypotheses = HYPOTHESIS_TEMPLATES.get(
            scenario,
            [
                {"name": "待进一步诊断", "pct": 50, "cls": "p"},
            ],
        )

        # 构建推理步骤
        reasoning_steps = [
            ReasoningStep(
                step_number=1,
                title="症状解析",
                body=f"用户症状: {request.symptom[:100]}\n场景分类: {scenario}",
                confidence=0.90,
            ),
            ReasoningStep(
                step_number=2,
                title="信号分析",
                body=f"当前信号状态: {len(request.signals)} 个信号",
                confidence=0.85,
            ),
            ReasoningStep(
                step_number=3,
                title="规则匹配",
                body=f"匹配场景: {scenario}",
                confidence=0.88,
            ),
        ]

        # 构建主要假设
        primary = None
        if hypotheses:
            h = hypotheses[0]
            primary = DiagnosticHypothesis(
                hypothesis_id="hypo_001",
                rank=1,
                root_cause=h.get("name", "待进一步诊断"),
                description=f"基于场景 {scenario} 的诊断假设",
                confidence=h.get("pct", 50) / 100.0,
                affected_components=[],
                verification_steps=[],
                priority="high" if h.get("pct", 50) > 70 else "medium",
            )

        # 构建置信度因子
        confidence_factors = [
            ConfidenceFactor(
                label="症状匹配度",
                value=0.90,
                weight=0.30,
                explanation="基于场景匹配",
            ),
            ConfidenceFactor(
                label="规则可信度",
                value=0.85,
                weight=0.35,
                explanation="来自知识库规则",
            ),
            ConfidenceFactor(
                label="数据质量",
                value=0.80 if request.signals else 0.50,
                weight=0.20,
                explanation="信号数据完整性",
            ),
            ConfidenceFactor(
                label="假设一致性",
                value=0.85,
                weight=0.15,
                explanation="假设与证据一致性",
            ),
        ]

        final_confidence = sum(f.value * f.weight for f in confidence_factors)

        # 获取输出模板
        templates = OUTPUT_TEMPLATES.get(scenario, {})
        output_text = templates.get(
            role_str, templates.get("owner", raw_text or "诊断完成")
        )

        return DiagnosisResponse(
            diagnosis_id=f"diag_fallback_{int(time.time() * 1000)}",
            summary=f"诊断分析 - 场景: {scenario}",
            reasoning_steps=reasoning_steps,
            primary_hypothesis=primary,
            secondary_hypotheses=[],
            final_confidence=final_confidence,
            confidence_factors=confidence_factors,
            output_for_owner=output_text if role_str == "owner" else None,
            output_for_technician=output_text if role_str == "technician" else None,
            output_for_customer_service=output_text
            if role_str == "customer_service"
            else None,
            model_used="fallback",
            escalation_hint=None,
        )

    def _fill_deficit_notes(
        self,
        steps: List[ReasoningStep],
        activated_knowledge: Optional[Any],
    ) -> List[ReasoningStep]:
        """
        Fill deficit_note on each step for LLM-only runs.

        Only called when activated_knowledge is None (pure LLM mode).
        Returns the same list with deficit_note set in-place.
        Modifies steps in-place; the returned list is the same object as the input.
        """
        if activated_knowledge is not None:
            return steps

        for step in steps:
            # Priority 1: output step — no note
            if step.agent == "output":
                step.deficit_note = None
                continue

            has_rules = step.rules_matched is not None and len(step.rules_matched) > 0
            has_signals = step.signals_referenced is not None and len(step.signals_referenced) > 0

            # Priority 2: hallucinated rules
            if has_rules:
                step.deficit_note = "规则引用来自 LLM 推测，未经 SPARQL 验证"
            # Priority 3: signals but no rules
            elif has_signals:
                step.deficit_note = "识别到信号异常，但未通过本体规则链验证"
            # Priority 4: fallback
            else:
                step.deficit_note = "无信号引用与规则依据，推理基于语义理解"

        return steps

    async def generate_output(
        self,
        diagnosis: DiagnosisResponse,
        role: str,
        additional_context: Optional[str] = None,
    ) -> str:
        """
        Generate role-adapted output text.

        Args:
            diagnosis: Diagnosis response
            role: Target user role
            additional_context: Additional context for generation

        Returns:
            str: Role-adapted output text
        """
        system_prompt = f"""你是一个汽车诊断报告生成器。请根据诊断结果，为{role}生成适当的输出文本。

角色说明：
- owner（车主）: 使用通俗易懂的语言，避免专业术语，提供简单可操作的建议
- technician（技师）: 使用专业术语，提供详细的技术分析和OBD诊断建议
- customer_service（客服）: 使用友好专业的语言，提供清晰的指导，并标注升级条件"""

        diagnosis_json = diagnosis.model_dump_json(indent=2, exclude_none=True)

        user_message = f"""## 诊断结果

{diagnosis_json}

{f"附加信息：{additional_context}" if additional_context else ""}

请为{role}生成合适的输出文本。直接返回文本内容，不要包含markdown标记。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            return await self.client.complete(messages)
        except (LLMError, httpx.HTTPError) as e:
            logger.warning(f"Output generation failed ({type(e).__name__}): {e}")
            return diagnosis.summary

    async def close(self):
        """Close LLM client."""
        if self._client and hasattr(self._client, "close"):
            await self._client.close()


# =============================================================================
# LLM Service (Main Interface)
# =============================================================================


class LLMService:
    """
    Main LLM Service interface.

    Provides high-level methods for diagnosis using LLM,
    with fallback to hardcoded rules when LLM is unavailable.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_llm_config()
        self.tools = LLMTools(self.config)

    async def diagnose(
        self,
        request: DiagnosisRequest,
        ontology_parser: Optional[Any] = None,
        fallback_handler: Optional[Callable] = None,
    ) -> DiagnosisResponse:
        """
        Perform complete diagnosis using LLM.

        Args:
            request: Diagnosis request
            ontology_parser: Ontology parser for context
            fallback_handler: Fallback function if LLM fails

        Returns:
            DiagnosisResponse
        """
        start_time = time.time()

        try:
            # Build ontology context
            ontology_context = ""
            if ontology_parser:
                ontology_context = self._build_ontology_context(
                    request.symptom, ontology_parser
                )

            # Parse symptom
            signals_dict = {s.key: s.value for s in request.signals}
            parsed = await self.tools.parse_symptom(
                request.symptom, signals_dict, ontology_context
            )

            # Get rules from ontology
            rules = []
            if ontology_parser:
                rules = ontology_parser.swrl_rules

            # Match rules
            matched_rules = await self.tools.match_diagnostic_rules(
                parsed,
                [
                    {
                        "id": r.rule_id,
                        "text": " -> ".join(r.actions),
                        "conditions": r.conditions,
                    }
                    for r in rules
                ],
                signals_dict,
            )

            # Generate diagnosis
            diagnosis = await self.tools.generate_diagnosis(
                request, ontology_context, matched_rules,
                activated_knowledge=request.activated_knowledge,
            )

            # Add processing time
            diagnosis.processing_time_ms = int((time.time() - start_time) * 1000)

            return diagnosis

        except Exception as e:
            logger.error(f"LLM diagnosis failed: {e}")

            if self.config.enable_fallback and fallback_handler:
                logger.info("Using fallback handler")
                return await fallback_handler(request)

            # Return minimal response
            return DiagnosisResponse(
                diagnosis_id=f"diag_{int(time.time() * 1000)}",
                summary=f"诊断服务暂时不可用: {str(e)}",
                final_confidence=0.0,
                model_used="fallback",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

    def _build_ontology_context(self, symptom: str, parser: Any) -> str:
        """
        Build ontology context for LLM prompt.

        Extracts relevant classes, properties, and rules
        based on symptom keywords.
        """
        parts = []

        # Search for relevant classes
        keywords = symptom.split()
        for keyword in keywords[:5]:  # Limit to first 5 keywords
            results = parser.search_by_keyword(keyword)
            if results["classes"]:
                for cls_name in results["classes"][:3]:
                    cls = parser.get_class(cls_name)
                    if cls:
                        parts.append(
                            f"## {cls.label} ({cls.label_zh})\n{cls.comment_zh or cls.comment}"
                        )

        # Add power mode info
        power_modes = parser.get_power_mode_info()
        if power_modes:
            parts.append(
                "## 电源模式\n"
                + "\n".join(
                    [
                        f"- {name}: {info.get('label_zh', info.get('label', ''))}"
                        for name, info in power_modes.items()
                    ]
                )
            )

        # Add key types
        key_types = parser.get_key_types()
        if key_types:
            parts.append(
                "## 钥匙类型\n"
                + "\n".join(
                    [
                        f"- {name}: {info.get('label_zh', info.get('label', ''))}"
                        for name, info in key_types.items()
                    ]
                )
            )

        return "\n\n".join(parts[:10])  # Limit context size

    async def close(self):
        """Close service resources."""
        await self.tools.close()


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
