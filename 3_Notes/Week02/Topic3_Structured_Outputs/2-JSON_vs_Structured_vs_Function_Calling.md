# Note 2: JSON Mode vs Structured Outputs vs Function Calling — When to Use Each

## Three Approaches, Different Guarantees

The industry has converged on three distinct approaches for getting structured data from LLMs. They look similar but provide different guarantees:

|Approach|Valid JSON|Schema Enforced|Provider Support|
|---|---|---|---|
|JSON Mode|✓|✗|OpenAI|
|Structured Outputs|✓|✓|OpenAI, Anthropic|
|Function Calling / Tool Use|✓|✓|OpenAI, Anthropic|

The key insight: **valid JSON ≠ valid schema**. JSON mode gets you parseable output. Structured outputs and function calling get you the exact fields and types you specified.

---

## JSON Mode

### What It Is

JSON mode is a model-level setting that guarantees the output will be syntactically valid JSON. The model physically cannot produce output that `json.loads()` would reject.

### OpenAI Implementation

**Responses API** (current):

```python
# Doc reference: OpenAI Responses API migration guide
# https://platform.openai.com/docs/guides/migrate-to-responses

from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    input=[
        {"role": "user", "content": "Extract the person's name and age as JSON"}
    ],
    text={
        "format": {
            "type": "json_object"
        }
    }
)

print(response.output_text)  # Guaranteed valid JSON, but schema unknown
```

**Chat Completions API** (legacy, still supported):

```python
# Doc reference: OpenAI JSON Mode guide
# https://help.openai.com/en/articles/8555517-function-calling-in-the-openai-api

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Respond in JSON format"},
        {"role": "user", "content": "Extract the person's name and age"}
    ],
    response_format={"type": "json_object"}
)
```

**Critical requirement**: Your prompt must include the word "JSON" somewhere. Without it, the API throws an error. This is OpenAI's safety check to ensure you actually want JSON output.

### Anthropic Approach

Anthropic doesn't have a dedicated "JSON mode" toggle. Instead, you either:

1. Use prompting (unreliable)
2. Use tool use / structured outputs (reliable)

For the Anthropic equivalent of "just give me valid JSON," you'd use their structured outputs feature (covered below).

### What JSON Mode Guarantees

- ✓ Output is parseable JSON
- ✓ No markdown code fences wrapping the JSON
- ✓ No conversational preamble ("Here's the JSON you requested:")

### What JSON Mode Does NOT Guarantee

- ✗ Specific field names (might return `"name"` or `"Name"` or `"user_name"`)
- ✗ Required fields present (might omit fields entirely)
- ✗ Correct types (might return `"30"` instead of `30`)
- ✗ Any particular structure (might return `{}` or `{"error": "cannot process"}`)

### When to Use JSON Mode

- **Prototyping**: Quick experiments where you'll manually inspect output
- **Flexible schemas**: When you genuinely don't care about exact structure
- **Simple extraction**: Single-field or very basic extractions
- **Fallback**: When structured outputs aren't available for your model

**Do not use for production** unless you're prepared to handle arbitrary JSON structures.

---

## Structured Outputs

### What It Is

Structured outputs go beyond JSON mode: you provide a JSON Schema, and the model's output is **constrained at decoding time** to match that schema exactly. This isn't prompt engineering — it's a hard constraint on what tokens the model can generate.

### OpenAI Implementation

**Responses API** (current):

```python
# Doc reference: OpenAI Structured Outputs guide
# https://platform.openai.com/docs/guides/structured-outputs
# OpenAI Responses API migration guide
# https://platform.openai.com/docs/guides/migrate-to-responses

from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    input=[
        {"role": "user", "content": "Jane Smith, 34 years old, lives in Boston"}
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "person_extraction",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "city": {"type": "string"}
                },
                "required": ["name", "age", "city"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
)

import json
data = json.loads(response.output_text)
# Guaranteed: {"name": "Jane Smith", "age": 34, "city": "Boston"}
# - All three fields present
# - age is integer, not string
# - No extra fields
```

**Chat Completions API** (legacy):

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "person_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "city": {"type": "string"}
                },
                "required": ["name", "age", "city"],
                "additionalProperties": False
            }
        }
    }
)
```

### Anthropic Implementation

Anthropic added structured outputs in November 2025. As of March 2026, it's GA (no longer requires beta headers).

```python
# Doc reference: Anthropic Structured Outputs
# https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
# https://platform.claude.com/docs/en/build-with-claude/structured-outputs

