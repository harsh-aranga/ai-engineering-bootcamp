# Note 6: Context-Aware Danger Assessment

## Beyond Static Rules

The previous notes covered _how_ to pause and resume. This note covers _when_ to pause — and more importantly, when _not_ to.

Static HITL (approve every tool call, or approve every action of type X) doesn't scale. It creates:

- **Approval fatigue:** Humans rubber-stamp after the 50th identical approval
- **Velocity loss:** Every pause is latency; too many pauses kill the agent's value proposition
- **False sense of security:** A bored approver is worse than no approver

The production pattern is **adaptive HITL**: the agent assesses risk dynamically and only escalates when warranted.

---

## The Risk Scoring Model

Instead of binary "always approve" vs. "never approve," assign a risk score to each action and trigger HITL based on thresholds.

### Risk Dimensions

**1. Reversibility** Can this action be undone?

|Action|Reversibility|Risk Weight|
|---|---|---|
|Read file|Fully reversible|0|
|Create draft|Fully reversible|1|
|Send email|Irreversible|5|
|Delete production DB|Irreversible|10|

**2. Blast Radius** How many things does this affect?

|Scope|Risk Weight|
|---|---|
|Single record|1|
|Batch (10-100)|3|
|All records|5|
|External parties|7|

**3. Financial Impact** What's the dollar value at stake?

|Amount|Risk Weight|
|---|---|
|$0 (read-only)|0|
|< $100|1|
|$100 - $1,000|3|
|$1,000 - $10,000|5|
|> $10,000|8|

**4. Confidence** How certain is the agent about this action?

|Confidence|Risk Weight|
|---|---|
|> 0.95|0|
|0.80 - 0.95|2|
|0.60 - 0.80|4|
|< 0.60|6|

**5. Anomaly Score** Is this action unusual for this user/context?

|Pattern|Risk Weight|
|---|---|
|Normal behavior|0|
|Unusual but plausible|2|
|First-time action|3|
|Contradicts recent actions|5|

### Composite Risk Score

```python
def calculate_risk_score(action: dict, context: dict) -> float:
    """Calculate composite risk score for an action."""
    
    weights = {
        "reversibility": 1.0,
        "blast_radius": 1.2,
        "financial_impact": 1.5,
        "confidence": 0.8,
        "anomaly": 1.0
    }
    
    scores = {
        "reversibility": score_reversibility(action),
        "blast_radius": score_blast_radius(action),
        "financial_impact": score_financial_impact(action, context),
        "confidence": score_confidence(action),
        "anomaly": score_anomaly(action, context)
    }
    
    composite = sum(weights[k] * scores[k] for k in weights)
    
    return composite
```

### Risk Tiers and Actions

```python
def determine_action(risk_score: float) -> str:
    """Map risk score to action tier."""
    
    if risk_score < 5:
        return "auto_execute"      # No human needed
    elif risk_score < 12:
        return "notify_async"      # Execute, notify human after
    elif risk_score < 20:
        return "require_approval"  # Pause for approval
    else:
        return "block_and_escalate"  # Don't even offer to execute
```

---

## Implementing Dynamic HITL

### Pattern: Risk-Based Routing

```python
from langgraph.graph import StateGraph
from langgraph.types import interrupt

class State(TypedDict):
    messages: list
    pending_action: dict
    risk_score: float
    risk_factors: list
    approved: bool

def assess_risk_node(state: State) -> dict:
    """Calculate risk and decide routing."""
    action = state["pending_action"]
    context = extract_context(state)
    
    risk_score = calculate_risk_score(action, context)
    risk_factors = identify_risk_factors(action, context)
    
    return {
        "risk_score": risk_score,
        "risk_factors": risk_factors
    }

def route_by_risk(state: State) -> str:
    """Conditional edge: route based on risk score."""
    score = state["risk_score"]
    
    if score < 5:
        return "execute"
    elif score < 20:
        return "request_approval"
    else:
        return "block"

def request_approval_node(state: State) -> dict:
    """Pause for human approval with risk context."""
    decision = interrupt({
        "action": state["pending_action"],
        "risk_score": state["risk_score"],
        "risk_factors": state["risk_factors"],
        "recommendation": "approve" if state["risk_score"] < 12 else "review_carefully"
    })
    
    return {"approved": decision.get("approved", False)}

def execute_node(state: State) -> dict:
    """Execute the action."""
    result = execute_action(state["pending_action"])
    return {"result": result}

def block_node(state: State) -> dict:
    """Block high-risk actions entirely."""
    return {
        "blocked": True,
        "reason": f"Risk score {state['risk_score']} exceeds threshold",
        "risk_factors": state["risk_factors"]
    }

# Build graph with conditional routing
builder = StateGraph(State)
builder.add_node("assess_risk", assess_risk_node)
builder.add_node("request_approval", request_approval_node)
builder.add_node("execute", execute_node)
builder.add_node("block", block_node)

builder.add_edge(START, "assess_risk")
builder.add_conditional_edges("assess_risk", route_by_risk)
builder.add_edge("request_approval", "execute")  # If approved
builder.add_edge("execute", END)
builder.add_edge("block", END)
```

