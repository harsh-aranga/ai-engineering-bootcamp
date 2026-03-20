# Note 1: LLM Cost Anatomy — Where the Money Goes

## Introduction: Why LLM Costs Are Different

Traditional compute pricing is straightforward: you pay for CPU hours, memory, or requests. A database query costs roughly the same whether it returns "yes" or a 10KB JSON blob.

LLM pricing breaks this mental model completely:

```
Traditional API:
  POST /api/users → $0.0001 per request (fixed)

LLM API:
  POST /v1/chat/completions → $0.000003 per INPUT token
                            → $0.000015 per OUTPUT token
                            → Variable based on what you send AND what comes back
```

This per-token model creates three fundamental cost dynamics you must internalize:

### 1. Input vs. Output Pricing Asymmetry

Output tokens are typically 2-5x more expensive than input tokens. This isn't arbitrary—generation is computationally harder than processing input.

**Current pricing (as of early 2026, per 1M tokens):**

|Model|Input|Output|Output/Input Ratio|
|---|---|---|---|
|GPT-4o|$2.50|$10.00|4x|
|GPT-4o-mini|$0.15|$0.60|4x|
|Claude Sonnet 4.6|$3.00|$15.00|5x|
|Claude Haiku 4.5|$1.00|$5.00|5x|
|Claude Opus 4.6|$5.00|$25.00|5x|

_Sources: OpenAI Pricing page (platform.openai.com/docs/pricing), Anthropic Pricing docs (platform.claude.com/docs/en/about-claude/pricing)_

**The implication**: Long prompts hurt, but verbose responses hurt more. A 2000-token input with a 500-token output costs less than a 500-token input with a 2000-token output.

### 2. Model Tier Price Gaps

The gap between model tiers is massive—often 10-20x:

```
GPT-4o-mini:  $0.15 input / $0.60 output  (per 1M tokens)
GPT-4o:       $2.50 input / $10.00 output (per 1M tokens)
                    ↑
              16.7x more expensive on input
              16.7x more expensive on output
```

For Anthropic:

```
Haiku 4.5:    $1.00 input / $5.00 output
Sonnet 4.6:   $3.00 input / $15.00 output  (3x Haiku)
Opus 4.6:     $5.00 input / $25.00 output  (5x Haiku)
```

**The implication**: Model selection is your biggest cost lever. Using GPT-4o for query classification when GPT-4o-mini works is burning money.

### 3. Embeddings Are Cheap, Generation Is Expensive

Embedding models are dramatically cheaper because they only produce fixed-size vectors, not variable-length text:

```
text-embedding-3-small: $0.02 per 1M tokens (input only, no output cost)
text-embedding-3-large: $0.13 per 1M tokens

Compare to generation:
GPT-4o-mini output:     $0.60 per 1M tokens (30x embedding cost)
GPT-4o output:          $10.00 per 1M tokens (500x embedding cost)
```

_Source: OpenAI Pricing page, embedding models section_

**The implication**: In a RAG system, the retrieval step (embeddings) is nearly free compared to the generation step.

---

## Breaking Down Cost Per Request

A typical RAG + Agent request involves multiple LLM calls. Here's where the money actually goes:

### Anatomy of a Research Assistant Query

```
User query: "What were Apple's main revenue drivers in Q3 2024?"

Step 1: Query Embedding
├── Input: ~20 tokens (the query)
├── Model: text-embedding-3-small
└── Cost: $0.02 / 1M × 20 = $0.0000004
    (Essentially free)

Step 2: Chunk Embeddings (already indexed, but for reference)
├── Input: ~500 tokens per chunk × 10 chunks retrieved
├── Model: text-embedding-3-small  
└── Cost: Already paid at index time

Step 3: Query Classification/Routing (if using LLM)
├── Input: ~100 tokens (query + classification prompt)
├── Output: ~10 tokens ("category: financial_analysis")
├── Model: GPT-4o-mini
└── Cost: ($0.15 × 100 + $0.60 × 10) / 1M = $0.000021

Step 4: Generation (THE BIG ONE)
├── Input: ~3000 tokens
│   ├── System prompt: ~200 tokens
│   ├── Retrieved chunks: ~2500 tokens (5 chunks × 500 tokens)
│   └── User query + formatting: ~300 tokens
├── Output: ~500 tokens (the actual answer)
├── Model: GPT-4o-mini
└── Cost: ($0.15 × 3000 + $0.60 × 500) / 1M = $0.00075

TOTAL: ~$0.00077 per query
```

