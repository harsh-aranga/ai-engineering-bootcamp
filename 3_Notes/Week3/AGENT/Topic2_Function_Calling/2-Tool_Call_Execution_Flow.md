# Note 2: The Tool Calling Execution Flow

## Week 3 Agents — Days 3-4 | Function Calling / Tool Use

---

## The Five-Step Flow

Tool calling follows a consistent pattern across all providers:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. REQUEST: You send user prompt + tool definitions           │
│                              ↓                                  │
│  2. DECISION: LLM decides if tool is needed                    │
│                              ↓                                  │
│  3. TOOL CALL: LLM returns structured request (not execution!) │
│                              ↓                                  │
│  4. EXECUTION: YOUR code runs the actual function              │
│                              ↓                                  │
│  5. COMPLETION: You send results back, LLM forms final answer  │
└─────────────────────────────────────────────────────────────────┘
```

Let's walk through each step with concrete examples.

---

## Step 1: You Send Tools + User Prompt

Your API request includes:

- The user's message
- Tool definitions (what tools are available)
- Optional: system prompt, model parameters

**Anthropic Example:**

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=[
        {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    ],
    messages=[
        {"role": "user", "content": "What's the weather in Tokyo?"}
    ]
)
```

**OpenAI Responses API Example:**

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    input=[
        {"role": "user", "content": "What's the weather in Tokyo?"}
    ],
    tools=[
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"],
                "additionalProperties": False
            }
        }
    ]
)
```

---

## Step 2: LLM Decides Whether to Use a Tool

The model evaluates:

- Does the query need external data/action?
- Is there a tool that matches the need?
- What arguments should be passed?

**Possible outcomes:**

1. **No tool needed** → Model responds directly with text
2. **Tool needed** → Model returns a tool call request

The model doesn't "execute" anything. It produces a structured output saying "I want to call this function with these arguments."

---

## Step 3: Understanding the Tool Call Response

When the model decides to use a tool, the response structure differs by provider.

### Anthropic Response Structure

```python
# response.stop_reason == "tool_use"

# response.content contains:
[
    {
        "type": "text",
        "text": "I'll check the weather in Tokyo for you."
    },
    {
        "type": "tool_use",
        "id": "toolu_01XFDUDYJgAACzvnptvVoYEL",  # Unique ID - save this!
        "name": "get_weather",
        "input": {
            "location": "Tokyo, Japan"
        }
    }
]
```

**Key fields:**

- `stop_reason: "tool_use"` — Signals "I want to call a tool"
- `type: "tool_use"` — The content block type
- `id` — Unique identifier you'll need when returning results
- `name` — Which tool to call
- `input` — Arguments (already parsed as dict, not JSON string)

### OpenAI Responses API Structure

```python
# response.output contains items of different types

[
    {
        "type": "message",
        "content": [{"type": "output_text", "text": "Let me check that for you."}]
    },
    {
        "type": "function_call",
        "id": "fc_67d2e3ccdee08191...",
        "call_id": "call_Co8dkB8h7NcTYq9d",  # Use this for results!
        "name": "get_weather",
        "arguments": "{\"location\": \"Tokyo, Japan\"}"  # JSON string - parse it!
    }
]
```

**Key difference:** OpenAI returns `arguments` as a JSON string. You must parse it:

```python
import json
args = json.loads(tool_call.arguments)
```

---

## Step 4: You Execute the Tool

This is where **your code** does the actual work. The LLM requested; you deliver.

```python
def get_weather(location: str) -> dict:
    """Your actual implementation - calls a weather API, database, etc."""
    # Real implementation would call an API
    return {
        "temperature": 22,
        "unit": "celsius",
        "conditions": "Partly cloudy"
    }

# Extract the tool call from response
for block in response.content:
    if block.type == "tool_use":
        tool_name = block.name
        tool_input = block.input
        tool_use_id = block.id
        
        # Execute the matching function
        if tool_name == "get_weather":
            result = get_weather(**tool_input)
