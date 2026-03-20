# Note 1: What Is Tool Use + Anatomy of a Tool

## Week 3 Agents — Days 3-4 | Function Calling / Tool Use

---

## The Capability Gap: LLMs Can Think, But Can't _Do_

An LLM, by itself, is a text prediction machine. It can reason about weather, stocks, databases, and calendars—but it cannot:

- Check the actual weather right now
- Look up a real stock price
- Query your production database
- Schedule a meeting on your calendar

This is the **capability gap**. The model has knowledge _about_ things but no ability to _interact with_ things.

**Tool use bridges this gap.** You give the LLM a way to request actions, and your code executes them.

```
Without tools: "What's the weather?" → "I don't have real-time data..."
With tools:    "What's the weather?" → [calls get_weather API] → "It's 22°C and sunny"
```

---

## Terminology: Function Calling vs Tool Use

These terms are **interchangeable**. Different providers use different names:

|Provider|Term Used|Meaning|
|---|---|---|
|OpenAI|Function Calling|Same thing|
|OpenAI|Tool Use|Same thing|
|Anthropic|Tool Use|Same thing|

The concept is identical: you describe available functions to the model, the model decides when to call them, and you execute the calls.

> **Key Insight:** The LLM never executes anything. It _requests_ execution. Your code is the executor; the LLM is the orchestrator.

---

## The Core Mental Model

Think of tool use as a **contract**:

1. **You declare**: "Here are functions you can call, here's what they do, here are their parameters"
2. **LLM decides**: "To answer this query, I need to call function X with arguments Y"
3. **You execute**: Run the actual function with those arguments
4. **You return**: Send results back to the LLM
5. **LLM responds**: Uses the results to form a final answer

The LLM is making a _structured request_. It's not running code—it's generating JSON that says "please call this function with these arguments."

---

## Anatomy of a Tool Definition

Every tool definition has three core components:

### 1. Name

A unique identifier for the tool. Must be clear and unambiguous.

```
"name": "get_weather"
"name": "search_database"  
"name": "send_email"
```

**Naming constraints:**

- OpenAI: `^[a-zA-Z0-9_-]{1,64}$` (letters, numbers, underscores, hyphens, max 64 chars)
- Anthropic: Same pattern

### 2. Description

A natural language explanation of what the tool does. **This is the most important field for model performance.**

```
"description": "Get the current weather in a given location. Returns temperature, conditions, humidity, and wind speed. Use this when the user asks about weather, temperature, or climate conditions for a specific place."
```

The description tells the model:

- What the tool does
- When to use it
- What it returns
- Edge cases or limitations

### 3. Parameters / Input Schema

A JSON Schema defining the expected inputs. This tells the model what arguments to provide.

```json
{
  "type": "object",
  "properties": {
    "location": {
      "type": "string",
      "description": "City and state/country, e.g., 'San Francisco, CA' or 'London, UK'"
    },
    "unit": {
      "type": "string",
      "enum": ["celsius", "fahrenheit"],
      "description": "Temperature unit for the response"
    }
  },
  "required": ["location"]
}
```

---

## Provider-Specific Schema Formats

### Anthropic Format

Anthropic uses `input_schema` at the top level:

```json
{
  "name": "get_weather",
  "description": "Get current weather for a location",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City and state, e.g., San Francisco, CA"
      }
    },
    "required": ["location"]
  }
}
```

**Reference:** [Anthropic Tool Use Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) (March 2026)

### OpenAI Responses API Format

OpenAI's newer Responses API uses a flatter structure:

```json
{
  "type": "function",
  "name": "get_weather",
  "description": "Get current weather for a location",
  "parameters": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City and state, e.g., San Francisco, CA"
      }
    },
    "required": ["location"],
    "additionalProperties": false
  }
}
```

### OpenAI Chat Completions API Format (Legacy)

