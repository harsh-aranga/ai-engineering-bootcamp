# Note 5: Tool Description Best Practices

## Week 3 Agents — Days 3-4 | Function Calling / Tool Use

---

## Why Descriptions Matter

Tool descriptions are **the most important factor in tool use performance**.

The LLM uses your descriptions to decide:

1. **Whether** to use a tool at all
2. **Which** tool to use when multiple are available
3. **How** to construct the arguments

A vague description = confused model = wrong tool calls = broken agent.

---

## The Core Principle

> Write descriptions as if explaining the tool to a smart colleague who has never seen it before.

The model doesn't know:

- What your tool actually does internally
- What edge cases exist
- What format the inputs need to be in
- What the output will look like
- When NOT to use the tool

You must tell it all of this.

---

## Anatomy of a Good Tool Description

### The Four Components

```
┌─────────────────────────────────────────────────────────────┐
│ 1. WHAT IT DOES                                             │
│    Clear, specific explanation of the tool's function       │
├─────────────────────────────────────────────────────────────┤
│ 2. WHEN TO USE IT                                           │
│    Triggers, scenarios, conditions for use                  │
├─────────────────────────────────────────────────────────────┤
│ 3. WHAT IT RETURNS                                          │
│    Output format, fields, data types                        │
├─────────────────────────────────────────────────────────────┤
│ 4. LIMITATIONS & CAVEATS                                    │
│    What it doesn't do, edge cases, constraints              │
└─────────────────────────────────────────────────────────────┘
```

---

## Good vs Bad Descriptions

### Example 1: Weather Tool

**❌ Bad:**

```python
{
    "name": "get_weather",
    "description": "Gets weather data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {"type": "string"}
        },
        "required": ["location"]
    }
}
```

**Problems:**

- What kind of weather data? Current? Forecast?
- What format is location? City name? Coordinates?
- What does it return?

**✅ Good:**

```python
{
    "name": "get_weather",
    "description": """Get the current weather conditions for a specific location.

Returns temperature (in Fahrenheit), humidity percentage, wind speed (mph), 
and a brief description of conditions (e.g., 'Partly cloudy').

Use this tool when the user asks about current weather, temperature, 
or outdoor conditions. Do NOT use for weather forecasts or historical weather.

The location should be a city name with optional state/country for disambiguation 
(e.g., 'San Francisco, CA' or 'London, UK'). Coordinates are not supported.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City name with optional state/country, e.g., 'San Francisco, CA' or 'Paris, France'"
            }
        },
        "required": ["location"]
    }
}
```

---

### Example 2: Database Query Tool

**❌ Bad:**

```python
{
    "name": "search_customers",
    "description": "Search for customers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"}
        }
    }
}
```

**✅ Good:**

```python
{
    "name": "search_customers",
    "description": """Search the customer database by name, email, or customer ID.

Performs a fuzzy match on customer names and exact match on email/ID.
Returns up to 'limit' results (default 10, max 100) sorted by relevance.

Each result includes: customer_id, full_name, email, account_status, 
and created_date. Does NOT include sensitive data like payment info.

Use when the user wants to find, look up, or identify a customer.
For retrieving a specific customer's full details, use get_customer_details instead.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term: customer name (partial OK), email address, or customer ID"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (1-100, default 10)"
            }
        },
        "required": ["query"]
    }
}
```

---

### Example 3: File Operations

**❌ Bad:**

```python
{
    "name": "write_file",
    "description": "Writes to a file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}
        }
    }
}
```

**✅ Good:**

```python
{
    "name": "write_file",
    "description": """Create or overwrite a file with the specified content.

WARNING: This will completely replace any existing file at the given path.
To append to a file, use append_to_file instead.

The path must be within the allowed directory (/workspace/). Attempting to 
write outside this directory will fail. Parent directories are created 
automatically if they don't exist.

Returns a confirmation message with the file path and bytes written.
Fails if the file is locked, the path is invalid, or permissions are denied.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to /workspace/, e.g., 'reports/output.txt'"
            },
            "content": {
                "type": "string",
                "description": "The complete content to write to the file (UTF-8 encoded)"
            }
        },
        "required": ["path", "content"]
    }
}
```

---

## Parameter Descriptions

Don't neglect parameter descriptions. They're just as important as the tool description.