**Key insight**: Generation dominates. The embedding step is 0.05% of the cost. The generation step is 97% of the cost.

### The Same Query with GPT-4o

```
Step 4: Generation (with GPT-4o instead)
├── Input: ~3000 tokens
├── Output: ~500 tokens
├── Model: GPT-4o
└── Cost: ($2.50 × 3000 + $10.00 × 500) / 1M = $0.0125

TOTAL: ~$0.0126 per query (16x more expensive)
```

At 10,000 queries/day:

- GPT-4o-mini: ~$7.70/day
- GPT-4o: ~$126/day

---

## Where Costs Hide in Agentic Systems

Agents are cost landmines. Unlike deterministic pipelines, agents make decisions—and each decision is an LLM call.

### Hidden Cost #1: Reasoning Loops

```python
# Simple pipeline: predictable cost
def pipeline_answer(query):
    chunks = retrieve(query)      # 1 embedding call
    answer = generate(query, chunks)  # 1 LLM call
    return answer
# Cost: ~2 LLM operations per query

# Agent: unpredictable cost
def agent_answer(query):
    while not done:
        thought = llm.think(state)           # LLM call
        action = llm.decide_action(thought)  # LLM call
        result = execute_tool(action)        # May trigger more LLM calls
        state = llm.update_state(result)     # LLM call
    return llm.synthesize(state)             # LLM call
# Cost: 4-20+ LLM operations per query
```

A ReAct agent doing web research might:

1. Analyze the query (1 call)
2. Decide to search (1 call)
3. Process search results (1 call)
4. Decide to search again with refined query (1 call)
5. Process new results (1 call)
6. Decide to fetch a specific page (1 call)
7. Extract information from page (1 call)
8. Synthesize final answer (1 call)

That's 8 LLM calls for one user query. If each call averages 1000 input + 200 output tokens at GPT-4o-mini rates:

```
8 calls × ($0.15 × 1000 + $0.60 × 200) / 1M = $0.00216 per query
```

Compare to single-shot: $0.00077. The agent is 2.8x more expensive—and this is a simple case.

### Hidden Cost #2: Tool Call Overhead

Every tool decision has a cost, even when the tool doesn't use LLMs:

```python
# Tool definitions inflate input tokens
tools = [
    {
        "name": "search_documents",
        "description": "Search internal documents for relevant information",
        "parameters": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Maximum results to return"}
        }
    },
    # ... 5 more tools
]
# Each tool definition: ~50-100 tokens
# 6 tools: ~400 tokens added to EVERY request
```

At $0.15/1M input tokens, 400 extra tokens per request across 100,000 requests/day = $6/day just for tool definitions.

### Hidden Cost #3: Retry Logic

Failed calls still cost money:

```python
def llm_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = llm.generate(prompt)
            if is_valid(response):
                return response
            # Invalid response: we paid, got nothing useful
        except RateLimitError:
            # We might have partially paid
            time.sleep(backoff)
        except APIError:
            # Depends on when error occurred
            continue
    raise MaxRetriesExceeded()
```

If 5% of requests need retries and each retry costs the same as the original:

```
100,000 requests × 5% retry rate × $0.001 average cost = $5/day in "waste"
```

### Hidden Cost #4: Verbose Context (The RAG Trap)

RAG systems retrieve chunks to ground responses. But chunks are input tokens:

