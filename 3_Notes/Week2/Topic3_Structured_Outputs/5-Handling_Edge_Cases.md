# Note 5: Handling Edge Cases — Missing Fields, Ambiguity, and Validation Failures

Structured outputs guarantee schema compliance. They don't guarantee correct extraction. This note covers the edge cases where schema-compliant output is still wrong, ambiguous, or incomplete.

---

## The "Field Not in Source" Problem

Consider this schema:

```python
class ContactInfo(BaseModel):
    name: str
    email: str      # Required
    phone: str      # Required
```

And this source text:

```
John Smith, Sales Manager
```

The text contains a name but no email or phone. What happens?

**With a required field**, the model has two choices:

1. Refuse to complete (rare with structured outputs)
2. Hallucinate plausible values

Option 2 is what usually happens:

```json
{
    "name": "John Smith",
    "email": "john.smith@company.com",  // Invented
    "phone": "555-0123"                  // Invented
}
```

This is schema-compliant but factually wrong. The email looks real but doesn't exist in the source.

### The Solution: Make Fields Optional

```python
class ContactInfo(BaseModel):
    name: str
    email: str | None = None    # None means "not found"
    phone: str | None = None    # None means "not found"
```

Now the model can legitimately output:

```json
{
    "name": "John Smith",
    "email": null,
    "phone": null
}
```

This is honest: "I found a name but no contact details."

---

## Designing for Missing Data

### Schema Design

Make any field optional if the source might not contain it:

```python
class JobPosting(BaseModel):
    # Usually present
    title: str
    company: str
    
    # Often missing
    salary_min: int | None = None
    salary_max: int | None = None
    location: str | None = None
    experience_years: int | None = None
    
    # Inferred, not extracted
    remote: bool | None = None  # None = not mentioned, not "False"
```

### Prompt Design

Explicitly tell the model how to handle missing information:

```python
system_prompt = """
Extract information from the text.

Rules:
- Only include information explicitly stated in the text
- Use null for fields where information is not found
- Do not infer, guess, or make up values
- If unsure whether information is present, use null
"""
```

### Validating "Not Found" vs "Forgot to Extract"

A `None` value should mean "not in source," not "model forgot." How do you know which?

**Add a confidence or completeness field:**

```python
class Extraction(BaseModel):
    title: str
    salary: int | None = None
    extraction_notes: str | None = Field(
        default=None,
        description="Brief notes on any fields that couldn't be extracted and why"
    )
```

Output might be:

```json
{
    "title": "Software Engineer",
    "salary": null,
    "extraction_notes": "No salary information found in the posting"
}
```

This provides an audit trail for null values.

---

## Handling Ambiguous Values

### The Range Problem

Source text:

```
"3-5 years of experience required"
```

Schema:

```python
class JobPosting(BaseModel):
    experience_years: int  # What should this be? 3? 4? 5?
```

The model has to pick one, and different runs might pick differently.

### Solution 1: Pick a Convention

Document and enforce a rule:

```python
class JobPosting(BaseModel):
    experience_years: int | None = Field(
        default=None,
        description="Minimum years of experience required. If a range is given (e.g., '3-5 years'), use the minimum value."
    )
```

Now "3-5 years" consistently becomes `3`.

### Solution 2: Model the Range

Redesign the schema to capture the actual data:

```python
class JobPosting(BaseModel):
    experience_min: int | None = Field(
        default=None,
        description="Minimum years of experience, or exact number if not a range"
    )
    experience_max: int | None = Field(
        default=None,
        description="Maximum years of experience, or same as min if not a range"
    )
```

Now "3-5 years" becomes `experience_min=3, experience_max=5`.

### Solution 3: Preserve Original

When precision matters more than structure:

```python
class JobPosting(BaseModel):
    experience_requirement: str | None = Field(
        default=None,
        description="Experience requirement as stated in the original text"
    )
```

Now "3-5 years" is preserved as `"3-5 years"`. You parse it downstream if needed.

**Trade-off**: Solution 1 loses information. Solution 2 is more complex. Solution 3 defers parsing.

---

## Boolean Inference

Booleans are tricky because absence of information doesn't mean `False`.

### The Remote Work Example

Source texts and expected outputs:

|Text|`remote` value|
|---|---|
|"Remote position"|`True`|
|"Work from home available"|`True`|
|"Hybrid - 2 days in office"|`True`|
|"On-site only"|`False`|
|"Must be in NYC office"|`False`|
|"Senior Engineer at TechCorp"|`None` (unknown)|

### Schema Design for Booleans

Don't make inference booleans required:

```python
# Bad - forces True/False even when unknown
class JobPosting(BaseModel):
    remote: bool

# Good - allows "I don't know"
class JobPosting(BaseModel):
    remote: bool | None = Field(
        default=None,
        description="True if remote/WFH/distributed explicitly mentioned. False if on-site/in-office explicitly required. Null if not mentioned."
    )
```