```

**Critical insight:** The LLM has no ability to execute code. It generated text that _looks like_ a function call. Your application must:

1. Parse the tool call
2. Map it to an actual function
3. Execute that function
4. Format the result for return

---

## Step 5: Return Results and Get Final Response

You must send the tool result back to the LLM in the correct format.

### Anthropic: Returning Tool Results

```python
# Continue the conversation with tool results
follow_up = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=[...],  # Same tools as before
    messages=[
        # Original user message
        {"role": "user", "content": "What's the weather in Tokyo?"},
        
        # Assistant's response (including the tool_use block)
        {"role": "assistant", "content": response.content},
        
        # Your tool result
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_01XFDUDYJgAACzvnptvVoYEL",  # Must match!
                    "content": '{"temperature": 22, "unit": "celsius", "conditions": "Partly cloudy"}'
                }
            ]
        }
    ]
)
```

### OpenAI Responses API: Returning Tool Results

```python
# Build the input list with all context
input_list = [
    {"role": "user", "content": "What's the weather in Tokyo?"}
]

# Add the model's output (includes the function_call)
input_list += response.output

# Add the tool result
input_list.append({
    "type": "function_call_output",
    "call_id": "call_Co8dkB8h7NcTYq9d",  # Must match the call_id!
    "output": '{"temperature": 22, "unit": "celsius", "conditions": "Partly cloudy"}'
})

# Get final response
final_response = client.responses.create(
    model="gpt-4o",
    input=input_list,
    tools=[...]  # Same tools
)

print(final_response.output_text)
# "The weather in Tokyo is currently 22°C and partly cloudy."
```

---

## The Complete Flow Visualized

```
YOU                                    LLM
 │                                      │
 │  ──── tools + "weather in Tokyo?" ──►│
 │                                      │
 │                                      │ (decides tool needed)
 │                                      │
 │  ◄── stop_reason: tool_use ─────────│
 │      tool: get_weather               │
 │      args: {location: "Tokyo"}       │
 │      id: "toolu_01XF..."             │
 │                                      │
 │  (you call real weather API)         │
 │                                      │
 │  ──── tool_result ──────────────────►│
 │       id: "toolu_01XF..."            │
 │       content: {temp: 22, ...}       │
 │                                      │
 │                                      │ (formulates answer)
 │                                      │
 │  ◄── "It's 22°C in Tokyo..." ───────│
 │                                      │
```

---

## Stop Reasons: How to Know What Happened

### Anthropic Stop Reasons

|`stop_reason`|Meaning|Action|
|---|---|---|
|`end_turn`|Model finished responding|Done, process the text|
|`tool_use`|Model wants to call a tool|Execute tool, return result|
|`max_tokens`|Response truncated|Retry with higher `max_tokens`|
|`pause_turn`|Server tool limit reached|Continue conversation to resume|
|`stop_sequence`|Hit a stop sequence|Process partial response|

### OpenAI Responses API

OpenAI uses item types in `output` rather than a single stop reason. Check the types:

```python
for item in response.output:
    if item.type == "function_call":
        # Tool call requested
        pass
    elif item.type == "message":
        # Text response
        pass
```

---

## Parsing Tool Calls: Provider Patterns

### Anthropic Pattern

```python
def extract_tool_calls(response):
    """Extract all tool calls from Anthropic response."""
    tool_calls = []
    
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input  # Already a dict
            })
    
    return tool_calls
```

### OpenAI Responses API Pattern

```python
import json

def extract_tool_calls(response):
    """Extract all tool calls from OpenAI Responses API response."""
    tool_calls = []
    
    for item in response.output:
        if item.type == "function_call":
            tool_calls.append({
                "call_id": item.call_id,
                "name": item.name,
                "input": json.loads(item.arguments)  # Must parse JSON!
            })
    
    return tool_calls
```

---

## Executing Tools: The Dispatch Pattern

A common pattern for mapping tool names to functions:

```python
# Define your tools
def get_weather(location: str) -> str:
    # Real implementation
    return '{"temp": 22, "conditions": "sunny"}'

def search_database(query: str, limit: int = 10) -> str:
    # Real implementation
    return '[{"id": 1, "name": "Result 1"}]'

def send_email(to: str, subject: str, body: str) -> str:
    # Real implementation
    return '{"status": "sent", "message_id": "abc123"}'

# Map names to functions
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "search_database": search_database,
    "send_email": send_email,
}