### Pattern: Progressive Trust

Start strict, loosen as the agent proves reliable:

```python
def get_risk_threshold(agent_id: str, action_type: str) -> float:
    """Dynamic threshold based on agent's track record."""
    
    # Get agent's history
    history = get_agent_history(agent_id, action_type)
    
    base_threshold = 12  # Default: require approval above 12
    
    # Successful executions without issues lower the threshold
    success_rate = history["successes"] / max(history["total"], 1)
    trust_adjustment = (success_rate - 0.9) * 10  # -1 to +1 range
    
    # Recent failures raise the threshold
    recent_failures = history["failures_last_7_days"]
    failure_penalty = recent_failures * 3
    
    adjusted_threshold = base_threshold + trust_adjustment - failure_penalty
    
    # Never go below minimum or above maximum
    return max(5, min(20, adjusted_threshold))
```

### Pattern: Context-Sensitive Risk

Same action, different risk based on context:

```python
def score_context_risk(action: dict, context: dict) -> float:
    """Adjust risk based on contextual factors."""
    
    base_risk = action["base_risk_score"]
    multipliers = []
    
    # Time-based risk
    if is_outside_business_hours():
        multipliers.append(1.5)  # Higher risk after hours
    
    # User-based risk
    if context["user"]["is_new"]:
        multipliers.append(1.3)  # New users get more scrutiny
    
    if context["user"]["role"] == "admin":
        multipliers.append(0.8)  # Admins trusted more
    
    # Session-based risk
    if context["session"]["anomaly_score"] > 0.7:
        multipliers.append(2.0)  # Unusual session patterns
    
    # Apply multipliers
    final_risk = base_risk
    for m in multipliers:
        final_risk *= m
    
    return final_risk
```

---

## The Confirm Mode Anti-Pattern

### What It Is

"Confirm mode" means requiring approval for every action. Some frameworks and demos default to this:

```python
# ❌ ANTI-PATTERN: Approve everything
def every_tool_node(state):
    for tool_call in state["tool_calls"]:
        decision = interrupt({
            "tool": tool_call["name"],
            "args": tool_call["args"]
        })
        if not decision["approved"]:
            continue
        execute_tool(tool_call)
```

### Why It Fails

1. **Approval fatigue:** After 20 approvals in a row, humans stop reading and just click "approve"
2. **Velocity destruction:** Each approval is 5-30 seconds of latency
3. **False security:** The 21st approval (the dangerous one) gets rubber-stamped
4. **User frustration:** "Why did I get an agent if I have to approve everything?"

Research on Claude Code usage (Anthropic, early 2026) found that experienced users increase their auto-approve rate over time—not because the agent got safer, but because constant approval becomes unsustainable.

### The Fix: Tiered Autonomy

```
Tier 1: AUTONOMOUS
- Read operations
- Drafts (not sent)
- Low-value, reversible actions
- Actions within established patterns

Tier 2: NOTIFY (Execute, then inform)
- Medium-value actions
- Actions matching user preferences
- Reversible but impactful

Tier 3: APPROVE (Pause for approval)
- High-value or irreversible
- First-time action patterns
- Actions affecting external parties

Tier 4: BLOCK (Don't execute, escalate)
- Destructive operations
- Policy violations
- Anomalous patterns
```

---

## Avoiding Approval Fatigue

### Strategy 1: Batch Similar Actions

Instead of 10 individual approvals for 10 similar emails:

```python
def batch_approval_node(state: State) -> dict:
    """Group similar actions for batch approval."""
    
    actions = state["pending_actions"]
    
    # Group by type and similarity
    groups = group_similar_actions(actions)
    
    approval_requests = []
    for group in groups:
        if len(group) == 1:
            approval_requests.append(group[0])
        else:
            # Batch: "5 order confirmation emails to customers"
            approval_requests.append({
                "type": "batch",
                "action_type": group[0]["type"],
                "count": len(group),
                "sample": group[0],  # Show one example
                "recipients": [a["to"] for a in group]
            })
    
    decisions = interrupt({
        "requests": approval_requests,
        "instructions": "Approve individually or in batches"
    })
    
    return {"approved_actions": expand_batch_decisions(decisions, actions)}
```

### Strategy 2: Sampled Approval

Approve a sample of low-risk actions to monitor drift:

```python
import random

def sampled_approval_node(state: State) -> dict:
    """Approve only a sample of low-risk actions."""
    
    action = state["pending_action"]
    risk_score = state["risk_score"]
    
    if risk_score >= 12:
        # High risk: always approve
        return interrupt_for_approval(action)
    
    # Low risk: sample at 10% rate
    sample_rate = 0.10
    if random.random() < sample_rate:
        decision = interrupt({
            "action": action,
            "note": "Sampled for quality check (1 in 10)",
            "risk_score": risk_score
        })
        log_sample_result(action, decision)
        return {"approved": decision["approved"]}
    
    # Auto-execute without approval
    return {"approved": True}
```

### Strategy 3: Exception-Based Review

Auto-approve unless something looks wrong:

```python
def exception_based_node(state: State) -> dict:
    """Auto-execute unless anomaly detected."""
    
    action = state["pending_action"]
    
    # Run anomaly detection
    anomalies = detect_anomalies(action, state["context"])
    
    if anomalies:
        return interrupt({
            "action": action,
            "anomalies": anomalies,
            "reason": "Unusual pattern detected",
            "recommendation": "review_carefully"
        })
    
    # No anomalies: auto-execute
    return {"approved": True, "auto_approved": True}
```

### Strategy 4: Time-Boxed Auto-Approve

Grant temporary elevated trust:

```python
def check_auto_approve_window(user_id: str, action_type: str) -> bool:
    """Check if user granted time-limited auto-approval."""
    
    grant = get_auto_approve_grant(user_id, action_type)
    
    if not grant:
        return False
    
    if grant["expires_at"] < datetime.utcnow():
        revoke_grant(grant["id"])
        return False
    
    if grant["remaining_uses"] <= 0:
        revoke_grant(grant["id"])
        return False
    
    # Valid grant: decrement and allow
    decrement_grant_uses(grant["id"])
    return True
```

User experience:

```
Agent: "You have 15 similar email responses to send. 
        Approve each individually, or grant auto-approval for the next hour?"

User: "Auto-approve similar emails for 1 hour"

Agent: [sends all 15 without pausing]
```

---

## Security Consideration: Approval Flooding

### The Attack

Adversaries can exploit HITL by overwhelming humans with approvals:

> "Attackers may flood human reviewers with alerts, decisions, or ambiguously framed prompts, forcing them to approve malicious actions under pressure or confusion." — OWASP Agentic AI Threats (2025)

If your agent surfaces 100 approvals, and the malicious one is #73, it gets rubber-stamped.

### Mitigations

**1. Rate Limiting** Cap approvals per time window:

```python
def check_approval_rate_limit(user_id: str) -> bool:
    """Prevent approval flooding."""
    
    recent_approvals = count_approvals(user_id, window_minutes=5)
    
    if recent_approvals > 10:
        # Too many approvals too fast
        alert_security_team(user_id, "approval_flood_suspected")
        return False  # Block further approvals
    
    return True
```

**2. Prioritization** Show high-risk first, don't bury them:

```python
def prioritize_approval_queue(pending_approvals: list) -> list:
    """Sort approvals so high-risk items are seen first."""
    
    return sorted(
        pending_approvals,
        key=lambda a: (-a["risk_score"], a["created_at"])
    )
```

**3. Mandatory Delays** Force humans to pause on high-risk items:

```python
def approval_ui_rules(action: dict) -> dict:
    """UI rules to prevent rubber-stamping."""
    
    risk = action["risk_score"]
    
    if risk > 15:
        return {
            "minimum_review_time_seconds": 10,
            "require_checkbox": True,
            "checkbox_text": "I have reviewed the details of this action"
        }
    elif risk > 10:
        return {
            "minimum_review_time_seconds": 3
        }
    else:
        return {}
```

---

## When to Skip HITL Entirely

