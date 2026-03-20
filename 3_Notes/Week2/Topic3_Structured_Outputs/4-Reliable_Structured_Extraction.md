# Note 4: Implementing Reliable Structured Extraction

This note provides complete, working implementations for extracting structured data using OpenAI and Anthropic APIs. All code examples are based on current documentation as of March 2025.

---

## OpenAI Structured Outputs Implementation

### Using the Responses API with Pydantic

The cleanest approach: pass your Pydantic model directly to `responses.parse()`.

```python
# Doc reference: OpenAI Structured Outputs guide
# https://platform.openai.com/docs/guides/structured-outputs
# OpenAI Responses API
# https://platform.openai.com/docs/guides/migrate-to-responses

from openai import OpenAI
from pydantic import BaseModel, Field

client = OpenAI()

class JobPosting(BaseModel):
    """Structured job posting data."""
    title: str = Field(description="The job title")
    company: str = Field(description="The company name")
    location: str | None = Field(default=None, description="Job location if mentioned")
    salary_min: int | None = Field(default=None, description="Minimum salary in USD")
    salary_max: int | None = Field(default=None, description="Maximum salary in USD")
    remote: bool = Field(description="True if remote/WFH/distributed mentioned")
    required_skills: list[str] = Field(description="Required skills listed")

# Using responses.parse() - SDK handles schema conversion automatically
response = client.responses.parse(
    model="gpt-4o",
    input=[
        {"role": "system", "content": "Extract job posting information from the text."},
        {"role": "user", "content": """
            Senior Python Developer at TechCorp
            Location: San Francisco (Remote OK)
            Salary: $150,000 - $180,000
            Requirements: Python, FastAPI, PostgreSQL, 5+ years experience
        """}
    ],
    text_format=JobPosting  # Pass the Pydantic class directly
)

# Already parsed into Pydantic model
job = response.output_parsed
print(f"Title: {job.title}")
print(f"Company: {job.company}")
print(f"Remote: {job.remote}")
print(f"Skills: {job.required_skills}")
```

### Using responses.create() with Manual Schema

When you need more control, use `responses.create()` with the raw JSON schema:

```python
# Doc reference: OpenAI Responses API migration guide
# https://platform.openai.com/docs/guides/migrate-to-responses

import json
from openai import OpenAI
from pydantic import BaseModel, Field

client = OpenAI()

class JobPosting(BaseModel):
    title: str
    company: str
    remote: bool
    required_skills: list[str]

# Get JSON schema from Pydantic model
schema = JobPosting.model_json_schema()

response = client.responses.create(
    model="gpt-4o",
    input=[
        {"role": "system", "content": "Extract job posting information from the text."},
        {"role": "user", "content": "Senior Python Developer at TechCorp, remote, needs Python and FastAPI"}
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "job_extraction",
            "schema": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": list(schema.get("properties", {}).keys()),
                "additionalProperties": False
            },
            "strict": True
        }
    }
)

# Parse JSON response into Pydantic model
data = json.loads(response.output_text)
job = JobPosting.model_validate(data)
```

---

## OpenAI Function Calling Implementation

Function calling provides schema enforcement through tool definitions. This pattern works for both actual tool invocation and pure data extraction.

```python
# Doc reference: OpenAI Function Calling guide
# https://platform.openai.com/docs/guides/tools
# https://developers.openai.com/api/docs/guides/function-calling

import json
from openai import OpenAI
from pydantic import BaseModel, Field

client = OpenAI()

class JobPosting(BaseModel):
    title: str = Field(description="The job title")
    company: str = Field(description="The company name")
    remote: bool = Field(description="True if remote work is available")
    required_skills: list[str] = Field(description="List of required skills")

# Define tool with schema
tools = [
    {
        "type": "function",
        "name": "extract_job_posting",
        "description": "Extract structured data from a job posting",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The job title"
                },
                "company": {
                    "type": "string",
                    "description": "The company name"
                },
                "remote": {
                    "type": "boolean",
                    "description": "True if remote work is available"
                },
                "required_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of required skills"
                }
            },
            "required": ["title", "company", "remote", "required_skills"],
            "additionalProperties": False
        },
        "strict": True  # Enable schema enforcement
    }
]

response = client.responses.create(
    model="gpt-4o",
    input=[
        {"role": "system", "content": "Extract job posting information using the provided function."},
        {"role": "user", "content": "Senior Python Developer at TechCorp, remote, needs Python and FastAPI"}
    ],
    tools=tools,
    tool_choice="required"  # Force tool use
)

# Extract function call arguments
tool_call = response.output[0]
data = json.loads(tool_call.arguments)
job = JobPosting.model_validate(data)

print(f"Extracted: {job.title} at {job.company}")
```

