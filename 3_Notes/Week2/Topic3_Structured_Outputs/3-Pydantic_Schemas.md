# Note 3: Defining Schemas with Pydantic for LLM Outputs

## Why Pydantic for LLM Schemas

Pydantic has become the de facto standard for defining structured output schemas in Python LLM applications. Here's why:

**Type hints → JSON Schema**: Pydantic converts your Python class definitions into JSON Schema automatically. You define `age: int`, and it generates `{"type": "integer"}` in the schema sent to the model.

**Validation on instantiation**: When you create a Pydantic object, it validates and coerces types immediately. If the model returns `"30"` for an int field, Pydantic converts it to `30`. If it returns `"abc"`, you get a clear `ValidationError`.

**Clear error messages**: When validation fails, Pydantic tells you exactly what went wrong — which field, what was expected, what was received.

**Industry standard**: OpenAI, Anthropic, LangChain, Instructor — they all provide native Pydantic integration. Define once, use everywhere.

---

## Basic Pydantic Model

```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
    city: str | None = None  # Optional with default

# Creating an instance validates automatically
person = Person(name="Alice", age=30)
print(person.name)  # "Alice"
print(person.age)   # 30 (int, not string)
print(person.city)  # None

# Type coercion happens automatically
person = Person(name="Bob", age="25")  # String "25" → int 25
print(person.age)  # 25

# Invalid data raises ValidationError
try:
    person = Person(name="Charlie", age="not a number")
except Exception as e:
    print(e)  # Input should be a valid integer
```

---

## Field Types for LLM Extraction

### Required Fields

A field without a default value is required. The model must provide it.

```python
class Person(BaseModel):
    name: str    # Required — must be present
    age: int     # Required — must be present
```

### Optional Fields with Default

Use `| None = None` for fields that might not be present in the source text.

```python
class Person(BaseModel):
    name: str                    # Required
    email: str | None = None     # Optional — None if not found
    phone: str | None = None     # Optional — None if not found
```

**Design principle**: If the source text might not contain the information, make the field optional. This prevents the model from hallucinating data to satisfy a required field.

### Lists

For extracting multiple values (skills, tags, items):

```python
class JobPosting(BaseModel):
    title: str
    required_skills: list[str]           # Multiple skills
    nice_to_have: list[str] | None = []  # Optional list, empty default
```

### Nested Models

For complex structures with sub-objects:

```python
class Address(BaseModel):
    street: str
    city: str
    country: str

class Person(BaseModel):
    name: str
    address: Address  # Nested object
```

### Enums with Literal

For constrained categorical values:

```python
from typing import Literal

class Classification(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    priority: Literal["low", "medium", "high", "critical"]
    category: Literal["bug", "feature", "question", "other"]
```

The model can only output one of the specified values. This is enforced at the schema level — the model literally cannot produce `"kinda positive"`.

---

## Converting Pydantic to JSON Schema

Pydantic provides `model_json_schema()` to generate a JSON Schema dict:

```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int
    city: str | None = None

schema = Person.model_json_schema()
print(schema)
```

Output:

```json
{
  "properties": {
    "name": {"title": "Name", "type": "string"},
    "age": {"title": "Age", "type": "integer"},
    "city": {
      "anyOf": [{"type": "string"}, {"type": "null"}],
      "default": null,
      "title": "City"
    }
  },
  "required": ["name", "age"],
  "title": "Person",
  "type": "object"
}
```

**Key observations**:

- Required fields appear in the `required` array
- Optional fields with defaults don't appear in `required`
- Type mapping: `str` → `"string"`, `int` → `"integer"`, `bool` → `"boolean"`
- `str | None` becomes `{"anyOf": [{"type": "string"}, {"type": "null"}]}`

### SDK Helpers Handle the Conversion

In practice, you rarely call `model_json_schema()` directly. The SDKs handle it:

```python
# OpenAI SDK handles conversion
# Doc reference: OpenAI Structured Outputs guide
# https://platform.openai.com/docs/guides/structured-outputs

response = client.responses.parse(
    model="gpt-4o",
    input=[{"role": "user", "content": "Extract: Jane, 34, Boston"}],
    text_format=Person  # Pass the class directly
)
person = response.output_parsed  # Already a Person instance

# Anthropic SDK handles conversion
# Doc reference: Anthropic Structured Outputs
# https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs

response = client.messages.parse(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Extract: Jane, 34, Boston"}],
    output_format=Person  # Pass the class directly
)
person = response.parsed_output  # Already a Person instance
```

---

## Designing Schemas for Extraction

### Make Fields Optional When Source Might Not Contain Them

Bad — forces hallucination:

```python
class ContactInfo(BaseModel):
    name: str
    email: str      # Required! Model will invent an email
    phone: str      # Required! Model will invent a phone number
    linkedin: str   # Required! Model will invent a URL
```

Good — allows "not found":

```python
class ContactInfo(BaseModel):
    name: str                        # Usually present
    email: str | None = None         # Might not be in source
    phone: str | None = None         # Might not be in source
    linkedin: str | None = None      # Might not be in source
```

### Use `None` as Explicit "Not Found" Signal

When you receive `None`, it means the model didn't find that information. This is different from an empty string or a hallucinated value.

```python
contact = extract_contact(text)

if contact.email is None:
    print("No email found in source text")
else:
    send_email(contact.email)
```

### Use Enums for Known Categories

When you know the valid values in advance, use `Literal`:

```python
class TicketClassification(BaseModel):
    urgency: Literal["low", "medium", "high", "critical"]
    category: Literal["billing", "technical", "sales", "other"]
    
    # NOT:
    # urgency: str  # Model might return "kinda urgent", "asap", "not really urgent"
```

### Use Lists for Variable-Count Items

When extracting multiple items of the same type:

```python
class Resume(BaseModel):
    skills: list[str]         # ["Python", "SQL", "Docker"]
    experience: list[Job]     # List of nested objects
    education: list[Degree]
```

### Avoid Overly Nested Structures

Deep nesting can cause models to struggle. Flatten when possible.

```python
# Harder for models:
class Document(BaseModel):
    metadata: DocumentMetadata
        # Which contains:
        author: Author
            # Which contains:
            contact: ContactInfo
                # Which contains:
                address: Address

# Easier for models:
class Document(BaseModel):
    title: str
    author_name: str
    author_email: str | None = None
    publication_date: str | None = None
```

---

## Field Descriptions for Better Extraction

Field descriptions are passed to the model as part of the schema. They guide extraction accuracy more than field names do.

```python
from pydantic import BaseModel, Field

class JobPosting(BaseModel):
    title: str = Field(
        description="The job title, e.g., 'Senior Software Engineer', 'Product Manager'"
    )
    
    salary_min: int | None = Field(
        default=None,
        description="Minimum salary in USD. Extract the number only, no currency symbols."
    )
    
    salary_max: int | None = Field(
        default=None,
        description="Maximum salary in USD. If only one number given, use it for both min and max."
    )
    
    remote: bool = Field(
        description="True if the job mentions remote work, work from home, WFH, or distributed. False otherwise."
    )
    
    experience_years: int | None = Field(
        default=None,
        description="Minimum years of experience required. Extract the number only. If a range like '3-5 years', use the minimum (3)."
    )
```

The descriptions appear in the JSON schema sent to the model:

```json
{
  "properties": {
    "remote": {
      "type": "boolean",
      "description": "True if the job mentions remote work, work from home, WFH, or distributed. False otherwise."
    }
  }
}
```

**Why descriptions matter more than field names**:

- `is_remote` vs `remote` vs `remote_work` — models might interpret these differently
- A clear description like "True if the job mentions remote work, WFH, or distributed" leaves no ambiguity

### Description Best Practices

1. **Give examples**: `"e.g., 'Senior Software Engineer'"`
2. **Specify format**: `"Extract the number only, no currency symbols"`
3. **Handle edge cases**: `"If a range like '3-5 years', use the minimum"`
4. **Define boolean logic**: `"True if X, Y, or Z mentioned. False otherwise."`

