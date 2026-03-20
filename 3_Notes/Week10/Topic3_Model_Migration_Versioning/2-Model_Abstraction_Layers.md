# Note 2: Model Abstraction Layers — Isolating Model Dependencies

## The Problem with Hardcoded Models

This is what most AI codebases look like after a few months of development:

```python
# In src/rag/retriever.py
response = openai.chat.completions.create(
    model="gpt-4o-mini",  # Hardcoded
    ...
)

# In src/agents/classifier.py
response = openai.chat.completions.create(
    model="gpt-4o-mini",  # Hardcoded again
    ...
)

# In src/utils/summarizer.py
response = openai.chat.completions.create(
    model="gpt-4o-mini",  # And again
    ...
)

# In tests/test_generation.py
response = openai.chat.completions.create(
    model="gpt-4o-mini",  # 47 places total
    ...
)
```

**Why this is terrible:**

|Problem|Impact|
|---|---|
|Change requires finding all instances|`grep -r "gpt-4o-mini"` across entire codebase|
|No central control|Can't enforce consistent settings (temperature, max_tokens)|
|Can't switch models without code changes|Testing a new model = modifying 47 files|
|Environment-specific models impossible|Same model in dev and prod|
|Provider lock-in|Switching from OpenAI to Anthropic = rewrite everything|

---

## The Model Abstraction Pattern

The solution is a clean separation:

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Code                          │
│  (Doesn't know or care which model is being used)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM Client (Abstraction)                  │
│  generate(messages) → response                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM Config                                │
│  model, temperature, max_tokens, provider                    │
│  (Loaded from environment or config file)                    │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ┌────────┐      ┌────────┐      ┌────────┐
         │ OpenAI │      │Anthropic│     │ Other  │
         └────────┘      └────────┘      └────────┘
```

**Benefits:**

- Single place to change model configuration
- Environment-based overrides (different models for dev/staging/prod)
- Provider switching without code changes
- Consistent settings across all LLM calls
- Easier testing (mock the client, not the API)

---

## Implementation: LLMConfig Class

The config class centralizes all model-related settings:

```python
# config/llm_config.py

import os
from dataclasses import dataclass
from typing import Optional
import yaml


@dataclass
class LLMConfig:
    """
    Centralized LLM configuration.
    
    Load order:
    1. Environment variables (highest priority)
    2. Config file
    3. Defaults (lowest priority)
    """
    
    # Model settings
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 1000
    
    # Optional overrides
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> "LLMConfig":
        """Load config from environment variables."""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1000")),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
        )
    
    @classmethod
    def from_file(cls, path: str) -> "LLMConfig":
        """Load config from YAML file, with env overrides."""
        with open(path) as f:
            file_config = yaml.safe_load(f)
        
        # Start with file config
        config = cls(
            provider=file_config.get("provider", "openai"),
            model=file_config.get("model", "gpt-4o-mini"),
            temperature=file_config.get("temperature", 0.7),
            max_tokens=file_config.get("max_tokens", 1000),
            api_key=file_config.get("api_key"),
            base_url=file_config.get("base_url"),
        )
        
        # Environment variables override file config
        if os.getenv("LLM_PROVIDER"):
            config.provider = os.getenv("LLM_PROVIDER")
        if os.getenv("LLM_MODEL"):
            config.model = os.getenv("LLM_MODEL")
        if os.getenv("LLM_TEMPERATURE"):
            config.temperature = float(os.getenv("LLM_TEMPERATURE"))
        if os.getenv("LLM_MAX_TOKENS"):
            config.max_tokens = int(os.getenv("LLM_MAX_TOKENS"))
        
        return config
    
    def validate(self) -> None:
        """Validate configuration on startup."""
        valid_providers = {"openai", "anthropic"}
        if self.provider not in valid_providers:
            raise ValueError(f"Invalid provider: {self.provider}. Must be one of {valid_providers}")
        
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.temperature}")
        
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
```

**Config file example:**

```yaml
# config/llm.yaml
provider: openai
model: gpt-4o-mini-2024-07-18  # Pinned version
temperature: 0.7
max_tokens: 1000
```

**Usage:**

```python
# Load from environment (12-factor app style)
config = LLMConfig.from_environment()

# Or load from file with env overrides
config = LLMConfig.from_file("config/llm.yaml")

# Validate before using
config.validate()
```

---

## Implementation: LLMClient Wrapper

The client wraps provider-specific details behind a unified interface:

```python
# clients/llm_client.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class LLMResponse:
    """Unified response format across providers."""
    content: str
    model: str
    usage: Dict[str, int]  # input_tokens, output_tokens
    finish_reason: str
    raw_response: Any  # Original provider response for debugging


