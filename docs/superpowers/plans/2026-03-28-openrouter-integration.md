# OpenRouter 集成实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为车辆诊断系统添加 OpenRouter 作为可选的 LLM 提供商，通过环境变量 `LLM_PROVIDER` 切换。

**Architecture:** 新增 `OpenRouterClient` 类实现 `LLMClient` 接口，修改 `LLMConfig` 添加 provider 选择字段，修改 `LLMTools.client` 属性根据 provider 返回正确的客户端。

**Tech Stack:** Python 3.10+, httpx, pydantic-settings

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/llm/config.py` | 修改 | 添加 `LLMProviderEnum`、`openrouter_api_key`、`openrouter_model` 字段 |
| `backend/llm/service.py` | 修改 | 添加 `OpenRouterClient` 类，修改 `LLMTools.client` 属性 |
| `backend/llm/__init__.py` | 修改 | 导出 `LLMProviderEnum` |
| `backend/llm/tests/test_openrouter.py` | 创建 | 测试 OpenRouter 客户端 |

---

### Task 1: 添加 LLMProviderEnum 和配置字段

**Files:**
- Modify: `backend/llm/config.py:1-50`

- [ ] **Step 1: 添加 LLMProviderEnum 枚举**

在 `backend/llm/config.py` 文件顶部的 import 部分之后，添加枚举类：

```python
from enum import Enum


class LLMProviderEnum(str, Enum):
    """LLM provider selection."""
    LOCAL = "local"
    OPENROUTER = "openrouter"