import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Jane Smith, 34 years old, lives in Boston"
        }
    ],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "city": {"type": "string"}
                },
                "required": ["name", "age", "city"],
                "additionalProperties": False
            }
        }
    }
)

import json
data = json.loads(response.content[0].text)
```

**With Pydantic** (recommended for both providers):

```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
    city: str

# OpenAI with SDK helper
response = client.responses.parse(
    model="gpt-4o",
    input=[{"role": "user", "content": "Jane Smith, 34, Boston"}],
    text_format=Person
)
person = response.output_parsed  # Person(name="Jane Smith", age=34, city="Boston")

# Anthropic with SDK helper
response = client.messages.parse(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Jane Smith, 34, Boston"}],
    output_format=Person
)
person = response.parsed_output  # Person(name="Jane Smith", age=34, city="Boston")
```

### Critical Requirements for Strict Mode

Both providers require:

1. **`additionalProperties: false`** — No extra fields allowed
2. **All fields in `required`** — When strict mode is on, every field must be required
3. **Supported schema subset** — Not all JSON Schema features work (no `oneOf`, `anyOf`, etc.)

### What Structured Outputs Guarantee

- ✓ Valid JSON (obviously)
- ✓ Exact field names you specified
- ✓ All required fields present
- ✓ Correct types (integer is integer, not string)
- ✓ No extra fields (with `additionalProperties: false`)
- ✓ Enum values respected (if specified)

### What Structured Outputs Do NOT Guarantee

- ✗ Semantic correctness (age might be -5 or 500)
- ✗ Values from source (model might hallucinate plausible data)
- ✗ Non-refusal (model can still refuse for safety reasons)

### When to Use Structured Outputs

- **Production data extraction**: When downstream code depends on exact schema
- **Complex nested structures**: Multiple levels, arrays of objects
- **Type-sensitive processing**: When `"30"` vs `30` breaks your code
- **Reliability-critical paths**: Payment processing, database writes, API responses

---

## Function Calling / Tool Use

### What It Is

Function calling was designed for agents to invoke tools. You define "functions" with parameter schemas, and the model outputs "I want to call this function with these arguments." The arguments are schema-enforced.

The key insight: **you don't have to actually call the function**. You can use the schema enforcement for extraction, treating the "function call" as your structured output.

### OpenAI Implementation

```python
# Doc reference: OpenAI Function Calling guide
# https://platform.openai.com/docs/guides/tools
# https://developers.openai.com/api/docs/guides/function-calling

from openai import OpenAI
client = OpenAI()

tools = [
    {
        "type": "function",
        "name": "extract_person",
        "description": "Extract person information from text",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The person's full name"
                },
                "age": {
                    "type": "integer",
                    "description": "The person's age in years"
                },
                "city": {
                    "type": "string",
                    "description": "The city where the person lives"
                }
            },
            "required": ["name", "age", "city"],
            "additionalProperties": False
        },
        "strict": True  # Enable schema enforcement
    }
]

response = client.responses.create(
    model="gpt-4o",
    input=[
        {"role": "user", "content": "Jane Smith, 34, lives in Boston"}
    ],
    tools=tools,
    tool_choice="required"  # Force the model to call a tool
)

# Extract the function call arguments
import json
tool_call = response.output[0]
data = json.loads(tool_call.arguments)
# {"name": "Jane Smith", "age": 34, "city": "Boston"}
```

### Anthropic Implementation

```python
# Doc reference: Anthropic Tool Use
# https://docs.anthropic.com/en/docs/build-with-claude/tool-use

import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "name": "extract_person",
        "description": "Extract person information from text",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The person's full name"
                },
                "age": {
                    "type": "integer",
                    "description": "The person's age in years"
                },
                "city": {
                    "type": "string",
                    "description": "The city where the person lives"
                }
            },
            "required": ["name", "age", "city"],
            "additionalProperties": False
        },
        "strict": True  # Enable strict schema enforcement
    }
]

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Jane Smith, 34, lives in Boston"}
    ],
    tools=tools,
    tool_choice={"type": "tool", "name": "extract_person"}  # Force specific tool
)