---

## Anthropic Structured Outputs Implementation

Anthropic's structured outputs became GA in early 2025. The pattern is similar to OpenAI.

### Using messages.parse() with Pydantic

```python
# Doc reference: Anthropic Structured Outputs
# https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs
# https://platform.claude.com/docs/en/build-with-claude/structured-outputs

import anthropic
from pydantic import BaseModel, Field

client = anthropic.Anthropic()

class JobPosting(BaseModel):
    """Structured job posting data."""
    title: str = Field(description="The job title")
    company: str = Field(description="The company name")
    remote: bool = Field(description="True if remote/WFH mentioned")
    required_skills: list[str] = Field(description="Required skills listed")

# Using messages.parse() - SDK handles schema conversion
response = client.messages.parse(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": """Extract job posting information:
            
            Senior Python Developer at TechCorp
            Remote OK
            Requirements: Python, FastAPI, PostgreSQL
            """
        }
    ],
    output_format=JobPosting  # Pass the Pydantic class directly
)

# Already parsed into Pydantic model
job = response.parsed_output
print(f"Title: {job.title}")
print(f"Company: {job.company}")
```

### Using messages.create() with Manual Schema

For more control, use `messages.create()` with `output_config`:

```python
# Doc reference: Anthropic Structured Outputs
# https://platform.claude.com/docs/en/build-with-claude/structured-outputs

import json
import anthropic
from pydantic import BaseModel

client = anthropic.Anthropic()

class JobPosting(BaseModel):
    title: str
    company: str
    remote: bool
    required_skills: list[str]

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Extract: Senior Python Developer at TechCorp, remote, needs Python and FastAPI"
        }
    ],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "remote": {"type": "boolean"},
                    "required_skills": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["title", "company", "remote", "required_skills"],
                "additionalProperties": False
            }
        }
    }
)

# Parse JSON from response
data = json.loads(response.content[0].text)
job = JobPosting.model_validate(data)
```

---

## Anthropic Tool Use Implementation

Same pattern as OpenAI function calling:

```python
# Doc reference: Anthropic Tool Use
# https://docs.anthropic.com/en/docs/build-with-claude/tool-use

import json
import anthropic
from pydantic import BaseModel, Field

client = anthropic.Anthropic()

class JobPosting(BaseModel):
    title: str
    company: str
    remote: bool
    required_skills: list[str]

tools = [
    {
        "name": "extract_job_posting",
        "description": "Extract structured data from a job posting",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The job title"
                },
                "company": {
                    "type": "string",
                    "description": "The company name"
                },
                "remote": {
                    "type": "boolean",
                    "description": "True if remote work is available"
                },
                "required_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of required skills"
                }
            },
            "required": ["title", "company", "remote", "required_skills"],
            "additionalProperties": False
        },
        "strict": True  # Enable strict schema enforcement
    }
]

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Extract: Senior Python Developer at TechCorp, remote, needs Python"
        }
    ],
    tools=tools,
    tool_choice={"type": "tool", "name": "extract_job_posting"}  # Force specific tool
)

# Find the tool_use block in response
tool_use_block = next(
    block for block in response.content 
    if block.type == "tool_use"
)
data = tool_use_block.input
job = JobPosting.model_validate(data)
```