```
Conservative RAG:
- 3 chunks × 300 tokens = 900 tokens input

Aggressive RAG:
- 10 chunks × 500 tokens = 5000 tokens input

Cost difference (GPT-4o):
- Conservative: $2.50 × 900 / 1M = $0.00225
- Aggressive: $2.50 × 5000 / 1M = $0.0125

5.5x cost increase for "more context"
```

More chunks ≠ better answers. Often 3 highly relevant chunks beat 10 mediocre ones—at lower cost.

---

## Measuring Your Actual Costs

### Token Counting with tiktoken

`tiktoken` is OpenAI's official tokenizer. Use it to count tokens _before_ making API calls:

```python
import tiktoken

# Get the encoding for your model
# o200k_base: GPT-4o, GPT-4o-mini
# cl100k_base: GPT-4, GPT-3.5-turbo, text-embedding models
encoding = tiktoken.encoding_for_model("gpt-4o")

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in a string."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Example
prompt = "Explain the key revenue drivers for Apple in Q3 2024."
tokens = count_tokens(prompt)
print(f"Tokens: {tokens}")  # Tokens: 14
```

_Source: OpenAI tiktoken GitHub (github.com/openai/tiktoken), OpenAI Cookbook token counting example_

### Pre-Request Cost Estimation

```python
import tiktoken
from dataclasses import dataclass

@dataclass
class CostEstimate:
    input_tokens: int
    estimated_output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    model: str

class TokenCostEstimator:
    """Estimate costs before making API calls."""
    
    # Prices per 1M tokens (update as needed)
    PRICES = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
        "text-embedding-3-large": {"input": 0.13, "output": 0.0},
        # Anthropic models
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
        "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    }
    
    def __init__(self):
        self._encodings = {}
    
    def _get_encoding(self, model: str):
        """Cache encodings for performance."""
        if model not in self._encodings:
            try:
                self._encodings[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback for unknown models
                self._encodings[model] = tiktoken.get_encoding("cl100k_base")
        return self._encodings[model]
    
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens in text for a specific model."""
        encoding = self._get_encoding(model)
        return len(encoding.encode(text))
    
    def estimate_cost(
        self,
        input_text: str,
        model: str,
        estimated_output_tokens: int = 500
    ) -> CostEstimate:
        """
        Estimate cost for a request.
        
        Args:
            input_text: The full prompt (system + user + context)
            model: Model identifier
            estimated_output_tokens: Expected output length
            
        Returns:
            CostEstimate with breakdown
        """
        if model not in self.PRICES:
            raise ValueError(f"Unknown model: {model}. Add to PRICES dict.")
        
        input_tokens = self.count_tokens(input_text, model)
        prices = self.PRICES[model]
        
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (estimated_output_tokens / 1_000_000) * prices["output"]
        
        return CostEstimate(
            input_tokens=input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
            model=model
        )

# Usage
estimator = TokenCostEstimator()

# Estimate a RAG query
system_prompt = "You are a financial analyst assistant..."  # ~50 tokens
retrieved_chunks = "Apple reported Q3 2024 revenue of..."    # ~2000 tokens
user_query = "What were the main revenue drivers?"           # ~10 tokens

full_prompt = f"{system_prompt}\n\nContext:\n{retrieved_chunks}\n\nQuery: {user_query}"

estimate = estimator.estimate_cost(
    input_text=full_prompt,
    model="gpt-4o-mini",
    estimated_output_tokens=400
)

print(f"Input tokens: {estimate.input_tokens}")
print(f"Estimated output: {estimate.estimated_output_tokens}")
print(f"Input cost: ${estimate.input_cost:.6f}")
print(f"Output cost: ${estimate.output_cost:.6f}")
print(f"Total estimated: ${estimate.total_cost:.6f}")
```

### Tracking Actual Costs from API Responses

Both OpenAI and Anthropic return usage in responses. Track it:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json