# Extract the tool use arguments
tool_use_block = next(
    block for block in response.content 
    if block.type == "tool_use"
)
data = tool_use_block.input
# {"name": "Jane Smith", "age": 34, "city": "Boston"}
```

### The "Fake Function" Pattern

Using function calling for extraction (without actually calling anything) is a legitimate, widely-used pattern:

```python
# You're not going to call this function — it's just for extraction
tools = [{
    "type": "function",
    "name": "record_job_posting",  # Name implies extraction, not action
    "description": "Record structured data extracted from a job posting",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "company": {"type": "string"},
            "salary_min": {"type": "integer"},
            "salary_max": {"type": "integer"},
            "remote": {"type": "boolean"}
        },
        "required": ["title", "company", "salary_min", "salary_max", "remote"],
        "additionalProperties": False
    },
    "strict": True
}]

# Force the model to "call" the extraction function
response = client.responses.create(
    model="gpt-4o",
    input=[{"role": "user", "content": job_posting_text}],
    tools=tools,
    tool_choice="required"
)

# Parse the "function arguments" as your extracted data
extracted = json.loads(response.output[0].arguments)
```

**Why this works**: The model doesn't know (or care) whether you'll actually call the function. It just outputs schema-compliant arguments. You take those arguments and use them as your extracted data.

**Is this a hack?** No. It's documented by both OpenAI and Anthropic as a valid extraction pattern. The mental model is: "I'm defining a schema for the data I want, and function calling is the mechanism to enforce it."

### When to Use Function Calling

- **Already building agents**: You're using tools anyway, extraction is another tool
- **Cross-provider compatibility**: Same pattern works for OpenAI and Anthropic
- **Multiple extraction types**: Define several "functions" for different extraction tasks
- **Mixed use case**: Some calls extract data, others actually invoke tools

---

## Decision Framework

```
┌─────────────────────────────────────────────────────────────────┐
│                     Do you need schema enforcement?             │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
           No                               Yes
              │                               │
              ▼                               │
    ┌─────────────────┐                      │
    │   JSON Mode     │                      │
    │  (prototype,    │                      │
    │   flexible)     │                      │
    └─────────────────┘                      │
                                             │
              ┌──────────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Need cross-provider compatibility?             │
    └─────────────────────────────────────────────────────────────┘
              │
  ┌───────────┴───────────┐
  │                       │
  ▼                       ▼
 Yes                      No
  │                       │
  ▼                       ▼
┌─────────────────┐   ┌─────────────────────────────────────────┐
│ Function        │   │        Already using tools/agents?      │
│ Calling         │   └─────────────────────────────────────────┘
│ (works both)    │               │
└─────────────────┘       ┌───────┴───────┐
                          │               │
                          ▼               ▼
                         Yes              No
                          │               │
                          ▼               ▼
                  ┌─────────────┐  ┌─────────────────┐
                  │ Function    │  │ Structured      │
                  │ Calling     │  │ Outputs         │
                  │ (consistent │  │ (cleaner API    │
                  │  pattern)   │  │  for pure       │
                  └─────────────┘  │  extraction)    │
                                   └─────────────────┘
```

### Quick Decision Rules

1. **Need cross-provider?** → Function calling (same pattern works everywhere)
2. **OpenAI only, pure extraction?** → Structured Outputs (cleaner, purpose-built)
3. **Simple/flexible needs?** → JSON Mode (but know the risks)
4. **Already using agents/tools?** → Function calling (consistent pattern)
5. **Anthropic only?** → Either Structured Outputs or Tool Use (same guarantees)

---

## Comparison Summary

|Aspect|JSON Mode|Structured Outputs|Function Calling|
|---|---|---|---|
|**Syntax guarantee**|✓|✓|✓|
|**Schema guarantee**|✗|✓|✓|
|**Purpose-built for extraction**|Partial|✓|✗ (but works)|
|**OpenAI support**|✓|✓|✓|
|**Anthropic support**|✗|✓|✓|
|**Pydantic integration**|Manual|Native|Native|
|**Mental model**|"Give me JSON"|"Give me this schema"|"Call this function"|
|**Production-ready**|Risky|✓|✓|

---

## The Bottom Line

**For most production use cases**, use either Structured Outputs or Function Calling — they provide the same schema guarantees. Choose based on:

- **Structured Outputs**: When you're purely extracting data, not building agents
- **Function Calling**: When you're building agents, need cross-provider support, or want a consistent pattern for both extraction and tool invocation

**Avoid JSON Mode in production** unless you have robust validation and retry logic to handle schema violations.

The next note covers Pydantic integration in detail — how to define schemas in Python and let the SDK handle conversion.