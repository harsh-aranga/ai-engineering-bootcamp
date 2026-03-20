# Error Handling in Tool Execution

## Why Tool Errors Matter

Tools fail. APIs time out, validation fails, files don't exist, rate limits hit. In a ReAct loop, unhandled errors crash the graph. Handled errors let the LLM recover — retry, try a different approach, or give up gracefully.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Unhandled Error                 Handled Error                 │
│   ───────────────                 ─────────────                 │
│                                                                 │
│   Tool raises exception     →     Tool raises exception         │
│   Graph crashes             →     ToolNode catches it           │
│   User sees error           →     Returns ToolMessage           │
│   Agent stops               →     LLM sees error text           │
│                             →     LLM can retry or adapt        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Two Types of Tool Errors

LangGraph distinguishes between two error categories:

|Type|When It Happens|Default Behavior|
|---|---|---|
|**Invocation Error**|LLM provides invalid arguments (Pydantic validation fails)|Caught, returned as ToolMessage|
|**Execution Error**|Tool runs but raises exception internally|**Re-raised** (crashes graph)|

### Invocation Error Example

```python
@tool
def calculate(expression: str, precision: int) -> str:
    """Evaluate math expression with given precision."""
    return str(round(eval(expression), precision))

# LLM calls: calculate(expression="2+2", precision="high")
# "high" is not an int → Pydantic validation fails
# → ToolInvocationError (caught by default)
```

### Execution Error Example

```python
@tool
def fetch_url(url: str) -> str:
    """Fetch content from URL."""
    response = requests.get(url, timeout=5)
    response.raise_for_status()  # Raises on 4xx/5xx
    return response.text

# LLM calls: fetch_url(url="https://example.com/api")
# Valid arguments, but server returns 500
# → requests.HTTPError (NOT caught by default)
```

---

## Critical: Default Changed in LangGraph 1.0.1+

**Before 1.0.1:** `ToolNode` caught all errors by default.

**After 1.0.1:** `ToolNode` only catches invocation errors. Execution errors propagate.

```python
# Default behavior (1.0.1+)
tool_node = ToolNode(tools)
# - Catches: Pydantic validation errors (invocation)
# - Re-raises: Everything else (execution)

# To catch ALL errors (recommended for most agents)
tool_node = ToolNode(tools, handle_tool_errors=True)
```

**Always explicitly set `handle_tool_errors=True`** for production agents. Don't rely on defaults.

---

## handle_tool_errors Options

The `handle_tool_errors` parameter accepts multiple types:

### Option 1: Boolean (True)

Catch all errors, return exception text as ToolMessage.

```python
from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools, handle_tool_errors=True)
```

When a tool raises `ValueError("Invalid input")`:

```
ToolMessage(
    content="Error: ValueError('Invalid input')",
    tool_call_id="call_123"
)
```

### Option 2: String

Catch all errors, return custom message.

```python
tool_node = ToolNode(
    tools,
    handle_tool_errors="Something went wrong. Please try a different approach."
)
```

### Option 3: Callable (Custom Handler)

Catch errors, process with custom function.

```python
def custom_error_handler(error: Exception) -> str:
    if isinstance(error, ValueError):
        return f"Invalid input: {error}. Please check your parameters."
    elif isinstance(error, TimeoutError):
        return "The operation timed out. Try again or use a simpler query."
    elif isinstance(error, PermissionError):
        return "Access denied. You don't have permission for this operation."
    else:
        return f"Unexpected error: {type(error).__name__}. Please try again."

tool_node = ToolNode(tools, handle_tool_errors=custom_error_handler)
```

### Option 4: Tuple of Exception Types

Only catch specific exception types, re-raise others.

```python
# Only catch ValueError and TypeError
# All other exceptions will crash the graph
tool_node = ToolNode(
    tools,
    handle_tool_errors=(ValueError, TypeError)
)
```

---

## Complete Error Handling Examples

### Basic Agent with Error Handling

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

@tool
def divide(a: float, b: float) -> str:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return str(a / b)

@tool
def fetch_data(endpoint: str) -> str:
    """Fetch data from API endpoint."""
    import requests
    response = requests.get(f"https://api.example.com/{endpoint}", timeout=5)
    response.raise_for_status()
    return response.text

tools = [divide, fetch_data]
llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)

def agent_node(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}

# Build graph with error handling
builder = StateGraph(MessagesState)
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))  # ← Key line
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

graph = builder.compile()
```

### Anthropic Version

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-20250514").bind_tools(tools)

# Rest of the graph is identical — error handling is provider-agnostic
```

---

## ToolException: Intentional Recoverable Errors

Use `ToolException` when your tool detects a recoverable error condition and wants to communicate it to the LLM.

