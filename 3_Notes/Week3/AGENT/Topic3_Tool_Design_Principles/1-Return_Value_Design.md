# Note 1: Return Value Design — Structured, Predictable, Actionable

## The Core Problem

When a tool executes and returns data, the LLM needs to:

1. **Parse** the result (understand what came back)
2. **Interpret** it (does this answer the question?)
3. **Act** on it (formulate a response, call another tool, or retry)

If your return value is ambiguous, inconsistent, or overwhelming, the agent makes poor decisions. The tool might work perfectly, but if the LLM can't use the result, it's useless.

---

## Return Value Design Principles

### 1. Structured Over Strings

**Bad: Raw strings**

```python
def search_database(query: str) -> str:
    results = db.search(query)
    return f"Found {len(results)} results: {results}"
```

The LLM has to parse this string, guess where the count ends and results begin, and hope the format doesn't change.

**Good: Structured data**

```python
def search_database(query: str) -> dict:
    results = db.search(query)
    return {
        "success": True,
        "count": len(results),
        "results": [
            {"id": r.id, "title": r.title, "relevance": r.score}
            for r in results
        ],
        "has_more": len(results) == 100  # pagination hint
    }
```

The LLM knows exactly where to find each piece of information.

### 2. Consistent Structure Every Time

Every call to the same tool should return the same shape, regardless of outcome.

**Bad: Shape changes based on result**

```python
def get_user(user_id: str):
    user = db.find_user(user_id)
    if user:
        return {"name": user.name, "email": user.email}
    else:
        return "User not found"  # Different type!
```

**Good: Same shape, different values**

```python
def get_user(user_id: str) -> dict:
    user = db.find_user(user_id)
    if user:
        return {
            "found": True,
            "user": {"name": user.name, "email": user.email}
        }
    else:
        return {
            "found": False,
            "user": None
        }
```

### 3. Actionable Information

Return data the LLM can act on, not just acknowledge.

**Bad: Vague confirmation**

```python
def create_ticket(title: str, body: str) -> str:
    ticket = ticketing_system.create(title, body)
    return "Ticket created successfully"
```

What's the ticket ID? URL? Status? The LLM can't tell the user where to find their ticket.

**Good: Actionable details**

```python
def create_ticket(title: str, body: str) -> dict:
    ticket = ticketing_system.create(title, body)
    return {
        "success": True,
        "ticket_id": ticket.id,
        "ticket_url": f"https://support.example.com/tickets/{ticket.id}",
        "status": "open",
        "created_at": ticket.created_at.isoformat()
    }
```

Now the LLM can say: "I've created ticket #12345. You can view it here: [link]"

---

## The Success/Error Pattern

Every tool return should clearly indicate success or failure. There are two common patterns:

### Pattern A: Boolean Flag

```python
# Success case
{
    "success": True,
    "data": { ... }
}

# Error case
{
    "success": False,
    "error": {
        "type": "NotFoundError",
        "message": "User with ID 'abc123' does not exist",
        "suggestion": "Check the user ID and try again"
    }
}
```

### Pattern B: Result/Error Union (Anthropic style)

When returning `tool_result` to Claude, you can use the `is_error` flag:

```python
# Success - return normally
{
    "type": "tool_result",
    "tool_use_id": "toolu_01abc",
    "content": json.dumps({"user": {"name": "Alice", "email": "alice@example.com"}})
}

# Error - set is_error flag
{
    "type": "tool_result",
    "tool_use_id": "toolu_01abc",
    "is_error": True,
    "content": "User not found. The ID 'xyz789' does not exist in the system."
}
```

The `is_error: True` flag tells Claude explicitly that the tool failed, prompting different reasoning (retry, ask user, try alternate approach).

---

## What NOT to Return

### 1. Raw HTML or Unprocessed Web Content

**Bad:**

```python
def fetch_webpage(url: str) -> str:
    response = requests.get(url)
    return response.text  # 50KB of HTML
```

The LLM wastes tokens parsing HTML, might hallucinate interpretations, and you burn context.

**Good:**

```python
def fetch_webpage(url: str) -> dict:
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return {
        "title": soup.title.string if soup.title else None,
        "main_content": extract_main_text(soup)[:5000],  # Limit length
        "links": [{"text": a.text, "href": a["href"]} for a in soup.find_all("a")[:20]]
    }
```

### 2. Massive Data Dumps

**Bad:**