---

## Schema Constraints for Structured Outputs

When using strict mode (OpenAI's `strict: true`, Anthropic's schema enforcement), there are constraints:

### Required: `additionalProperties: false`

Both OpenAI and Anthropic require this for strict mode. It means the model cannot add fields you didn't define.

Pydantic models need this configured explicitly for OpenAI:

```python
from pydantic import BaseModel, ConfigDict

class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Generates additionalProperties: false
    
    name: str
    age: int
```

Or use the SDK helpers that handle this automatically:

```python
# OpenAI SDK's transform (if needed manually)
from anthropic import transform_schema
schema = transform_schema(Person)  # Adds additionalProperties: false
```

### All Fields Must Be Explicitly Defined

No dynamic keys. You can't do:

```python
class FlexibleData(BaseModel):
    data: dict  # ❌ What keys? What types?
```

You must define the exact structure:

```python
class StructuredData(BaseModel):
    name: str
    value: int
    tags: list[str]
```

### All Fields Required in Strict Mode

When `strict: true`, all fields must be in the `required` array. Handle optional fields with union types:

```python
class Person(BaseModel):
    name: str                    # Will be required
    email: str | None = None     # Will be required, but can be null
```

The schema becomes:

```json
{
  "properties": {
    "name": {"type": "string"},
    "email": {"anyOf": [{"type": "string"}, {"type": "null"}]}
  },
  "required": ["name", "email"],  // Both required
  "additionalProperties": false
}
```

The field is _required_ in the schema (must be present), but its value can be `null`.

---

## Common Schema Patterns

### Entity Extraction

```python
class Entity(BaseModel):
    """An entity mentioned in the text."""
    name: str = Field(description="The entity's name as mentioned in text")
    entity_type: Literal["person", "organization", "location", "product", "other"]
    description: str | None = Field(
        default=None,
        description="Brief description or context about the entity from the text"
    )
```

### Document Metadata

```python
class DocumentMetadata(BaseModel):
    """Metadata extracted from a document."""
    title: str | None = Field(default=None, description="Document title if present")
    author: str | None = Field(default=None, description="Author name if mentioned")
    date: str | None = Field(
        default=None, 
        description="Publication or creation date in YYYY-MM-DD format if mentioned"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Key topics or themes covered in the document"
    )
    document_type: Literal["article", "report", "email", "memo", "other"] = Field(
        description="The type of document"
    )
```

### Classification with Reasoning

```python
class Classification(BaseModel):
    """A classification decision with reasoning."""
    category: Literal["spam", "not_spam"] = Field(
        description="The classification result"
    )
    confidence: Literal["low", "medium", "high"] = Field(
        description="Confidence in the classification"
    )
    reasoning: str = Field(
        description="Brief explanation of why this classification was chosen"
    )
```

### Multi-Item Extraction

```python
class ExtractedItem(BaseModel):
    """A single extracted item."""
    item: str
    quantity: int | None = None
    price: float | None = None

class Receipt(BaseModel):
    """Extracted receipt data."""
    store_name: str | None = None
    date: str | None = Field(default=None, description="Date in YYYY-MM-DD format")
    items: list[ExtractedItem] = Field(
        default_factory=list,
        description="All items on the receipt"
    )
    total: float | None = Field(default=None, description="Total amount in dollars")
```

---

## The Bottom Line

Pydantic provides three things for LLM extraction:

1. **Schema definition**: Type hints + `Field()` descriptions define what you want
2. **JSON Schema generation**: `model_json_schema()` creates the schema for the API
3. **Validation**: Instantiation validates and coerces types

Design principles:

- Make fields optional when source might not contain them
- Use `Literal` for constrained categories
- Write clear descriptions — they guide extraction more than field names
- Avoid deep nesting — flatten when practical
- Remember: schema compliance ≠ semantic correctness (the model can still hallucinate values that fit the schema)

The next note covers implementation — wiring Pydantic schemas to OpenAI and Anthropic APIs.