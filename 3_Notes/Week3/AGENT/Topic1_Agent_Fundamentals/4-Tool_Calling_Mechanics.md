# Tool Calling Mechanics (How LLMs "Use" Tools)

> **Doc References:** OpenAI Function Calling Guide, OpenAI Responses API docs, Anthropic Tool Use docs, OpenAI "New tools and features in the Responses API" (2025)

---

## The Fundamental Truth

**LLMs don't execute tools. They request tool execution.**

When we say an LLM "uses" a tool, here's what actually happens:

```
┌─────────────────────────────────────────────────────────────┐
│                    TOOL CALLING FLOW                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. You define tools (schema) → Send to LLM                 │
│                     ↓                                       │
│  2. LLM receives prompt + tool definitions                  │
│                     ↓                                       │
│  3. LLM decides: "I need to call get_weather(Tokyo)"        │
│                     ↓                                       │
│  4. LLM outputs structured request (NOT execution)          │
│     {"name": "get_weather", "arguments": {"location":"Tokyo"}}
│                     ↓                                       │
│  5. YOUR CODE parses this, calls actual weather API         │
│                     ↓                                       │
│  6. You send result back to LLM                             │
│                     ↓                                       │
│  7. LLM incorporates result into final response             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The LLM is a **text generator**. It generates text that _describes_ what tool to call. Your application code does the actual work.

---

## Anatomy of a Tool Definition

Tools are defined using JSON Schema. The model uses this to understand:

- What tools exist
- When to use each tool
- What arguments to provide

### OpenAI Responses API Format (Current)

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location. Use when user asks about weather conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and country, e.g., 'Tokyo, Japan'"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                "required": ["location"],
                "additionalProperties": False  # Required for strict mode
            },
            "strict": True  # Guarantees schema compliance
        }
    }
]
```

### Anthropic Claude Format

```python
tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location. Use when user asks about weather conditions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City and country, e.g., 'Tokyo, Japan'"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit"
                }
            },
            "required": ["location"]
        }
    }
]
```

**Key differences:**

- OpenAI: `function.parameters` | Anthropic: `input_schema`
- OpenAI: `strict: true` for guaranteed compliance | Anthropic: `strict: true` also available
- OpenAI: Nested under `"type": "function"` | Anthropic: Flat structure

---

## The Three Parts of Tool Definition

### 1. Name

```json
"name": "get_weather"
```

- Identifier the model uses to request this tool
- Keep it descriptive but concise
- Use snake_case by convention

### 2. Description

```json
"description": "Get current weather for a location. Use when user asks about weather, temperature, or conditions."
```

**This is critical.** The model uses this to decide _when_ to use the tool.

|Bad Description|Good Description|
|---|---|
|"Weather function"|"Get current weather for a location. Use when user asks about temperature, conditions, or forecasts."|
|"Search"|"Search the web for current information. Use for recent events, facts that may have changed, or topics beyond training data."|

**Tip:** Include trigger phrases: "Use when...", "Call this if..."

### 3. Parameters (Schema)

Defines the structure of arguments:

```json
"parameters": {
    "type": "object",
    "properties": {
        "location": {
            "type": "string",
            "description": "City name and country"
        },
        "include_forecast": {
            "type": "boolean",
            "description": "Whether to include 5-day forecast"
        }
    },
    "required": ["location"],
    "additionalProperties": false
}
```

**Property descriptions matter:** They tell the model what values to provide.

---

## Tool Call Response Format

When the model decides to use a tool, it returns a structured request.

### OpenAI Responses API

```json
{
  "output": [
    {
      "type": "function_call",
      "id": "call_abc123",
      "name": "get_weather",
      "arguments": "{\"location\": \"Tokyo, Japan\", \"unit\": \"celsius\"}"
    }
  ],
  "stop_reason": "tool_use"
}
```

### Anthropic Claude

```json
{
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_01A09q90qw90lq917835123",
      "name": "get_weather",
      "input": {"location": "Tokyo, Japan", "unit": "celsius"}
    }
  ],
  "stop_reason": "tool_use"
}
```

**Key fields:**

- `id` / `call_id`: Unique identifier to match result with request
- `name`: Which tool to call
- `arguments` / `input`: Parameters (may be JSON string or object)

---

## Executing Tools and Returning Results

Your code must:

1. Parse the tool call
2. Execute the actual function
3. Return results in the expected format

### OpenAI Responses API

```python
from openai import OpenAI
import json

client = OpenAI()

def get_weather(location: str, unit: str = "celsius") -> dict:
    # Your actual implementation
    return {"temp": 22, "condition": "Sunny", "unit": unit}

def run_agent(user_input: str):
    response = client.responses.create(
        model="gpt-4o",
        input=user_input,
        tools=tools
    )
    
    # Check if model wants to call tools
    while any(item.type == "function_call" for item in response.output):
        tool_results = []
        
        for item in response.output:
            if item.type == "function_call":
                # Parse arguments (may be JSON string)
                args = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                
                # Execute the tool
                if item.name == "get_weather":
                    result = get_weather(**args)
                else:
                    result = {"error": f"Unknown tool: {item.name}"}
                
                # Format result for API
                tool_results.append({
                    "type": "function_call_output",
                    "call_id": item.id,
                    "output": json.dumps(result)
                })
        
        # Continue with tool results
        response = client.responses.create(
            model="gpt-4o",
            previous_response_id=response.id,
            input=tool_results,
            tools=tools
        )
    
    return response.output_text
```

### Anthropic Claude

```python
import anthropic
import json

client = anthropic.Anthropic()

def run_agent(user_input: str):
    messages = [{"role": "user", "content": user_input}]
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        tools=tools,
        messages=messages
    )
    
    # Check if model wants to call tools
    while response.stop_reason == "tool_use":
        # Find tool use blocks
        tool_use_block = next(
            block for block in response.content 
            if block.type == "tool_use"
        )
        
        # Execute the tool
        if tool_use_block.name == "get_weather":
            result = get_weather(**tool_use_block.input)
        else:
            result = {"error": f"Unknown tool: {tool_use_block.name}"}
        
        # Add assistant response + tool result to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_block.id,
                "content": json.dumps(result)
            }]
        })
        
        # Continue conversation
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )
    
    return response.content[0].text
```

---

## Parallel Tool Calls

Modern models can request multiple tools in a single turn:

```json
{
  "output": [
    {
      "type": "function_call",
      "id": "call_1",
      "name": "get_weather",
      "arguments": "{\"location\": \"Tokyo\"}"
    },
    {
      "type": "function_call",
      "id": "call_2", 
      "name": "get_weather",
      "arguments": "{\"location\": \"New York\"}"
    }
  ]
}
```

**Handle all calls before continuing:**

```python
tool_results = []
for call in tool_calls:
    result = execute_tool(call.name, call.arguments)
    tool_results.append({
        "type": "function_call_output",
        "call_id": call.id,
        "output": json.dumps(result)
    })

# Send ALL results back together
response = client.responses.create(
    previous_response_id=response.id,
    input=tool_results,
    ...
)
```

**Disable parallel calls if needed:**

```python
# OpenAI
parallel_tool_calls=False

# Anthropic  
tool_choice={"type": "any", "disable_parallel_tool_use": True}
```

---

## Strict Mode (Structured Outputs)

**Problem:** Models sometimes generate malformed arguments (wrong types, missing fields).

**Solution:** `strict: true` guarantees schema compliance.

```python
{
    "type": "function",
    "function": {
        "name": "create_user",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"}
            },
            "required": ["name", "email"],
            "additionalProperties": False  # Required for strict
        },
        "strict": True  # Enable strict mode
    }
}
```

**Requirements for strict mode:**

- `additionalProperties: false` on all objects
- All properties in `required` array
- No unsupported schema features

**Recommendation:** Always use strict mode in production.

---

## Tool Choice: Controlling When Tools Are Used

|Setting|Behavior|
|---|---|
|`"auto"` (default)|Model decides whether to use tools|
|`"required"`|Model MUST use at least one tool|
|`"none"`|Model cannot use tools (even if defined)|
|`{"type": "function", "function": {"name": "X"}}`|Force specific tool|

```python
# OpenAI
response = client.responses.create(
    model="gpt-4o",
    input="...",
    tools=tools,
    tool_choice="required"  # Force tool use
)

# Anthropic
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=tools,
    tool_choice={"type": "tool", "name": "get_weather"}  # Force specific tool
)
```

**Use cases:**

- `"required"`: When you know a tool is needed (e.g., "search for X")
- `"none"`: When you want to force a direct response
- Specific tool: When testing or forcing a workflow

---

## Built-in Tools (OpenAI Responses API)

OpenAI provides server-executed tools—no code needed:

```python
response = client.responses.create(
    model="gpt-4o",
    input="What happened in the news today?",
    tools=[
        {"type": "web_search"},  # Web search
        {"type": "file_search", "vector_store_ids": ["vs_123"]},  # RAG
        {"type": "code_interpreter"}  # Python execution
    ]
)
```

**Available built-in tools:**

- `web_search`: Search the web
- `file_search`: RAG over your documents
- `code_interpreter`: Execute Python code
- `computer_use`: Screenshot-based UI automation (GPT-5.4+)
- `image_generation`: Generate images (gpt-image-1)

These execute server-side—you don't handle the loop.

---

## Anthropic Server Tools

Anthropic also has server-executed tools:

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=[
        {"type": "web_search_20250305", "name": "web_search"},
        {"type": "code_execution_20260120", "name": "code_execution"}
    ],
    ...
)
```

Server tools run in a managed loop—Anthropic handles execution.

---

## Common Mistakes

### 1. Not Matching call_id

```python
# WRONG
tool_results.append({
    "call_id": "some_random_id",  # Must match original
    ...
})

# RIGHT
tool_results.append({
    "call_id": item.id,  # Use the ID from the tool call
    ...
})
```

### 2. Not Handling Multiple Tool Calls

```python
# WRONG: Only handles first call
tool_call = response.output[0]
result = execute(tool_call)

# RIGHT: Handle all calls
for item in response.output:
    if item.type == "function_call":
        # Process each one
```

### 3. Poor Tool Descriptions

```python
# WRONG
"description": "Search"

# RIGHT
"description": "Search the web for current information. Use for recent events, news, or facts that may have changed since training."
```

### 4. Not Validating Arguments

```python
# WRONG: Trust model output blindly
result = my_function(**args)

# RIGHT: Validate first
if "location" not in args:
    return {"error": "Missing required field: location"}
result = my_function(**args)
```

### 5. Forgetting to Loop

```python
# WRONG: Single call, no loop
response = client.responses.create(...)
return response.output_text  # May be empty if tool was called!

# RIGHT: Loop until no more tool calls
while has_tool_calls(response):
    response = process_tools_and_continue(response)
return response.output_text
```

---

## The Execution Flow Summary

```
1. DEFINE: Create tool schemas with clear descriptions
       ↓
2. SEND: Include tools in API request
       ↓
3. RECEIVE: Model returns tool_call (or final text)
       ↓
4. CHECK: Is stop_reason "tool_use"?
       ↓
   YES → 5. EXECUTE: Run your function with provided args
         6. FORMAT: Package result with call_id
         7. RETURN: Send result back to model
         8. GOTO 3 (loop)
       ↓
   NO → 9. DONE: Extract final text response
```

---

## Key Takeaways

1. **LLMs don't execute tools** — they generate structured requests; your code executes
    
2. **Tool descriptions drive selection** — invest time in clear, detailed descriptions
    
3. **Use strict mode** — `strict: true` prevents schema violations in production
    
4. **Handle parallel calls** — models may request multiple tools at once
    
5. **Always loop** — tool calling is iterative; check `stop_reason` and continue
    
6. **Match call_ids** — results must reference the original request ID
    
7. **Built-in tools exist** — web search, code interpreter, file search execute server-side
    
8. **Both APIs follow the same pattern** — OpenAI and Anthropic differ in syntax, not concept
    

---

## Connection to Previous Topics

- **Agent Loop:** Tool calling is the "Act" phase—this topic shows the mechanics
- **ReAct:** Each Action in ReAct is a tool call; Observations are tool results
- **What Is an Agent:** Tools are what make agents capable of interacting with the world

## Up Next

With tool mechanics understood, the next topic covers **When to Use Agents vs. Simpler Solutions** — understanding when the complexity of agents is warranted.