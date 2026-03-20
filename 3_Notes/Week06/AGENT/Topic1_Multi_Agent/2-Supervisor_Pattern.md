# Note 2: Supervisor Pattern — Hierarchical Orchestration

> **Week 6 Agent Track — Days 1-2**  
> **Focus:** The supervisor pattern for coordinating specialized worker agents

---

## Mental Model: The Team Lead

The supervisor pattern mirrors how human teams work:

```
                    ┌─────────────────┐
                    │   SUPERVISOR    │
                    │  (Team Lead)    │
                    │                 │
                    │ • Receives task │
                    │ • Decides who   │
                    │ • Synthesizes   │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │  Research   │  │   Math      │  │   Writing   │
     │   Agent     │  │   Agent     │  │   Agent     │
     │             │  │             │  │             │
     │ Tools:      │  │ Tools:      │  │ Tools:      │
     │ • search    │  │ • calculate │  │ • (none)    │
     │ • scrape    │  │ • solve     │  │             │
     └─────────────┘  └─────────────┘  └─────────────┘
```

**Key characteristics:**

- **One supervisor, many workers:** Supervisor controls all routing decisions
- **Workers don't talk to each other:** All communication flows through supervisor
- **Workers report back:** After completing work, control returns to supervisor
- **Supervisor synthesizes:** Final output comes from supervisor, not workers

This is a **hierarchical** architecture — there's a clear chain of command.

---

## The `langgraph-supervisor` Library

LangGraph provides a dedicated library for this pattern:

```bash
pip install langgraph-supervisor
```

**Important context from LangChain team (2025):** They now recommend using the supervisor pattern directly via tools for most use cases, as it gives more control over context engineering. The library is being maintained for compatibility with LangChain 1.0, but the manual approach (building the graph yourself) is often preferable for production systems.

That said, the library is excellent for learning the pattern and for simpler use cases.

---

## Core Implementation

### Basic Supervisor Setup

**Reference:** GitHub langchain-ai/langgraph-supervisor-py (current as of 2025)

```python
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

model = ChatOpenAI(model="gpt-4o")

# Define tools for each worker
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

def web_search(query: str) -> str:
    """Search the web for information."""
    return "Search results for: " + query

# Create specialized worker agents
math_agent = create_react_agent(
    model=model,
    tools=[add, multiply],
    name="math_expert",  # Name is critical — supervisor uses this to route
    prompt="You are a math expert. Always use one tool at a time."
)

research_agent = create_react_agent(
    model=model,
    tools=[web_search],
    name="research_expert",
    prompt="You are a researcher with web search access. Do not do math."
)

# Create supervisor workflow
workflow = create_supervisor(
    [research_agent, math_agent],  # List of worker agents
    model=model,                    # LLM for supervisor decisions
    prompt=(
        "You are a team supervisor managing a research expert and a math expert. "
        "For current events, use research_expert. "
        "For math problems, use math_expert."
    )
)

# Compile and run
app = workflow.compile()
result = app.invoke({
    "messages": [
        {"role": "user", "content": "What's 25 * 47?"}
    ]
})
```

### What Happens Under the Hood

When you invoke this supervisor:

1. **Supervisor receives the message:** "What's 25 * 47?"
    
2. **Supervisor decides routing:** Based on its prompt and the message, it determines `math_expert` should handle this.
    
3. **Supervisor calls handoff tool:** Internally, the supervisor has tools like `transfer_to_math_expert`. It calls this tool to delegate.
    
4. **Worker executes:** `math_expert` receives the conversation, uses the `multiply` tool, returns the result.
    
5. **Control returns to supervisor:** Worker's response is added to message history.
    
6. **Supervisor decides next step:** It can delegate to another agent, or finish and respond to the user.
    
7. **Supervisor produces final output:** The final message to the user comes from the supervisor.
    

---

## Supervisor Responsibilities

The supervisor agent does three things:

### 1. Task Decomposition

