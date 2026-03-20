# Note 4: Designing What Humans See

## The UX Challenge

When your agent pauses for human input, what appears on the screen determines whether the human can make a good decision quickly — or whether they'll rubber-stamp approvals because the interface is overwhelming, unclear, or annoying.

The `interrupt()` payload isn't just technical plumbing. It's the entire UX of your human-in-the-loop system.

---

## The Minimal Information Principle

**Show the minimum information needed for the human to make a confident decision.**

Too little information → human can't evaluate properly → bad decisions or frustrated "just approve it" clicks

Too much information → cognitive overload → human skims and misses important details → bad decisions

The sweet spot:

```
What is the agent trying to do?
Why is it trying to do this?
What will happen if approved?
What are the key parameters?
```

Anything beyond this needs justification.

---

## Anatomy of a Good Interrupt Payload

### Required Elements

**1. Action Type** What category of action is this? Use consistent, recognizable labels.

```python
interrupt({
    "action": "send_email",  # Clear, consistent action identifier
    ...
})
```

**2. Key Parameters** The specific details of this instance of the action. These are what the human actually reviews.

```python
interrupt({
    "action": "send_email",
    "params": {
        "to": "customer@example.com",
        "subject": "Your order has shipped",
        "body_preview": "Dear Customer, Your order #12345..."  # Preview, not full text
    },
    ...
})
```

**3. Context/Reasoning** Why is the agent taking this action? This helps the human evaluate appropriateness.

```python
interrupt({
    "action": "send_email",
    "params": {...},
    "reason": "Customer asked about order status; order #12345 shipped today",
    ...
})
```

**4. Expected Response Format** Tell the human what kind of input you expect. Don't make them guess.

```python
interrupt({
    "action": "send_email",
    "params": {...},
    "reason": "...",
    "response_options": ["approve", "edit", "reject"],
    "instructions": "Approve to send as-is, edit to modify, reject to cancel"
})
```

### Optional Elements

**5. Risk Level** For systems with mixed-risk actions, surface the risk classification.

```python
interrupt({
    ...
    "risk": "medium",  # or "low", "high", "critical"
    "risk_factors": ["external_recipient", "contains_pii"]
})
```

**6. Reversibility** Can this be undone? Humans judge irreversible actions more carefully.

```python
interrupt({
    ...
    "reversible": False,
    "consequence": "Email cannot be unsent once delivered"
})
```

**7. Confidence Score** If the agent has uncertainty, surface it. Low confidence warrants more scrutiny.

```python
interrupt({
    ...
    "confidence": 0.73,
    "confidence_note": "Uncertain about recipient - multiple contacts named 'John'"
})
```

---

## Payload Patterns for Common Scenarios

### Pattern 1: Tool Call Approval

```python
def approval_node(state):
    tool_call = state["pending_tool_call"]
    
    return interrupt({
        "type": "tool_approval",
        "tool": tool_call["name"],
        "args": tool_call["args"],
        "reason": state.get("agent_reasoning", "Agent requested this tool"),
        "response_format": {
            "approve": "Execute with these arguments",
            "edit": "Provide modified args as {edited_args: {...}}",
            "reject": "Cancel with optional {reason: '...'}"
        }
    })
```

### Pattern 2: Content Review

```python
def content_review_node(state):
    draft = state["generated_content"]
    
    return interrupt({
        "type": "content_review",
        "content_type": "email_response",
        "draft": draft,
        "word_count": len(draft.split()),
        "tone_analysis": "professional",  # If you have this
        "instructions": "Review and edit the draft, or approve as-is",
        "response_format": {
            "approve": "Send as written",
            "edit": "Provide {edited_content: '...'}"
        }
    })
```

### Pattern 3: Decision Point

```python
def decision_node(state):
    options = state["available_options"]
    
    return interrupt({
        "type": "decision_required",
        "question": "How should we proceed with customer complaint?",
        "context": state["complaint_summary"],
        "options": [
            {"id": "refund", "label": "Issue full refund", "impact": "Costs $50"},
            {"id": "partial", "label": "Issue 20% discount", "impact": "Costs $10"},
            {"id": "escalate", "label": "Escalate to manager", "impact": "Delays resolution"}
        ],
        "recommendation": "refund",
        "recommendation_reason": "Customer is VIP with 5+ year history",
        "response_format": "Respond with {choice: 'refund'|'partial'|'escalate'}"
    })
```

### Pattern 4: Escalation

```python
def escalation_node(state):
    return interrupt({
        "type": "escalation",
        "severity": "high",
        "reason": "Agent cannot determine appropriate action",
        "situation": state["current_situation"],
        "attempted_actions": state["failed_attempts"],
        "needs": "Human guidance on next steps",
        "response_format": "Provide {action: '...', parameters: {...}}"
    })
```

