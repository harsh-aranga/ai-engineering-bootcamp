# Failure Modes in LLM Systems: A Taxonomy

## Why LLM Systems Fail Differently

Traditional distributed systems fail in predictable ways: network timeouts, database deadlocks, disk full errors. You get an exception, you handle it, you move on. LLM systems inherit all these failure modes and add entirely new categories that don't exist in conventional software.

### The Four Properties That Change Everything

**1. Non-Deterministic Outputs**

The same input can produce different outputs across invocations. This isn't a bug—it's fundamental to how LLMs work. Temperature settings, internal model state, and sampling randomness mean you can't write tests that assert exact output equality.

```python
# Traditional system: deterministic
def calculate_tax(amount: float, rate: float) -> float:
    return amount * rate  # Always the same result

# LLM system: non-deterministic
def summarize_document(doc: str) -> str:
    response = llm.invoke(f"Summarize: {doc}")
    return response  # Different each time, even with temperature=0
```

Even with `temperature=0`, outputs can vary slightly due to floating-point operations across different hardware, batching effects, and model updates by providers. You can't test for equality—you test for semantic equivalence or structural properties.

**2. External API Dependencies**

Your system's reliability is bounded by your least reliable external dependency. Most LLM applications depend on:

- LLM provider API (OpenAI, Anthropic, etc.)
- Embedding API (often different from LLM provider)
- Vector database (Pinecone, Qdrant, Chroma, etc.)
- Potentially: reranking APIs, web search APIs, tool APIs

Each adds a failure point. Each has its own rate limits, SLAs, and degradation patterns. Your 99.9% uptime means nothing if OpenAI has a bad day.

**3. Cascading Failures Across Pipeline Stages**

A RAG pipeline has multiple stages where failure at one point can poison everything downstream:

```
Query → Embedding → Retrieval → Reranking → Generation → Response
         ↓           ↓           ↓            ↓
       (fail)     (fail)      (fail)       (fail)
         ↓           ↓           ↓            ↓
    No vectors   No context   Wrong order  Hallucination
```

An embedding API timeout doesn't just fail—it means no retrieval, which means the LLM generates without context, which means confident hallucination. The user gets a wrong answer, not an error.

**4. Silent Failures**

This is the insidious one. Traditional systems crash loudly. LLM systems can fail silently—returning plausible-looking but wrong answers with no exception, no error code, nothing in your logs.

|Failure Type|Traditional System|LLM System|
|---|---|---|
|Wrong output|Exception or assertion failure|Confident wrong answer|
|Partial failure|Error propagates|Plausible degraded response|
|Timeout|Socket exception|Truncated response looks complete|
|Resource limit|Out of memory error|Response just stops mid-sentence|

Silent failures require fundamentally different detection strategies: semantic validation, confidence scoring, output structure verification.

---

## The Failure Taxonomy

### Category 1: External Service Failures

These are the most familiar—your dependencies are unavailable or misbehaving.

#### LLM API Failures

|Failure|Symptoms|Typical HTTP Status|Retryable?|
|---|---|---|---|
|API down|Connection refused, 503|503 Service Unavailable|Yes (with backoff)|
|Request timeout|No response within limit|N/A (client-side)|Yes|
|Rate limit exceeded|Request rejected|429 Too Many Requests|Yes (after delay)|
|Authentication failure|Invalid credentials|401/403|No|
|Invalid request|Malformed input|400 Bad Request|No (fix input first)|
|Server error|Internal provider issue|500/502/503|Yes (with backoff)|

**Provider Degradation: The Subtle Killer**

Sometimes the API doesn't fail—it just gets slow. Response times go from 500ms to 5 seconds. Your system doesn't crash, but user experience craters and timeouts start cascading.

```python
# Degradation detection
class LatencyTracker:
    def __init__(self, window_size: int = 100):
        self.latencies = deque(maxlen=window_size)
        self.baseline_p95 = None
    
    def record(self, latency_ms: float):
        self.latencies.append(latency_ms)
        
    def is_degraded(self, threshold_multiplier: float = 3.0) -> bool:
        if len(self.latencies) < 10:
            return False
        current_p95 = sorted(self.latencies)[int(len(self.latencies) * 0.95)]
        if self.baseline_p95 is None:
            self.baseline_p95 = current_p95
            return False
        return current_p95 > self.baseline_p95 * threshold_multiplier
```

