# Note 1: Why Agent Evaluation is Hard + What to Measure

## Why This Matters

You built an agent in Week 5. It works... sometimes. But how do you know if it's _good_? How do you know if your changes made it _better_?

Agent evaluation is fundamentally harder than evaluating RAG systems or single LLM calls. Without understanding why, you'll either:

- Over-invest in metrics that don't matter
- Miss failure modes that will blow up in production
- Have no systematic way to improve your agent

---

## Why Agents Are Harder to Evaluate Than Single LLM Calls

### 1. Non-Determinism at Multiple Levels

A single LLM call has one source of non-determinism: the model output. An agent has compounding non-determinism:

```
User Query → LLM Decision 1 → Tool Call 1 → LLM Decision 2 → Tool Call 2 → ...
              ↓ variance        ↓ variance      ↓ variance
```

Even with temperature=0, small variations in early decisions cascade through the trajectory. The same input can produce completely different paths to (potentially) the same answer.

**Why this matters:** You can't evaluate an agent once and trust the result. You need to run the same test multiple times and look at distributions, not single outcomes.

### 2. Multi-Step Failures Are Hard to Localize

When a RAG system fails, you know where to look:

- Bad retrieval? → Check the chunks
- Bad generation? → Check the prompt

When an agent fails, the failure could be at any step:

- Did it pick the wrong tool?
- Did it pass wrong arguments to the right tool?
- Did it misinterpret tool output?
- Did it stop too early or loop forever?
- Did an external tool fail, and the agent didn't handle it?

**Why this matters:** A simple pass/fail metric tells you almost nothing. You need trajectory-level visibility to debug and improve.

### 3. Tool Interactions Create External Dependencies

Single LLM calls are hermetic—you control all inputs. Agents interact with external systems:

- APIs that return different data over time
- Tools that can fail, timeout, or return errors
- Real-world state that changes between runs

**Why this matters:** Your agent might fail because your tool failed, not because your agent logic is wrong. You need to distinguish tool errors from agent errors.

### 4. Success Is Subjective and Context-Dependent

For a single LLM call: "Is the output correct?" is often answerable.

For an agent:

- Did it _complete_ the task? (partial credit?)
- Did it complete it _correctly_? (how do you verify?)
- Did it complete it _efficiently_? (does it matter?)
- Was the _path_ reasonable? (even if the answer is right?)
- Would a human accept this behavior? (subjective)

**Why this matters:** You need multi-dimensional evaluation. A single score collapses too much information.

---

## The Three Evaluation Levels

Based on the Langfuse agent evaluation framework and recent literature, there are three complementary levels at which you can evaluate an agent:

### Level 1: Final Output Evaluation (Black-Box)

**What it measures:** Did the agent produce the right answer?

**How it works:** Treat the agent as a black box. Give it input, compare output to expected output.

```
┌─────────────────────────────────────────┐
│                  AGENT                   │
│            (black box)                   │
│                                         │
│  Input ───────────────────────► Output  │
│                                    │     │
│                                    ▼     │
│                              Expected?   │
└─────────────────────────────────────────┘
```

**Pros:**

- Simplest to implement
- Works with any agent framework
- Most aligned with what users care about

**Cons:**

- Cannot tell you _why_ a failure occurred
- Cannot distinguish lucky correct answers from correct reasoning
- Misses trajectory quality entirely

**When to use:** Always use this as a baseline. It's the minimum viable evaluation.

### Level 2: Trajectory Evaluation (Glass-Box)

**What it measures:** Did the agent take the right path to get there?

**How it works:** Record the sequence of actions (tool calls, decisions, reasoning). Compare to expected trajectory or use LLM-as-judge to assess reasonableness.

```
┌─────────────────────────────────────────┐
│                  AGENT                   │
│                                         │
│  Input ─┬─► Decision 1 ─► Decision 2 ─► Output
│         │        │             │           │
│         │        ▼             ▼           │
│         └─► Trajectory: [D1, D2, D3, ...]  │
│                        │                    │
│                        ▼                    │
│               Expected/Reasonable?          │
└─────────────────────────────────────────────┘
```

**Pros:**

- Pinpoints where in the trajectory failure occurred
- Can evaluate trajectory quality even when final answer is correct
- Catches inefficient or dangerous paths that happen to work

**Cons:**

- Requires trajectory logging infrastructure
- Multiple valid trajectories for the same task (strict matching fails)
- LLM-as-judge for trajectories is expensive

