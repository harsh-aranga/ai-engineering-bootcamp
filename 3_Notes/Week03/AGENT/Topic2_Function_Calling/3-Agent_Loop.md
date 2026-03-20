# Note 3: The Agent Loop and Parallel Execution

## Week 3 Agents — Days 3-4 | Function Calling / Tool Use

---

## What Is the Agent Loop?

A single tool call often isn't enough. Complex tasks require multiple tools, chained together, with the LLM deciding what to do next based on results.

The **agent loop** is the pattern that enables this:

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │  User    │───►│   LLM    │───►│  Tools   │             │
│  │  Query   │    │          │    │          │             │
│  └──────────┘    └────┬─────┘    └────┬─────┘             │
│                       │               │                    │
│                       │◄──────────────┘                    │
│                       │    (results)                       │
│                       │                                    │
│                       ▼                                    │
│               ┌──────────────┐                            │
│               │ More tools   │──── YES ──► Continue loop  │
│               │   needed?    │                            │
│               └──────┬───────┘                            │
│                      │                                     │
│                      NO                                    │
│                      │                                     │
│                      ▼                                     │
│               ┌──────────────┐                            │
│               │ Final Answer │                            │
│               └──────────────┘                            │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

The loop continues until:

1. The model produces a final response (no tool calls)
2. A maximum iteration limit is reached
3. An explicit stop condition is met (error, user cancel, etc.)

---

## The Basic Agent Loop Implementation

### Anthropic Version

```python
import anthropic

def run_agent_loop(
    client: anthropic.Anthropic,
    user_message: str,
    tools: list[dict],
    tool_functions: dict[str, callable],
    max_iterations: int = 10,
    model: str = "claude-sonnet-4-20250514"
) -> str:
    """
    Run a tool-calling agent loop until completion or max iterations.
    
    Args:
        client: Anthropic client
        user_message: Initial user query
        tools: Tool definitions
        tool_functions: Map of tool name -> callable
        max_iterations: Safety limit to prevent runaway loops
        model: Model to use
    
    Returns:
        Final text response from the model
    """
    messages = [{"role": "user", "content": user_message}]
    
    for iteration in range(max_iterations):
        # Call the model
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            tools=tools,
            messages=messages
        )
        
        # Check if we're done (no tool use)
        if response.stop_reason == "end_turn":
            # Extract and return the text response
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""  # No text content
        
        # Check for tool use
        if response.stop_reason == "tool_use":
            # Add assistant's response to messages
            messages.append({"role": "assistant", "content": response.content})
            
            # Process all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # Execute the tool
                    result, is_error = execute_tool(
                        block.name, 
                        block.input, 
                        tool_functions
                    )
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error
                    })
            
            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})
        
        else:
            # Unexpected stop reason
            raise ValueError(f"Unexpected stop_reason: {response.stop_reason}")
    
    # Max iterations reached
    raise RuntimeError(f"Agent loop exceeded {max_iterations} iterations")


def execute_tool(name: str, arguments: dict, registry: dict) -> tuple[str, bool]:
    """Execute a tool and return (result, is_error)."""
    if name not in registry:
        return f"Error: Unknown tool '{name}'", True
    
    try:
        result = registry[name](**arguments)
        return str(result), False
    except Exception as e:
        return f"Error: {str(e)}", True
```

### OpenAI Responses API Version

```python
from openai import OpenAI
import json

def run_agent_loop(
    client: OpenAI,
    user_message: str,
    tools: list[dict],
    tool_functions: dict[str, callable],
    max_iterations: int = 10,
    model: str = "gpt-4o"
) -> str:
    """Run a tool-calling agent loop with OpenAI Responses API."""
    
    input_list = [{"role": "user", "content": user_message}]
    
    for iteration in range(max_iterations):
        response = client.responses.create(
            model=model,
            input=input_list,
            tools=tools
        )
        
        # Check for function calls in output
        function_calls = [
            item for item in response.output 
            if item.type == "function_call"
        ]
        
        if not function_calls:
            # No function calls — we're done
            return response.output_text
        
        # Add response output to input (includes function_call items)
        input_list += response.output
        
        # Execute each function call and add results
        for fc in function_calls:
            args = json.loads(fc.arguments)
            result, is_error = execute_tool(fc.name, args, tool_functions)
            
            input_list.append({
                "type": "function_call_output",
                "call_id": fc.call_id,
                "output": result
            })
    
    raise RuntimeError(f"Agent loop exceeded {max_iterations} iterations")
```