@dataclass
class RequestCost:
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    component: str  # "embedding", "classification", "generation", etc.
    user_id: Optional[str] = None
    request_id: Optional[str] = None

class CostTracker:
    """Track actual costs from API responses."""
    
    PRICES = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    }
    
    def __init__(self):
        self.costs: list[RequestCost] = []
    
    def record_openai_response(
        self,
        response,  # OpenAI response object
        component: str,
        user_id: Optional[str] = None
    ) -> RequestCost:
        """Extract cost from OpenAI response and record it."""
        usage = response.usage
        model = response.model
        
        # Handle model name variations (e.g., "gpt-4o-mini-2024-07-18")
        model_key = self._normalize_model_name(model)
        
        prices = self.PRICES.get(model_key, {"input": 0, "output": 0})
        
        cost = (
            (usage.prompt_tokens / 1_000_000) * prices["input"] +
            (usage.completion_tokens / 1_000_000) * prices["output"]
        )
        
        record = RequestCost(
            timestamp=datetime.now(),
            model=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            cost_usd=cost,
            component=component,
            user_id=user_id,
            request_id=response.id
        )
        
        self.costs.append(record)
        return record
    
    def record_anthropic_response(
        self,
        response,  # Anthropic response object
        component: str,
        user_id: Optional[str] = None
    ) -> RequestCost:
        """Extract cost from Anthropic response and record it."""
        usage = response.usage
        model = response.model
        
        model_key = self._normalize_model_name(model)
        prices = self.PRICES.get(model_key, {"input": 0, "output": 0})
        
        cost = (
            (usage.input_tokens / 1_000_000) * prices["input"] +
            (usage.output_tokens / 1_000_000) * prices["output"]
        )
        
        record = RequestCost(
            timestamp=datetime.now(),
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            component=component,
            user_id=user_id,
            request_id=response.id
        )
        
        self.costs.append(record)
        return record
    
    def _normalize_model_name(self, model: str) -> str:
        """Normalize model names to match PRICES keys."""
        # Handle versioned model names
        if model.startswith("gpt-4o-mini"):
            return "gpt-4o-mini"
        if model.startswith("gpt-4o"):
            return "gpt-4o"
        if "claude" in model.lower() and "sonnet" in model.lower():
            return "claude-sonnet-4-6"
        if "claude" in model.lower() and "haiku" in model.lower():
            return "claude-haiku-4-5"
        return model
    
    def get_breakdown_by_component(self) -> dict:
        """Get cost breakdown by component (embedding, generation, etc.)."""
        breakdown = {}
        for cost in self.costs:
            if cost.component not in breakdown:
                breakdown[cost.component] = {
                    "total_cost": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "request_count": 0
                }
            breakdown[cost.component]["total_cost"] += cost.cost_usd
            breakdown[cost.component]["total_input_tokens"] += cost.input_tokens
            breakdown[cost.component]["total_output_tokens"] += cost.output_tokens
            breakdown[cost.component]["request_count"] += 1
        return breakdown
    
    def get_total_cost(self) -> float:
        """Get total cost across all tracked requests."""
        return sum(c.cost_usd for c in self.costs)

# Usage with Week 7's observability
tracker = CostTracker()

# After each API call
# response = client.responses.create(...)
# tracker.record_openai_response(response, component="generation", user_id="user_123")

# At end of session or periodically
# breakdown = tracker.get_breakdown_by_component()
# print(json.dumps(breakdown, indent=2))
```

---

## Cost Variability in Agents

### Deterministic Pipeline: Predictable Cost

```
Query → Embed → Retrieve → Generate → Response

Every query follows the same path:
- 1 embedding call: ~$0.0000004
- 1 generation call: ~$0.00075
- Total: ~$0.00075 ± 10%

Variance comes only from:
- Query length (minor)
- Response length (moderate)
```

### Agentic System: Unpredictable Cost

```
Query → Agent Loop (?? iterations) → Response

Simple query: "What time is it in Tokyo?"
- 1 reasoning step → 1 tool call → done
- Cost: ~$0.0003