**When to use:** Add this when you need to debug failures or care about how the agent behaves, not just what it produces.

### Level 3: Single Step Evaluation (White-Box)

**What it measures:** Was each individual decision correct?

**How it works:** Unit test each decision point in isolation. Given context X, did the agent make correct choice Y?

```
┌─────────────────────────────────────────┐
│              SINGLE STEP                 │
│                                         │
│  Context: [prior actions, current state] │
│                     │                    │
│                     ▼                    │
│              Agent Decision              │
│                     │                    │
│                     ▼                    │
│           Expected action/tool?          │
└─────────────────────────────────────────┘
```

**Pros:**

- Most granular—identifies exact decision failures
- Fast to run (no full agent execution)
- Can validate tool selection and argument generation in isolation

**Cons:**

- Doesn't test the full interaction loop
- Requires maintaining step-level ground truth
- Can miss emergent failures from step combinations

**When to use:** Add this when you've localized failures to specific decision points and want to iterate quickly on those decisions.

---

## What Dimensions to Measure

Beyond the three levels, you need to decide _what aspects_ of agent behavior matter. Here are the core dimensions:

### 1. Task Completion

The most basic question: did the agent finish the job?

|Metric|What It Measures|
|---|---|
|**Completion Rate**|Did the agent reach a terminal state (not stuck, not crashed)?|
|**Correctness**|Is the final output actually correct?|
|**Partial Credit**|For complex tasks, what fraction of sub-goals were achieved?|

**Example evaluation question:** "Book a meeting with John for Friday at 2pm" → Is there a meeting on John's calendar for Friday at 2pm?

### 2. Efficiency

Two agents might both succeed, but one uses 50 tool calls and the other uses 3. Efficiency matters for:

- Cost (more LLM calls = more tokens = more money)
- Latency (users don't want to wait)
- Resource usage (API rate limits, compute)

|Metric|What It Measures|
|---|---|
|**Step Count**|How many actions did the agent take?|
|**Token Usage**|How many input/output tokens were consumed?|
|**Wall Clock Time**|How long did the full execution take?|
|**Redundant Actions**|Did the agent repeat the same tool call unnecessarily?|

### 3. Tool Use Accuracy

Agents are only as good as their tool usage. This dimension breaks down into:

|Metric|What It Measures|
|---|---|
|**Tool Selection**|Did the agent choose the right tool for the job?|
|**Argument Correctness**|Did it pass valid, correct arguments?|
|**Error Handling**|When a tool failed, did the agent recover appropriately?|
|**Tool Sequence**|Did it call tools in a sensible order?|

**Why separate from task completion:** An agent can get the right answer despite using the wrong tools (luck), or use all the right tools but still fail (bad synthesis). You want to measure both.

### 4. Safety and Guardrails

In production, an agent that completes tasks but occasionally does dangerous things is worse than one that fails safely.

|Metric|What It Measures|
|---|---|
|**Dangerous Action Attempts**|Did the agent try to do something forbidden?|
|**Guardrail Compliance**|Did it respect configured limits (max steps, allowed tools, etc.)?|
|**Appropriate Escalation**|When uncertain, did it ask for human input?|
|**Data Handling**|Did it expose or misuse sensitive information?|

### 5. Trajectory Quality

Even when the outcome is correct, the path matters.

|Metric|What It Measures|
|---|---|
|**Reasonableness**|Would a human expert take a similar path?|
|**No Backtracking**|Did the agent avoid unnecessary loops or reversals?|
|**Progressive Progress**|Did each step move closer to the goal?|
|**Coherent Reasoning**|Did the agent's explanations match its actions?|

---

## The Agent GPA Framework

A recent framework from Snowflake AI Research (October 2025) provides a structured way to think about agent evaluation. The **Agent GPA (Goal-Plan-Action)** framework decomposes evaluation into five metrics aligned with how agents actually operate:

```
        ┌─────────────────────────────────────────────────────────┐
        │                    AGENT OPERATION                       │
        │                                                          │
        │   ┌──────────┐     ┌──────────┐     ┌──────────┐        │
        │   │   GOAL   │────►│   PLAN   │────►│  ACTION  │        │
        │   └──────────┘     └──────────┘     └──────────┘        │
        │        │                │                │               │
        │        ▼                ▼                ▼               │
        │  Goal Fulfillment  Plan Quality    Plan Adherence       │
        │                    Logical         Execution             │
        │                    Consistency     Efficiency            │
        └─────────────────────────────────────────────────────────┘
```

### The Five GPA Metrics

|Metric|Question It Answers|Phase|
|---|---|---|
|**Goal Fulfillment**|Did the final outcome satisfy the user's goal?|Goal|
|**Plan Quality**|Are the agent's plans well-aligned with its goals?|Plan|
|**Logical Consistency**|Is each step grounded in prior context and reasoning?|Plan/Action|
|**Plan Adherence**|Did the agent's actions follow its stated plan?|Action|
|**Execution Efficiency**|Did the agent achieve the goal without wasted steps?|Action|

### Why GPA Is Useful

1. **Covers diverse failure modes:** The framework systematically captures different types of agent failures—from goal misunderstanding to plan drift to execution errors.
    
2. **Localizes errors:** When an agent fails, GPA tells you _where_ in the goal-plan-action loop the failure occurred.
    
3. **Reference-free evaluation:** Most GPA metrics can be computed using LLM-as-judge without requiring ground-truth trajectories.
    
4. **Actionable feedback:** Each metric points to a specific improvement:
    
    - Low Goal Fulfillment → Better goal understanding/clarification
    - Low Plan Quality → Better planning prompts/reasoning
    - Low Logical Consistency → Better context management
    - Low Plan Adherence → Better execution control
    - Low Execution Efficiency → Better tool selection/orchestration

### GPA in Practice

The framework achieves ~95% error detection rate in empirical studies, with ~86% accuracy in localizing which step caused the error. This is significantly better than outcome-only evaluation.

**Key insight:** Logical Consistency serves as a strong proxy for overall success. Agents that maintain coherent reasoning throughout their trajectory are more likely to succeed, even without comparing against ground-truth trajectories.

---

## Evaluation Approaches in Practice

### 1. Task-Based Evaluation (Outcome-Focused)

Define tasks with known correct outcomes. Run the agent. Check if outcome matches.

**Good for:** Baseline success rate, regression testing **Limitation:** Doesn't tell you why failures happen

### 2. Trajectory Evaluation (Process-Focused)

Record the sequence of actions. Compare to reference trajectories or use LLM-as-judge.

**Good for:** Debugging, understanding agent behavior **Limitation:** Multiple valid trajectories exist; strict matching is too brittle

**Trajectory matching modes (from agentevals library):**

- `strict`: Exact match required
- `unordered`: Same actions, any order
- `subset`: Agent trajectory contains expected actions
- `superset`: Expected trajectory is subset of agent trajectory

### 3. Component Evaluation (Unit-Test Style)

Test tool selection, argument generation, and decision-making in isolation.

**Good for:** Fast iteration on specific decisions **Limitation:** Doesn't test the full loop

### 4. Adversarial Evaluation (Stress-Testing)

Try to break the agent with edge cases, malformed inputs, conflicting instructions.

**Good for:** Finding failure modes before production **Limitation:** Hard to be exhaustive; requires creativity

---

## Key Takeaways

1. **Agent evaluation is multi-dimensional.** A single pass/fail score is insufficient. You need to measure completion, efficiency, tool use, safety, and trajectory quality.
    
2. **Three evaluation levels serve different purposes:**
    
    - Black-box (final output) → "Did it work?"
    - Glass-box (trajectory) → "Why did it fail?"
    - White-box (single step) → "Which decision was wrong?"
3. **Use the Agent GPA framework to localize failures.** Goal Fulfillment, Plan Quality, Logical Consistency, Plan Adherence, and Execution Efficiency give you actionable signals for improvement.
    
4. **Non-determinism requires statistical evaluation.** Run tests multiple times. Look at distributions, not single outcomes.
    
5. **Start with outcome evaluation, add trajectory evaluation when debugging.** Don't over-engineer your eval infrastructure before you know where the problems are.
    

---

## References

- Langfuse Agent Evaluation Guide: https://langfuse.com/guides/cookbook/example_pydantic_ai_mcp_agent_evaluation
- Agent GPA Paper (Jia et al., 2025): https://arxiv.org/abs/2510.08847
- LangSmith Agent Evaluation: https://www.langchain.com/langsmith/evaluation
- agentevals library: https://github.com/langchain-ai/agentevals
- Agent-as-a-Judge Framework (Zhuge et al., 2025): https://arxiv.org/html/2508.02994v1