---

## Loop Termination Conditions

### 1. Natural Completion

The model produces a response without requesting any tools:

```python
# Anthropic
if response.stop_reason == "end_turn":
    # Done! Extract text response

# OpenAI
function_calls = [item for item in response.output if item.type == "function_call"]
if not function_calls:
    # Done! Get output_text
```

### 2. Max Iterations Guard

**Critical safety measure.** Without this, bugs or adversarial inputs could cause infinite loops:

```python
MAX_ITERATIONS = 10  # Adjust based on your use case

for iteration in range(MAX_ITERATIONS):
    # ... loop body ...

raise RuntimeError("Max iterations exceeded")
```

**Choosing the limit:**

- Simple tasks: 3-5 iterations
- Complex research: 10-20 iterations
- Agentic workflows: 20-50 (with cost monitoring)

### 3. Cost/Token Budget

Track token usage and stop before exceeding budget:

```python
total_tokens = 0
MAX_TOKENS = 100_000

for iteration in range(MAX_ITERATIONS):
    response = client.messages.create(...)
    
    total_tokens += response.usage.input_tokens + response.usage.output_tokens
    
    if total_tokens > MAX_TOKENS:
        raise RuntimeError(f"Token budget exceeded: {total_tokens}")
```

### 4. Explicit Stop Conditions

Stop based on tool results or model behavior:

```python
for iteration in range(MAX_ITERATIONS):
    # ... execute tools ...
    
    # Stop if critical error
    if any(r["is_error"] and "FATAL" in r["content"] for r in tool_results):
        return "Agent stopped due to critical error"
    
    # Stop if model is repeating itself
    if is_repeating(messages):
        return "Agent stopped: repetitive behavior detected"
```

---

## Parallel Tool Calls

Models can request **multiple tools in a single response**. This is parallel tool calling.

### When Parallel Calls Happen

User: "What's the weather in Tokyo and New York?"

Model response (Anthropic):

```python
response.content = [
    {"type": "text", "text": "I'll check both locations for you."},
    {
        "type": "tool_use",
        "id": "toolu_01ABC",
        "name": "get_weather",
        "input": {"location": "Tokyo, Japan"}
    },
    {
        "type": "tool_use",
        "id": "toolu_02DEF",
        "name": "get_weather",
        "input": {"location": "New York, NY"}
    }
]
```

Both tools requested in the same turn → you execute both, return both results.

### Why Parallel Calls Matter

**Efficiency:**

- Sequential: 2 queries × 2 API calls = 4 round trips
- Parallel: 1 query → 2 tools → 1 result return = 2 round trips

**Latency:**

