# Defining Tools for LangGraph

## What Makes a LangGraph Tool?

A tool in LangGraph is a function the LLM can call. The LLM sees:

- **Name**: What to call the tool
- **Description**: When/why to use it
- **Parameters**: What inputs it needs (with types)

The LLM doesn't see your code — it decides based on the schema you provide.

---

## Three Ways to Create Tools

|Method|When to Use|Complexity|
|---|---|---|
|`@tool` decorator|Simple functions, quick prototyping|Low|
|`StructuredTool.from_function()`|Need custom name/description, infer schema|Medium|
|Subclass `BaseTool`|Complex tools, state management, custom behavior|High|

For 90% of cases, **use the `@tool` decorator**.

---

## Method 1: The `@tool` Decorator (Recommended)

### Basic Usage

```python
from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result."""
    return str(eval(expression))
```

That's it. LangChain extracts:

- **Name**: `calculator` (from function name)
- **Description**: `Evaluate a mathematical expression...` (from docstring)
- **Schema**: `{"expression": {"type": "string"}}` (from type hints)

### What the LLM Sees

When you bind this tool to a model, it receives a JSON schema like:

```json
{
  "name": "calculator",
  "description": "Evaluate a mathematical expression and return the result.",
  "parameters": {
    "type": "object",
    "properties": {
      "expression": {
        "type": "string"
      }
    },
    "required": ["expression"]
  }
}
```

**The docstring and type hints are critical** — they're the only information the LLM has.

### Multiple Parameters

```python
@tool
def search_notes(
    query: str,
    max_results: int = 5,
    include_archived: bool = False
) -> str:
    """Search through saved notes.
    
    Args:
        query: The search term to look for
        max_results: Maximum number of results to return
        include_archived: Whether to include archived notes
    """
    # Implementation...
    return f"Found notes matching: {query}"
```

**Pro tip:** Include `Args:` section in docstring — some models use it for parameter descriptions.

### Customizing Name and Description

```python
@tool(name="web_search", description="Search the internet for current information")
def search(query: str) -> str:
    """This docstring is ignored when description is provided."""
    return f"Results for: {query}"
```

---

## Method 2: StructuredTool.from_function()

When you need more control but don't want to subclass:

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# Optional: Explicit schema
class WeatherInput(BaseModel):
    """Input for weather lookup."""
    location: str = Field(description="City and state, e.g., 'San Francisco, CA'")
    units: str = Field(default="fahrenheit", description="Temperature units: 'celsius' or 'fahrenheit'")

def get_weather(location: str, units: str = "fahrenheit") -> str:
    """Get current weather for a location."""
    # Implementation...
    return f"Weather in {location}: 72°F"

weather_tool = StructuredTool.from_function(
    func=get_weather,
    name="get_weather",
    description="Get current weather conditions for any location",
    args_schema=WeatherInput  # Optional: explicit schema
)
```

### When to Use StructuredTool

- Need to rename a function without changing code
- Want explicit Pydantic validation
- Creating tools dynamically from existing functions
- Need to add `return_direct=True` (return tool output to user directly)

---

## Method 3: Subclassing BaseTool

For tools that need:

- State management
- Complex initialization
- Async support
- Custom error handling

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional

class DatabaseQueryInput(BaseModel):
    """Input for database queries."""
    query: str = Field(description="SQL query to execute")
    limit: int = Field(default=100, description="Maximum rows to return")

class DatabaseQueryTool(BaseTool):
    name: str = "database_query"
    description: str = "Execute SQL queries against the database"
    args_schema: Type[BaseModel] = DatabaseQueryInput
    
    # Custom attributes
    connection_string: str
    
    def __init__(self, connection_string: str, **kwargs):
        super().__init__(connection_string=connection_string, **kwargs)
        # Initialize connection, etc.
    
    def _run(self, query: str, limit: int = 100) -> str:
        """Synchronous execution."""
        # Execute query...
        return f"Executed: {query} (limit: {limit})"
    
    async def _arun(self, query: str, limit: int = 100) -> str:
        """Async execution (optional but recommended)."""
        # Async execution...
        return f"Async executed: {query}"

# Usage
db_tool = DatabaseQueryTool(connection_string="postgresql://...")
```

---

## The Schema: How LLMs Understand Your Tools

### Pydantic Field Descriptions

**These descriptions are sent to the LLM**. Write them clearly:

```python
from pydantic import BaseModel, Field

class CreateNoteInput(BaseModel):
    """Create a new note with optional tags."""
    
    title: str = Field(
        description="Short title for the note (max 100 chars)"
    )
    content: str = Field(
        description="The main body of the note. Can include markdown."
    )
    tags: list[str] = Field(
        default=[],
        description="Optional list of tags to categorize the note"
    )
```

### Viewing the Generated Schema

```python
@tool
def my_tool(x: int, y: str = "default") -> str:
    """Does something useful."""
    return "result"

# See what the LLM receives
print(my_tool.name)        # "my_tool"
print(my_tool.description) # "Does something useful."
print(my_tool.args)        # {'x': {'title': 'X', 'type': 'integer'}, 'y': {'title': 'Y', 'default': 'default', 'type': 'string'}}
print(my_tool.args_schema.schema())  # Full JSON schema
```

---

## Binding Tools to Models

### OpenAI

```python
from langchain_openai import ChatOpenAI

@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

@tool
def get_time() -> str:
    """Get current time."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

tools = [calculator, get_time]

# Bind tools to model
llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(tools)

# Now the model can request tool calls
response = llm_with_tools.invoke("What's 15% of 230?")
print(response.tool_calls)  # [{'name': 'calculator', 'args': {'expression': '230 * 0.15'}, 'id': '...'}]
```

### Anthropic

```python
from langchain_anthropic import ChatAnthropic

tools = [calculator, get_time]

# Same pattern
llm = ChatAnthropic(model="claude-sonnet-4-20250514")
llm_with_tools = llm.bind_tools(tools)

response = llm_with_tools.invoke("What's 15% of 230?")
print(response.tool_calls)  # Same structure
```

**The tool definition is identical** — only the LLM instantiation differs.

---

## Using Tools in LangGraph

### With ToolNode

```python
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START, END

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

@tool
def calculator(expression: str) -> str:
    """Evaluate math expressions."""
    return str(eval(expression))

tools = [search, calculator]

# Create ToolNode with your tools
tool_node = ToolNode(tools)

# Build graph
builder = StateGraph(MessagesState)
builder.add_node("tools", tool_node)
# ... add other nodes and edges
```

### Important: Same Tools in Two Places

You must pass the same tools to **both**:

1. `llm.bind_tools(tools)` — so the LLM knows what's available
2. `ToolNode(tools)` — so the graph can execute them

```python
tools = [search, calculator]

# Both use the same tools list
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)
```

Mismatch causes errors: LLM requests a tool that ToolNode doesn't have.

---

## Tool Return Types

### String (Default)

```python
@tool
def simple_tool(x: str) -> str:
    """Returns plain text."""
    return f"Processed: {x}"
```

The LLM receives this string as the tool result.

### Structured Objects

```python
@tool
def structured_tool(query: str) -> dict:
    """Returns structured data the model should parse."""
    return {
        "status": "success",
        "results": ["item1", "item2"],
        "count": 2
    }
```

The dict is serialized to string for the LLM.

### Command (State Updates)

Tools can update graph state directly:

```python
from langgraph.types import Command
from langchain_core.tools import tool

@tool
def set_language(language: str) -> Command:
    """Set the user's preferred language."""
    return Command(update={"preferred_language": language})
```

When returning `Command`, the tool's result updates state instead of being returned as a message.

### Content + Artifact

For tools that produce large outputs (dataframes, images) that shouldn't go to the LLM:

```python
from typing import Tuple, Any

@tool(response_format="content_and_artifact")
def data_analysis(query: str) -> Tuple[str, Any]:
    """Analyze data and return summary + full results."""
    import pandas as pd
    
    # Full dataframe (artifact - not sent to LLM)
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    
    # Summary (content - sent to LLM)
    summary = f"Analysis complete. Found {len(df)} rows."
    
    return summary, df  # (content, artifact)
```

---

## Async Tools

For I/O-bound operations (API calls, database queries):

```python
import httpx

@tool
async def async_search(query: str) -> str:
    """Search using async HTTP."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/search?q={query}")
        return response.text
```

`ToolNode` handles both sync and async tools automatically.

---

## Accessing Runtime Context

Tools can access graph state, config, and more via `ToolRuntime`:

```python
from langchain_core.tools import tool, ToolRuntime

@tool
def context_aware_tool(query: str, runtime: ToolRuntime) -> str:
    """Tool that accesses runtime context."""
    
    # Access current graph state
    messages = runtime.state.get("messages", [])
    
    # Access config (thread_id, etc.)
    thread_id = runtime.config.get("configurable", {}).get("thread_id")
    
    # Access tool call ID (for correlating with ToolMessage)
    call_id = runtime.tool_call_id
    
    return f"Processed {query} in thread {thread_id}"
```