Some contexts justify full autonomy:

### Sandboxed Environments

If the agent can't cause real harm:

```python
def check_sandbox_mode(context: dict) -> bool:
    """In sandbox, skip all HITL."""
    return context.get("environment") == "sandbox"

def risk_router(state: State) -> str:
    if check_sandbox_mode(state["context"]):
        return "execute"  # Always auto-execute in sandbox
    
    # Normal risk-based routing
    return route_by_risk(state)
```

### Explicit User Opt-Out

User takes responsibility:

```python
def check_user_preferences(user_id: str) -> dict:
    prefs = get_user_preferences(user_id)
    
    return {
        "auto_approve_reads": prefs.get("auto_approve_reads", True),
        "auto_approve_drafts": prefs.get("auto_approve_drafts", True),
        "auto_approve_sends": prefs.get("auto_approve_sends", False),
        "auto_approve_deletes": prefs.get("auto_approve_deletes", False)
    }
```

### Low-Stakes Domains

Email assistant vs. trading bot have different risk profiles:

```python
DOMAIN_BASE_RISK = {
    "email_drafting": 2,
    "calendar_management": 3,
    "data_analysis": 1,
    "code_generation": 4,
    "financial_trading": 15,
    "infrastructure_management": 12,
    "customer_communication": 8
}
```

---

## Observability for Risk Decisions

### What to Log

Every risk assessment should be traceable:

```python
def log_risk_assessment(
    action_id: str,
    action: dict,
    risk_score: float,
    risk_factors: list,
    decision: str,  # auto_execute, require_approval, block
    outcome: str,   # executed, approved, rejected, timeout
    human_override: bool
):
    """Full audit trail for risk decisions."""
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action_id": action_id,
        "action_type": action["type"],
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "decision": decision,
        "outcome": outcome,
        "human_override": human_override,
        "threshold_at_time": get_current_threshold()
    }
    
    audit_logger.info(json.dumps(log_entry))
```

### Metrics to Track

- **Auto-approve rate:** What percentage of actions auto-execute?
- **Approval latency:** How long do humans take to respond?
- **Override rate:** How often do humans disagree with recommendations?
- **False positive rate:** Actions blocked that shouldn't have been
- **False negative rate:** Actions approved that caused problems
- **Risk score distribution:** Are scores well-calibrated?

### Calibration Feedback Loop

Use outcomes to improve risk scoring:

```python
def update_risk_model(action: dict, predicted_risk: float, actual_outcome: str):
    """Learn from outcomes to improve risk prediction."""
    
    if actual_outcome == "caused_problem" and predicted_risk < 10:
        # Under-estimated risk
        log_calibration_error("false_negative", action, predicted_risk)
        increase_risk_weights(action["type"])
    
    elif actual_outcome == "fine" and predicted_risk > 15:
        # Over-estimated risk
        log_calibration_error("false_positive", action, predicted_risk)
        decrease_risk_weights(action["type"])
```

---

## Key Takeaways

1. **Static HITL doesn't scale.** Approving everything creates approval fatigue and false security.
    
2. **Risk scoring enables adaptive HITL.** Calculate composite risk from reversibility, blast radius, financial impact, confidence, and anomaly signals.
    
3. **Tier your actions.** Auto-execute low-risk, notify medium-risk, approve high-risk, block extreme-risk.
    
4. **Fight approval fatigue.** Use batching, sampling, exception-based review, and time-boxed auto-approve.
    
5. **Guard against approval flooding.** Rate-limit approvals, prioritize high-risk, and enforce mandatory review delays.
    
6. **Progressive trust.** Start strict, loosen as the agent proves reliable, tighten after failures.
    
7. **Observe and calibrate.** Log every risk decision, track override rates, and use outcomes to improve scoring.
    
8. **Context matters.** Same action, different risk in different contexts (time of day, user role, session patterns).
    

---

## Week 5 HITL Notes Complete

You now have the full HITL picture:

- **Note 1:** Why HITL and common patterns (taxonomy)
- **Note 2:** Pausing execution (breakpoints and interrupt())
- **Note 3:** Resumption with Command (mechanics of resume)
- **Note 4:** Designing what humans see (UX of the payload)
- **Note 5:** Production gotchas (double execution, timeouts, idempotency)
- **Note 6:** Context-aware danger assessment (dynamic triggering, avoiding fatigue)

Ready for the Ponder questions and mini challenge when you are.