---

## Where Does the UI Live?

The `interrupt()` payload surfaces via `result["__interrupt__"]`. Your application code must render this into an actual UI. Common patterns:

### CLI / Terminal

```python
# Simple CLI rendering
result = graph.invoke(input, config)

if "__interrupt__" in result:
    intr = result["__interrupt__"][0]
    payload = intr.value
    
    print(f"\n{'='*50}")
    print(f"ACTION: {payload['action']}")
    print(f"PARAMS: {json.dumps(payload['params'], indent=2)}")
    print(f"REASON: {payload['reason']}")
    print(f"{'='*50}")
    
    response = input("Enter decision (approve/edit/reject): ")
    
    if response == "approve":
        graph.invoke(Command(resume={"approved": True}), config)
    elif response == "reject":
        reason = input("Rejection reason: ")
        graph.invoke(Command(resume={"approved": False, "reason": reason}), config)
    # ... handle edit
```

### Web Application

```python
# API endpoint returns interrupt info
@app.route("/agent/status/<thread_id>")
def get_status(thread_id):
    state = graph.get_state({"configurable": {"thread_id": thread_id}})
    
    if state.tasks and state.tasks[0].interrupts:
        interrupt = state.tasks[0].interrupts[0]
        return jsonify({
            "status": "awaiting_approval",
            "interrupt_id": interrupt.id,
            "payload": interrupt.value
        })
    
    return jsonify({"status": "running" if state.next else "complete"})

# Frontend renders payload as approval card
# User clicks approve/reject
# Frontend calls resume endpoint

@app.route("/agent/resume/<thread_id>", methods=["POST"])
def resume(thread_id):
    decision = request.json
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume=decision), config)
    return jsonify({"status": "resumed", "result": result})
```

### Slack / Chat Integration

```python
# When interrupt occurs, send Slack message
def send_approval_request(interrupt_payload, thread_id):
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Action Required*: {interrupt_payload['action']}"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*To:* {interrupt_payload['params']['to']}"},
                {"type": "mrkdwn", "text": f"*Subject:* {interrupt_payload['params']['subject']}"}
            ]
        },
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Approve"}, 
                 "action_id": f"approve_{thread_id}", "style": "primary"},
                {"type": "button", "text": {"type": "plain_text", "text": "Reject"}, 
                 "action_id": f"reject_{thread_id}", "style": "danger"}
            ]
        }
    ]
    slack_client.chat_postMessage(channel="#approvals", blocks=blocks)
```

### Email Approval

For async workflows where humans might respond hours later:

```python
def send_approval_email(interrupt_payload, thread_id):
    approve_link = f"https://app.example.com/approve/{thread_id}?action=approve"
    reject_link = f"https://app.example.com/approve/{thread_id}?action=reject"
    
    body = f"""
    Action requires your approval:
    
    {interrupt_payload['action']}
    {json.dumps(interrupt_payload['params'], indent=2)}
    
    Reason: {interrupt_payload['reason']}
    
    [Approve]({approve_link}) | [Reject]({reject_link})
    """
    
    send_email(to=reviewer_email, subject="Approval Required", body=body)
```

---

## Anti-Patterns to Avoid

### 1. The Wall of Text

❌ Bad:

```python
interrupt({
    "message": f"The agent is attempting to execute the send_email tool with the following parameters: to={to}, subject={subject}, body={body}. This action was triggered because the user asked about their order status and the agent determined that sending an email would be the appropriate response. The email will be sent via the company SMTP server and cannot be recalled once sent. Please review carefully and decide whether to approve this action, reject it, or provide modifications to the parameters before execution proceeds."
})
```

✅ Good:

```python
interrupt({
    "action": "send_email",
    "to": "customer@example.com",
    "subject": "Order Status Update",
    "body_preview": "Your order #12345 has shipped...",
    "reason": "Customer asked about order status"
})
```

### 2. Missing Context

❌ Bad:

```python
interrupt({
    "tool": "delete_file",
    "path": "/data/records/2024/q3/report.xlsx"
})
# Human has no idea WHY this file should be deleted
```

✅ Good:

```python
interrupt({
    "action": "delete_file",
    "path": "/data/records/2024/q3/report.xlsx",
    "reason": "User requested cleanup of draft reports",
    "file_info": {
        "size": "2.3 MB",
        "modified": "2024-09-15",
        "created_by": "auto-generator"
    },
    "reversible": False,
    "warning": "This cannot be undone"
})
```

### 3. Unclear Response Expectations

❌ Bad:

```python
interrupt({"message": "Please provide input to continue"})
# Human has no idea what format or options are expected
```

✅ Good:

```python
interrupt({
    "question": "Select shipping priority",
    "options": ["standard", "express", "overnight"],
    "default": "standard",
    "response_format": "Respond with {choice: '...'}"
})
```

### 4. Technical Jargon

❌ Bad:

```python
interrupt({
    "tool_call_id": "call_abc123",
    "function": "execute_sql",
    "arguments": {"query": "DELETE FROM users WHERE status='inactive'"}
})
```

✅ Good:

```python
interrupt({
    "action": "Delete database records",
    "description": "Remove all inactive user accounts",
    "impact": "47 user records will be permanently deleted",
    "reversible": False,
    "technical_details": {  # Available if they want to drill down
        "query": "DELETE FROM users WHERE status='inactive'",
        "affected_rows": 47
    }
})
```

---

## Designing for Different User Types

### Technical Users (Developers, DBAs)

Show more technical details. They can handle SQL queries, API payloads, file paths.

```python
interrupt({
    "action": "execute_query",
    "query": "UPDATE accounts SET status='suspended' WHERE balance < 0",
    "affected_rows": 23,
    "execution_plan": "Index scan on balance column"  # They'll appreciate this
})
```

### Business Users (Managers, Ops)

Hide technical details. Focus on business impact.

```python
interrupt({
    "action": "Suspend accounts",
    "description": "Suspend accounts with negative balances",
    "count": 23,
    "impact": "These accounts will be unable to place orders",
    "reason": "Policy: accounts below $0 auto-suspend"
})
```

### External Users (Customers)

Minimal, friendly language. No internal terminology.

```python
interrupt({
    "question": "Should we send you email updates about your order?",
    "options": ["Yes, keep me updated", "No thanks"],
    "note": "You can change this later in your account settings"
})
```

---

## Handling Queues and Batches

When multiple approvals stack up, don't present them one at a time:

### Approval Queue UI

```python
# Return all pending interrupts for a dashboard view
def get_pending_approvals(user_id):
    threads = get_user_threads(user_id)
    pending = []
    
    for thread_id in threads:
        state = graph.get_state({"configurable": {"thread_id": thread_id}})
        if state.tasks and state.tasks[0].interrupts:
            intr = state.tasks[0].interrupts[0]
            pending.append({
                "thread_id": thread_id,
                "timestamp": state.created_at,
                "action": intr.value.get("action"),
                "summary": intr.value.get("reason"),
                "risk": intr.value.get("risk", "unknown")
            })
    
    return sorted(pending, key=lambda x: (x["risk"] == "high", x["timestamp"]), reverse=True)
```

### Bulk Actions

For similar low-risk items, allow bulk approval:

```python
# Frontend groups similar actions
# "5 emails to send - all order confirmations"
# [Approve All] [Review Individually]
```

---

## Response Handling: What Comes Back

Design your node to handle the response gracefully:

```python
def approval_node(state):
    response = interrupt({...})
    
    # Handle all expected response types
    if response.get("action") == "approve":
        return {"status": "approved", "proceed": True}
    
    elif response.get("action") == "edit":
        # Validate the edits
        edited = response.get("edited_params", {})
        if not validate_edits(edited):
            # Could re-interrupt with error message
            return interrupt({
                "error": "Invalid edits provided",
                "original_request": {...},
                "validation_errors": ["email format invalid"]
            })
        return {"status": "approved", "params": edited, "proceed": True}
    
    elif response.get("action") == "reject":
        return {
            "status": "rejected",
            "reason": response.get("reason", "User rejected"),
            "proceed": False
        }
    
    else:
        # Unexpected response format
        return interrupt({
            "error": "Unrecognized response",
            "received": response,
            "expected_format": {"action": "approve|edit|reject", ...}
        })
```

---

## Key Takeaways

1. **Minimal information principle:** Show what's needed for a confident decision, nothing more.
    
2. **Required elements:** Action type, key parameters, context/reasoning, expected response format.
    
3. **Optional elements:** Risk level, reversibility, confidence score — add when they help.
    
4. **Match the UI to the context:** CLI for developers, web cards for dashboards, Slack for ops, email for async.
    
5. **Avoid anti-patterns:** Wall of text, missing context, unclear expectations, technical jargon for non-technical users.
    
6. **Design for queues:** When approvals stack up, provide list views, sorting by risk/time, and bulk actions for similar items.
    
7. **Handle responses gracefully:** Validate edits, provide clear errors, support re-prompting on invalid input.
    

---

## What's Next

This note covered _what_ to show humans. The next note covers:

- **Note 5:** Production gotchas — double execution, timeouts, and idempotency