**Note:** `runtime` is injected automatically — the LLM doesn't see it in the schema.

---

## Common Mistakes

### 1. Missing Docstring

```python
# BAD — LLM has no idea what this does
@tool
def process(x: str) -> str:
    return x.upper()

# GOOD
@tool
def process(x: str) -> str:
    """Convert text to uppercase."""
    return x.upper()
```

### 2. Vague Parameter Names

```python
# BAD
@tool
def fetch(s: str, n: int) -> str:
    """Fetch data."""
    ...

# GOOD  
@tool
def fetch_user_data(user_id: str, max_records: int) -> str:
    """Fetch user data from the database.
    
    Args:
        user_id: The unique identifier of the user
        max_records: Maximum number of records to return
    """
    ...
```

### 3. No Type Hints

```python
# BAD — schema can't be inferred
@tool
def calculate(expression):
    """Calculate result."""
    return eval(expression)

# GOOD
@tool
def calculate(expression: str) -> str:
    """Calculate result."""
    return str(eval(expression))
```

### 4. Tool Name Mismatch

```python
tools = [my_calculator]
llm_with_tools = llm.bind_tools(tools)

# BAD — different tools list
tool_node = ToolNode([other_calculator])  # Will fail!

# GOOD — same list
tool_node = ToolNode(tools)
```

---

## Production Tool Patterns

### Pattern 1: Error Handling

```python
@tool
def safe_search(query: str) -> str:
    """Search with error handling."""
    try:
        result = external_api.search(query)
        return result
    except Exception as e:
        return f"Error performing search: {str(e)}"
```

Return errors as strings so the LLM can decide what to do (retry, rephrase, etc.).

### Pattern 2: Input Validation

```python
from pydantic import BaseModel, Field, field_validator

class SafeCalculatorInput(BaseModel):
    expression: str = Field(description="Math expression (no imports or exec)")
    
    @field_validator('expression')
    @classmethod
    def no_dangerous_code(cls, v: str) -> str:
        dangerous = ['import', 'exec', 'eval', '__', 'open']
        if any(d in v.lower() for d in dangerous):
            raise ValueError("Expression contains forbidden terms")
        return v

@tool(args_schema=SafeCalculatorInput)
def safe_calculator(expression: str) -> str:
    """Safely evaluate math expressions."""
    # Only allow safe operations
    allowed = set('0123456789+-*/().% ')
    if not all(c in allowed for c in expression):
        return "Error: Only basic math operations allowed"
    return str(eval(expression))
```

### Pattern 3: Timeouts

```python
import asyncio

@tool
async def search_with_timeout(query: str) -> str:
    """Search with 10 second timeout."""
    try:
        result = await asyncio.wait_for(
            external_search(query),
            timeout=10.0
        )
        return result
    except asyncio.TimeoutError:
        return "Search timed out. Try a more specific query."
```

---

## Quick Reference

### Import

```python
from langchain_core.tools import tool, BaseTool, StructuredTool, ToolRuntime
from pydantic import BaseModel, Field
```

### Minimal Tool

```python
@tool
def my_tool(param: str) -> str:
    """Clear description of what this tool does."""
    return f"Result: {param}"
```

### Bind to Model

```python
tools = [tool1, tool2, tool3]
llm_with_tools = llm.bind_tools(tools)
```

### Use in Graph

```python
from langgraph.prebuilt import ToolNode
tool_node = ToolNode(tools)
builder.add_node("tools", tool_node)
```

---

## Key Takeaways

1. **Use `@tool` decorator** for 90% of cases — it's simple and effective
    
2. **Docstrings and type hints are critical** — they're the LLM's only information about your tool
    
3. **Same tools in both places**: `llm.bind_tools(tools)` and `ToolNode(tools)`
    
4. **Return strings for simple results**, `Command` for state updates, tuple for content + artifact
    
5. **Handle errors gracefully** — return error strings so the LLM can adapt
    
6. **Provider-agnostic**: Tool definitions work identically with OpenAI and Anthropic
    

---

## References

- [LangChain Tools Documentation](https://docs.langchain.com/oss/python/langchain/tools) — Official tools guide
- [LangGraph ToolNode](https://docs.langchain.com/oss/python/langgraph/graph-api) — Using tools in graphs
- [StructuredTool API](https://reference.langchain.com/v0.3/python/core/tools/langchain_core.tools.structured.StructuredTool.html) — Full API reference