- You can execute the tools in parallel on your side too (if they're independent)
- User sees results faster

---

## Handling Parallel Tool Calls

### Pattern 1: Sequential Execution (Simple)

Execute tools one at a time. Simple, but doesn't leverage parallelism:

```python
tool_results = []

for block in response.content:
    if block.type == "tool_use":
        result = execute_tool(block.name, block.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": result
        })

# Return all results together
messages.append({"role": "user", "content": tool_results})
```

### Pattern 2: Parallel Execution (Async)

Execute independent tools concurrently:

```python
import asyncio

async def execute_tools_parallel(tool_calls: list, registry: dict) -> list:
    """Execute multiple tools in parallel."""
    
    async def execute_one(call):
        # If tool is async
        if asyncio.iscoroutinefunction(registry[call.name]):
            result = await registry[call.name](**call.input)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: registry[call.name](**call.input)
            )
        
        return {
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": str(result)
        }
    
    # Execute all tools concurrently
    results = await asyncio.gather(
        *[execute_one(call) for call in tool_calls],
        return_exceptions=True
    )
    
    # Handle any exceptions
    tool_results = []
    for call, result in zip(tool_calls, results):
        if isinstance(result, Exception):
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": f"Error: {str(result)}",
                "is_error": True
            })
        else:
            tool_results.append(result)
    
    return tool_results
```

### Pattern 3: Selective Parallelism

Some tools can run in parallel; others have dependencies:

```python
def categorize_tool_calls(calls: list) -> tuple[list, list]:
    """
    Separate independent calls (can parallelize) from dependent ones.
    """
    # Tools that are always safe to parallelize
    PARALLELIZABLE = {"get_weather", "get_stock_price", "search_web"}
    
    parallel = [c for c in calls if c.name in PARALLELIZABLE]
    sequential = [c for c in calls if c.name not in PARALLELIZABLE]
    
    return parallel, sequential

# In the loop:
parallel_calls, sequential_calls = categorize_tool_calls(tool_calls)

# Execute parallel ones first
parallel_results = await execute_tools_parallel(parallel_calls, registry)

# Then sequential
sequential_results = []
for call in sequential_calls:
    result = execute_tool(call.name, call.input, registry)
    sequential_results.append(result)

all_results = parallel_results + sequential_results
```

---

## Controlling Parallel Tool Use

### Anthropic: `disable_parallel_tool_use`

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=tools,
    tool_choice={
        "type": "auto",
        "disable_parallel_tool_use": True  # Force one tool at a time
    },
    messages=messages
)
```

**When to disable:**

- Tools have dependencies (one must complete before another)
- Debugging (easier to trace single calls)
- Cost control (parallel = more tokens per response)

### OpenAI: `parallel_tool_calls`

```python
response = client.responses.create(
    model="gpt-4o",
    input=input_list,
    tools=tools,
    parallel_tool_calls=False  # One function call at a time
)
```

**Note:** Some OpenAI reasoning models (o3, o4-mini) may not support parallel tool calls. Check model documentation.

---

## When Parallel Calls Cause Problems

### Problem 1: Dependencies Between Calls

User: "Get the weather for my current location"

If model calls both `get_user_location` and `get_weather` in parallel:

- `get_weather` needs the result from `get_user_location`
- Parallel execution fails

**Solution:** Disable parallel calls for workflows with dependencies, or design tools to be self-contained.

### Problem 2: Rate Limits

Parallel execution of 5 API calls might exceed rate limits on external services.

**Solution:** Use semaphores or rate limiters:

```python
import asyncio

RATE_LIMIT_SEMAPHORE = asyncio.Semaphore(3)  # Max 3 concurrent

async def execute_with_rate_limit(call, registry):
    async with RATE_LIMIT_SEMAPHORE:
        return await execute_tool_async(call, registry)
```

### Problem 3: Inconsistent Results

Parallel calls to the same resource might see inconsistent state.

Example: Two calls to `get_account_balance` during a transaction might return different values.

**Solution:** Sequential execution for stateful operations.

---

## The Tool Runner (SDK Feature)

Anthropic provides a **Tool Runner** that handles the agent loop automatically:

```python
import anthropic
from anthropic import beta_tool

client = anthropic.Anthropic()

# Define tools with decorator
@beta_tool
def get_weather(location: str) -> str:
    """Get the current weather in a given location."""
    return f"Weather in {location}: 72°F, sunny"

@beta_tool
def get_time(timezone: str) -> str:
    """Get the current time in a timezone."""
    from datetime import datetime
    return datetime.now().isoformat()

# Tool runner handles the loop automatically
runner = client.beta.messages.tool_runner(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=[get_weather, get_time],
    messages=[{"role": "user", "content": "What's the weather in SF and the time in NYC?"}]
)

# Iterate through the loop
for message in runner:
    print(f"Iteration: {message.stop_reason}")