class BaseLLMClient(ABC):
    """Abstract base for LLM clients."""
    
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Generate a response from messages."""
        pass
```

### OpenAI Implementation

**Doc reference:** OpenAI Responses API (https://developers.openai.com/api/reference/resources/responses/methods/create) — `client.responses.create()` with `input` parameter, returns `response.output_text`.

```python
# clients/openai_client.py

from openai import OpenAI
from config.llm_config import LLMConfig
from clients.llm_client import BaseLLMClient, LLMResponse
from typing import List, Dict, Any


class OpenAIClient(BaseLLMClient):
    """
    OpenAI client using the Responses API (March 2025+).
    
    Doc reference: https://developers.openai.com/api/reference/resources/responses/methods/create
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,  # Falls back to OPENAI_API_KEY env var if None
            base_url=config.base_url,
        )
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Generate using OpenAI Responses API.
        
        The Responses API uses 'input' for user messages and 'instructions' 
        for system-level guidance, replacing the older messages array format.
        """
        # Extract system message if present
        system_content = None
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)
        
        # For simple single-turn: use input string
        # For multi-turn: use input as list of messages
        if len(user_messages) == 1 and user_messages[0]["role"] == "user":
            input_content = user_messages[0]["content"]
        else:
            input_content = user_messages
        
        # Merge config defaults with call-specific overrides
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        response = self.client.responses.create(
            model=self.config.model,
            input=input_content,
            instructions=system_content,  # System prompt via instructions param
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        return LLMResponse(
            content=response.output_text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.status,  # "completed", "incomplete", etc.
            raw_response=response,
        )
```

### Anthropic Implementation

**Doc reference:** Anthropic Python SDK (https://platform.claude.com/docs/en/api/sdks/python) — `client.messages.create()` with `messages` list, returns `message.content[0].text`.

```python
# clients/anthropic_client.py

from anthropic import Anthropic
from config.llm_config import LLMConfig
from clients.llm_client import BaseLLMClient, LLMResponse
from typing import List, Dict, Any


class AnthropicClient(BaseLLMClient):
    """
    Anthropic client using the Messages API.
    
    Doc reference: https://platform.claude.com/docs/en/api/sdks/python
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = Anthropic(
            api_key=config.api_key,  # Falls back to ANTHROPIC_API_KEY env var if None
        )
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Generate using Anthropic Messages API.
        
        Anthropic uses a separate 'system' parameter rather than 
        including system messages in the messages array.
        """
        # Extract system message if present
        system_content = None
        api_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })
        
        # Merge config defaults with call-specific overrides
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        
        response = self.client.messages.create(
            model=self.config.model,
            messages=api_messages,
            system=system_content,  # Separate system parameter
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Extract text from content blocks
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
        
        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,  # "end_turn", "max_tokens", etc.
            raw_response=response,
        )
```

---

## Factory Pattern: Creating Clients from Config

The factory creates the right client based on configuration:

```python
# clients/factory.py

from config.llm_config import LLMConfig
from clients.llm_client import BaseLLMClient
from clients.openai_client import OpenAIClient
from clients.anthropic_client import AnthropicClient


def create_llm_client(config: LLMConfig) -> BaseLLMClient:
    """
    Factory function to create appropriate LLM client.
    
    Usage:
        config = LLMConfig.from_environment()
        client = create_llm_client(config)
        response = client.generate(messages)
    """
    config.validate()
    
    if config.provider == "openai":
        return OpenAIClient(config)
    elif config.provider == "anthropic":
        return AnthropicClient(config)
    else:
        raise ValueError(f"Unknown provider: {config.provider}")


# Convenience function for simple usage
def get_default_client() -> BaseLLMClient:
    """Get client with default/environment configuration."""
    config = LLMConfig.from_environment()
    return create_llm_client(config)
```

**Usage in application code:**

```python
# In your application — no provider details visible

from clients.factory import get_default_client

client = get_default_client()

response = client.generate([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain quantum computing in one sentence."},
])

print(response.content)
```

**Switching providers:**

```bash
# Development: Use cheaper model
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4o-mini

# Production: Use better model  
export LLM_PROVIDER=anthropic
export LLM_MODEL=claude-sonnet-4-5

# No code changes required
```

---

## Task-Specific Model Assignment

Different tasks have different requirements. A classifier doesn't need GPT-4o. An embedding model shouldn't be your generation model.

```python
# config/task_models.py

from dataclasses import dataclass
from typing import Dict, Optional
import yaml


@dataclass
class TaskModelConfig:
    """Model configuration for a specific task."""
    provider: str
    model: str
    temperature: float
    max_tokens: int


class TaskModelRegistry:
    """
    Maps tasks to their optimal model configurations.
    
    Different tasks have different requirements:
    - Generation: Higher quality, more tokens, moderate temperature
    - Classification: Fast, cheap, low temperature
    - Embeddings: Specific embedding models
    - Summarization: Moderate quality, higher token limit
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self._load_from_file(config_path)
        else:
            self._load_defaults()
    
    def _load_defaults(self):
        """Default task-to-model mapping."""
        self.tasks: Dict[str, TaskModelConfig] = {
            "generation": TaskModelConfig(
                provider="openai",
                model="gpt-4o",
                temperature=0.7,
                max_tokens=2000,
            ),
            "classification": TaskModelConfig(
                provider="openai",
                model="gpt-4o-mini",
                temperature=0.0,  # Deterministic for classification
                max_tokens=100,   # Classifications are short
            ),
            "summarization": TaskModelConfig(
                provider="openai",
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=500,
            ),
            "embedding": TaskModelConfig(
                provider="openai",
                model="text-embedding-3-small",
                temperature=0.0,  # N/A for embeddings, but kept for consistency
                max_tokens=0,     # N/A for embeddings
            ),
            "reranking": TaskModelConfig(
                provider="cohere",
                model="rerank-english-v3.0",
                temperature=0.0,
                max_tokens=0,
            ),
        }
    
    def _load_from_file(self, path: str):
        """Load task mappings from YAML."""
        with open(path) as f:
            config = yaml.safe_load(f)
        
        self.tasks = {}
        for task_name, task_config in config.get("tasks", {}).items():
            self.tasks[task_name] = TaskModelConfig(
                provider=task_config["provider"],
                model=task_config["model"],
                temperature=task_config.get("temperature", 0.7),
                max_tokens=task_config.get("max_tokens", 1000),
            )
    
    def get_config(self, task: str) -> TaskModelConfig:
        """Get model config for a specific task."""
        if task not in self.tasks:
            raise ValueError(f"Unknown task: {task}. Available: {list(self.tasks.keys())}")
        return self.tasks[task]
    
    def get_client(self, task: str):
        """Get a configured client for a specific task."""
        from clients.factory import create_llm_client
        from config.llm_config import LLMConfig
        
        task_config = self.get_config(task)
        
        llm_config = LLMConfig(
            provider=task_config.provider,
            model=task_config.model,
            temperature=task_config.temperature,
            max_tokens=task_config.max_tokens,
        )
        
        return create_llm_client(llm_config)