```

- [ ] **Step 2: 在 LLMConfig 类中添加新字段**

在 `LLMConfig` 类中，在 `model_config` 之后添加新字段：

```python
class LLMConfig(BaseSettings):
    """
    Configuration for LLM service.
    
    Supports both local LLM deployment and OpenRouter.
    All sensitive values can be set via environment variables.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Provider selection
    provider: LLMProviderEnum = Field(
        default=LLMProviderEnum.LOCAL,
        description="LLM provider: 'local' or 'openrouter'"
    )
    
    # OpenRouter specific configuration
    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key (LLM_OPENROUTER_API_KEY env var)"
    )
    openrouter_model: str = Field(
        default="openai/gpt-3.5-turbo",
        description="OpenRouter model name"
    )
    
    # Local model REST API endpoint (existing fields)
    endpoint: str = Field(
        default="https://llm-gateway.dev.cn-vwa.volkswagen-cea.com",
        description="Local LLM REST API endpoint"
    )
    # ... rest of existing fields ...
```

- [ ] **Step 3: 更新 to_dict 方法**

修改 `to_dict` 方法，添加新字段：

```python
def to_dict(self) -> Dict[str, Any]:
    """Convert to dictionary (excluding sensitive values)."""
    return {
        "provider": self.provider.value,
        "endpoint": self.endpoint,
        "model": self.model,
        "openrouter_model": self.openrouter_model,
        "temperature": self.temperature,
        "max_tokens": self.max_tokens,
        "timeout": self.timeout,
        "max_retries": self.max_retries,
        "enable_streaming": self.enable_streaming,
        "enable_fallback": self.enable_fallback,
    }
```

- [ ] **Step 4: 运行配置测试**

Run: `cd backend && python -c "from llm.config import LLMConfig, LLMProviderEnum; c = LLMConfig(); print(f'provider={c.provider}, openrouter_model={c.openrouter_model}')"`
Expected: `provider=LLMProviderEnum.LOCAL, openrouter_model=openai/gpt-3.5-turbo`

- [ ] **Step 5: Commit**

```bash
git add backend/llm/config.py
git commit -m "feat: add LLMProviderEnum and OpenRouter config fields"
```

---

### Task 2: 实现 OpenRouterClient 类

**Files:**
- Modify: `backend/llm/service.py:285-287` (after LocalLLMClient)

- [ ] **Step 1: 添加 OpenRouterClient 类**

在 `LocalLLMClient` 类之后（约 287 行），添加 `OpenRouterClient` 类：

```python
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
                timeout=httpx.Timeout(self.config.timeout),
                headers=headers
            )
        return self._client
    
    def _build_request_body(
        self,
        messages: List[Dict[str, str]],
        **kwargs
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
        retry=retry_if_exception_type((LLMConnectionError, LLMTimeoutError, LLMRateLimitError)),
        before_sleep_log(logger, logging.WARNING),
    )
    async def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """Send completion request to OpenRouter."""
        client = await self._get_client()
        body = self._build_request_body(messages, **kwargs)
        
        if self.config.log_requests:
            logger.debug(f"OpenRouter request: model={body['model']}, messages={len(messages)}")
        
        try:
            response = await client.post(
                OPENROUTER_API_URL,
                json=body
            )
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
                raise LLMConnectionError("OpenRouter authentication failed - check API key")
            else:
                raise LLMResponseError(f"OpenRouter HTTP error: {e.response.status_code}")
        except httpx.HTTPError as e:
            raise LLMConnectionError(f"OpenRouter request failed: {e}")
    
    async def complete_with_structure(
        self,
        messages: List[Dict[str, str]],
        response_model: type,
        **kwargs
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
        self,
        messages: List[Dict[str, str]],
        **kwargs
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
```

- [ ] **Step 2: 验证语法正确**

Run: `cd backend && python -c "from llm.service import OpenRouterClient; print('OpenRouterClient imported successfully')"`
Expected: `OpenRouterClient imported successfully`

- [ ] **Step 3: Commit**

```bash
git add backend/llm/service.py
git commit -m "feat: add OpenRouterClient implementation"
```

---

### Task 3: 修改 LLMTools 支持 Provider 选择

**Files:**
- Modify: `backend/llm/service.py:301-311` (LLMTools.client property)

- [ ] **Step 1: 修改 LLMTools.client 属性**

修改 `LLMTools` 类的 `client` 属性，根据 provider 选择客户端：

```python
@property
def client(self) -> LLMClient:
    """Get the appropriate LLM client based on provider."""
    if self._client is None:
        if self.config.provider == LLMProviderEnum.OPENROUTER:
            if not self.config.openrouter_api_key:
                raise LLMConnectionError(
                    "OpenRouter API key not set. Please set LLM_OPENROUTER_API_KEY environment variable."
                )
            self._client = OpenRouterClient(self.config)
            logger.info(f"Using OpenRouter client: model={self.config.openrouter_model}")
        else:
            self._client = LocalLLMClient(self.config)
            logger.info(f"Using Local LLM client: {self.config.endpoint}")
    return self._client
```

- [ ] **Step 2: 添加必要的 import**

在 `service.py` 顶部添加 `LLMProviderEnum` 的导入：

```python
from llm.config import LLMConfig, get_llm_config, LLMProviderEnum
```

- [ ] **Step 3: 验证修改**

Run: `cd backend && python -c "from llm.service import LLMTools; from llm.config import LLMConfig; c = LLMConfig(); t = LLMTools(c); print(f'Provider: {c.provider}')"`
Expected: `Provider: LLMProviderEnum.LOCAL`

- [ ] **Step 4: Commit**

```bash
git add backend/llm/service.py
git commit -m "feat: modify LLMTools to support provider selection"
```

---

### Task 4: 更新 __init__.py 导出

**Files:**
- Modify: `backend/llm/__init__.py`

- [ ] **Step 1: 添加导出**

修改 `backend/llm/__init__.py`：

```python
"""
LLM Module for Vehicle Power Diagnosis System.