def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments."""
    if name not in TOOL_REGISTRY:
        return f'{{"error": "Unknown tool: {name}"}}'
    
    func = TOOL_REGISTRY[name]
    
    try:
        result = func(**arguments)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'
```

---

## Formatting Tool Results

Tool results should be formatted for LLM consumption:

### String Results

```python
# Simple string
"The temperature is 22°C"

# JSON string (preferred for structured data)
'{"temperature": 22, "unit": "celsius", "conditions": "sunny"}'
```

### Anthropic: Rich Content Types

Anthropic supports multiple content types in tool results:

```python
# Text result
{
    "type": "tool_result",
    "tool_use_id": "toolu_01...",
    "content": "Temperature is 22°C"
}

# Structured content blocks
{
    "type": "tool_result",
    "tool_use_id": "toolu_01...",
    "content": [
        {"type": "text", "text": "Weather data retrieved successfully"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
    ]
}

# Error result
{
    "type": "tool_result",
    "tool_use_id": "toolu_01...",
    "content": "Error: Location 'Atlantis' not found in database",
    "is_error": True
}
```

---

## Critical Ordering Rules

### Anthropic Message Ordering

1. **Tool results must immediately follow tool use** — You cannot insert messages between the assistant's tool_use and your tool_result
    
2. **Tool results must come first in content array** — Text must come AFTER tool results
    

```python
# WRONG - text before tool_result
{
    "role": "user",
    "content": [
        {"type": "text", "text": "Here are the results:"},  # ❌ WRONG
        {"type": "tool_result", "tool_use_id": "...", "content": "..."}
    ]
}

# CORRECT - tool_result first
{
    "role": "user",
    "content": [
        {"type": "tool_result", "tool_use_id": "...", "content": "..."},
        {"type": "text", "text": "What should I do next?"}  # ✅ After
    ]
}
```

### OpenAI Responses API Ordering

1. **Include all prior output items** — When continuing, add `response.output` to your input
2. **Function output references call_id** — Must match exactly

```python
input_list = [
    {"role": "user", "content": "Original question"}
]

# Add ALL output items from previous response
input_list += response.output

# Add your tool result
input_list.append({
    "type": "function_call_output",
    "call_id": tool_call.call_id,  # Must match exactly
    "output": result_string
})
```

---

## When the Model Doesn't Use Tools

The model may respond directly without using tools when:

- The query doesn't need external data
- It can answer from its training knowledge
- No suitable tool is available
- The query is ambiguous (some models ask for clarification)

```python
# Check if tools were used
if response.stop_reason == "end_turn":
    # No tool use, just text response
    print(response.content[0].text)
elif response.stop_reason == "tool_use":
    # Tool call requested
    handle_tool_calls(response)
```

---

## Common Errors and How to Fix Them

### "Did not find tool_result block" (Anthropic)

**Cause:** You sent a message after assistant's tool_use without including the tool_result.

**Fix:** Always include tool_result immediately after assistant message containing tool_use:

```python
messages=[
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": response.content},  # Contains tool_use
    {"role": "user", "content": [{"type": "tool_result", ...}]}  # Must include this
]
```

### "No tool call found for function call output" (OpenAI)

**Cause:** The `call_id` doesn't match, or you didn't include the original function_call item.

**Fix:** Include ALL output items and ensure call_id matches exactly:

```python
input_list += response.output  # Includes the function_call item
input_list.append({
    "type": "function_call_output",
    "call_id": tool_call.call_id,  # Copy exactly
    "output": result
})
```

### "Requests must define tools" (Anthropic)

**Cause:** Your follow-up request includes tool_use/tool_result blocks but doesn't define tools.

**Fix:** Always include the same `tools` parameter in follow-up requests:

```python
response = client.messages.create(
    model="...",
    tools=tools,  # Don't forget this!
    messages=[...]
)
```

---

## Key Takeaways

1. **Five-step flow:** Request → Decision → Tool Call → Execution → Completion
    
2. **LLM requests, you execute** — The model outputs structured JSON, your code does the work
    
3. **Stop reason tells you what happened** — `tool_use` (Anthropic) or `function_call` item (OpenAI) means "execute this"
    
4. **ID matching is critical** — `tool_use_id` (Anthropic) and `call_id` (OpenAI) must match exactly when returning results
    
5. **Message ordering matters** — Tool results must immediately follow tool use, with no intervening messages
    
6. **Include full context** — Follow-up requests need the original messages, tool definitions, and proper result format
    

---

_Next: Note 3 — The Agent Loop and Parallel Execution_