For complex requests, the supervisor breaks them into subtasks:

**User:** "Research FAANG company headcounts and calculate the total."

**Supervisor's internal reasoning:**

- This requires two steps: research (get the data) then math (sum it)
- First delegate to `research_expert`
- Then delegate to `math_expert` with the research results
- Finally, synthesize and respond

### 2. Routing Decisions

The supervisor must decide _which_ agent handles _what_. This is controlled by:

- **Supervisor's system prompt:** Describes when to use each agent
- **Agent names and descriptions:** Help the supervisor understand agent capabilities
- **Conversation context:** What has already been done, what remains

Good supervisor prompts are explicit about routing rules:

```python
prompt = """You are a team supervisor managing specialized agents:

- research_expert: Use for any questions requiring web search, current events, 
  or factual lookups. Do NOT use for calculations.
  
- math_expert: Use for arithmetic, calculations, or numeric analysis. 
  Do NOT use for information retrieval.

When a task requires multiple steps:
1. Gather information first (research_expert)
2. Then process/calculate (math_expert)
3. Finally, synthesize the results yourself

Never ask an agent to do work outside its specialty."""
```

### 3. Result Aggregation

After workers complete their tasks, the supervisor:

- Receives all worker outputs in its message history
- Synthesizes them into a coherent final response
- May delegate to additional agents if more work is needed
- Produces the user-facing output

---

## Worker Agent Design

Workers should be **narrow specialists**, not generalists.

### Narrow Tool Sets

Each worker should have 2-5 tools, all within a single domain:

```python
# GOOD: Focused research agent
research_agent = create_react_agent(
    model=model,
    tools=[web_search, scrape_url, search_arxiv],
    name="research_expert",
    prompt="You find and gather information. Never analyze or calculate."
)

# BAD: Kitchen sink agent
everything_agent = create_react_agent(
    model=model,
    tools=[web_search, calculate, send_email, create_document, query_database],
    name="helper",  # Vague name
    prompt="You help with things."  # Vague prompt
)
```

### Focused System Prompts

Worker prompts should emphasize what the agent does AND what it doesn't do:

```python
math_agent = create_react_agent(
    model=model,
    tools=[add, subtract, multiply, divide],
    name="math_expert",
    prompt="""You are a math specialist. Your ONLY job is to perform calculations.

DO:
- Use your calculation tools for any arithmetic
- Show your work step by step
- Return precise numeric results

DO NOT:
- Search for information (you don't have search tools)
- Make assumptions about data you don't have
- Provide explanations beyond the math itself

If you need information you don't have, say so clearly. 
Another agent will provide it."""
)
```

### Worker Names Matter

The supervisor routes based on agent names. Make them descriptive:

```python
# GOOD: Clear, descriptive names
name="math_expert"
name="research_specialist"
name="document_writer"
name="code_reviewer"

# BAD: Vague or confusing names
name="agent1"
name="helper"
name="assistant"
name="worker"
```

---

## Handoff Mechanism

The supervisor delegates to workers using **handoff tools**. By default, `create_supervisor` generates these automatically.

### Default Handoff Tools

For each worker agent, a handoff tool is created:

```python
workflow = create_supervisor(
    [research_agent, math_agent],  # Named "research_expert", "math_expert"
    model=model,
)
# Automatically creates tools: transfer_to_research_expert, transfer_to_math_expert
```

### Customizing Handoff Tool Names

You can customize the prefix:

```python
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    handoff_tool_prefix="delegate_to"
)
# Creates tools: delegate_to_research_expert, delegate_to_math_expert
```

### Custom Handoff Tools

For more control, create custom handoff tools:

```python
from langgraph_supervisor import create_handoff_tool

workflow = create_supervisor(
    [research_agent, math_agent],
    tools=[
        create_handoff_tool(
            agent_name="math_expert", 
            name="assign_to_math_expert",
            description="Assign calculation tasks to the math expert"
        ),
        create_handoff_tool(
            agent_name="research_expert", 
            name="assign_to_research_expert",
            description="Assign research tasks to the research expert"
        )
    ],
    model=model,
)
```