#### Embedding API Failures

Same categories as LLM API, but with additional concerns:

- **Dimension mismatch**: If you switch embedding models, new vectors don't match old index
- **Model version changes**: Provider updates model, embeddings shift subtly
- **Batch size limits**: Large document batches may fail silently (partial processing)

#### Rate Limit Nuances

Rate limits aren't binary. Different providers implement them differently:

```python
# OpenAI-style: tokens per minute + requests per minute
# You might hit token limit before request limit on long prompts

# Anthropic-style: requests per minute with token bucket
# Burst allowed, but sustained high volume throttled

# Self-hosted: typically just concurrent requests
# No token limits, but queue depth matters
```

### Category 2: Retrieval Failures

Retrieval failures are particularly dangerous because they often don't throw exceptions—they just return bad or no results.

#### No Relevant Documents Found

The query has no good matches in your index. This isn't an error—it's a legitimate result that your system must handle.

```python
# Detection approaches
def detect_retrieval_failure(results: list, query: str) -> dict:
    if not results:
        return {"status": "no_results", "confidence": 0.0}
    
    # Check relevance scores
    top_score = results[0].score if results else 0
    if top_score < 0.5:  # Threshold depends on your embedding model
        return {"status": "low_relevance", "confidence": top_score}
    
    # Check score distribution (all low = probably no good matches)
    scores = [r.score for r in results]
    if max(scores) - min(scores) < 0.1:  # All scores clustered
        return {"status": "uncertain", "confidence": sum(scores)/len(scores)}
    
    return {"status": "ok", "confidence": top_score}
```

#### Vector Database Connection Failures

Standard connection issues apply: network partition, database overloaded, credentials expired. The difference is what happens next—unlike a SQL query that clearly fails, a vector search timeout might return partial results.

#### Results Below Relevance Threshold

You get results, but they're all garbage. The embedding model found the "nearest" vectors, but nearest doesn't mean relevant.

**Root causes:**

- Query is out-of-domain (asking about topic not in your corpus)
- Embedding model poorly suited to your domain
- Chunk size mismatch (query is sentence, chunks are pages)
- Index contains stale/outdated information

#### Index Corruption/Stale Index

Your vector index has drifted from reality:

- Documents were updated but index wasn't
- Deleted documents still in index
- Index rebuild failed silently
- Embedding model was updated but index uses old embeddings

Detection requires separate health checks—you can't detect this from query results alone.

### Category 3: Generation Failures

The LLM was called successfully, but the output is unusable.

#### Empty Response

The model returned nothing. Causes vary:

```python
# Possible causes of empty response
EMPTY_RESPONSE_CAUSES = [
    "Content filter triggered (input or output)",
    "Max tokens set to 0 or very low",
    "Model refused to answer (safety)",
    "API returned success but empty content",
    "Stop sequence hit immediately",
    "Response truncated and parser saw nothing"
]
```

Detection is straightforward—check for empty string or whitespace-only response.

#### Response Parsing Failed

You requested structured output (JSON, function call), but got unparseable text.

```python
# Common parsing failures
def parse_structured_response(response: str, expected_schema: dict) -> dict:
    # Failure 1: Not JSON at all
    # "I'd be happy to help! Here's the information..."
    
    # Failure 2: Partial JSON
    # '{"name": "test", "value":'  # Truncated
    
    # Failure 3: JSON with wrong schema
    # '{"wrong_field": "data"}'
    
    # Failure 4: JSON embedded in text
    # "Here's the result: ```json\n{...}\n```"
    
    try:
        # Handle markdown code blocks
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        
        data = json.loads(cleaned)
        # Validate schema...
        return data
    except json.JSONDecodeError as e:
        raise GenerationParsingError(f"Invalid JSON: {e}")
```

#### Content Filter Triggered

The model or provider refused to generate output due to safety filters. This can happen on input or output:

- **Input filter**: Your prompt was flagged before generation
- **Output filter**: Model generated something, filter blocked it

Both typically result in empty response or error, but some providers give specific error codes.

#### Context Window Exceeded

You sent more tokens than the model accepts. This manifests as:

- Explicit error (400 Bad Request with token count)
- Truncated input (provider silently drops oldest tokens)
- Truncated output (ran out of space for response)