```

**Config file example:**

```yaml
# config/task_models.yaml
tasks:
  generation:
    provider: openai
    model: gpt-4o-2024-08-06
    temperature: 0.7
    max_tokens: 2000
    
  classification:
    provider: openai
    model: gpt-4o-mini-2024-07-18
    temperature: 0.0
    max_tokens: 100
    
  summarization:
    provider: anthropic
    model: claude-haiku-4-5
    temperature: 0.3
    max_tokens: 500
    
  embedding:
    provider: openai
    model: text-embedding-3-small
```

**Usage:**

```python
registry = TaskModelRegistry("config/task_models.yaml")

# Get client optimized for classification
classifier = registry.get_client("classification")
result = classifier.generate([
    {"role": "user", "content": f"Classify this text as POSITIVE or NEGATIVE: {text}"}
])

# Get client optimized for generation
generator = registry.get_client("generation")
result = generator.generate([
    {"role": "system", "content": "You are a creative writing assistant."},
    {"role": "user", "content": "Write a short story about..."}
])
```

---

## Fallback Chains: Resilience Through Model Diversity

When your primary model is rate-limited or down, fall back to alternatives:

```python
# clients/fallback_client.py

from typing import List, Dict, Any, Optional
from clients.llm_client import BaseLLMClient, LLMResponse
from clients.factory import create_llm_client
from config.llm_config import LLMConfig
import logging

logger = logging.getLogger(__name__)