### Pattern: Complete Parameter Description

```python
"properties": {
    "start_date": {
        "type": "string",
        "description": "Start date for the query in ISO 8601 format (YYYY-MM-DD). "
                       "Defaults to 30 days ago if not provided. "
                       "Cannot be earlier than 2020-01-01."
    },
    "include_archived": {
        "type": "boolean",
        "description": "If true, include archived records in results. "
                       "Defaults to false. Archived records have status='ARCHIVED'."
    },
    "sort_by": {
        "type": "string",
        "enum": ["date", "amount", "name"],
        "description": "Field to sort results by. 'date' sorts newest first, "
                       "'amount' sorts highest first, 'name' sorts alphabetically."
    }
}
```

### What to Include in Parameter Descriptions

|Element|Example|
|---|---|
|Format|`"ISO 8601 format (YYYY-MM-DD)"`|
|Default|`"Defaults to 10 if not provided"`|
|Range|`"Must be between 1 and 100"`|
|Examples|`"e.g., 'San Francisco, CA'"`|
|Enum meaning|`"'pending' = awaiting review, 'approved' = ready to process"`|
|Edge cases|`"Use null for 'no limit'"`|

---

## Distinguishing Similar Tools

When you have multiple tools with overlapping purposes, your descriptions must clearly differentiate them.

### Bad: Ambiguous Tools

```python
tools = [
    {
        "name": "search_orders",
        "description": "Search for orders."
    },
    {
        "name": "get_order",
        "description": "Get order information."
    },
    {
        "name": "lookup_order",
        "description": "Look up an order."
    }
]
```

The model will guess randomly.

### Good: Clear Differentiation

```python
tools = [
    {
        "name": "search_orders",
        "description": """Search for orders matching criteria (date range, status, customer).
        
        Use when: User wants to FIND orders matching conditions, doesn't have a specific order ID.
        Returns: List of matching orders (summary info only: id, date, status, total).
        Use get_order_details for full information about a specific order."""
    },
    {
        "name": "get_order_details",
        "description": """Get complete details for a single order by order ID.
        
        Use when: User has a specific order ID and wants full details.
        Returns: Complete order info including line items, shipping, payment, timeline.
        Use search_orders first if the user doesn't have an order ID."""
    },
    {
        "name": "get_recent_orders",
        "description": """Get the most recent orders for a customer.
        
        Use when: User asks about their recent/latest orders without specific criteria.
        Returns: Last 10 orders (summary) for the given customer.
        Requires customer_id. Use search_orders for more specific queries."""
    }
]
```

---

## The "When to Use / When NOT to Use" Pattern

Explicitly stating when NOT to use a tool is powerful:

```python
{
    "name": "send_email",
    "description": """Send an email on behalf of the user.

WHEN TO USE:
- User explicitly asks to send an email
- User confirms they want to send after reviewing the draft

WHEN NOT TO USE:
- Just drafting/composing an email (use draft_email instead)
- User hasn't confirmed they want to send
- User is asking about email content without intent to send

This action is irreversible. Always confirm with the user before calling."""
}
```

---

## Describing Output Format

Tell the model what it will get back:

```python
{
    "name": "analyze_sentiment",
    "description": """Analyze the sentiment of the given text.

Returns a JSON object with:
- score: Float from -1.0 (very negative) to 1.0 (very positive)
- label: String, one of 'positive', 'negative', 'neutral', 'mixed'
- confidence: Float from 0.0 to 1.0 indicating model confidence
- key_phrases: Array of strings that influenced the sentiment

Example output:
{
  "score": 0.75,
  "label": "positive", 
  "confidence": 0.92,
  "key_phrases": ["excellent service", "highly recommend"]
}"""
}
```

---

## Using Input Examples (Beta)

For complex tools, Anthropic's `input_examples` field (beta) lets you show concrete usage patterns:

```python
{
    "name": "create_calendar_event",
    "description": """Create a calendar event with specified details.
    
Supports one-time and recurring events. Times should be in ISO 8601 format.
All-day events should set is_all_day to true and omit start_time/end_time.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "date": {"type": "string"},
            "start_time": {"type": "string"},
            "end_time": {"type": "string"},
            "is_all_day": {"type": "boolean"},
            "recurrence": {
                "type": "object",
                "properties": {
                    "frequency": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "interval": {"type": "integer"},
                    "end_date": {"type": "string"}
                }
            }
        },
        "required": ["title", "date"]
    },
    "input_examples": [
        # Simple one-time event
        {
            "title": "Team standup",
            "date": "2025-03-20",
            "start_time": "09:00",
            "end_time": "09:30"
        },
        # All-day event
        {
            "title": "Company holiday",
            "date": "2025-07-04",
            "is_all_day": True
        },
        # Recurring event
        {
            "title": "Weekly review",
            "date": "2025-03-17",
            "start_time": "14:00",
            "end_time": "15:00",
            "recurrence": {
                "frequency": "weekly",
                "interval": 1,
                "end_date": "2025-06-30"
            }
        }
    ]
}
```

**When to use `input_examples`:**

- Complex nested objects
- Non-obvious parameter combinations
- Format-sensitive inputs (dates, IDs, codes)
- When the schema alone isn't enough

**Cost:** ~20-50 tokens for simple examples, ~100-200 for complex nested objects.

---

## Description Length Guidelines

|Tool Complexity|Minimum Length|Target Length|
|---|---|---|
|Simple (1-2 params)|2-3 sentences|3-4 sentences|
|Medium (3-5 params)|4-5 sentences|5-7 sentences|
|Complex (6+ params, nested)|6-8 sentences|8-10+ sentences|

**Rule of thumb:** If you're unsure whether you've written enough, you probably haven't.

---

## Anti-Patterns to Avoid

### 1. Single-Word Descriptions

```python
# ❌ Never do this
"description": "Search."
```

### 2. Redundant Name Repetition

```python
# ❌ Tells the model nothing new
"name": "get_user_profile",
"description": "Gets the user profile."
```

### 3. Implementation Details

```python
# ❌ The model doesn't need to know your tech stack
"description": "Queries the PostgreSQL database using a LEFT JOIN 
               on the users and profiles tables via the ORM."
```

### 4. Assuming Context

```python
# ❌ What "the system"? What "standard format"?
"description": "Fetches data from the system in the standard format."
```

### 5. Contradictory Instructions

```python
# ❌ Confusing - is it required or optional?
"description": "The ID is required but you can leave it blank."
```

---

## Prompt Engineering for Tool Descriptions

### Use Clear Structure

```python
"description": """[One-line summary of what the tool does]

INPUTS:
- param1: What it means and format
- param2: What it means and format

OUTPUT:
Description of what gets returned and its format.

USE WHEN:
- Condition 1
- Condition 2

DO NOT USE WHEN:
- Condition 1
- Condition 2

NOTES:
- Important caveat 1
- Important caveat 2"""
```

### Be Specific About Data Types

```python
# ❌ Vague
"description": "Takes a date and amount"

# ✅ Specific
"description": "Takes a date (ISO 8601 format: YYYY-MM-DD) and amount (decimal, e.g., 99.99)"
```

### Specify Units

```python
# ❌ Ambiguous
"description": "Returns the distance between two points"

# ✅ Clear
"description": "Returns the distance between two points in kilometers (float, 2 decimal places)"
```

---

## Description Checklist

Before deploying a tool, verify:

- [ ] **What:** Does the description clearly state what the tool does?
- [ ] **When:** Is it clear when to use this tool vs others?
- [ ] **Inputs:** Are all parameters explained with format and examples?
- [ ] **Outputs:** Is the return value described (type, fields, format)?
- [ ] **Limits:** Are constraints, limits, and edge cases documented?
- [ ] **Not:** Is it clear when NOT to use the tool?
- [ ] **Length:** Is it at least 3-4 sentences for simple tools?
- [ ] **Standalone:** Can someone understand the tool without external context?

---

## Key Takeaways

1. **Descriptions are the #1 factor** in tool use performance — invest heavily in them
    
2. **Cover all four components:** What it does, when to use it, what it returns, limitations
    
3. **Parameter descriptions matter too** — include format, defaults, ranges, examples
    
4. **Differentiate similar tools** — explicitly state when to use each one
    
5. **State when NOT to use** — negative conditions are as important as positive ones
    
6. **Test and iterate** — run evaluations and refine descriptions based on failures
    
7. **Use `input_examples`** for complex tools where schema alone isn't enough
    

---

_Next: Note 6 — Client Tools vs Server Tools_