---

## Message History Management

A critical decision: **what does each worker see?**

### The `output_mode` Parameter

Controls how worker messages are added to the shared history:

**Full History Mode (default):**

```python
workflow = create_supervisor(
    agents=[agent1, agent2],
    output_mode="full_history"  # Workers see ALL previous messages
)
```

Workers receive the complete conversation history, including all previous worker outputs. Good for tasks requiring context from earlier steps.

**Last Message Mode:**

```python
workflow = create_supervisor(
    agents=[agent1, agent2],
    output_mode="last_message"  # Only the most recent message
)
```

Workers receive a condensed view. Good for reducing context bloat and keeping workers focused.

### The `add_handoff_messages` Parameter

Controls whether handoff tool invocations appear in history:

```python
# Include handoff messages (default)
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    add_handoff_messages=True  # History includes "transferring to math_expert..."
)

# Exclude handoff messages (cleaner history)
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    add_handoff_messages=False  # Handoff mechanics hidden from workers
)
```

Setting `add_handoff_messages=False` creates a cleaner message history but loses visibility into routing decisions.

---

## Adding Memory (Persistence)

The supervisor workflow is a LangGraph `StateGraph`. Add persistence as you would with any LangGraph:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# Short-term memory (conversation state across turns)
checkpointer = InMemorySaver()

# Long-term memory (cross-conversation knowledge)
store = InMemoryStore()

workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    prompt="You are a team supervisor..."
)

# Compile with memory
app = workflow.compile(
    checkpointer=checkpointer,
    store=store
)

# Use thread_id for conversation continuity
result = app.invoke(
    {"messages": [{"role": "user", "content": "What's 25 * 47?"}]},
    config={"configurable": {"thread_id": "user-123"}}
)
```

---

## Multi-Level Hierarchies

For complex systems, supervisors can manage other supervisors:

```python
# Level 1: Research team
research_team = create_supervisor(
    [search_agent, scrape_agent, summarize_agent],
    model=model,
    supervisor_name="research_supervisor"
).compile(name="research_team")

# Level 1: Writing team
writing_team = create_supervisor(
    [draft_agent, edit_agent, format_agent],
    model=model,
    supervisor_name="writing_supervisor"
).compile(name="writing_team")

# Level 2: Top-level supervisor manages teams
top_supervisor = create_supervisor(
    [research_team, writing_team],
    model=model,
    supervisor_name="project_manager",
    prompt="You manage a research team and a writing team..."
).compile()
```

Each team is encapsulated — the top supervisor doesn't need to know about individual agents within teams.

---

## When Supervisor Pattern Fits

### Good Use Cases

1. **Structured workflows with clear stages:**
    
    - Research → Analysis → Report
    - Data gathering → Processing → Visualization
2. **Quality control requirements:**
    
    - Supervisor can review worker outputs before proceeding
    - Can request re-work if quality is insufficient
3. **Heterogeneous expertise:**
    
    - Different domains with different tool requirements
    - Agents that shouldn't see each other's internal workings
4. **Audit trail needs:**
    
    - Supervisor logs show routing decisions
    - Clear accountability for which agent did what
5. **Human-in-the-loop integration:**
    
    - Supervisor can pause for human approval
    - Natural point for intervention

### Poor Use Cases

1. **Simple tasks:**
    
    - If one agent can handle it, don't add supervisor overhead
2. **Highly parallel work:**
    
    - Supervisor is inherently sequential (decide → delegate → wait → decide)
    - If tasks are independent, consider scatter-gather instead
3. **Peer collaboration:**
    
    - If agents need to debate or iterate with each other
    - Supervisor bottlenecks this communication
4. **Latency-critical applications:**
    
    - Every routing decision is an LLM call
    - Adds 200-500ms+ per delegation

---

## The Latency Trade-Off

Every supervisor decision requires an LLM call. Consider a simple research + calculate task:

**Without supervisor:**

```
User message → Single Agent (1 LLM call) → Tool calls → Response
Total: ~1-2 LLM calls
```

**With supervisor:**

```
User message → Supervisor (LLM call 1: decide routing)
            → Research Agent (LLM call 2: execute)
            → Supervisor (LLM call 3: decide next step)
            → Math Agent (LLM call 4: execute)
            → Supervisor (LLM call 5: synthesize final response)