### Field Descriptions Guide Inference

The description is critical:

```python
# Vague - model might guess
remote: bool | None = Field(description="Is the job remote?")

# Clear - model knows what to look for
remote: bool | None = Field(
    description="True if the posting mentions remote work, work from home, WFH, distributed team, or location flexibility. False if it explicitly requires on-site presence. Null if neither is mentioned."
)
```

---

## List Extraction Variations

Lists appear in many formats. Structured outputs handle them well.

### Various Input Formats

```python
class Skills(BaseModel):
    skills: list[str] = Field(description="Technical skills mentioned")
```

All of these should extract correctly:

```
# Comma-separated
"Required: Python, Java, SQL, Docker"
→ ["Python", "Java", "SQL", "Docker"]

# Bullet points
"Skills:
• Python
• Java
• SQL"
→ ["Python", "Java", "SQL"]

# Numbered list
"1. Python
2. Java
3. SQL"
→ ["Python", "Java", "SQL"]

# Prose
"Must be proficient in Python and Java, with SQL knowledge preferred"
→ ["Python", "Java", "SQL"]

# Mixed
"Python required. Also need Java/SQL experience."
→ ["Python", "Java", "SQL"]
```

### Handling Empty Lists

When no items are found:

```python
class JobPosting(BaseModel):
    # Empty list if no skills mentioned
    required_skills: list[str] = Field(
        default_factory=list,
        description="Required technical skills. Empty list if none mentioned."
    )
```

---

## Validation Failures

Even with structured outputs, validation can fail. Here's how to handle it.

### When Validation Fails

```python
from pydantic import BaseModel, ValidationError
from openai import OpenAI

def extract_with_fallback(text: str, schema: type[BaseModel]) -> BaseModel | None:
    client = OpenAI()
    
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
        
    except ValidationError as e:
        # Log the failure for debugging
        print(f"Validation failed: {e}")
        print(f"Source text: {text[:100]}...")
        
        # Options:
        # 1. Retry (expensive, may not help)
        # 2. Return None (safest)
        # 3. Return partial data (risky)
        
        return None
```

### Retry Strategy (Use Sparingly)

Retrying with feedback can help, but it's expensive:

```python
def extract_with_retry(
    text: str, 
    schema: type[BaseModel], 
    max_retries: int = 1
) -> BaseModel | None:
    client = OpenAI()
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Build messages
            messages = [
                {"role": "system", "content": "Extract information from text."},
                {"role": "user", "content": text}
            ]
            
            # If retrying, add error feedback
            if last_error and attempt > 0:
                messages.append({
                    "role": "user", 
                    "content": f"Previous extraction failed validation: {last_error}. Please try again."
                })
            
            response = client.responses.parse(
                model="gpt-4o-mini",
                input=messages,
                text_format=schema
            )
            return response.output_parsed
            
        except ValidationError as e:
            last_error = str(e)
            continue
    
    return None
```

**When to retry:**

- Intermittent issues (rate limits, timeouts)
- Simple validation errors that feedback might fix

**When not to retry:**

