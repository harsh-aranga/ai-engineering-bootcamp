# Note 5: Production Gotchas — Double Execution, Timeouts, and Idempotency

## The Core Production Problem

LangGraph's HITL primitives (`interrupt()` and `Command(resume=...)`) work elegantly in demos. But production reveals behaviors that aren't obvious from the docs:

1. **Double execution:** Nodes re-run from the beginning on resume
2. **Timeout handling:** No built-in expiry for abandoned workflows
3. **Idempotency:** Side effects can fire twice without safeguards
4. **State corruption:** Multiple interrupts in one node behave unexpectedly
5. **Parallel interrupt edge cases:** Known bugs with multi-interrupt resume

This note covers each gotcha and the production patterns to mitigate them.

---

## Gotcha 1: Node Re-Execution on Resume

### The Behavior

When a node calls `interrupt()` and later resumes via `Command(resume=...)`, **the entire node re-executes from the beginning**. The runtime does not resume from the exact line where `interrupt()` was called.

From the docs:

> "When execution resumes, the runtime restarts the entire node from the beginning—it does not resume from the exact line where interrupt was called."

### Why This Matters

Any code that runs _before_ the `interrupt()` call will run **twice**:

```python
def approval_node(state):
    # ⚠️ This runs TWICE: once on initial execution, once on resume
    result = call_expensive_llm(state["query"])
    log_to_audit_trail(result)
    send_slack_notification("Awaiting approval")
    
    # Interrupt happens here
    decision = interrupt({"action": "approve_result", "result": result})
    
    # This runs once, after resume
    return {"approved": decision["approved"], "result": result}
```

On resume:

- `call_expensive_llm()` runs again → double cost
- `log_to_audit_trail()` runs again → duplicate log entries
- `send_slack_notification()` runs again → user gets two Slack messages

### The Fix: Put Side Effects AFTER interrupt()

```python
def approval_node(state):
    # On resume, interrupt() immediately returns the stored resume value
    # without re-executing the code above it... but wait, there IS no code above it
    decision = interrupt({
        "action": "approve_result",
        "query": state["query"]  # Pass what's needed for UI
    })
    
    # Everything below runs ONCE, after human responds
    if decision["approved"]:
        result = call_expensive_llm(state["query"])
        log_to_audit_trail(result)
        send_slack_notification("Approved and processed")
        return {"approved": True, "result": result}
    else:
        return {"approved": False, "result": None}
```

### Alternative Fix: Split Into Multiple Nodes

If you need the LLM result for the approval UI, use separate nodes:

```python
def generate_node(state):
    # Runs once, result checkpointed
    result = call_expensive_llm(state["query"])
    return {"pending_result": result}

def approval_node(state):
    # Show the already-generated result
    decision = interrupt({
        "action": "approve_result",
        "result": state["pending_result"]
    })
    return {"approved": decision["approved"]}

def execute_node(state):
    # Runs once, after approval
    if state["approved"]:
        log_to_audit_trail(state["pending_result"])
        send_slack_notification("Approved")
    return {}

# Graph: generate → approval → execute
```

The key insight: **state changes from completed nodes are checkpointed**. When `approval_node` re-runs on resume, `state["pending_result"]` is already there from the checkpointed `generate_node` output.

### Detecting Re-Execution With Flags

If restructuring is too invasive, use state flags:

```python
def approval_node(state):
    # Check if we already did the expensive work
    if not state.get("llm_result_generated"):
        result = call_expensive_llm(state["query"])
        # Store result in state so it survives re-execution
        # But wait—this doesn't work! State updates from the same node
        # aren't checkpointed until the node completes.
    
    # ❌ This pattern doesn't work as expected in a single node
```

**This pattern fails** because state updates within a node aren't checkpointed until the node completes. The flag won't persist across the interrupt.

The only reliable patterns are:

1. Put side effects after `interrupt()`
2. Split into multiple nodes