---

## Generic Extraction Function

Here's a reusable extraction function that works with any Pydantic model:

```python
from typing import TypeVar, Type
import json
from openai import OpenAI
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

def extract_structured_data(
    text: str,
    schema: Type[T],
    model: str = "gpt-4o-mini",
    system_prompt: str | None = None
) -> T:
    """
    Extract structured data from unstructured text.
    
    Args:
        text: The unstructured text to extract from
        schema: Pydantic model class defining the expected structure
        model: OpenAI model to use
        system_prompt: Optional custom system prompt
    
    Returns:
        Validated Pydantic model instance
    
    Raises:
        pydantic.ValidationError: If extraction fails validation
    """
    client = OpenAI()
    
    default_system = f"Extract information matching the schema from the provided text. Only include information explicitly stated in the text. Use null for fields not found."
    
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": system_prompt or default_system},
            {"role": "user", "content": text}
        ],
        text_format=schema
    )
    
    return response.output_parsed


# Usage example
class Person(BaseModel):
    name: str
    age: int | None = None
    occupation: str | None = None

text = "John Smith is a 35-year-old software engineer from Boston."
person = extract_structured_data(text, Person)
print(f"{person.name}, {person.age}, {person.occupation}")
# Output: John Smith, 35, software engineer
```

### Anthropic Version

```python
from typing import TypeVar, Type
import anthropic
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

def extract_structured_data_anthropic(
    text: str,
    schema: Type[T],
    model: str = "claude-sonnet-4-5",
    system_prompt: str | None = None
) -> T:
    """
    Extract structured data using Anthropic's API.
    """
    client = anthropic.Anthropic()
    
    default_system = "Extract information matching the schema from the provided text."
    
    messages = [{"role": "user", "content": text}]
    
    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=system_prompt or default_system,
        messages=messages,
        output_format=schema
    )
    
    return response.parsed_output
```

---

## Prompt Design for Extraction

### Keep It Simple

The schema itself is the instruction. Don't over-explain what each field means — your Pydantic `Field(description=...)` already does that.

**Good prompt:**

```python
messages = [
    {"role": "system", "content": "Extract information from the text."},
    {"role": "user", "content": source_text}
]
```

**Over-engineered prompt:**

```python
# Don't do this — the schema already defines these fields
messages = [
    {"role": "system", "content": """Extract the following fields:
    - title: The job title
    - company: The company name
    - salary_min: The minimum salary
    - salary_max: The maximum salary
    ... (repeating what's in schema)
    """},
    {"role": "user", "content": source_text}
]
```

### Handle Missing Data

Tell the model what to do when information isn't present:

```python
system_prompt = """
Extract information from the text.
- Only include information explicitly stated in the text
- Use null for fields where information is not found
- Do not infer or guess values
"""
```

### Provide Context When Needed

If the extraction requires domain knowledge:

```python
system_prompt = """
Extract job posting information.
- "WFH", "work from home", "distributed" all mean remote=true
- Salary should be annual, in USD
- If salary is given as a range, extract both min and max
- If only one number given, use it for both min and max
"""
```

---

## Response Parsing

### Direct Parsing with SDK Helpers

Both OpenAI and Anthropic SDKs handle parsing automatically:

```python
# OpenAI - already parsed
response = client.responses.parse(model=..., text_format=MyModel)
result = response.output_parsed  # MyModel instance

# Anthropic - already parsed
response = client.messages.parse(model=..., output_format=MyModel)
result = response.parsed_output  # MyModel instance
```

### Manual Parsing When Using create()

When using `.create()` instead of `.parse()`:

```python
import json
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int

# From OpenAI response
json_string = response.output_text
data = json.loads(json_string)
person = Person.model_validate(data)

# Or in one step
person = Person.model_validate_json(json_string)
```

### Validation Methods

Pydantic provides two validation methods:

```python
# From dict
data = {"name": "Alice", "age": 30}
person = Person.model_validate(data)

# From JSON string
json_str = '{"name": "Alice", "age": 30}'
person = Person.model_validate_json(json_str)
```

