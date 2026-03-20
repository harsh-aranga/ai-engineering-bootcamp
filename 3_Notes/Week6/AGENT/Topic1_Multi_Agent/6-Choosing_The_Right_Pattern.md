# Note 6: Choosing the Right Pattern — Decision Framework

> **Week 6 Agent Track — Days 1-2**  
> **Focus:** When to use which multi-agent pattern, and when to avoid multi-agent entirely

---

## The Most Important Question: Do You Need Multi-Agent?

Before choosing between supervisor, swarm, or custom patterns, ask: **Do you actually need multi-agent at all?**

Most production AI systems don't use multi-agent architectures. They use a single, well-designed agent. Multi-agent adds complexity, cost, and failure modes. It's justified only when single-agent approaches have demonstrably failed.

### The Single-Agent-First Rule

**Start with a single agent. Add agents only when metrics prove the need.**

This isn't about being conservative — it's about engineering discipline. Multi-agent systems are harder to:

- Debug (which agent caused the failure?)
- Monitor (latency distributed across agents)
- Maintain (changes ripple across agent boundaries)
- Cost-optimize (each agent = more LLM calls)

### When Single Agent Works

A single agent handles most tasks well when:

- Tool count is manageable (< 10-12 tools)
- Tasks are similar in nature (all research, all coding, all writing)
- Context stays bounded (conversations don't exceed 10-15 turns)
- Quality is acceptable (> 90% success rate on your metrics)

### When You've Outgrown Single Agent

Multi-agent becomes necessary when you observe **specific, measurable failures**:

|Failure Pattern|Evidence|Multi-Agent Solution|
|---|---|---|
|Tool confusion|Agent picks wrong tool > 20% of the time|Split tools across specialist agents|
|Context overflow|Truncation errors, lost information|Agents with isolated contexts|
|Persona conflicts|Inconsistent tone/behavior|Separate agents for different modes|
|Quality degradation|Complex tasks fail > 30% of the time|Specialized experts + orchestration|
|Workflow violations|Steps skipped or misordered|Explicit control flow via graph|

**If you can't point to a specific, measured failure, you probably don't need multi-agent.**

---

## Decision Tree: Task Characteristics → Pattern

Once you've confirmed multi-agent is needed, use this decision tree:

```
START: You need multi-agent
│
├─► Q1: Do tasks have a clear sequence or hierarchy?
│   │
│   ├─► YES: Tasks flow A → B → C, or one "boss" delegates
│   │   │
│   │   └─► Q2: Is routing complex enough to need an LLM?
│   │       │
│   │       ├─► YES: Use SUPERVISOR pattern
│   │       │   (LLM decides who handles what)
│   │       │
│   │       └─► NO: Use EXPLICIT WORKFLOW (custom graph)
│   │           (Fixed edges, no routing LLM)
│   │
│   └─► NO: Agents collaborate as peers
│       │
│       └─► Q3: Is latency critical?
│           │
│           ├─► YES: Use SWARM pattern
│           │   (No supervisor overhead, direct handoffs)
│           │
│           └─► NO: Consider SUPERVISOR anyway
│               (More control, easier debugging)
│
└─► Q4: Do you need hybrid behavior?
    │
    └─► YES: Use CUSTOM GRAPH
        (Combine patterns as needed)
```

---

## Pattern Comparison: When Each Wins

### Supervisor Pattern

**Use when:**

- Clear task decomposition needed (break complex requests into subtasks)
- Quality control required (supervisor reviews before proceeding)
- Heterogeneous agents (research agent, math agent, writing agent — different capabilities)
- Audit requirements (need to log routing decisions)
- Human-in-the-loop (supervisor is natural checkpoint)

**Avoid when:**

- Latency is critical (supervisor adds routing LLM call every hop)
- Simple, predictable workflows (overhead not worth it)
- Agents need to collaborate directly (supervisor bottlenecks peer interaction)

**Performance profile:**

- LLM calls: 2N+1 for N-agent task (supervisor + each agent + final synthesis)
- Latency: Higher due to routing decisions
- Control: High — supervisor enforces workflow

### Swarm Pattern

**Use when:**

- Real-time conversations (chatbots, support systems)
- Dynamic, unpredictable routing (user might ask anything)
- Latency sensitive (eliminating supervisor saves ~40% LLM calls)
- Persona-based systems (user talks to "Bob" then "Alice")
- Resumable conversations (active_agent tracking)

**Avoid when:**

- Strict workflow enforcement needed (agents might skip steps)
- Quality gates required (no checkpoint between agents)
- Debugging is priority (distributed routing is harder to trace)

**Performance profile:**

- LLM calls: N for N-agent task (no separate routing)
- Latency: Lower — no routing overhead
- Control: Lower — agents self-organize

### Custom Graph (Explicit Workflow)

**Use when:**

- Fixed sequence: A → B → C (no routing decisions needed)
- Conditional exits only (quality gates, error handling)
- Hybrid patterns (supervisor + peer within teams)
- Hierarchical teams (subgraphs as agents)
- Maximum control needed

**Avoid when:**

- Routing is genuinely dynamic (hard to pre-define edges)
- Rapid prototyping (higher implementation overhead)

**Performance profile:**

- LLM calls: Exactly what you design
- Latency: Minimal overhead (no routing LLM)
- Control: Maximum — you define everything

---

## Performance Comparison: Hard Numbers

Let's compare patterns on a concrete task: "Research X, analyze the data, write a summary."

### Single Agent (Baseline)

```
User → Agent (1 LLM call) → tool calls → Agent (1 LLM call) → Response
```

- **LLM calls:** 2-3 (depending on tool use)
- **Latency:** ~2-4 seconds
- **Cost:** $0.01-0.03 (GPT-4o pricing)

### Supervisor Pattern (3 Agents)

```
User → Supervisor (routing) → Research Agent → Supervisor (routing)
     → Analysis Agent → Supervisor (routing) → Writer Agent
     → Supervisor (synthesis) → Response
```

- **LLM calls:** 7-9 (4 supervisor + 3 workers, each may use tools)
- **Latency:** ~8-15 seconds
- **Cost:** $0.05-0.10

### Swarm Pattern (3 Agents)

```
User → Research Agent (works + hands off) → Analysis Agent (works + hands off)
     → Writer Agent (works + responds) → Response
```

- **LLM calls:** 3-5 (each agent, no separate router)
- **Latency:** ~4-8 seconds
- **Cost:** $0.02-0.05

### Summary Table

|Pattern|LLM Calls|Latency|Cost|Control|
|---|---|---|---|---|
|Single Agent|2-3|~2-4s|$0.01-0.03|Medium|
|Supervisor|7-9|~8-15s|$0.05-0.10|High|
|Swarm|3-5|~4-8s|$0.02-0.05|Low|
|Custom (fixed)|3-4|~3-6s|$0.02-0.04|Maximum|

**Key insight:** Supervisor costs ~3x single agent. Is that quality improvement worth 3x? Usually only for complex, high-stakes tasks.

---

## Complexity Assessment Checklist

Before committing to multi-agent, score your situation:

### Signs You Need Multi-Agent (+1 each)

- [ ] Single agent fails > 25% on your task type
- [ ] You have > 12 tools and agent confuses them
- [ ] Tasks require genuinely different expertise (research vs. coding vs. analysis)
- [ ] Workflow has strict ordering requirements
- [ ] Quality gates needed between steps
- [ ] Different personas for different contexts
- [ ] Context regularly exceeds 15,000 tokens

### Signs You Don't Need Multi-Agent (-1 each)

- [ ] Single agent succeeds > 85% of the time
- [ ] Tasks are homogeneous (all similar type)
- [ ] You have < 8 tools
- [ ] Latency is critical (user-facing, real-time)
- [ ] Team lacks multi-agent debugging experience
- [ ] Rapid iteration is priority
- [ ] Cost is a major constraint

**Score:**

- **+3 or higher:** Multi-agent likely justified
- **0 to +2:** Consider improving single agent first
- **Negative:** Stick with single agent

---

## Starting Simple: The Progressive Complexity Path

Don't jump to multi-agent. Follow this progression:

### Level 1: Improve Single Agent

Before adding agents, try:

1. **Better prompts:** Clearer instructions, few-shot examples
2. **Tool optimization:** Better descriptions, reduce tool count
3. **Context management:** Summarization, trimming, structured output
4. **Conditional logic:** Route within agent based on task type

### Level 2: Explicit Workflow (No Routing LLM)

If single agent isn't enough:

1. **Fixed sequence:** Research → Analyze → Write
2. **Quality gates:** If quality < threshold, retry
3. **Conditional exits:** Different paths for different inputs

This gets multi-agent benefits without routing overhead.

### Level 3: Supervisor Pattern

If you need dynamic routing:

1. **LLM-based routing:** Supervisor decides who handles what
2. **Quality control:** Supervisor reviews outputs
3. **Complex orchestration:** Multi-step with dependencies

### Level 4: Swarm or Custom Hybrid

If supervisor is too slow or rigid:

1. **Swarm:** For real-time, dynamic conversations
2. **Hybrid:** Supervisor for high-level, swarm within teams
3. **Custom:** When no library pattern fits

**Never skip levels.** Each level adds complexity. Justify the jump with measured failures at the current level.

---

## Combining Patterns: Hybrid Architectures

Real production systems often combine patterns.

### Pattern: Supervisor + Peer Teams

```
                    ┌─────────────────┐
                    │   SUPERVISOR    │
                    │  (routes tasks) │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                                 ▼
     ┌─────────────────────────────┐   ┌─────────────┐
     │       RESEARCH TEAM         │   │    CODING   │
     │  (swarm: search ↔ analyze)  │   │    AGENT    │
     └─────────────────────────────┘   └─────────────┘
```

- **Supervisor:** Routes between teams/agents
- **Research Team:** Internal swarm for peer collaboration
- **Coding Agent:** Standalone, no internal complexity

**When to use:** Different sub-tasks have different collaboration needs.

### Pattern: Swarm with Quality Checkpoints

```
Agent A ──► Agent B ──► Quality Gate ──► Agent C
    ▲                        │
    └────── (if reject) ─────┘
```

- **Swarm:** Agents hand off directly
- **Quality Gate:** Explicit checkpoint node (not an agent)
- **Retry Logic:** Failed quality sends back for revision

**When to use:** Want swarm latency but need quality control.

### Pattern: Hierarchical Supervisors

```
                    ┌─────────────────┐
                    │ TOP SUPERVISOR  │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                                 ▼
     ┌─────────────────┐             ┌─────────────────┐
     │ RESEARCH SUPER  │             │ WRITING SUPER   │
     └────────┬────────┘             └────────┬────────┘
              │                               │
       ┌──────┴──────┐                 ┌──────┴──────┐
       ▼             ▼                 ▼             ▼
    Search        Analyze           Draft          Edit
```

- **Top Supervisor:** Routes to team supervisors
- **Team Supervisors:** Manage their specialists
- **Workers:** Execute specific tasks

**When to use:** Very complex workflows with distinct domains.

---

## Red Flags: Signs of Over-Engineering

### Red Flag 1: Adding Agents Without Measured Need

"Let's add a review agent for quality!"

**Ask:** What's the current failure rate? If it's 5%, is adding an agent (with its cost and latency) worth marginal improvement?

### Red Flag 2: Premature Multi-Agent

"We should design for scale from the start!"

**Reality:** Most projects never reach the scale where multi-agent matters. Start simple, measure, then add complexity.

### Red Flag 3: Too Many Agents

"We have 12 specialized agents!"

**Problem:** Each agent boundary is a potential failure point. More agents = more:

- Communication overhead
- Context loss at handoffs
- Debugging complexity
- Latency

**Rule of thumb:** If you have > 5-6 agents, question whether some should merge.

### Red Flag 4: Agents for Simple Tasks

"This agent just formats the output."

**Better:** A function. Not everything needs an LLM. If the task is deterministic, use code.

### Red Flag 5: Copying Architectures Without Understanding

"OpenAI uses multi-agent, so should we!"

**Reality:** Your task isn't their task. Design for your specific requirements.

---

## LangChain's Current Recommendation

**From LangGraph Supervisor documentation (2025):**

> "We now recommend using the **supervisor pattern directly via tools** rather than this library for most use cases. The tool-calling approach gives you more control over context engineering."

### What This Means

The library (`langgraph-supervisor`) is a convenience wrapper. For production systems, LangChain recommends:

1. **Build the graph yourself:** More control over state, routing, context
2. **Use tool calling for handoffs:** Agent's tools include "hand off to X"
3. **Manage context explicitly:** Don't rely on library defaults

### The Manual Supervisor Pattern

Instead of `create_supervisor()`:

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command

def supervisor_node(state) -> Command[Literal["research", "math", END]]:
    # Your custom routing logic
    decision = route_with_full_control(state)
    return Command(goto=decision, update={...})

def research_node(state) -> Command[Literal["supervisor"]]:
    result = research_agent.invoke(state)
    return Command(goto="supervisor", update={"messages": result["messages"]})

# Build explicitly
graph = StateGraph(MessagesState)
graph.add_node("supervisor", supervisor_node)
graph.add_node("research", research_node)
graph.add_node("math", math_node)
graph.add_edge(START, "supervisor")
# ... etc
```

**Benefits:**

- Full control over context (what each agent sees)
- Custom routing logic (not just LLM-based)
- Explicit state management
- Easier debugging (you wrote it, you understand it)

---

## Decision Checklist: Before You Build

Before implementing multi-agent, answer these:

### Requirements

- [ ] What specific failure am I solving?
- [ ] What's my current single-agent success rate?
- [ ] What success rate do I need?
- [ ] What latency can I tolerate?
- [ ] What's my cost budget per query?

### Design

- [ ] How many agents do I actually need?
- [ ] What are the clear boundaries between them?
- [ ] What state needs to be shared vs. private?
- [ ] What routing logic is required?
- [ ] What are my quality checkpoints?

### Validation

- [ ] How will I know if multi-agent is working?
- [ ] What metrics will I track?
- [ ] How will I debug failures?
- [ ] What's my rollback plan?

---

## Quick Reference: Pattern Selection

|Situation|Pattern|Why|
|---|---|---|
|Single agent works > 85%|**None**|Don't add complexity|
|Need strict A → B → C|**Explicit workflow**|No routing overhead|
|Need dynamic routing + quality control|**Supervisor**|LLM routing + checkpoints|
|Real-time chat, latency critical|**Swarm**|No routing overhead|
|Different sub-tasks need different patterns|**Hybrid**|Combine as needed|
|No library pattern fits|**Custom graph**|Full control|

---

## Key Takeaways

1. **Start with single agent.** Multi-agent is the exception, not the rule. Add complexity only when metrics prove need.
    
2. **Measure before deciding.** "We need multi-agent" isn't a decision — it's a hypothesis. Test it with failure rates, latency, and cost.
    
3. **Supervisor costs ~3x single agent.** Every routing decision is an LLM call. Budget for it.
    
4. **Swarm trades control for speed.** ~40% fewer LLM calls, but harder to enforce workflows.
    
5. **Build explicitly when it matters.** Libraries are conveniences. Production systems often need manual graphs for full control.
    
6. **Red flags exist.** Too many agents, premature complexity, and copying architectures are common mistakes.
    
7. **LangChain's recommendation:** Tool-calling approach gives more control. Consider manual implementation for production.
    

---

## References

**Documentation referenced for this note:**

- LangGraph Supervisor README: "We now recommend using the supervisor pattern directly via tools..."
- LangGraph concepts: Multi-agent patterns
- LangChain Blog: "LangGraph: Multi-Agent Workflows"

**Patterns covered in this module:**

- Note 1: Why Multi-Agent (failure modes)
- Note 2: Supervisor Pattern (hierarchical orchestration)
- Note 3: Swarm Pattern (decentralized handoffs)
- Note 4: Custom Workflows (building without libraries)
- Note 5: Inter-Agent Communication (state management)