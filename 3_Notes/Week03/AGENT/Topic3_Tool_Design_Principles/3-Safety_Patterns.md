# Note 3: Safety Patterns — Dangerous Tools, Confirmation, and Idempotency

## Why Tool Safety Matters

An agent with tools is powerful — and dangerous. Unlike a chatbot that can only generate text, an agent with tools can:

- Delete files
- Send emails
- Execute payments
- Modify databases
- Publish content
- Revoke access

A single bad tool call can have irreversible consequences. Safety patterns aren't optional; they're essential for production systems.

---

## Categorizing Tools by Risk

### Risk Tiers

|Tier|Risk Level|Examples|Handling|
|---|---|---|---|
|**Tier 1**|Read-only|`get_user`, `search_products`, `list_files`|No confirmation needed|
|**Tier 2**|Reversible writes|`create_draft_email`, `add_to_cart`, `save_note`|Optional confirmation|
|**Tier 3**|Impactful actions|`send_email`, `submit_order`, `publish_post`|Require confirmation|
|**Tier 4**|Destructive/Irreversible|`delete_account`, `empty_trash`, `revoke_access`|Require explicit confirmation + audit|

---

## Where Does Confirmation Logic Live?

This is a key design decision. There are three approaches:

### Option 1: Confirmation in the Tool Schema

Add a `confirm` parameter to dangerous tools:

```python
{
    "name": "delete_file",
    "description": "Permanently delete a file. REQUIRES confirm=true to execute.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to delete"},
            "confirm": {
                "type": "boolean",
                "description": "Must be true to actually delete. Set false to preview what would be deleted."
            }
        },
        "required": ["path", "confirm"]
    }
}
```

**Implementation:**

```python
def delete_file(path: str, confirm: bool) -> dict:
    if not confirm:
        return {
            "preview": True,
            "would_delete": path,
            "file_size": os.path.getsize(path),
            "message": "Call again with confirm=true to delete"
        }
    
    os.remove(path)
    return {"deleted": True, "path": path}
```

**Pros:**

- Self-documenting (the schema shows it's dangerous)
- Forces a two-step process

**Cons:**

- Relies on the LLM respecting the pattern
- Can be bypassed if the model just sets `confirm=true`

#### **⚠️ Why This Is Weak**
This approach relies on the LLM choosing to set `confirm=false` first. In practice, if the user says "delete that file," the model will often set `confirm=true` immediately to be helpful. The LLM controls the parameter, not the user — so this isn't real safety, it's hope. Use this only as a soft hint, not as your primary protection.

### Option 2: Confirmation in the Orchestration Layer

The agent loop handles confirmation, not the tool:

```python
DANGEROUS_TOOLS = {"delete_file", "send_email", "submit_payment", "revoke_access"}

def agent_loop(user_message: str):
    while True:
        response = call_llm(messages)
        
        if response.stop_reason == "tool_use":
            tool_call = response.tool_use
            
            # Check if dangerous
            if tool_call.name in DANGEROUS_TOOLS:
                # Ask user for confirmation
                user_confirmation = get_user_input(
                    f"The agent wants to {tool_call.name} with args {tool_call.input}. Allow? (yes/no)"
                )
                
                if user_confirmation.lower() != "yes":
                    # Tell the agent the action was denied
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "is_error": True,
                            "content": "Action denied by user. Ask for alternative approach."
                        }]
                    })
                    continue
            
            # Execute tool
            result = execute_tool(tool_call)
            messages.append(format_tool_result(tool_call.id, result))
        else:
            break
```

**Pros:**

- Centralized control
- User is always in the loop for dangerous actions
- Tool implementation stays simple

**Cons:**

- Requires UI/UX for confirmation
- Adds latency to the interaction

### Option 3: Separate Planning and Execution Tools

Make the LLM explicitly plan before acting:

```python
tools = [
    {
        "name": "plan_deletion",
        "description": "Plan file deletion. Returns what would be deleted. Does NOT delete anything.",
        ...
    },
    {
        "name": "execute_deletion",
        "description": "Execute a previously planned deletion. Requires a plan_id from plan_deletion.",
        ...
    }
]
```

**Pros:**

- Forces a two-step workflow
- Audit trail built in

**Cons:**

- More complex tool surface
- State management between calls

### Recommendation

**For most systems**: Use **Option 2 (Orchestration Layer)**.

The orchestration layer is the right place for policy enforcement because:

- Tools stay simple and single-purpose
- Policies can change without modifying tools
- Easier to audit and log
- Consistent behavior across all dangerous tools

---

## Implementing Human-in-the-Loop

For high-stakes actions, always get human approval:

```python
class HumanApprovalRequired(Exception):
    def __init__(self, action: str, details: dict):
        self.action = action
        self.details = details

def send_payment(recipient: str, amount: float, currency: str) -> dict:
    if amount > 1000:  # Threshold for human approval
        raise HumanApprovalRequired(
            action="send_payment",
            details={
                "recipient": recipient,
                "amount": amount,
                "currency": currency,
                "reason": f"Payment over $1000 requires approval"
            }
        )
    
    # Process payment
    return process_payment(recipient, amount, currency)

# In orchestration layer
try:
    result = execute_tool(tool_call)
except HumanApprovalRequired as e:
    approval = request_human_approval(e.action, e.details)
    if approval.granted:
        result = execute_tool_with_approval(tool_call, approval.token)
    else:
        result = {"error": "Payment rejected by approver", "reason": approval.reason}
```

---

## Idempotency: Safe to Retry

Idempotency means: calling the same operation multiple times produces the same result as calling it once.

### Why It Matters for Agents

Agents operate in loops. If something fails mid-way:

- The agent retries
- The tool gets called again
- Without idempotency, you might send two emails or charge twice

### Making Tools Idempotent

**Non-idempotent (Dangerous):**

```python
def create_order(items: list, user_id: str) -> dict:
    order = Order(items=items, user_id=user_id)
    db.save(order)  # Creates a new order every time
    return {"order_id": order.id}
```

**Idempotent (Safe):**

```python
def create_order(items: list, user_id: str, idempotency_key: str) -> dict:
    # Check if we've seen this key before
    existing = db.find_order_by_idempotency_key(idempotency_key)
    if existing:
        return {"order_id": existing.id, "status": "already_created"}
    
    order = Order(items=items, user_id=user_id, idempotency_key=idempotency_key)
    db.save(order)
    return {"order_id": order.id, "status": "created"}
```

**Tool Schema with Idempotency Key:**

```python
{
    "name": "create_order",
    "description": "Create a new order. Use idempotency_key to prevent duplicate orders on retry.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {"type": "array", ...},
            "user_id": {"type": "string"},
            "idempotency_key": {
                "type": "string",
                "description": "Unique key for this request. If the same key is used twice, the second call returns the existing order instead of creating a duplicate."
            }
        },
        "required": ["items", "user_id", "idempotency_key"]
    }
}
```

### Idempotency Patterns by Operation Type

|Operation|Idempotency Strategy|
|---|---|
|**Create**|Use idempotency key, return existing if duplicate|
|**Update**|Use version/ETag, fail if resource changed|
|**Delete**|Return success even if already deleted|
|**Send message**|Use message_id deduplication|
|**Process payment**|Use transaction_id, check before charging|

---

## Rate Limiting and Throttling

Prevent runaway agents from hammering APIs:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class RateLimiter:
    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.call_times = []
    
    def check(self):
        now = time.time()
        self.call_times = [t for t in self.call_times if now - t < 60]
        if len(self.call_times) >= self.calls_per_minute:
            raise RateLimitExceeded(f"Limit: {self.calls_per_minute}/min")
        self.call_times.append(now)

# Tool with rate limiting
email_limiter = RateLimiter(calls_per_minute=10)

def send_email(to: str, subject: str, body: str) -> dict:
    email_limiter.check()  # Raises if over limit
    return email_service.send(to, subject, body)
```

Tell the agent about rate limits in the tool description:

```
"description": "Send an email. Rate limited to 10 emails per minute. If rate limited, wait and retry."
```

---

## Audit Logging for Dangerous Operations

Every dangerous tool call should be logged:

```python
def audit_log(tool_name: str, inputs: dict, result: dict, user_id: str):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "tool": tool_name,
        "inputs": sanitize_sensitive_data(inputs),
        "result_summary": result.get("status", "unknown"),
        "user_id": user_id,
        "session_id": get_current_session_id()
    }
    audit_db.insert(log_entry)

