# Note 7: Scaling Tool Use — Advanced Patterns + Token Economics

## Week 3 Agents — Days 3-4 | Function Calling / Tool Use

---

## The Token Cost Problem

Every tool you define consumes context window tokens. This overhead exists _before_ the conversation even starts.

### Where Tokens Are Consumed

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOKEN CONSUMPTION BREAKDOWN                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 1. TOOL DEFINITIONS (~system prompt injection)          │   │
│  │    • Tool names, descriptions, parameter schemas        │   │
│  │    • ~50-500 tokens per tool (depends on complexity)    │   │
│  │    • 50 tools = 2,500 - 25,000 tokens OVERHEAD          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            +                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 2. TOOL USE SYSTEM PROMPT (automatic, per-model)        │   │
│  │    • Anthropic: 699-935 tokens (varies by model)        │   │
│  │    • OpenAI: Similar overhead (not publicly documented) │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            +                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 3. CONVERSATION HISTORY (tool calls + results)          │   │
│  │    • Each tool_use block                                │   │
│  │    • Each tool_result (can be large!)                   │   │
│  │    • Accumulates with each iteration                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            =                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ TOTAL: Context consumed before user sees first response │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Real-World Examples (from Anthropic's Engineering Blog)

|Setup|Tools|Token Overhead|
|---|---|---|
|Single MCP server|10-15|~10K tokens|
|5 MCP servers|58|~55K tokens|
|Enterprise (with Jira)|75+|~77K+ tokens|
|Before optimization|134|134K tokens|

**That's 50,000-134,000 tokens consumed before a single user message is processed.**

---

## Anthropic Tool Definition Token Costs

### System Prompt Overhead (Automatic)

When you include _any_ tool, Anthropic adds a system prompt:

|Model|Tool Use System Tokens|
|---|---|
|Claude Sonnet 4.5|699|
|Claude Opus 4.5|935|
|Claude Haiku 4.5|699|
|Computer use beta|+466-499 additional|

### Per-Tool Token Costs

Rough estimates (varies by description length):

|Tool Complexity|Tokens Per Tool|
|---|---|
|Simple (1-2 params)|50-100|
|Medium (3-5 params)|100-250|
|Complex (nested objects)|250-500|
|With input_examples|+20-200 per example|

### Counting Tokens Accurately

```python
import anthropic

client = anthropic.Anthropic()

# Count tokens BEFORE making the request
token_count = client.messages.count_tokens(
    model="claude-sonnet-4-5-20250514",
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "What's the weather?"}],
    tools=[
        {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"]
            }
        }
    ]
)

print(f"Input tokens (including tools): {token_count.input_tokens}")
```

---

## Pattern 1: Tool Search (On-Demand Discovery)

**Problem**: Loading 100+ tools upfront wastes tokens on tools that won't be used.

**Solution**: Load only the tools Claude actually needs.

### How Tool Search Works

```
┌─────────────────────────────────────────────────────────────────┐
│  TRADITIONAL APPROACH                                           │
│                                                                 │
│  Request starts with: [tool1, tool2, ... tool100]              │
│  All 100 tool definitions = ~50K tokens consumed               │
│  Claude uses 2-3 tools                                         │
│  47K tokens WASTED                                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  TOOL SEARCH APPROACH                                          │
│                                                                 │
│  Request starts with: [tool_search_tool] + [3 always-loaded]   │
│  ~3K tokens consumed                                           │
│                                                                 │
│  Claude searches → "github pull request"                       │
│  API returns: [github.createPR, github.listPRs, github.mergePR]│
│  Only needed tools loaded                                      │
│  ~8K total tokens                                              │
│                                                                 │
│  SAVINGS: 85% reduction in tool definition tokens              │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import anthropic

client = anthropic.Anthropic()

response = client.beta.messages.create(
    betas=["advanced-tool-use-2025-11-20"],
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    tools=[
        # Tool Search Tool (always loaded, ~500 tokens)
        {
            "type": "tool_search_tool_regex_20251119",
            "name": "tool_search_tool_regex"
        },
        
        # Always-loaded critical tools (defer_loading: false by default)
        {
            "name": "get_user_context",
            "description": "Get current user's context and permissions",
            "input_schema": {...}
        },
        
        # Deferred tools (discovered on-demand)
        {
            "name": "github.createPullRequest",
            "description": "Create a pull request on GitHub",
            "input_schema": {...},
            "defer_loading": True  # NOT loaded initially
        },
        {
            "name": "slack.sendMessage",
            "description": "Send a message to a Slack channel",
            "input_schema": {...},
            "defer_loading": True
        },
        # ... 100 more deferred tools
    ],
    messages=[{"role": "user", "content": "Create a PR for my changes"}]
)
```

### Tool Search Variants

|Type|How It Works|Best For|
|---|---|---|
|`tool_search_tool_regex_20251119`|Pattern matching on tool names/descriptions|Technical tools with clear naming|
|`tool_search_tool_bm25_20251119`|Natural language similarity search|Natural language queries|
|Custom (you implement)|Embeddings, semantic search, etc.|Domain-specific discovery|

### Accuracy Results (Anthropic Benchmarks)

|Model|Traditional|With Tool Search|
|---|---|---|
|Claude Opus 4|49%|74%|
|Claude Opus 4.5|79.5%|88.1%|

**Tool search doesn't just save tokens — it improves accuracy.**

---

## Pattern 2: Prompt Caching for Tools

**Problem**: Sending the same tool definitions with every request wastes money.

**Solution**: Cache tool definitions across requests.

### How Prompt Caching Works

```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST 1 (Cache Write)                                       │
│                                                                 │
│  [System Prompt] + [Tools] + [Message]                         │
│        ↓               ↓                                        │
│     Cached         Cached                                       │
│                                                                 │
│  Cost: 1.25x base price for cached content                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  REQUEST 2+ (Cache Hit)                                        │
│                                                                 │
│  [System Prompt] + [Tools] + [New Message]                     │
│        ↓               ↓                                        │
│   From Cache      From Cache                                    │
│                                                                 │
│  Cost: 0.1x base price (90% savings!)                          │
└─────────────────────────────────────────────────────────────────┘
```

### Caching Duration Options

|Duration|Write Cost|Read Cost|Use Case|
|---|---|---|---|
|5 minutes (default)|1.25x|0.1x|Short conversations|
|1 hour|2x|0.1x|Long-running agents|

### Implementation

```python
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=4096,
    cache_control={"type": "ephemeral"},  # Enable automatic caching
    system="You are a helpful assistant with access to various tools.",
    tools=[
        # All these tool definitions will be cached
        {"name": "tool1", "description": "...", "input_schema": {...}},
        {"name": "tool2", "description": "...", "input_schema": {...}},
        # ...
    ],
    messages=[{"role": "user", "content": "Help me with a task"}]
)
```

### Prompt Caching + Tool Search = Maximum Savings

```python
# Best practice: Cache the search tool, defer everything else
response = client.beta.messages.create(
    betas=["advanced-tool-use-2025-11-20"],
    cache_control={"type": "ephemeral"},  # Cache the search tool
    tools=[
        {"type": "tool_search_tool_regex_20251119", "name": "tool_search_tool_regex"},
        # Deferred tools don't break cache — they're not in initial context
        {"name": "tool1", ..., "defer_loading": True},
        {"name": "tool2", ..., "defer_loading": True},
    ],
    ...
)
```

---

## Pattern 3: Programmatic Tool Calling (Code Execution)

**Problem**: Each tool call requires a full model inference pass, and intermediate results pile up in context.

**Solution**: Let Claude write code that calls tools, filtering results before they enter context.

### Traditional vs Programmatic

```
┌─────────────────────────────────────────────────────────────────┐
│  TRADITIONAL: Check 20 employee budgets                        │
│                                                                 │
│  Inference 1: Claude calls get_expenses(emp1)                  │
│  Inference 2: Claude calls get_expenses(emp2)                  │
│  ...                                                           │
│  Inference 20: Claude calls get_expenses(emp20)                │
│  Inference 21: Claude analyzes 2000+ expense line items        │
│                                                                 │
│  = 21 model calls, 150K+ tokens in context                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PROGRAMMATIC: Check 20 employee budgets                       │
│                                                                 │
│  Claude writes Python:                                         │
│  ```python                                                     │
│  results = []                                                  │
│  for emp_id in employee_ids:                                   │
│      expenses = get_expenses(emp_id)                           │
│      if expenses.total > budget_limit:                         │
│          results.append({"id": emp_id, "over_by": ...})        │
│  print(json.dumps(results))                                    │
│  ```                                                           │
│                                                                 │
│  Code executes in sandbox → returns only summary               │
│  Claude sees: 3 employees over budget                          │
│                                                                 │
│  = 2 model calls, ~2K tokens in context                        │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
response = client.beta.messages.create(
    betas=["advanced-tool-use-2025-11-20"],
    model="claude-opus-4-5-20250929",
    max_tokens=4096,
    tools=[
        # Code execution tool
        {"type": "code_execution_20250825", "name": "code_execution"},
        
        # Tools callable FROM code
        {
            "name": "get_employee_expenses",
            "description": "Get expenses for an employee. Returns: List of expense objects with {amount, category, date}",
            "input_schema": {
                "type": "object",
                "properties": {"employee_id": {"type": "string"}},
                "required": ["employee_id"]
            },
            "allowed_callers": ["code_execution"]  # Can be called from code
        },
        {
            "name": "get_budget_limit",
            "description": "Get budget limit for a department",
            "input_schema": {...},
            "allowed_callers": ["code_execution"]
        }
    ],
    messages=[{
        "role": "user",
        "content": "Check which of our 20 team members are over their expense budget"
    }]
)
```

### When Programmatic Pays Off

|Use Case|Traditional|Programmatic|Winner|
|---|---|---|---|
|Single tool call|1 inference|2 inferences (code + execution)|Traditional|
|5 sequential calls|5 inferences|2 inferences|Programmatic|
|20 calls with filtering|21 inferences + 150K context|2 inferences + 2K context|Programmatic (98.7% token reduction)|
|Loop with conditionals|Complex prompt engineering|Natural Python|Programmatic|

**Rule of thumb**: If you'd write a loop in code, use programmatic tool calling.

---

## Pattern 4: Tool Use Examples

**Problem**: JSON Schema defines valid structure but not correct usage patterns.

**Solution**: Provide examples of how to use tools correctly.

### The Gap Between Valid and Correct

```json
// Schema says this is valid:
{
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-12-31"
  },
  "status": "all"
}

// But your API actually expects:
{
  "date_range": {
    "start": "2024-01-01T00:00:00Z",  // ISO 8601 with timezone
    "end": "2024-12-31T23:59:59Z"
  },
  "status": ["pending", "completed"]  // Array, not string "all"
}
```

### Adding Examples

```python
{
    "name": "search_orders",
    "description": "Search customer orders with filters",
    "input_schema": {...},
    "input_examples": [
        {
            "description": "Find pending orders from last week",
            "input": {
                "date_range": {
                    "start": "2024-12-08T00:00:00Z",
                    "end": "2024-12-15T23:59:59Z"
                },
                "status": ["pending"]
            }
        },
        {
            "description": "Get all orders for a specific customer",
            "input": {
                "customer_id": "cust_abc123",
                "status": ["pending", "shipped", "delivered"]
            }
        }
    ]
}
```

### Accuracy Impact (Anthropic Testing)

|Scenario|Without Examples|With Examples|
|---|---|---|
|Complex nested structures|~72% correct|~90% correct|
|Optional parameter inclusion|Poor|Good|
|Domain-specific conventions|Guessing|Correct|

### Example Guidelines

- **1-5 examples per tool** (more isn't always better)
- **Show variety**: minimal, partial, and full specification
- **Use realistic data**: not just "example_value"
- **Token cost**: ~20-200 tokens per example

---

## Pattern 5: Automatic Tool Clearing

**Problem**: Long conversations accumulate tool results that are no longer relevant.

**Solution**: Automatically clear old tool use results as you approach token limits.

### Implementation (Beta)

```python
response = client.beta.messages.create(
    betas=["context-management-2025-06-27"],
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    context_management={
        "strategy": "clear_tool_uses_20250919",
        "config": {
            "threshold_tokens": 150000,  # Start clearing at 150K
            "preserve_recent": 5,         # Keep last 5 tool results
            "preserve_tagged": True       # Keep results with cache_control
        }
    },
    tools=[...],
    messages=[...]
)
```

**Caveat**: This invalidates prompt caching if your cache includes tool results.

---

## Pattern 6: Token-Efficient Tool Use

**Problem**: Claude 3.7 Sonnet produces verbose tool call outputs.

**Solution**: Enable token-efficient mode (now default in Claude 4).

```python
# For Claude 3.7 Sonnet (beta header required)
response = client.beta.messages.create(
    betas=["token-efficient-tools-2025-02-19"],
    model="claude-3-7-sonnet-20250305",
    ...
)

# Claude 4+ models have this built-in — no header needed
response = client.messages.create(
    model="claude-sonnet-4-5-20250514",
    ...
)
```

**Result**: Up to 70% reduction in output tokens (14% average).

---

## Cost Comparison: Anthropic vs OpenAI

### Model Pricing (per Million Tokens)

|Model|Input|Output|Notes|
|---|---|---|---|
|**Claude Opus 4.5**|$5|$25|Best for complex tools|
|**Claude Sonnet 4.5**|$3|$15|Production workhorse|
|**Claude Haiku 4.5**|$0.80|$4|Cost-efficient (no tool search)|
|**GPT-5**|$1.25|$10|Agentic flagship|
|**GPT-5 mini**|$0.25|$2|Balanced|
|**GPT-5 nano**|$0.05|$0.40|Highest volume|
|**GPT-4o**|$2.50|$10|Previous gen|

### Additional Server Tool Costs (Anthropic)

|Tool|Pricing|
|---|---|
|Web search|Per-search fee + tokens|
|Code execution|Compute time + tokens|
|Web fetch|Per-fetch fee + tokens|

### Additional Tool Costs (OpenAI)

|Tool|Pricing|
|---|---|
|Code Interpreter|$0.03 per session|
|File Search|$0.10/GB/day storage + $2.50/1000 calls|
|Web Search|Varies|

---

## Cost Optimization Checklist

### Before Building

- [ ] Count baseline token cost with all tools defined
- [ ] Identify tools that could be deferred (rarely used)
- [ ] Identify tools that could be combined (similar functionality)

### Tool Design

- [ ] Keep descriptions concise but clear
- [ ] Use enums to reduce output tokens
- [ ] Avoid deeply nested schemas when flat works
- [ ] Add examples only for complex parameters

### At Runtime

- [ ] Enable prompt caching for static tools/system prompts
- [ ] Use tool search for 10+ tools
- [ ] Consider programmatic calling for batch operations
- [ ] Set max_tokens to prevent runaway output
- [ ] Use appropriate model tier (Haiku for simple, Opus for complex)

### For Multi-Turn Conversations

- [ ] Summarize tool results before storing
- [ ] Consider tool result clearing for long sessions
- [ ] Cache tool definitions across turns

---

## Decision Matrix: Which Pattern to Use

|Scenario|Pattern|
|---|---|
|10+ tools, most rarely used|Tool Search|
|Same tools across many requests|Prompt Caching|
|Multiple calls with filtering|Programmatic Tool Calling|
|Complex parameter formats|Tool Use Examples|
|Long conversations|Tool Result Clearing|
|Simple tools, high volume|Haiku + minimal descriptions|
|Complex reasoning required|Opus + rich descriptions|

---

## Key Takeaways

1. **Token overhead is real** — 50K+ tokens before your first message with many tools
    
2. **Tool Search = 85% token reduction** for large tool libraries, plus accuracy improvements
    
3. **Prompt Caching = 90% cost reduction** on repeated tool definitions (after first request)
    
4. **Programmatic Tool Calling = 98%+ token reduction** for batch/loop operations
    
5. **Examples improve accuracy by ~18%** on complex parameter structures
    
6. **Claude 4 models have built-in token efficiency** — no beta headers needed
    
7. **Measure before optimizing** — use `count_tokens` to understand your baseline
    
8. **Right-size your model** — Haiku for simple tools, Opus for complex reasoning
    

---

_This completes the Week 3 Agents Days 3-4 theory notes on Function Calling / Tool Use._

**Next up**: Mini Challenge — Build a working tool-using agent (no framework).