# Or get final message directly
final = runner.get_final_message()
print(final.content[0].text)
```

**What Tool Runner handles:**

- Automatic tool execution
- Result formatting
- Conversation state management
- Error handling (returns `is_error: true` on exceptions)
- Automatic compaction (optional, for long-running tasks)

**When to use Tool Runner:**

- Standard tool calling workflows
- When you don't need custom control flow

**When to use manual loop:**

- Custom termination conditions
- Streaming requirements
- Human-in-the-loop patterns
- Selective parallel execution

---

## Complete Agent Loop with Parallel Execution

```python
import anthropic
import asyncio
from typing import Callable

class ToolAgent:
    def __init__(
        self,
        client: anthropic.Anthropic,
        tools: list[dict],
        tool_functions: dict[str, Callable],
        model: str = "claude-sonnet-4-20250514",
        max_iterations: int = 10,
        parallel_execution: bool = True
    ):
        self.client = client
        self.tools = tools
        self.tool_functions = tool_functions
        self.model = model
        self.max_iterations = max_iterations
        self.parallel_execution = parallel_execution
    
    async def run(self, user_message: str) -> str:
        """Run the agent loop asynchronously."""
        messages = [{"role": "user", "content": user_message}]
        
        for iteration in range(self.max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=self.tools,
                messages=messages
            )
            
            # Check for completion
            if response.stop_reason == "end_turn":
                return self._extract_text(response)
            
            if response.stop_reason != "tool_use":
                raise ValueError(f"Unexpected stop_reason: {response.stop_reason}")
            
            # Add assistant response
            messages.append({"role": "assistant", "content": response.content})
            
            # Extract tool calls
            tool_calls = [
                block for block in response.content 
                if block.type == "tool_use"
            ]
            
            # Execute tools
            if self.parallel_execution:
                tool_results = await self._execute_parallel(tool_calls)
            else:
                tool_results = await self._execute_sequential(tool_calls)
            
            # Add results
            messages.append({"role": "user", "content": tool_results})
        
        raise RuntimeError(f"Max iterations ({self.max_iterations}) exceeded")
    
    async def _execute_parallel(self, tool_calls: list) -> list:
        """Execute tools in parallel."""
        async def execute_one(call):
            try:
                func = self.tool_functions[call.name]
                if asyncio.iscoroutinefunction(func):
                    result = await func(**call.input)
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, lambda: func(**call.input)
                    )
                return {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": str(result)
                }
            except Exception as e:
                return {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": f"Error: {str(e)}",
                    "is_error": True
                }
        
        return await asyncio.gather(*[execute_one(c) for c in tool_calls])
    
    async def _execute_sequential(self, tool_calls: list) -> list:
        """Execute tools one at a time."""
        results = []
        for call in tool_calls:
            result = await self._execute_parallel([call])
            results.extend(result)
        return results
    
    def _extract_text(self, response) -> str:
        """Extract text from response."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""


# Usage
async def main():
    client = anthropic.Anthropic()
    
    tools = [
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"]
            }
        }
    ]
    
    def get_weather(location: str) -> str:
        return f"{location}: 72°F, sunny"
    
    agent = ToolAgent(
        client=client,
        tools=tools,
        tool_functions={"get_weather": get_weather}
    )
    
    result = await agent.run("What's the weather in Tokyo and London?")
    print(result)

asyncio.run(main())
```

---

## Key Takeaways

1. **The agent loop is the core pattern** — Request → Tool calls → Execute → Return results → Repeat until done
    
2. **Always set max iterations** — Without a limit, bugs can cause infinite loops and runaway costs
    
3. **Parallel tool calls improve efficiency** — But only when tools are independent
    
4. **Control parallelism explicitly** — Use `disable_parallel_tool_use` (Anthropic) or `parallel_tool_calls` (OpenAI) when needed
    
5. **Consider using Tool Runner** — SDK-provided automation handles most cases; manual loop for custom control
    
6. **Watch for dependencies** — If tool B needs output from tool A, disable parallel calls or design tools to be self-contained
    

---

_Next: Note 4 — Error Handling and Security_