Total: ~5 LLM calls
```

That's roughly **3x the latency** for a two-step task. For more complex workflows, the overhead compounds.

### Mitigation Strategies

1. **Batch similar tasks:**
    
    - "Research all these topics" as one delegation, not separate calls
2. **Use faster models for routing:**
    
    - Supervisor can use `gpt-4o-mini` for routing decisions
    - Workers use `gpt-4o` for actual work
3. **Pre-plan multi-step tasks:**
    
    - If the task is known to require research then math, skip the intermediate routing check
4. **Accept the trade-off:**
    
    - If accuracy matters more than speed, the overhead is worth it

---

## Common Mistakes

### 1. Supervisor Does Too Much Work

```python
# BAD: Supervisor also does research
prompt = """You are a team supervisor who also does research.
If it's a simple search, do it yourself. Otherwise delegate."""
```

This blurs responsibilities. The supervisor should ONLY route and synthesize.

### 2. Vague Routing Rules

```python
# BAD: Unclear when to use each agent
prompt = "You manage a research agent and a math agent. Use them wisely."
```

Be explicit: "Use research_agent for X, Y, Z. Use math_agent for A, B, C."

### 3. Workers That Overlap

```python
# BAD: Both agents can search
research_agent = create_react_agent(tools=[web_search, ...])
analyst_agent = create_react_agent(tools=[web_search, analyze, ...])
```

Now the supervisor must decide which searcher to use. Keep tool sets disjoint.

### 4. Missing Error Handling

What if a worker fails? The supervisor needs instructions:

```python
prompt = """...
If an agent reports an error or says it cannot complete the task:
1. Try a different agent if appropriate
2. Ask for clarification if the task is ambiguous
3. Report the failure clearly to the user if no agent can help
"""
```

---

## Key Takeaways

1. **Supervisor = router + synthesizer:** It decides who does what and combines results. It doesn't do the actual work.
    
2. **Workers are narrow specialists:** Few tools, focused prompts, clear boundaries.
    
3. **Handoff tools are the mechanism:** Supervisor delegates by calling tools like `transfer_to_agent_name`.
    
4. **Message history management matters:** Use `output_mode` and `add_handoff_messages` to control context.
    
5. **Latency overhead is real:** Every routing decision costs an LLM call. Budget for ~30-50%+ latency increase.
    
6. **Hierarchies can nest:** Supervisors can manage other supervisors for complex organizations.
    

---

## What's Next

- **Note 3:** Network/Collaboration Pattern — when agents need to work together without a central controller
- **Note 4:** Swarm Pattern — dynamic handoffs based on specialization
- **Note 5:** Handoffs Deep Dive — the `Command` object and custom handoff implementations

---

## References

**Documentation referenced for this note:**

- GitHub: langchain-ai/langgraph-supervisor-py (README, current as of March 2025)
- PyPI: langgraph-supervisor v0.0.31
- LangChain Docs: Multi-agent systems (https://docs.langchain.com/oss/python/langchain/multi-agent)

**Key API elements:**

- `create_supervisor()` — main function to create supervisor workflow
- `create_react_agent()` — creates worker agents with ReAct pattern
- `create_handoff_tool()` — creates custom handoff tools
- `output_mode` — controls message history (`"full_history"` or `"last_message"`)
- `add_handoff_messages` — whether handoff tool calls appear in history
- `handoff_tool_prefix` — prefix for auto-generated handoff tools