# Output Format Specification
## The Problem
LLMs generate text. You need structured data (JSON, markdown, tables).

**Without format specification:**
- Model adds explanations: "Sure! Here's the JSON: ```json..."
- Inconsistent structure: sometimes array, sometimes object
- Invalid syntax: trailing commas, unescaped quotes
- Mixed formats: prose + JSON in same output

**This breaks parsers and requires manual cleanup.**

---
## Three Levels of Control
### 1. **Instructional (Weakest)**
Just ask nicely in the prompt:
```
Extract the name and email from this text.
Return as JSON.
```

**Problem:** Model might return:
```
Sure! Here's the extracted information:
{"name": "John", "email": "john@example.com"}
Hope this helps!
```

**Success rate:** ~70-80% for simple JSON

---
### 2. **Explicit Format Specification (Better)**
Be extremely specific about the format:
```
Extract the name and email from this text.
Return ONLY valid JSON with no additional text.
Format:
{
  "name": "string",
  "email": "string"
}

If information is missing, use null.
```

**Success rate:** ~90-95%

**Key improvements:**
- "ONLY valid JSON with no additional text" — reduces preamble
- Show exact schema — reduces structure variation
- Handle missing data explicitly — prevents hallucination

---
### 3. **API-Level Enforcement (Strongest)**
Use API features that force format:

**OpenAI — Structured Outputs (Recommended):**
```python
response = openai.chat.completions.create(
    model="gpt-4o-2024-08-06",  # or gpt-4o-mini
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "response_schema",
            "strict": True,  # Enforces schema adherence
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["name", "email"]
            }
        }
    },
    messages=[...]
)
# 100% schema compliance (per OpenAI evals)
```

**Anthropic — Method 1: Prefill (Force JSON Start)**
```python
response = anthropic.messages.create(
    model="claude-sonnet-4-5-20250514",
    messages=[
        {"role": "user", "content": "Extract name and email from: John Doe, john@example.com"},
        {"role": "assistant", "content": "{"}  # Prefill forces JSON start
    ]
)
# Claude MUST continue from "{" → guarantees valid JSON structure
```

**Anthropic — Method 2: Tool Schemas (Validated Structure)**
```python
tools = [{
    "name": "extract_info",
    "description": "Extract structured information",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"}
        },
        "required": ["name", "email"]
    }
}]

response = anthropic.messages.create(
    model="claude-sonnet-4-5-20250514",
    messages=[{"role": "user", "content": "Extract from: John, john@example.com"}],
    tools=tools
)
# Returns structured tool_use block with schema-validated data
```

**Success rate:** ~99%+ (API validates before returning)

**When to use which:**
- **OpenAI Structured Outputs (`strict: True`):** Best reliability, complex schemas, production systems
- **Anthropic Prefill:** Force specific output start, simple cases
- **Anthropic Tool Schema:** Complex structures, validation required, production systems.

---
## Common Output Formats
### JSON
**When to use:** Structured data, APIs, databases

**Specification pattern:**
```
Return as valid JSON with this exact structure:
{
  "field1": "type",
  "field2": ["array", "of", "strings"],
  "field3": 123
}

Rules:
- No additional text before or after JSON
- Use null for missing values
- Ensure all quotes are properly escaped
```

### Markdown
**When to use:** Human-readable documents, formatted text

**Specification pattern:**
```
Return as markdown with this structure:
# Title
## Section 1
- Bullet point
- Bullet point

## Section 2
Content here
```

### CSV/TSV
**When to use:** Tabular data, spreadsheets

**Specification pattern:**
```
Return as CSV with these exact columns:
name,email,phone

Rules:
- Include header row
- Wrap fields with commas in quotes
- One row per entry
```

---
## The "99.9% Reliability" Problem
**You ask for JSON. 
95% of time it works. 
5% of time:**
- Adds explanation text
- Returns markdown code block with JSON inside
- Invalid syntax

**How to get to 99.9%:**
1. **Explicit boundaries:**
   ```
   Return ONLY the JSON object.
   Do not include any text before or after.
   Do not wrap in markdown code blocks.
   Start your response with { and end with }
   ```

2. **Post-processing (defense in depth):**
   ```python
   # Strip markdown code blocks
   if response.startswith("```"):
       response = response.split("```")[1]
       if response.startswith("json"):
           response = response[4:]
   
   # Find first { and last }
   start = response.find("{")
   end = response.rfind("}") + 1
   json_str = response[start:end]
   
   data = json.loads(json_str)
   ```

3. **Validation + retry:**
   ```python
   try:
       data = json.loads(response)
   except json.JSONDecodeError:
       # Retry with stronger instructions
       pass
   ```

4. **Use API JSON mode when available** (OpenAI's `response_format`)

---