The older Chat Completions API wraps the function in a `function` key:

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get current weather for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string"
        }
      },
      "required": ["location"]
    }
  }
}
```

> ⚠️ **Important:** OpenAI deprecated the Assistants API in August 2025 (sunset August 2026). The Responses API is now the primary interface. Schema formats differ between APIs—using Chat Completions schema in Responses API will fail with "Missing required parameter: 'tools[0].function'".

---

## JSON Schema Fundamentals for Tool Parameters

You don't need to be a JSON Schema expert, but you need these basics:

### Primitive Types

```json
{"type": "string"}                    // Any string
{"type": "number"}                    // Any number (int or float)
{"type": "integer"}                   // Integers only
{"type": "boolean"}                   // true or false
{"type": "null"}                      // null value
```

### Constrained Strings with Enums

```json
{
  "type": "string",
  "enum": ["low", "medium", "high"]
}
```

The model can only output one of the listed values.

### Arrays

```json
{
  "type": "array",
  "items": {"type": "string"}
}
```

### Nested Objects

```json
{
  "type": "object",
  "properties": {
    "address": {
      "type": "object",
      "properties": {
        "street": {"type": "string"},
        "city": {"type": "string"}
      }
    }
  }
}
```

### Required vs Optional Parameters

```json
{
  "type": "object",
  "properties": {
    "query": {"type": "string"},      // Required
    "limit": {"type": "integer"}       // Optional
  },
  "required": ["query"]
}
```

Parameters in `required` array must be provided. Others are optional—model may or may not include them.

---

## Strict Mode: Guaranteed Schema Conformance

Both OpenAI and Anthropic support **strict mode** for tool calling:

### OpenAI Strict Mode

```json
{
  "type": "function",
  "name": "get_weather",
  "strict": true,
  "parameters": {
    "type": "object",
    "properties": {
      "location": {"type": "string"}
    },
    "required": ["location"],
    "additionalProperties": false
  }
}
```

**Requirements when `strict: true`:**

- `additionalProperties` must be `false` for all objects
- All properties must be listed in `required` (use `"type": ["string", "null"]` for optional fields)
- Guarantees output matches schema exactly

### Anthropic Strict Mode

```json
{
  "name": "get_weather",
  "description": "...",
  "strict": true,
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {"type": "string"}
    },
    "required": ["location"]
  }
}
```

> **When to use strict mode:** Production systems where invalid parameters would cause failures. Strict mode eliminates "best effort" matching and guarantees schema adherence.

---

## Complete Tool Definition Examples

### Example 1: Simple Tool (Weather)

**Anthropic format:**

```python
weather_tool = {
    "name": "get_weather",
    "description": "Get the current weather in a given location. Returns temperature, humidity, and conditions. Use when user asks about current weather, temperature, or if they should bring an umbrella/jacket.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City and state/country, e.g., 'San Francisco, CA' or 'Tokyo, Japan'"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit. Default to celsius for non-US locations."
            }
        },
        "required": ["location"]
    }
}
```

### Example 2: Tool with Complex Parameters (Database Query)

```python
query_tool = {
    "name": "search_customers",
    "description": "Search the customer database. Returns matching customer records with name, email, and account status. Use when user asks to find, look up, or search for customers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term to match against customer name or email"
            },
            "status_filter": {
                "type": "string",
                "enum": ["active", "inactive", "all"],
                "description": "Filter by account status. Defaults to 'all' if not specified."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return. Default 10, max 100."
            }
        },
        "required": ["query"]
    }
}
```

### Example 3: Tool with Nested Objects

```python
create_order_tool = {
    "name": "create_order",
    "description": "Create a new order in the system. Use when user wants to place an order or purchase items.",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Unique customer identifier"
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer"}
                    },
                    "required": ["product_id", "quantity"]
                },
                "description": "List of items to order"
            },
            "shipping_address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "postal_code": {"type": "string"},
                    "country": {"type": "string"}
                },
                "required": ["street", "city", "postal_code", "country"]
            }
        },
        "required": ["customer_id", "items", "shipping_address"]
    }
}
```

---

## What Happens When You Send Tools to the API

When you include tools in your API request, the provider constructs a special system prompt internally.

**Anthropic's internal construction:**

```
In this environment you have access to a set of tools you can use to answer the user's question.

{{ FORMATTING INSTRUCTIONS }}

String and scalar parameters should be specified as is, while lists and objects should use JSON format.

Here are the functions available in JSONSchema format:
{{ TOOL DEFINITIONS IN JSON SCHEMA }}

{{ USER SYSTEM PROMPT }}

{{ TOOL CONFIGURATION }}
```

You don't write this—the API builds it from your tool definitions. But knowing it exists explains:

- Why tool definitions count against context limits
- Why better descriptions lead to better tool selection
- Why tools are "billed as input tokens"

---

## Input Examples: Teaching Through Demonstration

For complex tools, you can provide example inputs to help the model understand usage patterns:

```python
{
    "name": "search_flights",
    "description": "Search for available flights between airports",
    "input_schema": {
        "type": "object",
        "properties": {
            "origin": {"type": "string", "description": "Origin airport code (IATA)"},
            "destination": {"type": "string", "description": "Destination airport code (IATA)"},
            "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"}
        },
        "required": ["origin", "destination", "date"]
    },
    "input_examples": [
        {"origin": "SFO", "destination": "JFK", "date": "2026-04-15"},
        {"origin": "LAX", "destination": "LHR", "date": "2026-05-01"},
        {"origin": "ORD", "destination": "NRT", "date": "2026-06-20"}
    ]
}
```

**When to use `input_examples`:**

- Complex nested structures
- Format-sensitive inputs (dates, codes, IDs)
- When the schema alone doesn't convey usage patterns

**Note:** Each example adds ~20-50 tokens (simple) to ~100-200 tokens (complex nested). Use judiciously.

---

## Key Takeaways

1. **Tool use = LLM requests, you execute.** The model never runs code—it generates structured requests for your code to fulfill.
    
2. **Three core components:** Name (identifier), Description (when/how to use), Parameters (input schema).
    
3. **Description is king.** The model decides _whether_ to use a tool based primarily on the description. Invest effort here.
    
4. **Schema formats differ by provider and API.** Anthropic uses `input_schema`, OpenAI Responses API uses `parameters` at top level, legacy Chat Completions wraps in `function`.
    
5. **Strict mode guarantees conformance.** Use in production to eliminate schema validation errors.
    
6. **Tools consume tokens.** Every tool definition is injected into the prompt. More tools = higher cost + context pressure.
    

---

## Quick Reference: Minimum Viable Tool

**Anthropic:**

```python
{
    "name": "tool_name",
    "description": "What it does and when to use it",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "What this param is"}
        },
        "required": ["param1"]
    }
}
```

**OpenAI Responses API:**

```python
{
    "type": "function",
    "name": "tool_name", 
    "description": "What it does and when to use it",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "What this param is"}
        },
        "required": ["param1"],
        "additionalProperties": False
    }
}
```

---

_Next: Note 2 — The Tool Calling Execution Flow_