```python
def get_all_orders() -> list:
    return db.query("SELECT * FROM orders")  # 10,000 rows
```

**Good:**

```python
def get_orders(limit: int = 10, offset: int = 0, status: str = None) -> dict:
    query = build_query(limit, offset, status)
    orders = db.query(query)
    return {
        "orders": orders,
        "count": len(orders),
        "total_available": db.count_orders(status),
        "has_more": offset + len(orders) < db.count_orders(status)
    }
```

### 3. Internal System Details

**Bad:**

```python
def delete_file(path: str) -> dict:
    try:
        os.remove(path)
        return {"deleted": True, "inode": os.stat(path).st_ino}  # Why?
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}  # Dangerous!
```

**Good:**

```python
def delete_file(path: str) -> dict:
    try:
        os.remove(path)
        return {"success": True, "path": path}
    except FileNotFoundError:
        return {"success": False, "error": "File does not exist", "path": path}
    except PermissionError:
        return {"success": False, "error": "Permission denied", "path": path}
```

### 4. Ambiguous Status Messages

**Bad:**

```python
def send_email(to: str, subject: str, body: str) -> str:
    result = email_service.send(to, subject, body)
    return result.status  # "queued" — did it work or not?
```

**Good:**

```python
def send_email(to: str, subject: str, body: str) -> dict:
    result = email_service.send(to, subject, body)
    return {
        "success": result.status in ["sent", "queued"],
        "status": result.status,
        "message_id": result.message_id,
        "note": "Email queued for delivery" if result.status == "queued" else None
    }
```

---

## Designing for LLM Consumption

### Include Metadata for Decision-Making

```python
def search_products(query: str, max_results: int = 10) -> dict:
    results = catalog.search(query, limit=max_results)
    return {
        "results": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "in_stock": p.inventory > 0,
                "relevance_score": p.score
            }
            for p in results
        ],
        "total_matches": catalog.count(query),
        "returned": len(results),
        "query_time_ms": results.timing,
        "suggestion": "Try broader terms" if len(results) == 0 else None
    }
```

The LLM can now:

- Tell the user how many total results exist
- Decide if it should paginate
- Suggest search refinements if no results

### Use Enums for Categorical Outcomes

**Bad:**

```python
{"status": "it worked but there were some warnings"}
```

**Good:**

```python
{
    "status": "partial_success",  # One of: success, partial_success, failure
    "warnings": ["Image was resized to fit constraints"],
    "errors": []
}
```

### Provide Next Steps When Applicable

```python
def upload_document(file_content: bytes, filename: str) -> dict:
    doc = storage.upload(file_content, filename)
    return {
        "success": True,
        "document_id": doc.id,
        "status": "processing",
        "next_steps": [
            "Document is being processed. Check status with get_document_status()",
            "Processing typically takes 30-60 seconds"
        ],
        "available_actions": ["get_document_status", "delete_document", "share_document"]
    }
```

---

## OpenAI vs Anthropic: Returning Tool Results

### OpenAI Format

```python
# Tool result message
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": json.dumps({
        "temperature": 72,
        "unit": "fahrenheit",
        "conditions": "sunny"
    })
}
```

### Anthropic Format

```python
# Tool result in user message
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01abc",
            "content": json.dumps({
                "temperature": 72,
                "unit": "fahrenheit",
                "conditions": "sunny"
            })
            # Optional: "is_error": True for failures
        }
    ]
}
```

Both accept JSON strings as content. The key difference:

- **OpenAI**: Separate `tool` role message
- **Anthropic**: `tool_result` block inside a `user` message, with optional `is_error` flag

---

## Summary Checklist

When designing tool return values:

- [ ] **Structured**: Return JSON objects, not formatted strings
- [ ] **Consistent**: Same shape every time, regardless of success/failure
- [ ] **Actionable**: Include IDs, URLs, next steps — things the LLM can use
- [ ] **Bounded**: Limit data size, paginate large results
- [ ] **Clear status**: Explicit success/failure indicator
- [ ] **Typed errors**: Error type + message + suggestion, not stack traces
- [ ] **Metadata**: Include counts, timing, pagination hints where relevant
- [ ] **Clean**: No internal system details, no raw HTML, no sensitive data

---

## Key Takeaway

> **Design return values for the LLM, not for logging.**
> 
> The LLM is the consumer. Ask: "Can the model parse this? Can it decide what to do next? Can it explain the result to the user?"