class FallbackLLMClient(BaseLLMClient):
    """
    Client that tries multiple models in sequence.
    
    Use cases:
    - Primary model rate-limited → fall back to secondary
    - OpenAI outage → fall back to Anthropic
    - Cost optimization → try cheaper model first, escalate if needed
    
    Example chain:
        ["gpt-4o", "gpt-4o-mini", "claude-haiku-4-5"]
    """
    
    def __init__(
        self,
        model_configs: List[LLMConfig],
        retry_exceptions: tuple = (Exception,),
    ):
        """
        Args:
            model_configs: List of configs to try in order
            retry_exceptions: Exception types that trigger fallback
        """
        if not model_configs:
            raise ValueError("Must provide at least one model config")
        
        self.clients = [create_llm_client(config) for config in model_configs]
        self.model_configs = model_configs
        self.retry_exceptions = retry_exceptions
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Try each model in sequence until one succeeds.
        
        Returns response with metadata about which model was used.
        Raises last exception if all models fail.
        """
        last_exception: Optional[Exception] = None
        
        for i, client in enumerate(self.clients):
            model_name = self.model_configs[i].model
            
            try:
                logger.debug(f"Trying model: {model_name}")
                response = client.generate(messages, **kwargs)
                
                if i > 0:
                    # Log that we fell back
                    logger.warning(
                        f"Used fallback model {model_name} "
                        f"(primary models failed)"
                    )
                
                return response
                
            except self.retry_exceptions as e:
                logger.warning(f"Model {model_name} failed: {e}")
                last_exception = e
                continue
        
        # All models failed
        raise AllModelsFailedError(
            f"All {len(self.clients)} models failed. Last error: {last_exception}"
        ) from last_exception


class AllModelsFailedError(Exception):
    """Raised when all models in fallback chain fail."""
    pass


# Convenience constructor
def create_fallback_client(
    models: List[Dict[str, str]],
    **shared_config
) -> FallbackLLMClient:
    """
    Create fallback client from list of model specs.
    
    Usage:
        client = create_fallback_client([
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "anthropic", "model": "claude-haiku-4-5"},
        ])
    """
    configs = []
    for model_spec in models:
        config = LLMConfig(
            provider=model_spec["provider"],
            model=model_spec["model"],
            temperature=shared_config.get("temperature", 0.7),
            max_tokens=shared_config.get("max_tokens", 1000),
        )
        configs.append(config)
    
    return FallbackLLMClient(configs)
```

**Usage:**

```python
from clients.fallback_client import create_fallback_client

# Create client with fallback chain
client = create_fallback_client([
    {"provider": "openai", "model": "gpt-4o"},
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "anthropic", "model": "claude-haiku-4-5"},
])

# If OpenAI is down or rate-limited, automatically falls back
response = client.generate([
    {"role": "user", "content": "Hello, world!"}
])

print(f"Response from: {response.model}")
```

---

## Environment Variable Overrides for Deployment

Standard pattern for 12-factor apps:

```bash
# .env.development
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7

# .env.staging
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini-2024-07-18  # Pinned for consistency
LLM_TEMPERATURE=0.7

# .env.production
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-2024-08-06  # Best model, pinned version
LLM_TEMPERATURE=0.5  # Lower temperature for production

# Emergency fallback (set at runtime)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
```

**Kubernetes/Docker deployment:**

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: app
          env:
            - name: LLM_PROVIDER
              valueFrom:
                configMapKeyRef:
                  name: llm-config
                  key: provider
            - name: LLM_MODEL
              valueFrom:
                configMapKeyRef:
                  name: llm-config
                  key: model
            - name: LLM_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llm-secrets
                  key: api-key
```

---

## Complete Example: Putting It All Together

```python
# main.py

import os
from config.llm_config import LLMConfig
from clients.factory import create_llm_client


def main():
    # Load configuration
    # Priority: env vars > config file > defaults
    if os.path.exists("config/llm.yaml"):
        config = LLMConfig.from_file("config/llm.yaml")
    else:
        config = LLMConfig.from_environment()
    
    # Validate before using
    config.validate()
    
    # Create client
    client = create_llm_client(config)
    
    # Use client — no provider-specific code here
    response = client.generate([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ])
    
    print(f"Model: {response.model}")
    print(f"Response: {response.content}")
    print(f"Tokens: {response.usage}")


if __name__ == "__main__":
    main()
```

**Result:**

- Change `LLM_PROVIDER=anthropic` and `LLM_MODEL=claude-sonnet-4-5` in environment
- Run same code
- Now using Anthropic instead of OpenAI
- Zero code changes

---

## Summary

|Pattern|Purpose|
|---|---|
|**LLMConfig**|Centralize configuration, load from env/file, validate on startup|
|**LLMClient**|Unified interface, hide provider details|
|**Factory**|Create correct client from config|
|**TaskModelRegistry**|Different models for different tasks|
|**FallbackClient**|Resilience through model diversity|
|**Env overrides**|Deploy-time configuration without code changes|

**The key insight:** Your application code should never know which model or provider it's using. That's a deployment decision, not a code decision.

---

## What's Next

- **Note 3:** Prompt Versioning — how to version and manage prompts
- **Note 4:** Embedding Migration — blue-green deployment for vector indexes
- **Note 5:** A/B Testing and Shadow Mode — safely testing new models in production