# Wrapper for dangerous tools
def execute_dangerous_tool(tool_call, user_id: str) -> dict:
    try:
        result = execute_tool(tool_call)
        audit_log(tool_call.name, tool_call.input, result, user_id)
        return result
    except Exception as e:
        audit_log(tool_call.name, tool_call.input, {"error": str(e)}, user_id)
        raise
```

---

## Guardrails in Tool Descriptions

Use the description to set boundaries:

```python
{
    "name": "delete_files",
    "description": """Delete files matching a pattern.

SAFETY RULES:
- NEVER delete system files (/etc/*, /usr/*, /bin/*)
- NEVER delete more than 100 files in one call
- ALWAYS confirm with user before deleting production data
- Use dry_run=true first to preview what would be deleted

If user asks to delete something risky, explain the risk and ask for confirmation.""",
    ...
}
```

The LLM reads this description and (usually) follows the rules. Not a guarantee, but a strong signal.

---

## Separation of Privileges

Different tools for different trust levels:

```python
# User-level tools (anyone can use)
user_tools = [
    {"name": "search_products", ...},
    {"name": "view_order", ...},
    {"name": "update_profile", ...},
]

# Admin-level tools (requires admin role)
admin_tools = [
    {"name": "delete_user", ...},
    {"name": "modify_permissions", ...},
    {"name": "access_all_orders", ...},
]

def get_tools_for_user(user: User) -> list:
    if user.role == "admin":
        return user_tools + admin_tools
    return user_tools
```

---

## Summary: Safety Checklist

### Before Deploying a Tool

- [ ] **Classified risk tier**: Read-only? Reversible? Destructive?
- [ ] **Confirmation flow**: Human-in-the-loop for Tier 3+?
- [ ] **Idempotent**: Safe to call multiple times?
- [ ] **Rate limited**: Can't run away?
- [ ] **Audit logged**: Who did what, when?
- [ ] **Scoped permissions**: Least privilege?
- [ ] **Description includes safety rules**: LLM knows the boundaries?
- [ ] **Error handling**: Fails gracefully, doesn't leak secrets?

### Orchestration Layer Responsibilities

|Concern|Where It Lives|
|---|---|
|Confirmation prompts|Orchestration|
|Permission checks|Orchestration|
|Rate limiting|Tool or Orchestration|
|Audit logging|Orchestration|
|Idempotency|Tool implementation|
|Input validation|Tool implementation|

---

## Key Takeaway

> **Assume the LLM will eventually call the wrong tool with the wrong arguments.**
> 
> Design your system so that when this happens, the damage is limited, reversible, or caught before execution. Safety is a system property, not a prompt engineering problem.