This module provides LLM integration for intelligent diagnosis,
replacing hardcoded rules with semantic reasoning.
"""

from llm.config import LLMConfig, get_llm_config, LLMProviderEnum
from llm.service import LLMService, LLMTools, get_llm_service, OpenRouterClient
from llm.schemas import (
    DiagnosisRequest,
    DiagnosisResponse,
    DiagnosticHypothesis,
    ReasoningStep,
    ConfidenceFactor,
    Role,
    SignalInfo,
)
from llm.prompts import PromptBuilder, get_prompt_builder
from llm.fallback import FallbackHandler, get_fallback_handler

__all__ = [
    # Config
    "LLMConfig",
    "get_llm_config",
    "LLMProviderEnum",
    # Service
    "LLMService",
    "LLMTools",
    "get_llm_service",
    "OpenRouterClient",
    # Schemas
    "DiagnosisRequest",
    "DiagnosisResponse",
    "DiagnosticHypothesis",
    "ReasoningStep",
    "ConfidenceFactor",
    "Role",
    "SignalInfo",
    # Prompts
    "PromptBuilder",
    "get_prompt_builder",
    # Fallback
    "FallbackHandler",
    "get_fallback_handler",
]
```

- [ ] **Step 2: 验证导入**

Run: `cd backend && python -c "from llm import LLMProviderEnum, OpenRouterClient; print('All exports work')"`
Expected: `All exports work`

- [ ] **Step 3: Commit**

```bash
git add backend/llm/__init__.py
git commit -m "feat: export LLMProviderEnum and OpenRouterClient"
```

---

### Task 5: 添加单元测试

**Files:**
- Create: `backend/tests/test_openrouter.py`

- [ ] **Step 1: 创建测试文件**

创建 `backend/tests/test_openrouter.py`：

```python
"""
Tests for OpenRouter integration.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from llm.config import LLMConfig, LLMProviderEnum
from llm.service import OpenRouterClient, LLMTools, LLMConnectionError


class TestLLMProviderEnum:
    """Tests for LLMProviderEnum."""
    
    def test_provider_enum_values(self):
        """Test enum values."""
        assert LLMProviderEnum.LOCAL.value == "local"
        assert LLMProviderEnum.OPENROUTER.value == "openrouter"
    
    def test_provider_enum_from_string(self):
        """Test creating enum from string."""
        assert LLMProviderEnum("local") == LLMProviderEnum.LOCAL
        assert LLMProviderEnum("openrouter") == LLMProviderEnum.OPENROUTER


class TestLLMConfigWithProvider:
    """Tests for LLMConfig with provider field."""
    
    def test_default_provider_is_local(self):
        """Test default provider is local."""
        config = LLMConfig()
        assert config.provider == LLMProviderEnum.LOCAL
    
    def test_provider_can_be_set_to_openrouter(self):
        """Test provider can be set to openrouter."""
        config = LLMConfig(provider=LLMProviderEnum.OPENROUTER)
        assert config.provider == LLMProviderEnum.OPENROUTER
    
    def test_openrouter_model_default(self):
        """Test default OpenRouter model."""
        config = LLMConfig()
        assert config.openrouter_model == "openai/gpt-3.5-turbo"


