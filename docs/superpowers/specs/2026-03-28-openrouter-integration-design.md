# OpenRouter 集成设计文档

**日期**: 2026-03-28  
**状态**: 已批准  
**目标**: 为车辆诊断系统添加 OpenRouter 作为可选的 LLM 提供商

---

## 1. 背景

现有的车辆诊断系统使用本地 LLM (`LocalLLMClient`) 连接远程本地部署的 LLM 服务。为支持更灵活的部署方式，需要添加 OpenRouter 作为可选的 LLM 提供商。

---

## 2. 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 切换策略 | 配置切换 | 通过环境变量切换，无需代码修改 |
| 默认提供商 | 本地 LLM | 保持现有行为不变 |
| 切换变量 | `LLM_PROVIDER` | 环境变量 `local` / `openrouter` |
| 默认模型 | `gpt-3.5-turbo` | 性价比高 |

---

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      LLMService                             │
│                    (入口点)                                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   LLMProviderEnum     │  ← LLM_PROVIDER=local|openrouter
              │   - LOCAL             │
              │   - OPENROUTER        │
              └───────────┬───────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐     ┌─────────────────────┐
│    LocalLLMClient   │     │  OpenRouterClient   │
│      (现有)          │     │      (新增)          │
│ - endpoint: 本地地址 │     │ - endpoint: OpenAI  │
│ - model: GLM-5-FP8  │     │ - model: gpt-3.5-turbo │
└─────────────────────┘     └─────────────────────┘
```

---

## 4. 接口设计

### 4.1 LLMProviderEnum

```python
from enum import Enum

class LLMProviderEnum(str, Enum):
    LOCAL = "local"
    OPENROUTER = "openrouter"
```

### 4.2 OpenRouterClient

实现 `LLMClient` 抽象接口：

```python
class OpenRouterClient(LLMClient):
    def __init__(self, config: LLMConfig):
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.api_key = config.openrouter_api_key
        self.model = config.openrouter_model
        self.timeout = config.timeout
        
    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # 实现 OpenAI 兼容的 API 调用
        
    async def complete_with_structure(self, messages, response_model: type, **kwargs) -> Any:
        # 支持结构化输出
        
    def stream(self, messages, **kwargs) -> AsyncGenerator[str, None]:
        # 支持流式输出
```

---

## 5. 配置变更

### 5.1 新增环境变量

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `LLM_PROVIDER` | string | `local` | LLM 提供商选择 |
| `LLM_OPENROUTER_API_KEY` | string | - | OpenRouter API Key |
| `LLM_OPENROUTER_MODEL` | string | `openai/gpt-3.5-turbo` | OpenRouter 模型 |

### 5.2 LLMConfig 新增字段

```python
class LLMConfig(BaseSettings):
    # ... 现有字段 ...
    
    provider: LLMProviderEnum = LLMProviderEnum.LOCAL
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "openai/gpt-3.5-turbo"
```

---

## 6. 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/llm/config.py` | 新增 `LLMProviderEnum`，添加 `provider`、`openrouter_api_key`、`openrouter_model` 字段 |
| `backend/llm/service.py` | 新增 `OpenRouterClient` 类，修改 `LLMService.create_client()` 根据 provider 选择 |
| `backend/llm/__init__.py` | 导出 `LLMProviderEnum` |
| `.env.example` | 添加 OpenRouter 相关环境变量示例 |

---

## 7. 使用示例

### 使用本地 LLM（默认）
```bash
LLM_PROVIDER=local
LLM_ENDPOINT=https://llm-gateway.dev.cn-vwa.volkswagen-cea.com
LLM_API_KEY=your-local-api-key
```

### 使用 OpenRouter
```bash
LLM_PROVIDER=openrouter
LLM_OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxx
LLM_OPENROUTER_MODEL=openai/gpt-3.5-turbo
```

---

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| API Key 泄露 | 使用环境变量，不写入代码；添加安全提示 |
| 连接失败 | 保留本地 LLM 作为主要方案，OpenRouter 仅作备用 |
| 成本控制 | 默认使用 gpt-3.5-turbo，用户可配置更便宜的模型 |

---

## 9. 测试计划

1. **单元测试**: 测试 `OpenRouterClient` 各方法
2. **集成测试**: 测试配置切换功能
3. **手动测试**: 验证 OpenRouter 连接正常工作