```python
# Prevention: count tokens before sending
import tiktoken

def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def check_context_limit(
    prompt: str, 
    max_context: int = 128000,
    reserve_for_response: int = 4096
) -> bool:
    prompt_tokens = estimate_tokens(prompt)
    available = max_context - reserve_for_response
    return prompt_tokens <= available
```

#### Malformed Function Calling / Tool Use

The model attempted to call a tool but produced invalid arguments.

```python
# Expected tool call
{
    "name": "search_database",
    "arguments": {
        "query": "revenue Q4 2024",
        "limit": 10
    }
}

# Malformed examples
{
    "name": "search_database",
    "arguments": {
        "query": "revenue Q4 2024",
        "limit": "ten"  # String instead of int
    }
}

{
    "name": "search_database",
    "arguments": "{\"query\": \"...\", \"limit\": 10}"  # JSON string instead of object
}

{
    "name": "search_databse",  # Typo in tool name
    "arguments": {...}
}
```

Even with `strict: true` in structured outputs, edge cases slip through. Always validate tool arguments before execution.

### Category 4: Agent Failures

Agents introduce failure modes that don't exist in single-call LLM systems.

#### Infinite Loop

The agent keeps calling tools without terminating. Classic causes:

- Tool returns error, agent retries same action
- Agent lacks information to complete but keeps trying
- Circular reasoning: A calls B, B calls A
- Agent misinterprets tool output, repeats action

```python
# Detection
class LoopDetector:
    def __init__(self, max_iterations: int = 10, 
                 repeat_threshold: int = 3):
        self.iterations = 0
        self.action_history = []
        self.max_iterations = max_iterations
        self.repeat_threshold = repeat_threshold
    
    def record_action(self, action: dict) -> None:
        self.iterations += 1
        self.action_history.append(action)
    
    def is_looping(self) -> bool:
        if self.iterations >= self.max_iterations:
            return True
        
        # Check for repeated identical actions
        if len(self.action_history) >= self.repeat_threshold:
            recent = self.action_history[-self.repeat_threshold:]
            if all(a == recent[0] for a in recent):
                return True
        
        return False
```

#### Max Iterations Exceeded

The agent hit a configured limit. This is defensive—you set the limit to prevent runaway costs. But it means the task didn't complete.

**Interpretation matters:**

- Hit limit on easy task? Something's wrong with the agent
- Hit limit on complex task? Might need higher limit or task decomposition

#### Tool Execution Failed

A tool the agent called threw an error. The question: should the agent retry, try a different tool, or give up?

```python
# Tool failure handling strategy
class ToolFailureHandler:
    def __init__(self):
        self.failure_counts = defaultdict(int)
    
    def handle_failure(
        self, 
        tool_name: str, 
        error: Exception
    ) -> str:
        """Returns instruction for agent on how to proceed."""
        
        self.failure_counts[tool_name] += 1
        
        if isinstance(error, RetryableError):
            if self.failure_counts[tool_name] < 3:
                return f"Tool '{tool_name}' temporarily failed. Try again."
            else:
                return f"Tool '{tool_name}' consistently failing. Try alternative approach."
        
        elif isinstance(error, InvalidArgumentError):
            return f"Tool '{tool_name}' received invalid arguments: {error}. Fix and retry."
        
        else:
            return f"Tool '{tool_name}' failed permanently: {error}. Use different tool or acknowledge limitation."
```

#### Invalid Tool Arguments

The agent understood which tool to use but passed wrong arguments. Common patterns:

- Type mismatches (string vs int vs list)
- Missing required fields
- Extra unexpected fields
- Values outside allowed ranges
- Malformed nested structures

#### Stuck in Reasoning Loop

The agent keeps "thinking" but never acts. Internal monologue goes in circles.

```
Thought: I need to search for X
Thought: But first I should consider Y
Thought: Actually, X depends on Z
Thought: Let me think about X again...
[Never calls a tool, never produces answer]
```

Detection: track thought-to-action ratio. If agent has N thoughts with no actions, force termination or action.

### Category 5: Resource Exhaustion

Your system ran out of something.

#### Memory Exhausted

Large document processing, accumulating conversation history, or embedding batches can exhaust memory:

```python
# Common memory issues
MEMORY_EXHAUSTION_CAUSES = [
    "Loading entire document corpus into memory",
    "Unbounded conversation history",
    "Large embedding batches",
    "Multiple large model instances",
    "Memory leaks in long-running processes"
]

# Prevention
class ConversationMemory:
    def __init__(self, max_tokens: int = 10000):
        self.messages = []
        self.max_tokens = max_tokens
    
    def add(self, message: dict):
        self.messages.append(message)
        self._prune()
    
    def _prune(self):
        while self._total_tokens() > self.max_tokens:
            # Remove oldest non-system message
            for i, msg in enumerate(self.messages):
                if msg["role"] != "system":
                    self.messages.pop(i)
                    break
```

#### Timeout Reached

Your operation took too long. Different timeout scopes:

- **API call timeout**: Single external request exceeded limit
- **Operation timeout**: Multi-step operation (e.g., RAG pipeline) exceeded total budget
- **Request timeout**: User-facing request exceeded SLA

```python
# Layered timeout strategy
TIMEOUT_CONFIG = {
    "llm_call": 30,        # Single LLM API call
    "embedding_call": 10,   # Single embedding request
    "retrieval": 5,         # Vector search
    "total_operation": 60,  # Full RAG pipeline
    "user_request": 90      # End-to-end request
}
```

#### Budget Exhausted

You've spent your allocated money/tokens:

```python
class BudgetTracker:
    def __init__(self, max_tokens: int, max_cost_usd: float):
        self.max_tokens = max_tokens
        self.max_cost = max_cost_usd
        self.tokens_used = 0
        self.cost_incurred = 0.0
    
    def record_usage(self, tokens: int, cost: float):
        self.tokens_used += tokens
        self.cost_incurred += cost
    
    def can_continue(self) -> bool:
        return (
            self.tokens_used < self.max_tokens and 
            self.cost_incurred < self.max_cost
        )
    
    def remaining_budget(self) -> dict:
        return {
            "tokens": self.max_tokens - self.tokens_used,
            "cost_usd": self.max_cost - self.cost_incurred
        }
```

#### Rate Limit Exhausted

Different from a single rate limit error—you've systematically exhausted your quota:

- Minute limits: Recovers quickly, retry after brief wait
- Daily limits: Recovers at quota reset, need fallback provider
- Per-model limits: Try different model tier

---

## Failure Characteristics

Not all failures are equal. Understanding characteristics guides your handling strategy.

### Transient vs Persistent

|Characteristic|Transient|Persistent|
|---|---|---|
|Will retry succeed?|Yes (probably)|No|
|Examples|Timeout, rate limit, 503|Auth failure, invalid input, 400|
|Strategy|Retry with backoff|Fail fast, fix root cause|
|User message|"Please wait..."|"Unable to process. Check input."|

### Partial Failures

Some components work, others don't. Your system must decide:

- Continue with degraded functionality?
- Fail entirely for consistency?
- Return partial result with disclaimer?

```python
# Partial failure handling
class PartialResult:
    def __init__(self):
        self.components = {}
        
    def record(self, component: str, status: str, result: any = None):
        self.components[component] = {
            "status": status,
            "result": result
        }
    
    def overall_status(self) -> str:
        statuses = [c["status"] for c in self.components.values()]
        if all(s == "success" for s in statuses):
            return "success"
        if all(s == "failed" for s in statuses):
            return "failed"
        return "partial"
    
    def get_usable_results(self) -> dict:
        return {
            k: v["result"] 
            for k, v in self.components.items() 
            if v["status"] == "success"
        }
```

### Silent Failures

The most dangerous. Detection strategies:

```python
class SilentFailureDetector:
    def check_response(self, query: str, response: str, 
                       context: list) -> dict:
        issues = []
        
        # Empty or near-empty
        if len(response.strip()) < 10:
            issues.append("response_too_short")
        
        # Refusal patterns
        refusal_patterns = [
            "I cannot", "I'm unable", "I don't have",
            "As an AI", "I apologize"
        ]
        if any(p.lower() in response.lower() for p in refusal_patterns):
            issues.append("possible_refusal")
        
        # No grounding in context (when context was provided)
        if context and not self._references_context(response, context):
            issues.append("ungrounded_response")
        
        # Hedging language (low confidence)
        hedging = ["might be", "could be", "possibly", "perhaps", "I think"]
        hedge_count = sum(1 for h in hedging if h.lower() in response.lower())
        if hedge_count > 2:
            issues.append("excessive_hedging")
        
        return {
            "passed": len(issues) == 0,
            "issues": issues
        }
    
    def _references_context(self, response: str, context: list) -> bool:
        # Check if response contains key terms from context
        context_text = " ".join(str(c) for c in context).lower()
        response_lower = response.lower()
        
        # Extract key terms (simplified - real implementation would be smarter)
        context_words = set(context_text.split())
        response_words = set(response_lower.split())
        
        overlap = context_words & response_words
        # Require some meaningful overlap
        return len(overlap) > 5
```