---

## Gotcha 2: Multiple Interrupts in One Node

### The Index-Based Matching Problem

When a node has multiple `interrupt()` calls, LangGraph matches resume values **by index**, not by ID:

```python
def multi_step_approval(state):
    name = interrupt("What's your name?")      # Index 0
    age = interrupt("What's your age?")        # Index 1
    city = interrupt("What's your city?")      # Index 2
    return {"name": name, "age": age, "city": city}
```

If the user provides resumes in order, this works. But if interrupt order changes between executions (due to conditionals), you get mismatched values.

### The Anti-Pattern: Conditional Interrupts

```python
def conditional_approval(state):
    # ❌ BROKEN: interrupt order depends on runtime condition
    if state["needs_name"]:
        name = interrupt("What's your name?")   # Sometimes index 0
    
    age = interrupt("What's your age?")         # Index 0 or 1 depending on above
    
    return {"name": name, "age": age}
```

If `needs_name` is True on first run but False on resume (due to some state change), the resume value meant for "name" goes to "age".

### The Fix: Consistent Interrupt Order

```python
def consistent_approval(state):
    # ✅ Always call interrupts in the same order
    name = interrupt("What's your name?")
    age = interrupt("What's your age?")
    city = interrupt("What's your city?")
    return {"name": name, "age": age, "city": city}
```

Or, if you truly need conditional interrupts, use separate nodes:

```python
def name_node(state):
    if state["needs_name"]:
        name = interrupt("What's your name?")
        return {"name": name}
    return {}

def age_node(state):
    age = interrupt("What's your age?")
    return {"age": age}
```

### Known Bugs (As of Late 2025)

- **Issue #6208:** Node with two interrupts will rerun after only one resume
- **Issue #6533:** Interrupt resume values misrouted between tools in ToolNode
- **Issue #6626:** Parallel interrupts generating identical IDs

The maintainer-recommended workaround: **chain multiple nodes rather than mixing multiple interrupts in one node**.

---

## Gotcha 3: No Built-In Timeout / Expiry

### The Problem

When a workflow pauses for human input, the checkpoint sits in the database indefinitely. LangGraph has no built-in mechanism for:

- Timing out abandoned workflows
- Escalating stale approvals
- Cleaning up old checkpoints

A human might close the browser tab, go on vacation, or simply forget. The workflow waits forever.

### Solution: Application-Level Timeout Tracking

Track interrupt timestamps and run a cleanup job:

```python
from datetime import datetime, timedelta
import json

# When interrupt occurs, store metadata
def approval_node(state):
    interrupt_time = datetime.utcnow().isoformat()
    
    decision = interrupt({
        "action": "approve_email",
        "params": state["email_params"],
        "created_at": interrupt_time,
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    })
    
    return {"approved": decision["approved"]}

# Separate cleanup job (cron, Celery, etc.)
async def cleanup_stale_workflows():
    """Run periodically to handle abandoned workflows."""
    
    # Query your database for threads with pending interrupts
    stale_threads = await db.query("""
        SELECT thread_id, interrupt_payload 
        FROM workflow_interrupts 
        WHERE status = 'pending' 
        AND created_at < NOW() - INTERVAL '24 hours'
    """)
    
    for thread in stale_threads:
        # Option 1: Auto-reject
        await graph.invoke(
            Command(resume={"approved": False, "reason": "timeout"}),
            {"configurable": {"thread_id": thread["thread_id"]}}
        )
        
        # Option 2: Escalate to supervisor
        await notify_supervisor(thread)
        
        # Option 3: Just mark as abandoned
        await db.execute(
            "UPDATE workflow_interrupts SET status = 'abandoned' WHERE thread_id = %s",
            thread["thread_id"]
        )
```

### Solution: TTL in Checkpoint Store

If using Postgres, add a TTL column and cleanup job:

```sql
-- Add expiry tracking
ALTER TABLE checkpoints ADD COLUMN expires_at TIMESTAMP;
ALTER TABLE checkpoints ADD COLUMN status VARCHAR(20) DEFAULT 'active';

-- Cleanup job
DELETE FROM checkpoints 
WHERE expires_at < NOW() 
AND status = 'pending_human';
```

### Solution: Include Deadline in Interrupt Payload

Let the UI show a countdown:

```python
def approval_node(state):
    decision = interrupt({
        "action": "approve_transfer",
        "amount": state["amount"],
        "deadline": (datetime.utcnow() + timedelta(hours=4)).isoformat(),
        "warning": "This request will auto-reject in 4 hours"
    })
    return {"approved": decision["approved"]}
```

---

## Gotcha 4: Idempotency for Side Effects

### The Problem

Even with proper node structure, side effects can fire twice due to:

- Network retries
- Process crashes after tool execution but before checkpoint write
- Multi-pod deployments with race conditions

### Solution: Idempotency Keys

Generate a unique key before the operation, use it to deduplicate:

```python
import uuid

class State(TypedDict):
    messages: list
    idempotency_key: str  # Generated before side effect

def generate_key_node(state):
    """Generate idempotency key before the risky operation."""
    return {"idempotency_key": str(uuid.uuid4())}

def execute_tool_node(state):
    """Execute with idempotency protection."""
    key = state["idempotency_key"]
    
    # Check if this key was already used
    if already_executed(key):
        return {"result": get_cached_result(key)}
    
    # Execute the actual operation
    result = risky_external_api_call(
        data=state["data"],
        idempotency_key=key  # Pass to API if it supports idempotency
    )
    
    # Cache the result
    cache_result(key, result)
    
    return {"result": result}
```

### Solution: Server-Side Idempotency

Many APIs support idempotency keys natively:

```python
import stripe

def charge_customer_node(state):
    # Stripe uses idempotency_key to prevent duplicate charges
    charge = stripe.Charge.create(
        amount=state["amount"],
        currency="usd",
        customer=state["customer_id"],
        idempotency_key=state["charge_idempotency_key"]
    )
    return {"charge_id": charge.id}
```

### Solution: Check-Before-Execute Pattern

For APIs without native idempotency:

```python
def send_email_node(state):
    email_id = state["email_id"]
    
    # Check if email was already sent
    if email_tracking_db.exists(email_id):
        return {"status": "already_sent"}
    
    # Mark as "sending" before actually sending
    email_tracking_db.insert(email_id, status="sending")
    
    try:
        send_email(state["email_params"])
        email_tracking_db.update(email_id, status="sent")
        return {"status": "sent"}
    except Exception as e:
        email_tracking_db.update(email_id, status="failed", error=str(e))
        raise
```

---

## Gotcha 5: Distributed Deployment Considerations

### Multi-Pod Race Conditions

With multiple server instances, two pods could try to resume the same workflow:

```
Pod A: Receives resume request for thread-123
Pod B: Receives resume request for thread-123 (duplicate click, webhook retry, etc.)

Both load checkpoint, both execute tool, both try to write checkpoint
```

### Solution: Distributed Locking

Use Redis or your checkpoint store for locking:

```python
import redis

redis_client = redis.Redis()

async def resume_with_lock(thread_id: str, resume_value: dict):
    lock_key = f"workflow_lock:{thread_id}"
    
    # Try to acquire lock (5 second expiry)
    acquired = redis_client.set(lock_key, "locked", nx=True, ex=5)
    
    if not acquired:
        raise ConcurrentResumeError(f"Thread {thread_id} is already being resumed")
    
    try:
        result = await graph.ainvoke(
            Command(resume=resume_value),
            {"configurable": {"thread_id": thread_id}}
        )
        return result
    finally:
        redis_client.delete(lock_key)
```

### Solution: PostgresSaver for Shared State

`MemorySaver` is per-process. Use `PostgresSaver` for multi-pod:

```python
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    conninfo="postgresql://user:pass@host:5432/langgraph",
    max_size=10
)

with pool.connection() as conn:
    saver = PostgresSaver(conn)
    saver.setup()  # Creates tables if needed

graph = builder.compile(checkpointer=saver)
```

Now any pod can load any thread's checkpoint.

---

## Gotcha 6: State Corruption From Partial Writes

### The Problem

If a node updates multiple state fields and crashes mid-update:

```python
def complex_node(state):
    # Update 1: Write to external DB
    db.insert(state["record"])
    
    # Crash here! 
    
    # Update 2: Return state update
    return {"record_saved": True, "db_id": db.last_id}
```

The external DB has the record, but state doesn't know it. On retry, you might insert a duplicate.

### Solution: Sync Durability Mode

LangGraph offers durability modes:

```python
# Default: async (faster, small risk of lost checkpoints on crash)
graph = builder.compile(checkpointer=saver)

# Sync: checkpoint written before next step starts
# Higher durability, some performance cost
graph = builder.compile(checkpointer=saver, durability_mode="sync")
```

### Solution: Tasks for Non-Deterministic Operations

LangGraph's `@task` decorator caches results to prevent re-execution:

```python
from langgraph.func import task

@task
def fetch_external_data(query: str):
    """This runs once, result cached in checkpoint."""
    return expensive_api_call(query)

def my_node(state):
    # If this node re-runs, the task result is loaded from cache
    data = fetch_external_data(state["query"])
    
    decision = interrupt({"data": data})
    
    return {"approved": decision["approved"]}
```

**Caveat:** As of late 2025, there are reports that `@task` caching doesn't work reliably with the LangGraph API server (see Issue discussions). The workaround is to use separate nodes instead.

---

## Production Checklist

### Before Deploying HITL Workflows

- [ ] **Side effects after interrupt():** Ensure expensive operations, notifications, and logging happen after the interrupt, not before.
    
- [ ] **One interrupt per node:** Avoid multiple `interrupt()` calls in a single node. Split into chained nodes if needed.
    
- [ ] **Consistent interrupt order:** If you must have multiple interrupts, ensure they execute in the same order every time (no conditionals).
    
- [ ] **Idempotency keys:** Generate unique keys for side effects, pass to APIs that support them, or implement check-before-execute.
    
- [ ] **Timeout handling:** Implement application-level expiry tracking and cleanup jobs for abandoned workflows.
    
- [ ] **Distributed locking:** If multi-pod, use Redis locks or database-level locking to prevent concurrent resumes.
    
- [ ] **Production checkpointer:** Use `PostgresSaver` or `AsyncPostgresSaver`, not `MemorySaver`.
    
- [ ] **Checkpoint pruning:** Implement a policy to clean up old checkpoints and prevent unbounded database growth.
    
- [ ] **Observability:** Log node executions, interrupt payloads, and resume events. Connect to LangSmith or your APM for tracing.
    

---

## Key Takeaways

1. **Node re-execution is by design.** The entire node restarts on resume. Put side effects after `interrupt()` or split into multiple nodes.
    
2. **Multiple interrupts per node are fragile.** Index-based matching breaks with conditional logic. Use separate nodes.
    
3. **No built-in timeout.** Implement application-level expiry tracking and cleanup.
    
4. **Idempotency is your responsibility.** Use idempotency keys, check-before-execute, or leverage API-native idempotency.
    
5. **`MemorySaver` is dev-only.** Production requires `PostgresSaver` with connection pooling.
    
6. **Known bugs exist.** Issues #6208, #6533, #6626 cover edge cases with multi-interrupt nodes. The maintainer-recommended workaround is to chain nodes.
    

---

## What's Next

This note covered the mechanical gotchas of HITL. The next note covers:

- **Note 6:** Context-Aware Danger Assessment — dynamic triggering, risk scoring, and avoiding HITL fatigue