---

## Error Handling

### Error Types

```python
import json
from pydantic import BaseModel, ValidationError
from openai import OpenAI

class Person(BaseModel):
    name: str
    age: int
    email: str

def safe_extract(text: str, schema: type[BaseModel], max_retries: int = 2) -> BaseModel | None:
    client = OpenAI()
    
    for attempt in range(max_retries + 1):
        try:
            response = client.responses.parse(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": "Extract information from text."},
                    {"role": "user", "content": text}
                ],
                text_format=schema
            )
            return response.output_parsed
            
        except json.JSONDecodeError as e:
            # Shouldn't happen with structured outputs, but handle anyway
            print(f"JSON parse error (attempt {attempt + 1}): {e}")
            continue
            
        except ValidationError as e:
            # Schema mismatch - model output didn't match Pydantic model
            print(f"Validation error (attempt {attempt + 1}): {e}")
            continue
            
        except Exception as e:
            # API errors, rate limits, etc.
            print(f"API error: {e}")
            raise
    
    return None
```

### When Errors Occur

With structured outputs enabled:

- **`json.JSONDecodeError`**: Should not happen — the model is constrained to valid JSON
- **`pydantic.ValidationError`**: Can happen if schema conversion has issues, or if model refuses
- **API errors**: Rate limits, timeouts, network issues

### Model Refusals

Both providers can still refuse for safety reasons:

```python
# OpenAI
response = client.responses.parse(...)
if response.output_parsed is None and response.refusal:
    print(f"Model refused: {response.refusal}")

# Anthropic
response = client.messages.parse(...)
# Check stop_reason for safety-related stops
```

---

## Testing Extraction

### Test Multiple Input Formats

The same data can appear in many formats. Test all of them:

```python
test_cases = [
    # Structured format
    """
    Position: Senior Engineer
    Company: TechCorp
    Salary: $150,000
    """,
    
    # Prose format
    "TechCorp is hiring a Senior Engineer at $150k.",
    
    # Minimal format
    "Senior Engineer - TechCorp - 150K",
    
    # Verbose format
    """
    We are excited to announce that TechCorp, a leading technology
    company, is looking for a Senior Engineer to join our team.
    The compensation package starts at $150,000 annually...
    """,
]

for text in test_cases:
    result = extract_structured_data(text, JobPosting)
    assert result.title == "Senior Engineer"
    assert result.company == "TechCorp"
```

### Test Edge Cases

```python
# Minimal information
text = "Engineer at Corp"
result = extract(text, JobPosting)
assert result.salary_min is None  # Not mentioned

# Completely unrelated text
text = "The weather is nice today."
result = extract(text, JobPosting)
# Should still return valid schema, just with null/empty values

# Ambiguous information
text = "Engineer, $100-150k"
result = extract(text, JobPosting)
assert result.salary_min == 100000
assert result.salary_max == 150000
```

### Test Schema Edge Cases

```python
# Boolean inference
text = "Remote position available"
result = extract(text, JobPosting)
assert result.remote == True

text = "Must work from our NYC office"
result = extract(text, JobPosting)
assert result.remote == False

# List extraction from various formats
text = "Skills: Python, SQL, Docker"  # Comma-separated
text = "Skills:\n- Python\n- SQL\n- Docker"  # Bullet points
text = "Must know Python and SQL plus Docker"  # Prose
# All should extract: ["Python", "SQL", "Docker"]
```

---

## The Bottom Line

Implementation checklist:

1. **Define your Pydantic model** with clear field descriptions
2. **Use SDK helpers** (`responses.parse()` or `messages.parse()`) when possible
3. **Keep prompts simple** — the schema is the instruction
4. **Handle missing data** with optional fields and explicit guidance
5. **Test varied inputs** — same data, different formats
6. **Handle errors gracefully** — even with guarantees, things can fail

The next note covers edge cases: hallucination, missing fields, ranges, and when extraction should fail gracefully.