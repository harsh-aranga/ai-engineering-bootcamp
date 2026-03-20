# Note 3: Trajectory Evaluation — Recording and Analyzing Paths

## Why This Matters

Task-based evaluation (Note 2) tells you _if_ your agent succeeded. Trajectory evaluation tells you _how_ it got there.

Two agents can produce the same correct answer but take wildly different paths:

- Agent A: Searched → Found answer → Responded (3 steps)
- Agent B: Searched wrong thing → Retried → Searched again → Found answer → Responded (5 steps)

Both succeed on task-based eval. But Agent B has a problem you'll want to fix before production.

Trajectory evaluation captures and analyzes the sequence of messages and tool calls—the agent's "decision trail"—so you can:

- Verify the agent used the right tools in the right order
- Catch inefficient or dangerous paths that happen to work
- Regression test that refactors don't break expected behavior
- Debug failures by seeing exactly where things went wrong

---

## What Is a Trajectory?

A trajectory is the complete sequence of messages exchanged during an agent's execution. In OpenAI message format (which is the standard for most agent frameworks), it looks like this:

```python
trajectory = [
    # 1. User input
    {"role": "user", "content": "What's the weather in Tokyo?"},
    
    # 2. Assistant decides to call a tool
    {
        "role": "assistant",
        "content": "",  # Empty content when making tool calls
        "tool_calls": [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"city": "Tokyo"}'
                }
            }
        ]
    },
    
    # 3. Tool returns result
    {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": "72°F, partly cloudy"
    },
    
    # 4. Assistant synthesizes final response
    {
        "role": "assistant",
        "content": "The weather in Tokyo is 72°F and partly cloudy."
    }
]
```

### Key Components

|Message Role|Purpose|Contains|
|---|---|---|
|`user`|Initial query or follow-up|Natural language input|
|`assistant`|LLM decisions|Either `content` (text) or `tool_calls` (actions)|
|`tool`|Tool execution results|Output from tool, linked via `tool_call_id`|

### What Makes a "Good" Trajectory?

A good trajectory:

1. **Progresses toward the goal** — Each step moves closer to answering the user's question
2. **Uses appropriate tools** — Selects the right tool for each sub-task
3. **Passes correct arguments** — Tool calls have valid, sensible parameters
4. **Is efficient** — No unnecessary loops, retries, or redundant calls
5. **Handles errors gracefully** — Recovers from tool failures appropriately

---

## The `agentevals` Library

LangChain provides an open-source library called `agentevals` specifically for trajectory evaluation. It offers two main approaches:

1. **Trajectory Match Evaluators** — Compare actual trajectory against a reference (deterministic)
2. **Trajectory LLM-as-Judge** — Use an LLM to assess trajectory quality (flexible)

This note focuses on trajectory matching. Note 4 covers LLM-as-judge.

### Installation

```bash
pip install agentevals
```

### Basic Usage

```python
from agentevals.trajectory.match import create_trajectory_match_evaluator
import json

# Create an evaluator
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict"  # or "unordered", "subset", "superset"
)

# Actual trajectory from running your agent
actual_trajectory = [
    {"role": "user", "content": "What's the weather in SF?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"city": "San Francisco"})
            }
        }]
    },
    {"role": "tool", "content": "72°F, sunny"},
    {"role": "assistant", "content": "It's 72°F and sunny in San Francisco."}
]

# Expected trajectory (what you want the agent to do)
reference_trajectory = [
    {"role": "user", "content": "What's the weather in SF?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"city": "San Francisco"})
            }
        }]
    },
    {"role": "tool", "content": "72°F, sunny"},
    {"role": "assistant", "content": "The weather in SF is 72 degrees and sunny."}
]

# Evaluate
result = evaluator(
    outputs=actual_trajectory,
    reference_outputs=reference_trajectory
)

print(result)
# {'key': 'trajectory_strict_match', 'score': True, 'comment': None}
```