```python
from langchain_core.tools import tool, ToolException

@tool
def write_file(path: str, content: str, overwrite: bool = False) -> str:
    """Write content to a file."""
    import os
    
    if os.path.exists(path) and not overwrite:
        raise ToolException(
            f"File '{path}' already exists. Set overwrite=True to replace it."
        )
    
    with open(path, 'w') as f:
        f.write(content)
    return f"Successfully wrote {len(content)} bytes to {path}"

@tool
def search_database(query: str) -> str:
    """Search the database."""
    results = db.search(query)
    
    if not results:
        raise ToolException(
            f"No results found for '{query}'. Try broader search terms."
        )
    
    return format_results(results)
```

**Note:** `ToolException` is only caught when `handle_tool_errors=True`. With default settings (post-1.0.1), it will crash the graph.

---

## Error Handling Strategies

### Strategy 1: Catch All, Let LLM Decide

Simple, works for most cases. LLM sees error and decides what to do.

```python
tool_node = ToolNode(tools, handle_tool_errors=True)
```

### Strategy 2: Categorize and Customize

Different messages for different error types.

```python
def categorized_handler(error: Exception) -> str:
    # Validation errors — LLM provided bad input
    if isinstance(error, (ValueError, TypeError)):
        return f"Invalid input: {error}. Please check your parameters and try again."
    
    # Network errors — transient, may succeed on retry
    if isinstance(error, (TimeoutError, ConnectionError)):
        return f"Network error: {error}. The service may be temporarily unavailable."
    
    # Permission errors — LLM can't fix this
    if isinstance(error, PermissionError):
        return f"Permission denied: {error}. This operation is not allowed."
    
    # Rate limits — should wait or reduce requests
    if "rate limit" in str(error).lower():
        return "Rate limit exceeded. Please wait before making more requests."
    
    # Unknown — give LLM context to adapt
    return f"Error ({type(error).__name__}): {error}"

tool_node = ToolNode(tools, handle_tool_errors=categorized_handler)
```

### Strategy 3: Critical vs Non-Critical

Some errors should crash (critical), others should be recoverable.

```python
class CriticalError(Exception):
    """Errors that should crash the graph."""
    pass

def selective_handler(error: Exception) -> str:
    # Let critical errors propagate
    if isinstance(error, CriticalError):
        raise error
    
    # Handle everything else
    return f"Error: {error}"

tool_node = ToolNode(tools, handle_tool_errors=selective_handler)
```

---

## Error Handling in Tools vs ToolNode

You can handle errors at two levels:

### Level 1: Inside the Tool (Recommended for Expected Errors)

```python
@tool
def safe_divide(a: float, b: float) -> str:
    """Divide a by b."""
    if b == 0:
        return "Error: Cannot divide by zero. Please provide a non-zero divisor."
    return str(a / b)
```

**Pros:**

- No exception raised
- Full control over message
- Works regardless of ToolNode config

**Cons:**

- Must anticipate every error case
- Can't distinguish error from success in downstream logic

### Level 2: In ToolNode (Recommended for Unexpected Errors)

```python
@tool
def divide(a: float, b: float) -> str:
    """Divide a by b."""
    return str(a / b)  # Let ZeroDivisionError raise

tool_node = ToolNode(tools, handle_tool_errors=True)
```

**Pros:**

- Catches unexpected errors
- Consistent handling across all tools
- Less boilerplate in tool code

**Cons:**

- Less control over error message format
- Error details may not be user-friendly

### Best Practice: Both Levels

```python
@tool
def robust_api_call(endpoint: str) -> str:
    """Call an API endpoint."""
    import requests
    
    # Handle expected errors in tool
    if not endpoint.startswith("/"):
        return "Error: Endpoint must start with '/'"
    
    try:
        response = requests.get(f"https://api.example.com{endpoint}", timeout=5)
        response.raise_for_status()
        return response.text
    except requests.Timeout:
        return "Error: Request timed out. The API is slow. Try again later."
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return f"Error: Endpoint '{endpoint}' not found. Check the path."
        # Let other HTTP errors propagate to ToolNode
        raise

# ToolNode catches anything that slips through
tool_node = ToolNode(tools, handle_tool_errors=True)
```

---

## Retry Logic with Error Handling

### Option 1: Runnable Retry (LangChain Level)

```python
from langchain_core.runnables import RunnableLambda

@tool
def flaky_api() -> str:
    """Call a flaky API."""
    import random
    if random.random() < 0.7:
        raise ConnectionError("Temporary failure")
    return "Success!"

# Wrap with retry
flaky_api_with_retry = flaky_api.with_retry(
    retry_if_exception_type=(ConnectionError,),
    wait_exponential_jitter=True,
    stop_after_attempt=3
)
```

### Option 2: LangGraph Retry Policy (Node Level)