Complex query: "Compare Apple and Microsoft's AI strategies, 
               including recent acquisitions and partnerships"
- 5 reasoning steps
- 8 search calls
- 3 page fetches
- 2 synthesis steps
- Cost: ~$0.015

50x cost difference for queries that look similarly complex to users.
```

### Visualizing Cost Distribution

```
Simple RAG Pipeline:
Cost per query: $0.0006 - $0.0010
                ████████████████████████ (tight distribution)

Agent System:
Cost per query: $0.0003 - $0.0200
                ██ (simple)
                ████████ (moderate)
                ████████████████████████████████████████ (complex)
                (wide distribution, long tail)
```

**Production implication**: You can't just multiply "average cost × expected queries" for agents. You need percentile analysis:

- P50 (median): $0.002
- P90: $0.008
- P99: $0.025
- P99.9: $0.100 (runaway queries)

---

## The 80/20 of LLM Costs

Before optimizing, identify your actual cost drivers. Don't optimize embedding costs when generation is 99% of spend.

### Typical RAG System Cost Breakdown

```
Component               | % of Total Cost | Optimization Priority
------------------------|-----------------|----------------------
Generation (LLM)        | 85-95%          | HIGH - model selection, 
                        |                 | output length, caching
Retrieved context       | 3-10%           | MEDIUM - fewer/smaller chunks
Query embedding         | 0.1-1%          | LOW - already cheap
Classification/routing  | 1-3%            | LOW unless high volume
```

### Typical Agent System Cost Breakdown

```
Component               | % of Total Cost | Optimization Priority
------------------------|-----------------|----------------------
Reasoning loops         | 40-60%          | HIGH - loop limits, early exit
Tool result processing  | 20-30%          | MEDIUM - summarize tool outputs
Final synthesis         | 15-25%          | MEDIUM - model selection
Tool definitions        | 1-5%            | LOW - one-time per request
```

### Finding Your Cost Drivers

Use the CostTracker above with your actual traffic:

```python
# After running 1000 queries through your system
breakdown = tracker.get_breakdown_by_component()

# Sort by cost
sorted_breakdown = sorted(
    breakdown.items(), 
    key=lambda x: x[1]["total_cost"], 
    reverse=True
)

print("Cost Breakdown (Top Components):")
total = sum(b["total_cost"] for _, b in breakdown.items())
for component, stats in sorted_breakdown:
    pct = (stats["total_cost"] / total) * 100
    print(f"  {component}: ${stats['total_cost']:.4f} ({pct:.1f}%)")
    print(f"    Avg tokens: {stats['total_input_tokens'] / stats['request_count']:.0f} in, "
          f"{stats['total_output_tokens'] / stats['request_count']:.0f} out")
```

---

## Key Takeaways

1. **Output tokens cost 4-5x more than input tokens** — optimize response length before prompt length
    
2. **Model selection is your biggest lever** — GPT-4o-mini vs GPT-4o is a 16x cost difference
    
3. **Embeddings are nearly free** — don't optimize embedding costs, optimize generation costs
    
4. **Agent costs are unpredictable** — budget for P99, not average; implement loop limits
    
5. **Measure before optimizing** — use component-level tracking to find actual cost drivers
    
6. **Hidden costs accumulate**:
    
    - Tool definitions in every request
    - Retry logic on failures
    - Verbose RAG context
    - Agent reasoning loops

---

## What's Next

With a clear picture of where costs come from, the next notes cover:

- **Note 2**: Model routing strategies (use cheap models for cheap tasks)
- **Note 3**: Token budgeting and context management
- **Note 4**: Rate limiting implementation
- **Note 5**: Graceful degradation when limits hit

---

## References

- OpenAI Pricing: https://platform.openai.com/docs/pricing
- Anthropic Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- tiktoken GitHub: https://github.com/openai/tiktoken
- OpenAI Cookbook - Token Counting: https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken