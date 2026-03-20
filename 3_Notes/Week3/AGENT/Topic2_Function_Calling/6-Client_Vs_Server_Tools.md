# Note 6: Client Tools vs Server Tools

## Week 3 Agents — Days 3-4 | Function Calling / Tool Use

---

## The Two Execution Models

When you use tools with Claude, there are two fundamentally different execution models:

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT TOOLS                               │
│                                                                 │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                │
│  │  Claude  │────►│ Your Code │────►│ Your API │                │
│  │   API    │◄────│ (execute) │◄────│ / Service│                │
│  └──────────┘     └──────────┘     └──────────┘                │
│                                                                 │
│  • YOU define the tool                                         │
│  • YOU execute the tool                                        │
│  • YOU return results                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      SERVER TOOLS                               │
│                                                                 │
│  ┌──────────┐     ┌────────────────────────────┐               │
│  │  Claude  │────►│  Anthropic's Infrastructure │               │
│  │   API    │◄────│  (executes tool internally) │               │
│  └──────────┘     └────────────────────────────┘               │
│                                                                 │
│  • ANTHROPIC defines the tool                                  │
│  • ANTHROPIC executes the tool                                 │
│  • Results incorporated automatically                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Comparison

|Aspect|Client Tools|Server Tools|
|---|---|---|
|**Who defines**|You|Anthropic|
|**Who executes**|Your code|Anthropic's servers|
|**Response structure**|`stop_reason: "tool_use"`|Results embedded in response|
|**Your responsibility**|Full implementation|Just enable in request|
|**Customization**|Complete control|Limited to parameters|
|**Error handling**|You handle with `is_error`|Anthropic handles|
|**Examples**|Your business APIs|Web search, code execution|
|**Pricing**|Standard token pricing|May have additional per-use fees|

---

## Client Tools: Your Custom Tools

### How They Work

1. **You define** the tool schema (name, description, parameters)
2. **Claude decides** to use the tool and generates arguments
3. **API returns** `stop_reason: "tool_use"` with tool call details
4. **You execute** the tool in your code
5. **You return** the result via `tool_result` content block
6. **Claude continues** with the result

### Response Structure

```python
# Claude's response when it wants to use a client tool
{
    "stop_reason": "tool_use",
    "content": [
        {
            "type": "text",
            "text": "I'll check the weather for you."
        },
        {
            "type": "tool_use",
            "id": "toolu_01ABC123",
            "name": "get_weather",
            "input": {"location": "San Francisco, CA"}
        }
    ]
}
```

### Returning Results

```python
# Your message with the tool result
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01ABC123",
            "content": "72°F, sunny, humidity 45%"
        }
    ]
}
```

### When to Use Client Tools

- **Your business logic**: CRM queries, internal APIs, databases
- **Custom integrations**: Proprietary systems, internal services
- **Sensitive operations**: Anything requiring your security context
- **Full control needed**: Custom error handling, caching, logging

---

## Server Tools: Anthropic-Managed Tools

### Available Server Tools (Current)

|Tool|Version|Purpose|
|---|---|---|
|`web_search`|`web_search_20250305` / `web_search_20260209`|Real-time web search|
|`web_fetch`|`web_fetch_20250305`|Fetch and analyze web pages|
|`code_execution`|`code_execution_20250825`|Run Python/Bash in sandbox|
|`text_editor`|`text_editor_20250124`|File editing in sandbox|
|`computer`|`computer_20250124`|Computer use (beta)|
|`memory`|(current version)|Persistent memory|
|`bash`|`bash_20250124`|Shell commands|

### How They Work

1. **You enable** the tool in your request
2. **Claude decides** to use the tool
3. **Anthropic executes** the tool on their servers
4. **Results are incorporated** into Claude's response automatically
5. **No round-trip needed** — you get final answer directly

### Response Structure

Server tools use different content block types:

```python
# Response showing server tool was used
{
    "stop_reason": "end_turn",  # NOT "tool_use"
    "content": [
        {
            "type": "text",
            "text": "I'll search for that information."
        },
        {
            "type": "server_tool_use",  # Different type
            "id": "srvtoolu_xyz789",
            "name": "web_search"
        },
        {
            "type": "web_search_tool_result",  # Results embedded
            "tool_use_id": "srvtoolu_xyz789",
            "content": [...]
        },
        {
            "type": "text",
            "text": "Based on my search, here's what I found..."
        }
    ]
}
```

### Example: Web Search

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": "What are the latest developments in quantum computing?"
    }],
    tools=[{
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5  # Optional: limit searches
    }]
)

# Response already includes search results and Claude's analysis
# No need to execute anything — just use response.content
print(response.content[-1].text)
```

### Example: Code Execution

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": "Calculate the first 50 Fibonacci numbers and plot them"
    }],
    tools=[{
        "type": "code_execution_20250825",
        "name": "code_execution"
    }]
)

# Claude writes code, executes it in sandbox, returns results
# Including any generated charts or files
```

---

## The Server Tool Loop: `pause_turn`

Server tools run in a loop on Anthropic's servers. This loop has a limit (default: 10 iterations).

### What Happens

```
┌─────────────────────────────────────────────────────────────┐
│  Anthropic Server-Side Loop                                 │
│                                                             │
│  Iteration 1: Claude calls web_search("topic A")            │
│  Iteration 2: Claude calls web_search("topic B")            │
│  Iteration 3: Claude calls web_fetch(url1)                  │
│  ...                                                        │
│  Iteration 10: LIMIT REACHED                                │
│                                                             │
│  → Response returns with stop_reason: "pause_turn"          │
└─────────────────────────────────────────────────────────────┘
```

### Handling `pause_turn`

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Deep research on quantum computing"}],
    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 15}]
)

if response.stop_reason == "pause_turn":
    # Claude needs to continue — send response back
    messages = [
        {"role": "user", "content": "Deep research on quantum computing"},
        {"role": "assistant", "content": response.content}  # Include partial work
    ]
    
    continuation = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=messages,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 15}]
    )
```

---

## Mixing Client and Server Tools

You can use both in the same request:

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": "Search for weather APIs, then use our internal weather service to get SF weather"
    }],
    tools=[
        # Server tool
        {
            "type": "web_search_20250305",
            "name": "web_search"
        },
        # Client tool
        {
            "name": "internal_weather_api",
            "description": "Get weather from our internal service",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    ]
)

# Check what happened
for block in response.content:
    if block.type == "server_tool_use":
        # Server tool was used and executed automatically
        print(f"Server tool used: {block.name}")
    elif block.type == "tool_use":
        # Client tool — YOU need to execute this
        print(f"Client tool requested: {block.name}")
        # Execute and return result...
```

---

## Code Execution Tool Deep Dive

The code execution tool is particularly powerful — it runs Python/Bash in a sandboxed container.

### Basic Usage

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": "Analyze this CSV data and create a visualization"
    }],
    tools=[{
        "type": "code_execution_20250825",
        "name": "code_execution"
    }]
)
```

### Container Persistence

You can reuse containers across requests:

```python
# First request
response1 = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Create a file with some data"}],
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}]
)

# Get container ID
container_id = response1.container.id

# Second request — reuse container
response2 = client.messages.create(
    container=container_id,  # Reuse same container
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Read the file I created earlier"}],
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}]
)
```

### Uploading Files to Sandbox

```python
# Upload file first
with open("data.csv", "rb") as f:
    file_response = client.files.create(file=f)

# Use in code execution
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Analyze this data"},
            {"type": "container_upload", "file_id": file_response.id}
        ]
    }],
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}]
)
```

---

## Dynamic Filtering (Advanced)

Latest web search/fetch tools can filter results using code execution:

```python
response = client.messages.create(
    model="claude-opus-4-6",  # Requires Opus 4.6 or Sonnet 4.6
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": "Find stock prices for AAPL and GOOGL, calculate P/E ratios"
    }],
    tools=[
        {"type": "web_search_20260209", "name": "web_search"},  # New version
        {"type": "code_execution_20250825", "name": "code_execution"}  # Required for filtering
    ]
)
```

Claude can write code to filter search results before they consume context — extracting only relevant data.

---

## Pricing Differences

|Tool Type|Pricing Model|
|---|---|
|Client tools|Standard token pricing (input + output)|
|Web search|Per-search fee + token pricing|
|Code execution|Compute time + token pricing|
|Web fetch|Per-fetch fee + token pricing|

Server tools may have additional usage-based charges beyond token costs. Check Anthropic's pricing page for current rates.

---

## Error Handling Differences

### Client Tools: You Handle Errors

```python
# Your code
def execute_tool(name, args):
    try:
        result = my_tools[name](**args)
        return {"content": str(result), "is_error": False}
    except Exception as e:
        return {"content": f"Error: {str(e)}", "is_error": True}

# Return to Claude
{
    "type": "tool_result",
    "tool_use_id": "toolu_01ABC",
    "content": "Error: Database connection failed",
    "is_error": True  # YOU set this
}
```

### Server Tools: Anthropic Handles Errors

For server tools, errors are handled internally. Claude will explain what went wrong in its response:

```python
# If web search fails, Claude's response might include:
"I encountered an error searching for that information. The search service 
may be temporarily unavailable. Let me try a different approach..."
```

You don't need to handle `is_error` for server tools — Claude does this automatically.

---

## Programmatic Tool Calling (Advanced)

For complex workflows, Claude can write code that calls your tools:

```python
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": "Check budget compliance for all 20 team members"
    }],
    tools=[
        {"type": "code_execution_20250825", "name": "code_execution"},
        {
            "name": "get_employee_expenses",
            "description": "Get expenses for an employee",
            "input_schema": {...},
            "allowed_callers": ["code_execution"]  # Can be called from code
        },
        {
            "name": "get_budget_limit",
            "description": "Get budget limit for a department",
            "input_schema": {...},
            "allowed_callers": ["code_execution"]
        }
    ]
)
```

Claude writes a Python loop that calls your tools, processes results locally, and only returns the summary — saving tokens and latency.

---

## Decision Guide: Which to Use?

### Use Client Tools When:

- You need to access your own systems (databases, APIs, services)
- Security/authentication is required
- You need custom error handling or logging
- You want full control over execution

### Use Server Tools When:

- You need real-time web information
- You need code execution without running your own sandbox
- You want simpler implementation (no execution loop)
- The built-in tools fit your use case

### Combine Both When:

- Research tasks that need web search + your internal data
- Analysis tasks that need code execution + your APIs
- Complex workflows requiring multiple data sources

---

## Key Takeaways

1. **Client tools = you execute, server tools = Anthropic executes**
    
2. **Different response structures**: Client tools → `tool_use` block, Server tools → `server_tool_use` + results embedded
    
3. **No agent loop needed for server tools** — results come back automatically
    
4. **`pause_turn`** means server-side loop hit limit — send response back to continue
    
5. **Server tools may have additional per-use pricing** beyond tokens
    
6. **You can mix both** in the same request
    
7. **Code execution enables advanced patterns** like container persistence, file uploads, and programmatic tool calling
    

---

_Next: Note 7 — Scaling Tool Use: Advanced Patterns + Token Economics_