- Source text genuinely lacks required information
- Schema fundamentally mismatches source content
- Same error repeats (model can't fix it)

### Always Log Failures

```python
import logging

logger = logging.getLogger(__name__)

def extract(text: str, schema: type[BaseModel]) -> BaseModel | None:
    try:
        # ... extraction logic ...
        return result
    except ValidationError as e:
        logger.error(
            "Extraction validation failed",
            extra={
                "schema": schema.__name__,
                "error": str(e),
                "source_preview": text[:200],
            }
        )
        return None
```

Logged failures help you:

- Identify schema design issues
- Find edge cases in source data
- Improve prompts based on actual failures

---

## Irrelevant Source Text

What happens when you apply a job posting schema to a recipe?

### The Hallucination Risk

Schema:

```python
class JobPosting(BaseModel):
    title: str
    company: str
    salary: int | None = None
```

Source: "Chocolate Chip Cookie Recipe - Preheat oven to 350°F..."

Possible (bad) output:

```json
{
    "title": "Cookie Recipe Developer",
    "company": "Home Kitchen",
    "salary": null
}
```

The model might try to find job-like patterns anywhere.

### Detection: Confidence Field

Add a confidence indicator:

```python
class JobPosting(BaseModel):
    title: str
    company: str
    salary: int | None = None
    
    extraction_confidence: float = Field(
        description="Confidence that source text is actually a job posting. 0.0 to 1.0."
    )
```

Check confidence before using:

```python
result = extract(text, JobPosting)
if result.extraction_confidence < 0.5:
    print("Source may not be a job posting")
```

### Pre-Classification

For batch processing, classify before extracting:

```python
class DocumentClassification(BaseModel):
    document_type: Literal["job_posting", "recipe", "article", "other"]
    confidence: float

def extract_job_if_relevant(text: str) -> JobPosting | None:
    # Step 1: Classify (cheaper)
    classification = extract(text, DocumentClassification)
    
    if classification.document_type != "job_posting":
        return None
    
    if classification.confidence < 0.7:
        return None
    
    # Step 2: Extract (more expensive, but we know it's relevant)
    return extract(text, JobPosting)
```

---

## Cost Considerations for Batch Extraction

When extracting from thousands of documents, costs add up.

### Pre-Filter Irrelevant Documents

Use cheaper methods before LLM extraction:

```python
import re

def might_be_job_posting(text: str) -> bool:
    """Quick heuristic check before expensive extraction."""
    job_keywords = ["position", "hiring", "salary", "experience", "apply", "job"]
    text_lower = text.lower()
    
    matches = sum(1 for kw in job_keywords if kw in text_lower)
    return matches >= 2  # At least 2 keywords

# Only extract from likely job postings
for doc in documents:
    if might_be_job_posting(doc.text):
        result = extract(doc.text, JobPosting)
```

### Use Cheaper Models for Classification

```python
def process_documents(documents: list[str]) -> list[JobPosting]:
    results = []
    
    for doc in documents:
        # Cheap classification with smaller model
        classification = extract(
            doc, 
            DocumentClassification, 
            model="gpt-4o-mini"  # Cheaper
        )
        
        if classification.document_type != "job_posting":
            continue
        
        # Expensive extraction with better model
        job = extract(
            doc, 
            JobPosting, 
            model="gpt-4o"  # More capable
        )
        
        if job:
            results.append(job)
    
    return results
```

### Schema Caching

First request with a new schema incurs extra latency (OpenAI compiles and caches the schema). Subsequent requests are faster.

**Implication**: Batch documents by schema type to maximize cache hits.

```python
# Good: Process all job postings together, then all recipes
for doc in job_posting_docs:
    extract(doc, JobPosting)  # Schema cached after first call

for doc in recipe_docs:
    extract(doc, Recipe)  # Different schema, new cache

# Less efficient: Alternating schemas
for doc in mixed_docs:
    if doc.type == "job":
        extract(doc, JobPosting)  # Cache miss if previous was Recipe
    else:
        extract(doc, Recipe)  # Cache miss if previous was JobPosting
```

---

## Testing Edge Cases

### Minimal Viable Text

Test with the bare minimum information:

```python
# Minimum job posting
texts = [
    "Engineer at Corp",  # Title and company only
    "Hiring developers",  # Just a hint
    "Software role $100k",  # Title and salary, no company
]

for text in texts:
    result = extract(text, JobPosting)
    # Verify it handles sparse input gracefully
```

### Maximum Ambiguity

Test with conflicting or unclear signals:

```python
texts = [
    # Conflicting remote signals
    "Remote position, must be in SF office twice monthly",
    
    # Ambiguous salary
    "Compensation: competitive salary plus equity",
    
    # Multiple roles in one posting
    "Hiring Engineers and Product Managers, $150-200k",
]
```

### Wrong Domain

Intentionally apply wrong schemas:

```python
# Job schema on recipe
result = extract("Chocolate chip cookies: mix flour and sugar...", JobPosting)
assert result.extraction_confidence < 0.5

# Recipe schema on job posting
result = extract("Senior Engineer at TechCorp, $150k...", Recipe)
# Should fail gracefully
```

### Partial Information

Test various combinations of present/missing fields:

```python
test_cases = [
    # All fields present
    ("Engineer at TechCorp, $150k, remote, needs Python", 
     {"title": "Engineer", "company": "TechCorp", "salary": 150000, "remote": True}),
    
    # Title only
    ("Software Engineer role available",
     {"title": "Software Engineer", "company": None, "salary": None}),
    
    # Salary only (weird but valid)
    ("$200k position",
     {"salary": 200000, "title": None, "company": None}),
]

for text, expected in test_cases:
    result = extract(text, JobPosting)
    for key, value in expected.items():
        assert getattr(result, key) == value
```

---

## Summary: Edge Case Checklist

|Edge Case|Solution|
|---|---|
|Field not in source|Make field optional (`T|
|Model might hallucinate|Prompt: "use null if not found"|
|Ambiguous values (ranges)|Either pick convention or model the range|
|Boolean unknown vs False|Use `bool|
|List formats vary|Schema handles it; test various formats|
|Validation failure|Log, optionally retry, return None|
|Wrong domain text|Add confidence field or pre-classify|
|Batch cost|Pre-filter, use cheaper models for classification|

The key insight: **structured outputs guarantee schema compliance, not semantic correctness**. Your schema design, prompt engineering, and validation logic work together to ensure the extracted data is actually useful.