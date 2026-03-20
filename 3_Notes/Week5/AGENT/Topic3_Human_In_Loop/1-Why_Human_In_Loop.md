# Note 1: Why Human-in-the-Loop and Common Patterns

## Why Autonomous Agents Need Human Checkpoints

Autonomous agents are powerful precisely because they can chain multiple actions without waiting for human input. But this same power creates risk. An agent that can send emails, delete files, execute database queries, and make API calls can cause significant damage in seconds — faster than any human can intervene after the fact.

The core problem isn't that agents make mistakes. Humans make mistakes too. The problem is that agents make mistakes at machine speed, across multiple systems, without the natural pause points that human workflows have.

### Risk Categories That Demand HITL

**1. Irreversibility** Some actions cannot be undone. Once an email is sent, a file is permanently deleted, or a database record is dropped, there's no rollback. Agents don't inherently understand which actions cross this threshold.

**2. Financial Cost** API calls cost money. Cloud resources cost money. Purchasing decisions cost money. An agent in a loop can burn through budget in minutes. A human checkpoint before expensive operations isn't paranoia — it's basic cost control.

**3. External Effects** Actions that touch systems or people outside your control deserve extra scrutiny. Sending a message to a customer, posting to social media, triggering a webhook to a third-party service — these create effects you can't contain or reverse.

**4. Reputational Risk** An agent responding to customers, generating public content, or making decisions that represent your organization carries brand risk. The cost of one bad automated response can far exceed the efficiency gains of automation.

**5. Regulatory/Compliance Requirements** In finance, healthcare, legal, and other regulated domains, certain decisions legally require human approval. Full automation isn't just risky — it's non-compliant.

### The Trust Gradient

Not all agent actions need the same level of oversight. Think of trust as a gradient:

```
Low Risk (Auto-approve)          High Risk (Always require approval)
    │                                        │
    ▼                                        ▼
┌────────┬────────┬────────┬────────┬────────┐
│  Read  │ Search │ Draft  │ Modify │ Delete │
│  data  │  web   │ content│  data  │ / Send │
└────────┴────────┴────────┴────────┴────────┘
```

Reading data? Usually safe to auto-approve. Searching the web? Low risk. Drafting content for review? Medium risk. Modifying production data? High risk. Deleting files or sending external communications? Highest risk — almost always worth a human checkpoint.

---

## The Four Core HITL Patterns

Human-in-the-loop isn't one pattern — it's a family of patterns with different trade-offs. Each pattern answers a different question about how humans should interact with agent decisions.

### Pattern 1: Approval (Binary Gate)

**What it does:** Agent proposes an action. Human says yes or no. If yes, action executes as proposed. If no, agent must find an alternative.

**The flow:**

```
Agent plans action → Human reviews → Approve? 
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
                   YES                                      NO
                    │                                       │
            Execute action                     Agent tries alternative
                    │                          (or explains failure)
                    ▼                                       │
                Continue                                    ▼
                                                    Back to human
```

**When to use:**

- High-stakes, low-volume decisions (loan approvals, large purchases)
- Actions where the parameters are non-negotiable (delete this specific file: yes or no?)
- Regulatory requirements that mandate human sign-off

**When NOT to use:**

- High-volume decisions (approval fatigue will cause humans to rubber-stamp everything)
- Situations where the human might want to modify, not just accept/reject

**Real-world example:** Claude Code asking "Allow this bash command? [y/n]" before executing shell commands.

---

### Pattern 2: Edit (Human Modifies Before Execution)

**What it does:** Agent drafts something (an email, a query, a plan). Human reviews and can modify the draft before it executes.

**The flow:**

```
Agent drafts action → Human reviews draft → Human edits (optional)
                                                    │
                                                    ▼
                                          Execute modified version
                                                    │
                                                    ▼
                                                Continue
```

**When to use:**

- Content generation (emails, documents, social posts)
- Query construction (SQL, API calls) where parameters matter
- Any situation where the agent's output is "close but not quite right" frequently

**When NOT to use:**

- Binary decisions where editing doesn't make sense
- Time-critical operations where editing latency is unacceptable

**Real-world example:** An agent drafts a customer response email. Human tweaks the tone, fixes a detail, then approves sending.

**Key insight:** Edit is strictly more powerful than Approval. With Edit, the human can always just approve without changes (making it equivalent to Approval), but they also have the option to fix issues without rejecting entirely.

---

### Pattern 3: Review (Post-Hoc Verification)

**What it does:** Agent executes an action, then pauses for human to verify the result before continuing. This is "review after" rather than "approve before."

**The flow:**

```
Agent executes action → Human reviews result → Acceptable?
                                                    │
                    ┌───────────────────────────────┴──────────────────────────┐
                    ▼                                                          ▼
                   YES                                                         NO
                    │                                                          │
                Continue with                                         Rollback/Compensate
                next action                                           (if possible)
                                                                              │
                                                                              ▼
                                                                      Agent retries
```

**When to use:**

- Actions that are reversible (created a draft, staged a change, wrote to a temp location)
- Situations where seeing the result is easier than predicting it
- Multi-step processes where you want to verify intermediate outputs

**When NOT to use:**