**Source:** agentevals GitHub repository (https://github.com/langchain-ai/agentevals)

---

## Trajectory Match Modes

The `trajectory_match_mode` parameter controls how strictly the evaluator compares trajectories. There are four modes:

### 1. Strict Match

**What it checks:** Same messages, same order, same tool calls.

**Use when:** You need to enforce a specific sequence of operations.

```python
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict"
)
```

**Example scenario:** "Always check company policy BEFORE authorizing vacation time."

```
Expected: user → policy_lookup → tool_result → vacation_request → tool_result → response
Actual:   user → vacation_request → tool_result → policy_lookup → tool_result → response
Result:   FAIL (wrong order)
```

**Note:** Strict mode allows differences in message _content_ but requires identical tool calls in identical order.

### 2. Unordered Match

**What it checks:** Same tool calls, any order.

**Use when:** You care that specific tools were called, but order doesn't matter.

```python
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="unordered"
)
```

**Example scenario:** "Must call both weather API and calendar API, but order doesn't matter."

```
Expected: user → get_weather → get_calendar → response
Actual:   user → get_calendar → get_weather → response
Result:   PASS (same tools, different order)
```

### 3. Subset Match

**What it checks:** Reference trajectory is a subset of actual trajectory.

**Use when:** You want to ensure the agent didn't call any tools beyond the expected ones.

```python
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="subset"
)
```

**Example scenario:** "Agent should ONLY use approved tools, no extras."

```
Expected: [get_weather]
Actual:   [get_weather, web_search]
Result:   FAIL (actual has extra tool not in reference)
```

### 4. Superset Match

**What it checks:** Actual trajectory contains all expected tool calls (and possibly more).

**Use when:** You want to ensure key tools were called, but extra tools are acceptable.

```python
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="superset"
)
```

**Example scenario:** "Must call authentication, but can also call other tools."

```
Expected: [authenticate]
Actual:   [authenticate, log_action, notify_user]
Result:   PASS (actual includes all expected tools)
```

### Match Mode Summary

|Mode|Actual vs Reference|Order Matters?|Extra Tools OK?|
|---|---|---|---|
|`strict`|Must be identical|Yes|No|
|`unordered`|Must have same tools|No|No|
|`subset`|Reference ⊆ Actual|No|Yes|
|`superset`|Actual ⊇ Reference|No|Yes|

---

## Tool Argument Matching

By default, trajectory matching requires tool arguments to match exactly. But LLMs generate arguments non-deterministically—"San Francisco" vs "SF" vs "san francisco" might all be valid.

The `tool_args_match_mode` parameter controls this:

### Argument Match Modes

```python
# Default: exact match required
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_mode="exact"  # Default
)

# Ignore arguments entirely (only tool names matter)
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_mode="ignore"
)

# Actual args must contain all reference args (can have extras)
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_mode="superset"
)

# Actual args must be subset of reference args
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_mode="subset"
)
```

### Custom Argument Matchers

For fine-grained control, use `tool_args_match_overrides` with a custom function:

```python
import json
from agentevals.trajectory.match import create_trajectory_match_evaluator

# Custom matcher: case-insensitive city comparison
def city_matcher(actual_args: dict, reference_args: dict) -> bool:
    """Compare city arguments case-insensitively."""
    actual_city = actual_args.get("city", "").lower()
    reference_city = reference_args.get("city", "").lower()
    return actual_city == reference_city

evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_mode="exact",  # Default for other tools
    tool_args_match_overrides={
        "get_weather": city_matcher  # Custom for this specific tool
    }
)

# Now "SF" matches "sf" matches "San Francisco"... wait, no.
# This example only does case-insensitive. For synonyms, you'd need more logic.
```

You can also specify that only certain fields must match:

```python
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_overrides={
        # For search tool, only 'query' field must match exactly
        "search": ["query"],
        # For calendar tool, ignore all arguments
        "get_calendar": "ignore",
        # For weather, use custom function
        "get_weather": city_matcher
    }
)
```

**Source:** agentevals GitHub repository, tool_args_match_modes documentation

---

## When to Use Trajectory Match

Trajectory matching works best for:

### 1. Deterministic Workflows

When there's a _known correct path_ for a given input:

```python
# Example: Customer refund workflow must follow this exact sequence
reference = [
    # Step 1: Look up order
    {"role": "assistant", "tool_calls": [{"function": {"name": "lookup_order", ...}}]},
    # Step 2: Check refund policy
    {"role": "assistant", "tool_calls": [{"function": {"name": "check_policy", ...}}]},
    # Step 3: Process refund
    {"role": "assistant", "tool_calls": [{"function": {"name": "process_refund", ...}}]},
]
```

### 2. Regression Testing

After refactoring, verify the agent still takes the same paths:

```python
# Before refactor: agent did [search → summarize]
# After refactor: should still do [search → summarize]

evaluator = create_trajectory_match_evaluator(trajectory_match_mode="strict")
result = evaluator(outputs=new_agent_trajectory, reference_outputs=old_agent_trajectory)

if not result["score"]:
    raise Exception("Refactor changed agent behavior!")
```

### 3. Tool Selection Unit Tests

Test that specific queries trigger specific tools:

```python
test_cases = [
    {
        "input": "What's the weather?",
        "expected_tools": ["get_weather"]
    },
    {
        "input": "Book a meeting",
        "expected_tools": ["check_calendar", "create_event"]
    },
    {
        "input": "Send an email to John",
        "expected_tools": ["lookup_contact", "send_email"]
    }
]

for case in test_cases:
    trajectory = run_agent(case["input"])
    actual_tools = extract_tool_names(trajectory)
    
    evaluator = create_trajectory_match_evaluator(
        trajectory_match_mode="unordered",
        tool_args_match_mode="ignore"  # Only check tool names
    )
    
    result = evaluator(
        outputs=trajectory,
        reference_outputs=build_reference(case["expected_tools"])
    )
```

---

## Limitations of Trajectory Matching

Trajectory matching is powerful but has significant limitations:

### 1. Multiple Valid Paths

Real agents are non-deterministic. The same query might have multiple correct trajectories:

```
Query: "What's happening in tech news?"

Valid Path A: search("tech news today") → summarize
Valid Path B: search("technology headlines") → summarize  
Valid Path C: search("tech") → search("startup news") → summarize
```

Strict matching fails on all but one of these, even though all are valid.

### 2. Content Variability

Tool results vary over time:

- Weather changes
- Search results change
- Database state changes

If your reference trajectory has `"72°F"` but the actual run gets `"75°F"`, that's not an agent failure—it's reality.

### 3. Argument Variations

LLMs phrase arguments differently:

- `{"city": "San Francisco"}` vs `{"city": "SF"}`
- `{"query": "weather san francisco"}` vs `{"query": "SF weather forecast"}`

You'll need custom matchers or `tool_args_match_mode="ignore"` to handle this.

### 4. Maintenance Burden

Reference trajectories become stale:

- You add a new tool → all references need updating
- You rename a tool → all references break
- You change tool signatures → all references need new arguments

### When NOT to Use Trajectory Matching

- **Exploratory agents** that should find their own path
- **Creative tasks** with no "correct" sequence
- **Dynamic environments** where tool results change frequently
- **Early development** when you're still iterating on tools and flow

For these cases, use **LLM-as-judge trajectory evaluation** (Note 4) instead.

---

## Recording Trajectories

Before you can evaluate trajectories, you need to capture them. Here's how:

### From LangGraph

LangGraph provides a utility to extract trajectories from a thread:

```python
from agentevals.graph_trajectory.utils import extract_langgraph_trajectory_from_thread
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# Create agent with checkpointing
checkpointer = MemorySaver()
agent = create_react_agent(
    model="gpt-4o-mini",
    tools=[...],
    checkpointer=checkpointer
)

# Run agent
agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather in SF?"}]},
    config={"configurable": {"thread_id": "123"}}
)

# Extract trajectory
trajectory = extract_langgraph_trajectory_from_thread(
    agent,
    {"configurable": {"thread_id": "123"}}
)

# trajectory["outputs"]["steps"] contains the node sequence
# trajectory["outputs"]["results"] contains outputs at each step
```

**Source:** agentevals documentation, Graph Trajectory section

### From Raw Agent Runs

If you're not using LangGraph, capture messages manually:

```python
def run_agent_with_trajectory(agent, user_input: str) -> tuple[str, list[dict]]:
    """Run agent and return (final_response, trajectory)."""
    
    trajectory = []
    
    # Add user message
    trajectory.append({"role": "user", "content": user_input})
    
    messages = [{"role": "user", "content": user_input}]
    
    while True:
        # Get LLM response
        response = agent.llm.chat(messages)
        
        if response.tool_calls:
            # Assistant decided to call tools
            trajectory.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response.tool_calls
                ]
            })
            
            # Execute tools
            for tool_call in response.tool_calls:
                result = agent.execute_tool(tool_call)
                trajectory.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            
            messages.append(response.model_dump())
        else:
            # Final response
            trajectory.append({
                "role": "assistant",
                "content": response.content
            })
            return response.content, trajectory
```

---

## Practical Example: Tool Selection Test Suite

Here's a complete example of using trajectory matching for regression testing:

```python
import json
from agentevals.trajectory.match import create_trajectory_match_evaluator

# Test cases: input → expected tool sequence
TOOL_SELECTION_TESTS = [
    {
        "name": "weather_query",
        "input": "What's the weather in Tokyo?",
        "expected_tools": [
            {"name": "get_weather", "args": {"city": "Tokyo"}}
        ]
    },
    {
        "name": "multi_tool_query",
        "input": "What's the weather and what events are happening in Tokyo?",
        "expected_tools": [
            {"name": "get_weather", "args": {"city": "Tokyo"}},
            {"name": "get_events", "args": {"city": "Tokyo"}}
        ]
    },
    {
        "name": "no_tool_query",
        "input": "Hello, how are you?",
        "expected_tools": []  # Should respond directly, no tools
    }
]


def build_reference_trajectory(expected_tools: list[dict]) -> list[dict]:
    """Build a minimal reference trajectory from expected tools."""
    trajectory = []
    
    if not expected_tools:
        # No tools expected - just a direct response
        trajectory.append({"role": "assistant", "content": "..."})
    else:
        # Build tool call message
        trajectory.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": tool["name"],
                        "arguments": json.dumps(tool["args"])
                    }
                }
                for tool in expected_tools
            ]
        })
        
        # Add tool result placeholders
        for tool in expected_tools:
            trajectory.append({"role": "tool", "content": "..."})
        
        # Add final response
        trajectory.append({"role": "assistant", "content": "..."})
    
    return trajectory


def run_tool_selection_tests(agent):
    """Run all tool selection tests against an agent."""
    
    # Use unordered mode (tool order doesn't matter)
    # Use custom arg matcher for city fields
    evaluator = create_trajectory_match_evaluator(
        trajectory_match_mode="unordered",
        tool_args_match_mode="exact",
        tool_args_match_overrides={
            "get_weather": lambda a, r: a.get("city", "").lower() == r.get("city", "").lower(),
            "get_events": lambda a, r: a.get("city", "").lower() == r.get("city", "").lower(),
        }
    )
    
    results = []
    
    for test in TOOL_SELECTION_TESTS:
        # Run agent
        _, actual_trajectory = run_agent_with_trajectory(agent, test["input"])
        
        # Build reference
        reference = build_reference_trajectory(test["expected_tools"])
        
        # Evaluate
        result = evaluator(
            outputs=actual_trajectory,
            reference_outputs=reference
        )
        
        results.append({
            "test": test["name"],
            "passed": result["score"],
            "details": result
        })
        
        if not result["score"]:
            print(f"FAILED: {test['name']}")
            print(f"  Expected tools: {[t['name'] for t in test['expected_tools']]}")
            print(f"  Actual trajectory: {actual_trajectory}")
    
    # Summary
    passed = sum(1 for r in results if r["passed"])
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    return results
```

---

## Key Takeaways

1. **A trajectory is the complete message sequence** including user inputs, assistant decisions, tool calls, tool results, and final responses.
    
2. **Four match modes serve different needs:**
    
    - `strict`: Same messages, same order (for required sequences)
    - `unordered`: Same tools, any order (for required tools, flexible order)
    - `subset`: Reference ⊆ actual (ensure no extra tools)
    - `superset`: Actual ⊇ reference (ensure required tools, extras OK)
3. **Tool argument matching is configurable:** Use `tool_args_match_mode` for global behavior, `tool_args_match_overrides` for per-tool custom logic.
    
4. **Trajectory matching works best for:**
    
    - Deterministic workflows with known correct paths
    - Regression testing after refactors
    - Tool selection unit tests
5. **Limitations are real:** Non-deterministic agents, multiple valid paths, and content variability make strict matching brittle. Use LLM-as-judge (Note 4) for more flexibility.
    
6. **Record trajectories systematically:** Use LangGraph's built-in extraction or implement custom recording for evaluation.
    

---

## References

- agentevals GitHub Repository: https://github.com/langchain-ai/agentevals
- agentevals PyPI Package: https://pypi.org/project/agentevals/
- LangSmith Trajectory Evaluation Docs: https://docs.langchain.com/langsmith/trajectory-evals
- LangGraph Agent Evaluation: https://langchain-ai.lang.chat/langgraph/agents/evals/