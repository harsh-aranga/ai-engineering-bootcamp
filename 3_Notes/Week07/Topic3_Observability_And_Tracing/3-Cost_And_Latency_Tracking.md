# Note 3: Cost and Latency Tracking

## Documentation Reference

Code and pricing in this note verified against:

- OpenAI Pricing (https://platform.openai.com/docs/pricing) — verified March 2026
- Anthropic Pricing (https://docs.anthropic.com/claude/docs/pricing) — verified March 2026
- tiktoken GitHub (https://github.com/openai/tiktoken) and PyPI — version as of Oct 2025
- OpenAI Cookbook: How to Count Tokens (https://cookbook.openai.com/)

**Pricing disclaimer**: LLM pricing changes frequently. The prices in this note are accurate as of March 2026 but should be verified against current documentation before production use.

---

## Why Cost Tracking Matters for LLM Systems

Traditional compute costs are predictable. You pay for CPU time, memory, storage — resources you provision and control. LLM costs are fundamentally different.

### LLM Calls Are Expensive

A single RAG query might cost $0.005. That sounds negligible until you realize:

- 1,000 queries/day = $5/day = $150/month
- 10,000 queries/day = $50/day = $1,500/month
- With agentic patterns that loop, costs multiply

For context: a traditional API backend handling 10,000 requests/day might cost $20-50/month in compute. The same volume through LLMs can cost 30-75x more.

### Agentic Systems: Non-Deterministic Cost

With agentic systems, you don't control how many LLM calls happen. The agent decides:

```
User Query: "Compare our Q3 performance to competitors"

Possible execution paths:

Path A (simple):
├── RAG retrieval: 1 call
└── Generation: 1 call
Total: 2 calls, ~$0.003

Path B (agent decides more context needed):
├── RAG retrieval: 1 call
├── Agent: "Need competitor data"
├── Web search tool: 1 call
├── Agent: "Need historical context"
├── RAG retrieval: 1 call
├── Agent: "Let me verify these numbers"
├── Calculator tool: 1 call
└── Generation: 1 call
Total: 6 calls, ~$0.012

Path C (agent loops for self-correction):
├── 3 retrieval cycles
├── 4 reasoning steps
├── 2 tool calls
└── Final generation
Total: 10+ calls, ~$0.025
```

The same query can cost anywhere from $0.003 to $0.025 depending on the agent's decisions. Without tracking, you can't predict or optimize.

### Without Tracking: Surprise Bills

Common scenario: You launch with a $100/month budget estimate based on testing. Week one goes fine. Week two, usage grows. Week three, a viral post sends traffic 10x. Your bill is $2,000.

Cost tracking turns this into:

- Real-time visibility: "We're at 60% of budget with 10 days left"
- Per-query insight: "These 5% of queries consume 40% of budget"
- Optimization targets: "Switching to mini for simple queries saves 80%"

---

## Token Counting Basics

### Input vs. Output Tokens

Every LLM call is billed on two dimensions:

**Input tokens**: Everything you send to the model

- System prompt
- Conversation history
- Retrieved context (RAG chunks)
- Tool definitions
- The user query itself

**Output tokens**: Everything the model generates

- The response text
- Tool calls (structured JSON)
- Reasoning tokens (for reasoning models — billed as output)

### Pricing Asymmetry

Output tokens are more expensive than input tokens. This reflects the computational cost — generating tokens requires autoregressive inference, while processing input is parallelizable.

Current pricing examples (per 1M tokens):

|Model|Input|Output|Output/Input Ratio|
|---|---|---|---|
|GPT-4o-mini|$0.15|$0.60|4x|
|GPT-4o|$2.50|$10.00|4x|
|GPT-4.1|$2.00|$8.00|4x|
|Claude Haiku 4.5|$1.00|$5.00|5x|
|Claude Sonnet 4.6|$3.00|$15.00|5x|
|Claude Opus 4.6|$5.00|$25.00|5x|

**Implication**: Long verbose outputs are disproportionately expensive. A 500-token query with a 2,000-token response costs more in output than input, despite the response being "shorter" in perceived length.

### Token ≠ Word

A token is a subword unit, not a word. Common rules of thumb:

- English: ~1.3 tokens per word
- ~4 characters per token
- Code: Often more tokens per "word" (symbols, punctuation)

The phrase "Hello, how are you?" is 6 tokens, not 4 words.

---

## Using tiktoken for Token Counting

tiktoken is OpenAI's fast BPE tokenizer. Use it to count tokens before sending requests (cost estimation) or after (cost calculation).

### Installation

```bash
pip install tiktoken
```

### Basic Usage

```python
import tiktoken

# Get encoding for a specific model
enc = tiktoken.encoding_for_model("gpt-4o-mini")

# Count tokens in a string
text = "What is the refund policy for enterprise customers?"
tokens = enc.encode(text)
print(f"Token count: {len(tokens)}")  # 9 tokens

# Decode back to text (useful for debugging)
decoded = enc.decode(tokens)
print(decoded)  # "What is the refund policy for enterprise customers?"
```

**Doc reference**: tiktoken GitHub (https://github.com/openai/tiktoken)

### Encoding by Model

Different models use different tokenizers:

|Encoding|Models|
|---|---|
|`o200k_base`|GPT-4o, GPT-4o-mini, GPT-4.1|
|`cl100k_base`|GPT-4, GPT-3.5-turbo, text-embedding-3-*|

```python
# For GPT-4o family
enc = tiktoken.encoding_for_model("gpt-4o-mini")

# Or get encoding directly
enc = tiktoken.get_encoding("o200k_base")
```

### Counting Tokens for Chat Messages

Chat messages have structure overhead beyond raw text. Each message includes role markers and formatting:

```python
import tiktoken

def count_message_tokens(
    messages: list[dict],
    model: str = "gpt-4o-mini"
) -> int:
    """
    Count tokens for chat completion messages.
    
    Based on OpenAI Cookbook guidance. Note that exact token counting
    for messages may change between model versions — treat as estimate.
    """
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("o200k_base")
    
    # Overhead per message (role markers, formatting)
    tokens_per_message = 3
    
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(enc.encode(str(value)))
    
    # Every reply is primed with <|start|>assistant<|message|>
    num_tokens += 3
    
    return num_tokens


# Example
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What's the refund policy?"}
]

tokens = count_message_tokens(messages)
print(f"Input tokens: {tokens}")  # ~20 tokens
```

**Doc reference**: OpenAI Cookbook, "How to count tokens with tiktoken"

### Anthropic Token Counting

Anthropic uses a different tokenizer. For estimation, you can use the API's token counting endpoint or approximate with character count:

```python
def estimate_anthropic_tokens(text: str) -> int:
    """
    Rough estimate of Anthropic tokens.
    Anthropic uses a different tokenizer than OpenAI.
    For accurate counts, use Anthropic's token counting API.
    
    Rule of thumb: ~4 characters per token (similar to OpenAI).
    """
    return len(text) // 4
```

For production accuracy, use Anthropic's `count_tokens` endpoint or check the `usage` field in API responses.

---

## Cost Estimation Implementation

### Basic Cost Calculator

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelPricing:
    """Pricing per 1M tokens (in USD)."""
    input_per_million: float
    output_per_million: float
    cached_input_per_million: Optional[float] = None


# Pricing as of March 2026 — verify against current docs
MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI
    "gpt-4o-mini": ModelPricing(0.15, 0.60, 0.075),
    "gpt-4o": ModelPricing(2.50, 10.00, 1.25),
    "gpt-4.1": ModelPricing(2.00, 8.00, 0.50),
    "gpt-4.1-mini": ModelPricing(0.40, 1.60, 0.10),
    
    # Anthropic  
    "claude-haiku-4-5": ModelPricing(1.00, 5.00, 0.10),
    "claude-sonnet-4-6": ModelPricing(3.00, 15.00, 0.30),
    "claude-opus-4-6": ModelPricing(5.00, 25.00, 0.50),
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0
) -> float:
    """
    Estimate cost in USD for an LLM call.
    
    Args:
        model: Model identifier
        input_tokens: Number of input tokens (non-cached)
        output_tokens: Number of output tokens
        cached_input_tokens: Number of cached input tokens (prompt caching)
    
    Returns:
        Estimated cost in USD
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        raise ValueError(f"Unknown model: {model}. Add pricing to MODEL_PRICING.")
    
    input_cost = input_tokens * pricing.input_per_million / 1_000_000
    output_cost = output_tokens * pricing.output_per_million / 1_000_000
    
    cached_cost = 0.0
    if cached_input_tokens > 0 and pricing.cached_input_per_million:
        cached_cost = cached_input_tokens * pricing.cached_input_per_million / 1_000_000
    
    return input_cost + output_cost + cached_cost


# Example usage
cost = estimate_cost(
    model="gpt-4o-mini",
    input_tokens=1000,
    output_tokens=500
)
print(f"Estimated cost: ${cost:.6f}")  # $0.000450
```

### CostTracker Class

For production, accumulate costs across spans and track by multiple dimensions:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class LLMCallRecord:
    """Record of a single LLM call."""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    trace_id: Optional[str] = None
    span_name: Optional[str] = None
    feature: Optional[str] = None
    user_id: Optional[str] = None
    latency_ms: Optional[float] = None


class CostTracker:
    """
    Track LLM costs across calls.
    
    Accumulates costs and provides aggregations by model, feature, and user.
    """
    
    def __init__(self):
        self.calls: list[LLMCallRecord] = []
        self._total_cost: float = 0.0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
    
    def log_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        trace_id: Optional[str] = None,
        span_name: Optional[str] = None,
        feature: Optional[str] = None,
        user_id: Optional[str] = None,
        latency_ms: Optional[float] = None
    ) -> float:
        """
        Log an LLM call and return its cost.
        
        Returns:
            Cost of this call in USD
        """
        cost = estimate_cost(model, input_tokens, output_tokens)
        
        record = LLMCallRecord(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            trace_id=trace_id,
            span_name=span_name,
            feature=feature,
            user_id=user_id,
            latency_ms=latency_ms
        )
        
        self.calls.append(record)
        self._total_cost += cost
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        
        return cost
    
    @property
    def total_cost(self) -> float:
        return self._total_cost
    
    @property
    def total_tokens(self) -> int:
        return self._total_input_tokens + self._total_output_tokens
    
    def cost_by_model(self) -> dict[str, float]:
        """Aggregate costs by model."""
        by_model: dict[str, float] = {}
        for call in self.calls:
            by_model[call.model] = by_model.get(call.model, 0) + call.cost_usd
        return by_model
    
    def cost_by_feature(self) -> dict[str, float]:
        """Aggregate costs by feature."""
        by_feature: dict[str, float] = {}
        for call in self.calls:
            key = call.feature or "untagged"
            by_feature[key] = by_feature.get(key, 0) + call.cost_usd
        return by_feature
    
    def cost_by_user(self) -> dict[str, float]:
        """Aggregate costs by user."""
        by_user: dict[str, float] = {}
        for call in self.calls:
            key = call.user_id or "anonymous"
            by_user[key] = by_user.get(key, 0) + call.cost_usd
        return by_user
    
    def get_summary(self) -> dict:
        """Get summary statistics."""
        if not self.calls:
            return {"total_calls": 0, "total_cost_usd": 0}
        
        return {
            "total_calls": len(self.calls),
            "total_cost_usd": round(self._total_cost, 6),
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "avg_cost_per_call": round(self._total_cost / len(self.calls), 6),
            "cost_by_model": self.cost_by_model(),
            "cost_by_feature": self.cost_by_feature(),
        }


# Usage example
tracker = CostTracker()

# Log some calls
tracker.log_call(
    model="gpt-4o-mini",
    input_tokens=1500,
    output_tokens=800,
    feature="rag_query",
    span_name="generate_answer"
)

tracker.log_call(
    model="gpt-4o",
    input_tokens=500,
    output_tokens=200,
    feature="agent_decision",
    span_name="classify_intent"
)

print(json.dumps(tracker.get_summary(), indent=2))
```

---

## Adding Cost to LangSmith Traces

Integrate cost tracking with your tracing setup to see costs in the dashboard:

```python
import tiktoken
from langsmith import traceable
from langsmith.wrappers import wrap_openai
import openai

client = wrap_openai(openai.OpenAI())
tracker = CostTracker()


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Count tokens for a text string."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


@traceable(
    name="generate_with_cost",
    metadata={"tracks_cost": True}
)
def generate_with_cost(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    feature: str = "default"
) -> dict:
    """
    Generate completion with cost tracking.
    
    Returns response plus cost metadata.
    """
    import time
    start = time.perf_counter()
    
    response = client.chat.completions.create(
        model=model,
        messages=messages
    )
    
    latency_ms = (time.perf_counter() - start) * 1000
    
    # Extract token usage from response
    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    
    # Log to cost tracker
    cost = tracker.log_call(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        feature=feature,
        latency_ms=latency_ms
    )
    
    return {
        "content": response.choices[0].message.content,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "latency_ms": latency_ms
    }


@traceable(name="rag_query_with_cost")
def rag_query_with_cost(query: str, context: list[str]) -> dict:
    """RAG query with full cost tracking."""
    context_text = "\n\n".join(context)
    
    messages = [
        {"role": "system", "content": f"Answer based on this context:\n{context_text}"},
        {"role": "user", "content": query}
    ]
    
    result = generate_with_cost(
        messages=messages,
        model="gpt-4o-mini",
        feature="rag_query"
    )
    
    return result


# After running queries, check costs
print(f"Session cost: ${tracker.total_cost:.4f}")
print(f"Cost by feature: {tracker.cost_by_feature()}")
```

The cost metadata appears in LangSmith traces, making it visible in the dashboard alongside timing and token information.

---

## Latency Profiling

Cost isn't the only metric. Latency determines user experience.

### Per-Span Latency

Track latency at each step to find bottlenecks:

```python
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class LatencyRecord:
    span_name: str
    latency_ms: float
    parent_span: Optional[str] = None


class LatencyProfiler:
    """Profile latency across spans."""
    
    def __init__(self):
        self.records: list[LatencyRecord] = []
    
    def record(
        self,
        span_name: str,
        latency_ms: float,
        parent_span: Optional[str] = None
    ):
        self.records.append(LatencyRecord(
            span_name=span_name,
            latency_ms=latency_ms,
            parent_span=parent_span
        ))
    
    def get_breakdown(self) -> dict[str, dict]:
        """Get latency stats per span."""
        by_span: dict[str, list[float]] = {}
        
        for record in self.records:
            if record.span_name not in by_span:
                by_span[record.span_name] = []
            by_span[record.span_name].append(record.latency_ms)
        
        stats = {}
        for span, latencies in by_span.items():
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            stats[span] = {
                "count": n,
                "mean_ms": sum(sorted_lat) / n,
                "p50_ms": sorted_lat[n // 2],
                "p95_ms": sorted_lat[int(n * 0.95)] if n >= 20 else sorted_lat[-1],
                "p99_ms": sorted_lat[int(n * 0.99)] if n >= 100 else sorted_lat[-1],
                "min_ms": sorted_lat[0],
                "max_ms": sorted_lat[-1],
            }
        
        return stats
    
    def identify_bottleneck(self) -> str:
        """Identify the slowest span by mean latency."""
        stats = self.get_breakdown()
        if not stats:
            return "No data"
        
        slowest = max(stats.items(), key=lambda x: x[1]["mean_ms"])
        return f"{slowest[0]}: {slowest[1]['mean_ms']:.0f}ms mean"


# Usage
profiler = LatencyProfiler()

# Simulate recording latencies
profiler.record("query_transform", 85.2)
profiler.record("embed_query", 45.1)
profiler.record("vector_search", 120.5)
profiler.record("rerank", 95.3)
profiler.record("generate", 1250.8)

print(f"Bottleneck: {profiler.identify_bottleneck()}")
# Output: "Bottleneck: generate: 1251ms mean"
```

### Percentiles: Averages Lie

Mean latency hides tail behavior. A system with 200ms mean might have:

- p50: 150ms (half of requests)
- p95: 500ms (1 in 20 requests)
- p99: 2000ms (1 in 100 requests)

Your users hitting p99 have a terrible experience. Always track percentiles:

```
Example RAG system latency:

Span            | Mean   | p50    | p95    | p99
----------------|--------|--------|--------|--------
query_transform |   80ms |   75ms |  150ms |  200ms
retrieval       |  120ms |  100ms |  250ms |  400ms
rerank          |  100ms |   90ms |  180ms |  300ms
generate        | 1200ms | 1100ms | 2000ms | 3500ms  ← High variance
----------------|--------|--------|--------|--------
Total           | 1500ms | 1365ms | 2580ms | 4400ms
```

The generate step dominates both mean and variance. Users hitting p99 wait 3.5 seconds for generation alone.

---

## Bottleneck Identification Patterns

Different bottlenecks require different optimization strategies:

### Generation Slow

**Symptom**: `generate` span dominates latency (usually 60-80% of total)

**Why**: LLM inference is inherently slow. You're waiting for autoregressive token generation.

**Options**:

- **Reduce context size**: Fewer input tokens = faster processing. Aggressive reranking, shorter system prompts.
- **Reduce output length**: Set `max_tokens` lower. Prompt for concise responses.
- **Use faster model**: GPT-4o-mini is faster than GPT-4o. Claude Haiku is faster than Sonnet.
- **Streaming**: Doesn't reduce total latency but improves perceived responsiveness.

**What you can't do**: Make the model itself faster. That's infrastructure, not application.

### Retrieval Slow

**Symptom**: `retrieval` span takes >500ms

**Why**: Vector search, embedding generation, or network latency to vector store.

**Options**:

- **Embedding caching**: Cache embeddings for common queries.
- **Index optimization**: Ensure vector store has proper indexes. Use approximate nearest neighbor (ANN) instead of exact.
- **Reduce top_k**: Retrieving 50 chunks is slower than 10.
- **Collocate**: Put vector store in same region as application.

### Reranking Slow

**Symptom**: `rerank` span takes >200ms

**Why**: Cross-encoder models are compute-intensive, especially with many candidates.

**Options**:

- **Reduce candidates**: Rerank top-10, not top-50.
- **Batch efficiently**: Process candidates in parallel batches.
- **Smaller reranker**: Use a faster cross-encoder model.
- **Skip for simple queries**: Not every query needs reranking.

### Tool Calls Slow

**Symptom**: `tool_call:*` spans are slow

**Why**: External API latency, rate limiting, or expensive computation.

**Options**:

- **Async execution**: Call multiple tools in parallel when possible.
- **Caching**: Cache tool results for repeated queries.
- **Timeout and fallback**: Don't let one slow tool block everything.
- **Precompute**: If tool results are predictable, precompute offline.

---

## Cost vs. Quality Trade-offs

Cost optimization always trades against something — usually quality or capability.

### Model Selection

|Trade-off|Cheaper Option|Quality Impact|
|---|---|---|
|gpt-4o vs gpt-4o-mini|gpt-4o-mini (16x cheaper)|Noticeable on complex reasoning|
|claude-opus vs claude-sonnet|claude-sonnet (5x cheaper)|Matters for nuanced tasks|
|claude-sonnet vs claude-haiku|claude-haiku (3x cheaper)|Fine for simple classification|

**Strategy**: Route by query complexity. Use mini/haiku for simple queries, escalate to larger models only when needed.

```python
def select_model(query_complexity: str) -> str:
    """Route to appropriate model by complexity."""
    if query_complexity == "simple":
        return "gpt-4o-mini"  # $0.15/$0.60 per M
    elif query_complexity == "moderate":
        return "gpt-4o"  # $2.50/$10.00 per M
    else:  # complex
        return "gpt-4.1"  # $2.00/$8.00 per M
```

### Retrieval Depth

|Trade-off|Cheaper Option|Quality Impact|
|---|---|---|
|More chunks|Fewer chunks|Risk missing relevant info|
|Full documents|Truncated chunks|Lose context|
|Multiple retrieval cycles|Single retrieval|Miss follow-up info|

**Strategy**: Start with minimal retrieval, expand only if confidence is low.

### RAG vs. Agentic Patterns

| Pattern                 | Cost   | When to Use                                |
| ----------------------- | ------ | ------------------------------------------ |
| Simple RAG              | $      | Questions with clear answers in corpus     |
| RAG + reranking         | $$     | When retrieval precision matters           |
| Agentic RAG (iterative) | $$$    | Complex queries requiring multiple lookups |
| Full agent with tools   | COSTLY | Open-ended tasks, research, synthesis      |

**Strategy**: Don't default to agentic patterns. Simple RAG handles 80% of queries at 20% of the cost.

### Making Informed Decisions

Cost data enables evidence-based optimization:

```
Analysis of last 1,000 queries:

Query Type     | Count | Avg Cost | Avg Quality Score
---------------|-------|----------|------------------
Simple lookup  |   600 | $0.002   | 4.5/5
Comparison     |   250 | $0.008   | 4.2/5
Synthesis      |   100 | $0.025   | 3.9/5
Research       |    50 | $0.045   | 4.0/5

Observations:
1. Simple lookups (60% of volume) are cheap and high quality
2. Research queries (5% of volume) consume 22% of budget
3. Synthesis quality is lowest — more context might help

Action:
- Keep simple lookups on gpt-4o-mini
- For synthesis, try adding one more retrieval cycle — cost +$0.005, quality +0.3?
- For research, set budget cap and warn users
```

Without cost tracking, you'd be guessing.

---

## Quick Reference: Cost Formulas

### Per-Query Cost

```
cost = (input_tokens × input_price) + (output_tokens × output_price)
```

### Estimating RAG Query Cost

```
Typical RAG query:
├── System prompt: ~200 tokens
├── Retrieved context: ~2000 tokens (5 chunks × 400 tokens)
├── User query: ~50 tokens
├── Total input: ~2250 tokens
│
└── Response: ~500 tokens

Cost (gpt-4o-mini):
= (2250 × $0.15/1M) + (500 × $0.60/1M)
= $0.000338 + $0.000300
= $0.000638 per query
= ~$0.64 per 1,000 queries
```

### Estimating Agent Cost

```
Typical agent execution (3 tool calls):
├── Initial routing: 300 input, 50 output
├── Tool call 1 (RAG): 2000 input, 400 output
├── Tool call 2 (search): 1500 input, 300 output
├── Final synthesis: 3000 input, 800 output
│
└── Total: 6800 input, 1550 output

Cost (gpt-4o-mini):
= (6800 × $0.15/1M) + (1550 × $0.60/1M)
= $0.00102 + $0.00093
= $0.00195 per agent run
= ~$1.95 per 1,000 runs
```

---

## What's Next

With cost and latency tracked, you have visibility into system behavior. But visibility isn't enough — you need to act on anomalies. The next note covers monitoring patterns, alerting on cost thresholds, and building dashboards for production observability.