- Irreversible actions (once sent, you can't unsend)
- Situations where the cost of rollback is high

**Real-world example:** An agent generates a report and saves it to a staging folder. Human reviews the report. If acceptable, agent moves it to the final location and notifies stakeholders.

**Key insight:** Review flips the default. With Approval, the default is "don't do it" until human says yes. With Review, the default is "do it" but pause before downstream effects.

---

### Pattern 4: Escalation (Conditional Human Involvement)

**What it does:** Agent handles routine cases autonomously. When it encounters uncertainty, edge cases, or high-stakes situations, it escalates to a human.

**The flow:**

```
Agent analyzes situation → Confidence check
                                │
            ┌───────────────────┴───────────────────┐
            ▼                                       ▼
    High confidence                          Low confidence
    (or low stakes)                         (or high stakes)
            │                                       │
            ▼                                       ▼
    Execute autonomously                   Escalate to human
            │                                       │
            ▼                                       ▼
        Continue                           Human decides
                                                   │
                                                   ▼
                                               Continue
```

**When to use:**

- High-volume workflows where most cases are routine
- Tiered support systems (AI handles L1, humans handle L2+)
- Any situation with a natural "confidence threshold"

**When NOT to use:**

- All cases require human review (just use Approval)
- No clear criteria for what makes a case "routine" vs. "escalate"

**Real-world example:** An expense approval agent auto-approves expenses under $100 that match policy. Expenses over $100, or with unusual categories, get escalated to a manager.

**Key insight:** Escalation is the only pattern where most actions don't involve humans. This makes it the most efficient but also the most dangerous — if your escalation criteria are wrong, bad decisions flow through unchecked.

---

## Pattern Selection Criteria

Choosing the right pattern isn't arbitrary. Use this decision tree:

```
Is the action reversible?
    │
    ├─ YES → Is seeing the result easier than predicting it?
    │            │
    │            ├─ YES → REVIEW (execute, then verify)
    │            │
    │            └─ NO → Is the action high-volume?
    │                        │
    │                        ├─ YES → ESCALATION (auto-approve routine cases)
    │                        │
    │                        └─ NO → APPROVAL or EDIT
    │
    └─ NO (irreversible) → Does the human need to modify details?
                               │
                               ├─ YES → EDIT (human can tweak before execution)
                               │
                               └─ NO → APPROVAL (binary yes/no gate)
```

### Combining Patterns

Real systems often combine patterns. A single workflow might use:

- **Escalation** to filter which cases need human attention
- **Edit** for those escalated cases, allowing humans to modify the proposed action
- **Review** after execution to verify the result before notifying stakeholders

The patterns are building blocks, not mutually exclusive choices.

---

## The Approval Fatigue Problem

The biggest failure mode in HITL systems isn't technical — it's psychological.

When humans see too many approval requests, they stop reading them. They click "Approve" reflexively. This is worse than no HITL at all, because you have the cost of interruption without the benefit of genuine review.

**Signs of approval fatigue:**

- Average review time drops below what's needed to actually read the request
- Approval rate approaches 100%
- Errors that should have been caught slip through

**Mitigations:**

1. Use Escalation to reduce volume — only surface cases that genuinely need human judgment
2. Batch related approvals — review 10 similar items at once instead of 10 separate interrupts
3. Provide context that makes review fast — don't make humans dig for information
4. Track approval patterns — if someone approves everything in < 2 seconds, the system isn't working

---

## Framework-Agnostic Principles

The four patterns above aren't LangGraph-specific. They apply to any agent system:

|Pattern|OpenAI Agents SDK|LangGraph|Custom Implementation|
|---|---|---|---|
|Approval|Pause before tool execution, await confirmation|`interrupt()` before action node|Check flag before executing tool|
|Edit|Return proposed action, accept modifications|`interrupt()` with editable payload|Present draft, accept modified version|
|Review|Execute in sandbox, await confirmation to commit|`interrupt()` after action node|Stage changes, await approval to finalize|
|Escalation|Confidence threshold in tool logic|Conditional routing to human node|If-else based on risk score|

The implementation details change. The patterns don't.

---

## Key Takeaways

1. **HITL exists because agents operate at machine speed with machine blindness to risk.** The patterns add human judgment at critical decision points.
    
2. **Four patterns cover most use cases:** Approval (binary gate), Edit (modify before execute), Review (verify after execute), Escalation (conditional involvement).
    
3. **Pattern choice depends on reversibility, volume, and whether humans need to modify vs. just approve.**
    
4. **Approval fatigue is the silent killer.** A HITL system that interrupts too often becomes a rubber-stamp system, which is worse than no HITL.
    
5. **Patterns combine.** Real systems often use Escalation to filter, Edit to modify, and Review to verify — all in one workflow.
    

---

## What's Next

This note covered _why_ HITL and _which patterns_ to use. The next notes will cover:

- **Note 2:** How to technically pause execution (breakpoints vs. `interrupt()`)
- **Note 3:** How to resume after human input (`Command` and state updates)
- **Note 4:** What information to show humans at the checkpoint
- **Note 5:** Production gotchas (double execution, timeouts, idempotency)
- **Note 6:** Dynamic danger assessment (deciding when to trigger HITL)