```python
from langgraph.pregel import RetryPolicy

# Define retry policy
retry_policy = RetryPolicy(
    max_attempts=3,
    initial_interval=1.0,  # seconds
    backoff_factor=2.0,
    retry_on=(ConnectionError, TimeoutError)
)

# Apply to node
builder.add_node(
    "tools",
    ToolNode(tools, handle_tool_errors=True),
    retry=retry_policy
)
```

### Option 3: Retry in Custom Handler

```python
import time

def retry_handler(error: Exception) -> str:
    """Handler that suggests retry to LLM."""
    if isinstance(error, (ConnectionError, TimeoutError)):
        return (
            f"Temporary error: {error}. "
            "This may be transient. Consider retrying the same operation."
        )
    return f"Error: {error}"

tool_node = ToolNode(tools, handle_tool_errors=retry_handler)
```

---

## Fallback Pattern with ToolNode

Create a ToolNode with fallback handling using `with_fallbacks`:

```python
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks

def handle_tool_error(state: dict) -> dict:
    """Fallback handler when ToolNode fails."""
    error = state.get("error")
    last_message = state["messages"][-1]
    
    # Create error ToolMessages for each failed tool call
    error_messages = []
    for tool_call in last_message.tool_calls:
        error_messages.append(
            ToolMessage(
                content=f"Tool execution failed: {error}",
                tool_call_id=tool_call["id"]
            )
        )
    
    return {"messages": error_messages}

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks:
    """Create ToolNode with error fallback."""
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)],
        exception_key="error"
    )

# Use in graph
builder.add_node("tools", create_tool_node_with_fallback(tools))
```

---

## Common Error Scenarios and Solutions

### Scenario 1: LLM Calls Non-Existent Tool

```python
# LLM hallucinates tool name: "calculater" instead of "calculator"
# This is a ToolInvocationError — caught by default
```

**Solution:** Improve tool descriptions, use fewer tools, or catch with `handle_tool_errors=True`.

### Scenario 2: API Rate Limit

```python
@tool
def search_api(query: str) -> str:
    """Search an external API."""
    response = requests.get(f"https://api.example.com/search?q={query}")
    if response.status_code == 429:
        raise Exception("Rate limit exceeded")
    return response.text
```

**Solution:** Use custom handler with specific guidance:

```python
def rate_limit_handler(e: Exception) -> str:
    if "rate limit" in str(e).lower():
        return (
            "Rate limit exceeded. Options: "
            "1) Wait 60 seconds and retry, "
            "2) Use cached results if available, "
            "3) Simplify your query"
        )
    return str(e)
```

### Scenario 3: Tool Timeout

```python
@tool
def slow_operation(data: str) -> str:
    """Process data (may be slow)."""
    import asyncio
    # This might take too long
    result = process_large_dataset(data)
    return result
```

**Solution:** Add timeout in tool:

```python
import asyncio

@tool
async def slow_operation(data: str) -> str:
    """Process data with timeout."""
    try:
        result = await asyncio.wait_for(
            process_large_dataset_async(data),
            timeout=30.0
        )
        return result
    except asyncio.TimeoutError:
        return "Operation timed out. Try with smaller data or simpler query."
```

---

## Error Handling Summary Table

|Configuration|Invocation Errors|Execution Errors|Use Case|
|---|---|---|---|
|`ToolNode(tools)`|✅ Caught|❌ Re-raised|Debugging, fail-fast|
|`handle_tool_errors=True`|✅ Caught|✅ Caught|Production agents|
|`handle_tool_errors="message"`|✅ Custom msg|✅ Custom msg|User-friendly errors|
|`handle_tool_errors=callable`|✅ Custom|✅ Custom|Categorized handling|
|`handle_tool_errors=(TypeError,)`|✅ Caught|⚠️ Only specified|Selective catching|

---

## Key Takeaways

1. **Always set `handle_tool_errors=True`** in production — the default changed in 1.0.1+
    
2. **Two error types:** Invocation (bad args, caught by default) vs Execution (tool fails, NOT caught by default)
    
3. **Use `ToolException`** for intentional, recoverable errors with helpful messages
    
4. **Handle expected errors in tools, unexpected errors in ToolNode** — defense in depth
    
5. **Custom handlers let LLMs recover intelligently** — categorize errors, suggest alternatives
    
6. **Error messages become ToolMessages** — LLM sees them and can adapt
    
7. **Retry logic can live at multiple levels** — Runnable, node policy, or LLM-driven
    

---

## References

- [LangChain Tools Documentation](https://docs.langchain.com/oss/python/langchain/tools) — Error handling config
- [ToolNode API Reference](https://reference.langchain.com/python/langgraph.prebuilt/tool_node/ToolNode) — Parameter details
- [GitHub Issue #6486](https://github.com/langchain-ai/langgraph/issues/6486) — Default behavior change in 1.0.1
- [Error Handling Patterns](https://aiproduct.engineer/tutorials/langgraph-tutorial-error-handling-patterns-unit-23-exercise-6) — Advanced patterns