class TestOpenRouterClient:
    """Tests for OpenRouterClient."""
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        return LLMConfig(
            provider=LLMProviderEnum.OPENROUTER,
            openrouter_api_key="test-api-key",
            openrouter_model="openai/gpt-3.5-turbo",
            log_requests=False,
        )
    
    @pytest.fixture
    def client(self, config):
        """Create test client."""
        return OpenRouterClient(config)
    
    def test_client_initialization(self, client, config):
        """Test client initialization."""
        assert client.config == config
        assert client._api_key == "test-api-key"
        assert client._model == "openai/gpt-3.5-turbo"
    
    @pytest.mark.asyncio
    async def test_complete_success(self, client):
        """Test successful completion request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "Test response"}}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client
            
            result = await client.complete([
                {"role": "user", "content": "Hello"}
            ])
            
            assert result == "Test response"
    
    @pytest.mark.asyncio
    async def test_complete_auth_error(self, client):
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )
        
        with patch.object(client, '_get_client') as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client
            
            with pytest.raises(LLMConnectionError) as exc_info:
                await client.complete([{"role": "user", "content": "Hello"}])
            
            assert "authentication failed" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_close_client(self, client):
        """Test closing client."""
        client._client = AsyncMock()
        client._client.aclose = AsyncMock()
        
        await client.close()
        
        client._client.aclose.assert_called_once()
        assert client._client is None


class TestLLMToolsProviderSelection:
    """Tests for LLMTools provider selection."""
    
    def test_local_provider_uses_local_client(self):
        """Test local provider uses LocalLLMClient."""
        config = LLMConfig(provider=LLMProviderEnum.LOCAL)
        tools = LLMTools(config)
        
        from llm.service import LocalLLMClient
        assert isinstance(tools.client, LocalLLMClient)
    
    def test_openrouter_provider_uses_openrouter_client(self):
        """Test openrouter provider uses OpenRouterClient."""
        config = LLMConfig(
            provider=LLMProviderEnum.OPENROUTER,
            openrouter_api_key="test-key"
        )
        tools = LLMTools(config)
        
        assert isinstance(tools.client, OpenRouterClient)
    
    def test_openrouter_without_api_key_raises_error(self):
        """Test openrouter without API key raises error."""
        config = LLMConfig(
            provider=LLMProviderEnum.OPENROUTER,
            openrouter_api_key=None
        )
        tools = LLMTools(config)
        
        with pytest.raises(LLMConnectionError) as exc_info:
            _ = tools.client
        
        assert "API key not set" in str(exc_info.value)
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest tests/test_openrouter.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_openrouter.py
git commit -m "test: add OpenRouter integration tests"
```

---

### Task 6: 添加环境变量示例

**Files:**
- Modify: `.env.example` (create if not exists)

- [ ] **Step 1: 创建或更新 .env.example**

在项目根目录创建 `.env.example`：

```bash
# LLM Provider Configuration
# ==========================
# Select LLM provider: 'local' or 'openrouter'
LLM_PROVIDER=local

# Local LLM Configuration
# =======================
LLM_ENDPOINT=https://llm-gateway.dev.cn-vwa.volkswagen-cea.com
LLM_API_KEY=your-local-api-key
LLM_MODEL=GLM-5-FP8

# OpenRouter Configuration
# ========================
# Required when LLM_PROVIDER=openrouter
LLM_OPENROUTER_API_KEY=sk-or-your-api-key
LLM_OPENROUTER_MODEL=openai/gpt-3.5-turbo

# Other LLM Settings
# ==================
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
LLM_TIMEOUT=60
LLM_ENABLE_FALLBACK=true
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add .env.example with OpenRouter configuration"
```

---

### Task 7: 更新文档

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: 更新 AGENTS.md 配置部分**

在 `AGENTS.md` 的 Configuration 部分添加 OpenRouter 配置说明：

```markdown
### LLM Provider Selection

The system supports two LLM providers:

1. **Local LLM** (default) - Custom REST API endpoint
2. **OpenRouter** - Cloud LLM service with multiple models

Set the provider via environment variable:

```bash
# Use local LLM (default)
LLM_PROVIDER=local

# Use OpenRouter
LLM_PROVIDER=openrouter
LLM_OPENROUTER_API_KEY=sk-or-xxxxx
LLM_OPENROUTER_MODEL=openai/gpt-3.5-turbo
```
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md with OpenRouter configuration"
```

---

### Task 8: 集成测试

**Files:**
- No new files

- [ ] **Step 1: 运行所有测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: 测试本地 LLM 模式**

Run: `cd backend && LLM_PROVIDER=local python -c "from llm import LLMTools, LLMConfig; c = LLMConfig(); print(f'Provider: {c.provider}')"`
Expected: `Provider: LLMProviderEnum.LOCAL`

- [ ] **Step 3: 测试 OpenRouter 模式配置**

Run: `cd backend && LLM_PROVIDER=openrouter LLM_OPENROUTER_API_KEY=test-key python -c "from llm import LLMTools, LLMConfig; c = LLMConfig(); print(f'Provider: {c.provider}')"`
Expected: `Provider: LLMProviderEnum.OPENROUTER`

---

## 完成标准

- [ ] 所有测试通过
- [ ] 本地 LLM 模式工作正常
- [ ] OpenRouter 模式配置正确
- [ ] 文档已更新
- [ ] 所有代码已提交