---

## Failure Detection Methods

### Explicit Detection

Errors that announce themselves:

```python
# Exception-based detection
EXPLICIT_ERRORS = {
    # HTTP errors
    requests.exceptions.ConnectionError: "connection_failed",
    requests.exceptions.Timeout: "timeout",
    
    # Provider-specific
    openai.RateLimitError: "rate_limited",
    openai.AuthenticationError: "auth_failed",
    anthropic.APIStatusError: "api_error",
    
    # Parsing
    json.JSONDecodeError: "invalid_json",
    pydantic.ValidationError: "schema_mismatch"
}

def classify_explicit_error(error: Exception) -> str:
    for error_type, classification in EXPLICIT_ERRORS.items():
        if isinstance(error, error_type):
            return classification
    return "unknown_error"
```

### Implicit Detection

Failures hidden in "successful" responses:

```python
class ImplicitFailureDetector:
    def analyze(self, response: dict, expected: dict) -> list:
        failures = []
        
        # Empty content
        if not response.get("content"):
            failures.append({
                "type": "empty_response",
                "severity": "high"
            })
        
        # Missing expected fields
        for field in expected.get("required_fields", []):
            if field not in response:
                failures.append({
                    "type": "missing_field",
                    "field": field,
                    "severity": "medium"
                })
        
        # Low confidence indicators
        content = response.get("content", "")
        if self._has_low_confidence_markers(content):
            failures.append({
                "type": "low_confidence",
                "severity": "low"
            })
        
        # Truncation indicators
        if self._appears_truncated(content):
            failures.append({
                "type": "truncated",
                "severity": "medium"
            })
        
        return failures
    
    def _has_low_confidence_markers(self, text: str) -> bool:
        markers = ["I'm not sure", "I don't know", "I cannot find"]
        return any(m.lower() in text.lower() for m in markers)
    
    def _appears_truncated(self, text: str) -> bool:
        # Ends mid-sentence or mid-word
        if not text:
            return False
        last_char = text.strip()[-1] if text.strip() else ""
        return last_char not in ".!?\"')]}>"
```

### Latency Anomaly Detection

When things are slow but not failing:

```python
import statistics
from collections import deque

class LatencyAnomalyDetector:
    def __init__(self, window_size: int = 100, 
                 std_dev_threshold: float = 3.0):
        self.window = deque(maxlen=window_size)
        self.threshold = std_dev_threshold
    
    def record_and_check(self, latency_ms: float) -> dict:
        result = {"latency_ms": latency_ms, "anomaly": False}
        
        if len(self.window) >= 10:
            mean = statistics.mean(self.window)
            std = statistics.stdev(self.window)
            
            if std > 0:
                z_score = (latency_ms - mean) / std
                if z_score > self.threshold:
                    result["anomaly"] = True
                    result["z_score"] = z_score
                    result["expected_range"] = (
                        mean - std * 2, 
                        mean + std * 2
                    )
        
        self.window.append(latency_ms)
        return result
```

---

## Summary

LLM system failures require a different mental model than traditional software:

1. **Expect non-determinism**: You can't assert on exact outputs
2. **Assume dependencies fail**: External APIs are your weakest link
3. **Watch for cascades**: One failure can poison the whole pipeline
4. **Hunt silent failures**: Wrong answers are worse than errors

The taxonomy gives you a vocabulary for discussing failures:

- **Where** it happened (external, retrieval, generation, agent, resource)
- **What** it means (transient vs persistent, partial vs total)
- **How** to detect it (explicit errors vs implicit signals)

Next notes will cover what to do about these failures: retry strategies, circuit breakers, and fallback hierarchies.

---

## Connections

- **Note 2**: Retry patterns for transient failures
- **Note 3**: Circuit breakers to prevent cascade failures
- **Note 4**: Fallback hierarchies for graceful degradation
- **Week 7-8**: These failure modes feed directly into observability (you need to detect them to monitor them)