# Note 5: Inter-Agent Communication and Shared State

> **Week 6 Agent Track — Days 1-2**  
> **Focus:** How agents share information, the context loss problem, and practical state management patterns

---

## The Context Loss Problem

When Agent A hands off to Agent B, something critical happens: **Agent B only knows what Agent A explicitly told it.**

This seems obvious, but the implications are profound:

```
Agent A's Context:
├── Original user request
├── 3 search queries tried
├── 15 search results reviewed
├── Internal reasoning: "Result #7 looks promising because..."
├── 2 dead ends explored
├── Confidence assessment: "Pretty sure, but #3 might contradict"
└── Open questions: "Should verify the 2024 data"

What A sends to B:
└── "Here are the key findings: [summary]"
```

Agent B receives a compressed summary. All of A's reasoning, confidence levels, dead ends, and open questions are lost — unless A explicitly includes them.

### Why This Matters

1. **B makes decisions with incomplete information:** B might re-explore dead ends A already tried.
    
2. **Lost reasoning = lost context:** B doesn't know _why_ A concluded what it did.
    
3. **No confidence signals:** B treats A's uncertain findings the same as A's confident ones.
    
4. **Open questions evaporate:** Things A flagged for verification get forgotten.
    

### The Fundamental Tension

**More context = better decisions, but also = context bloat.**

Pass everything → B's context fills with noise, loses focus.  
Pass too little → B lacks crucial information.

There's no perfect answer — only trade-offs you choose deliberately.

---

## Handoff Payloads: What to Include

When designing handoffs, consider what the receiving agent actually needs.

### Minimal Handoff (Just Results)

```python
def research_node(state):
    result = research_agent.invoke(state)
    
    # Minimal: just the final answer
    return {
        "messages": [
            HumanMessage(
                content=result["messages"][-1].content,
                name="researcher"
            )
        ]
    }
```

**Pros:** Clean context, no noise.  
**Cons:** Loses all reasoning and confidence information.

### Rich Handoff (Structured Payload)

```python
def research_node(state):
    result = research_agent.invoke(state)
    
    # Extract structured information
    findings = extract_findings(result)
    
    # Rich payload
    handoff_message = f"""
## Research Findings

### Key Results
{findings['summary']}

### Confidence Level
{findings['confidence']}/10 — {findings['confidence_reasoning']}

### Sources Used
{findings['sources']}

### Open Questions
{findings['open_questions']}

### Dead Ends (Don't Retry)
{findings['dead_ends']}
"""
    
    return {
        "messages": [
            HumanMessage(content=handoff_message, name="researcher")
        ]
    }
```

**Pros:** Receiving agent has full context.  
**Cons:** Takes up tokens, might overwhelm simple tasks.

### What to Include (Decision Framework)

|Information Type|Include When|Skip When|
|---|---|---|
|**Final result**|Always|Never|
|**Confidence level**|Decision-making downstream|Just passing data|
|**Sources/citations**|Quality matters|Internal processing|
|**Reasoning chain**|Complex decisions|Simple handoffs|
|**Dead ends tried**|Agent might retry|Fresh perspective wanted|
|**Open questions**|Verification needed|Task is complete|

---

## Shared State: The `messages` Channel

In LangGraph multi-agent systems, all agents typically share a single `messages` list. This is the default communication channel.

### How It Works

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class SharedState(TypedDict):
    messages: Annotated[list, add_messages]  # Shared by all agents
```

Every agent:

1. Receives the full message history
2. Adds its responses to the same list
3. Passes the extended list to the next agent

```
Turn 1: User → "Research quantum computing"
        messages = [HumanMessage("Research quantum computing")]

Turn 2: Researcher adds findings
        messages = [HumanMessage("Research..."), AIMessage("Here's what I found...")]

Turn 3: Writer adds draft
        messages = [HumanMessage("Research..."), AIMessage("Here's what I found..."), 
                   AIMessage("Draft article: ...")]
```

### Benefits of Shared Messages

1. **Complete context:** Every agent sees everything that happened before.
2. **Auditability:** Full trace of who said what.
3. **Simple implementation:** One state key, standard reducer.

### Problems with Shared Messages

1. **Context bloat:** Long conversations fill up context windows.
2. **Noise exposure:** Agent B sees Agent A's internal reasoning, which might confuse it.
3. **No privacy:** Can't have "internal" agent thoughts.

---

## Private State: Agent-Specific Keys

When agents need private scratchpads, use separate state keys.

### The Pattern

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class MultiAgentState(TypedDict):
    # Shared communication channel
    messages: Annotated[list, add_messages]
    
    # Private scratchpads
    alice_internal: Annotated[list, add_messages]  # Only Alice uses this
    bob_internal: Annotated[list, add_messages]    # Only Bob uses this
    
    # Shared structured data
    research_findings: dict
    active_agent: str
```

### Implementation

```python
def alice_node(state: MultiAgentState):
    # Alice sees shared messages + her private history
    alice_context = state["messages"] + state.get("alice_internal", [])
    
    # Alice does her work
    result = alice_agent.invoke({"messages": alice_context})
    
    # Separate what's shared vs. private
    internal_reasoning = extract_reasoning(result)
    public_output = extract_final_answer(result)
    
    return {
        # Only final answer goes to shared channel
        "messages": [HumanMessage(content=public_output, name="alice")],
        # Internal reasoning stays private
        "alice_internal": internal_reasoning
    }
```

### When to Use Private State

- **Long reasoning chains:** Agent thinks through 10 steps, only final answer matters.
- **Sensitive information:** Agent accesses data other agents shouldn't see.
- **Avoiding confusion:** Agent A's reasoning might mislead Agent B.
- **Debugging:** Keep internal traces without polluting shared context.

---

## State Schema Transformations

When agents need fundamentally different state schemas, use wrapper functions to transform between them.

### The Problem

```python
# Parent graph state
class OrchestratorState(TypedDict):
    messages: Annotated[list, add_messages]
    task: str
    status: str

# Research agent expects different schema
class ResearchState(TypedDict):
    research_messages: Annotated[list, add_messages]
    search_queries: list[str]
    findings: dict
```

These schemas are incompatible. You can't directly invoke the research agent from the orchestrator.

### The Solution: Wrapper Functions

```python
# Compile research agent with its own schema
research_agent = StateGraph(ResearchState)
# ... build the agent ...
research_compiled = research_agent.compile()

# Wrapper transforms parent state → agent state → parent state
def call_research_agent(state: OrchestratorState) -> dict:
    # INPUT TRANSFORMATION: Parent → Agent
    agent_input = {
        "research_messages": state["messages"],
        "search_queries": extract_queries(state["messages"][-1]),
        "findings": {}
    }
    
    # Invoke agent with its native schema
    result = research_compiled.invoke(agent_input)
    
    # OUTPUT TRANSFORMATION: Agent → Parent
    return {
        "messages": [
            HumanMessage(
                content=summarize_findings(result["findings"]),
                name="researcher"
            )
        ],
        "status": "research_complete"
    }

# Add wrapper as node in parent graph
orchestrator.add_node("research", call_research_agent)
```

### Key Points

1. **Agent keeps its native schema:** No need to redesign agents for orchestration.
2. **Transformation is explicit:** You control exactly what crosses boundaries.
3. **Information filtering:** Output transformation can summarize, not just pass through.
4. **Enables heterogeneous teams:** Agents built at different times with different schemas can work together.

---

## State Explosion: The Context Bloat Trap

As multi-agent conversations grow, state accumulates. This causes real problems.

### How State Explodes

```
Turn 1: 500 tokens (user message)
Turn 2: +1,200 tokens (research agent's findings)
Turn 3: +800 tokens (analyst agent's commentary)
Turn 4: +2,000 tokens (writer agent's draft)
Turn 5: +500 tokens (reviewer agent's feedback)
Turn 6: +2,500 tokens (writer agent's revision)
Turn 7: +300 tokens (reviewer agent's approval)
...

Total after 7 turns: ~7,800 tokens
```

And this is a simple workflow. Complex multi-agent systems can hit 50,000+ tokens quickly.

### Problems from State Explosion

1. **Context window limits:** Hit the model's maximum, get truncation or errors.
2. **Lost-in-the-middle:** Important information buried in the middle gets less attention.
3. **Cost:** More tokens = more money.
4. **Latency:** Processing more tokens takes longer.
5. **Confusion:** Too much context overwhelms the agent's focus.

### Mitigation Strategies

#### 1. Summary Handoffs (Instead of Full History)

```python
def research_node(state):
    result = research_agent.invoke(state)
    
    # Instead of passing all messages...
    # ...generate a summary
    summary = summarize_agent.invoke({
        "messages": [
            HumanMessage(
                content=f"Summarize these findings in 200 words:\n{result['messages'][-1].content}"
            )
        ]
    })
    
    return {"messages": [HumanMessage(content=summary, name="researcher")]}
```

**Trade-off:** Loses detail but keeps context manageable.

#### 2. Message Trimming

```python
from langchain_core.messages import trim_messages

def agent_node(state):
    # Trim to last N messages or N tokens
    trimmed = trim_messages(
        state["messages"],
        max_tokens=4000,
        token_counter=len,  # Or use tiktoken for accuracy
        strategy="last"  # Keep most recent
    )
    
    result = agent.invoke({"messages": trimmed})
    return {"messages": result["messages"]}
```

**Trade-off:** Loses old context but prevents overflow.

#### 3. Selective Context (Pass Only What's Needed)

```python
def writer_node(state):
    # Writer only needs the research summary, not the full history
    research_summary = state.get("research_findings", {}).get("summary", "")
    
    writer_context = [
        SystemMessage(content="You are a writer. Create content based on the research provided."),
        HumanMessage(content=f"Research summary:\n{research_summary}\n\nWrite a blog post.")
    ]
    
    result = writer_agent.invoke({"messages": writer_context})
    return {"messages": result["messages"]}
```

**Trade-off:** Agent has fresh context but might miss relevant history.

#### 4. Structured State (Not Just Messages)

```python
class StructuredState(TypedDict):
    messages: Annotated[list, add_messages]  # Keep minimal
    
    # Structured data that doesn't bloat
    research_summary: str           # 200 tokens, not 2000
    key_facts: list[str]           # Bullet points
    confidence_scores: dict        # {"finding_1": 0.9, ...}
    open_questions: list[str]      # Things to verify
```

**Trade-off:** Requires explicit structure but highly efficient.

---

## Practical Patterns

### Pattern 1: Full History Handoff

All messages pass between agents unchanged.

```python
def agent_node(state):
    result = agent.invoke(state)
    return {"messages": result["messages"]}
```

**Best for:**

- Short workflows (< 10 turns)
- When context continuity is critical
- Debugging (full trace available)

**Avoid when:**

- Long conversations
- Many agents (context explodes)
- Sensitive internal reasoning

### Pattern 2: Summary Handoff

Each agent summarizes before passing.

```python
def agent_node(state):
    result = agent.invoke(state)
    
    # Summarize for next agent
    summary = f"I completed X. Key findings: Y. Next step: Z."
    
    return {
        "messages": [HumanMessage(content=summary, name="agent")]
    }
```

**Best for:**

- Long workflows
- Many specialized agents
- When details don't matter downstream

**Avoid when:**

- Downstream needs full reasoning
- Quality assessment required (need to see work)

### Pattern 3: Structured Handoff

Use non-message state for handoffs.

```python
class WorkflowState(TypedDict):
    messages: Annotated[list, add_messages]
    current_task: str
    research_output: dict  # Structured, not messages
    analysis_output: dict
    final_output: str

def research_node(state):
    result = research_agent.invoke(state)
    
    # Parse structured output
    findings = parse_findings(result["messages"][-1].content)
    
    return {
        "research_output": findings,  # Structured data
        "messages": [HumanMessage(content="Research complete.", name="researcher")]
    }

def analysis_node(state):
    # Read structured data, not message history
    findings = state["research_output"]
    
    analysis = analyze(findings)
    
    return {
        "analysis_output": analysis,
        "messages": [HumanMessage(content="Analysis complete.", name="analyst")]
    }
```

**Best for:**

- Complex workflows with clear data contracts
- When you need programmatic access to agent outputs
- Production systems with strict schemas

**Avoid when:**

- Rapid prototyping (overhead)
- Conversational agents (messages are the product)

### Pattern 4: Hybrid (Messages + Structured)

Messages for conversation, structured state for data.

```python
class HybridState(TypedDict):
    # User-facing conversation
    messages: Annotated[list, add_messages]
    
    # Internal structured data (not shown to user)
    internal: dict  # {"research": {...}, "analysis": {...}, ...}
    
    # Routing control
    active_agent: str
    next_step: str

def research_node(state):
    result = research_agent.invoke(state)
    
    # Extract what matters
    findings = extract_findings(result)
    user_summary = generate_user_summary(findings)
    
    return {
        # User sees summary
        "messages": [AIMessage(content=user_summary)],
        # System stores details
        "internal": {
            **state.get("internal", {}),
            "research": findings
        }
    }
```

**Best for:**

- User-facing applications (clean conversation)
- Behind-the-scenes complexity
- When different consumers need different views

---

## Reducers: How State Updates Merge

When multiple agents update the same key, LangGraph uses **reducers** to merge updates.

### The Default: `add_messages`

```python
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]
```

`add_messages` appends new messages to existing ones (with deduplication by ID).

### Custom Reducers

For non-message state, define your own:

```python
from typing import Annotated
import operator

class State(TypedDict):
    messages: Annotated[list, add_messages]
    
    # Append to list
    findings: Annotated[list, operator.add]
    
    # Overwrite (last write wins)
    status: str  # No annotation = overwrite
    
    # Custom merge logic
    scores: Annotated[dict, merge_scores]

def merge_scores(existing: dict, new: dict) -> dict:
    """Keep highest score for each key."""
    result = existing.copy()
    for k, v in new.items():
        if k not in result or v > result[k]:
            result[k] = v
    return result
```

### Reducer Gotchas

1. **No annotation = overwrite:** Last agent to update wins.
2. **List without reducer grows forever:** Use `operator.add` deliberately.
3. **Concurrent updates merge atomically:** LangGraph handles this, but order matters.

---

## Common Mistakes

### 1. Assuming Agents Share Memory

```python
# Agent A sets a variable
research_results = do_research()  # Local variable!

# Agent B can't access it
def agent_b(state):
    # research_results doesn't exist here
```

**Fix:** All shared data must be in the state.

### 2. Unbounded Message Growth

```python
# Every agent appends, nothing trims
def agent_node(state):
    return {"messages": state["messages"] + [new_message]}  # Grows forever
```

**Fix:** Trim, summarize, or use structured state.

### 3. Leaking Internal Reasoning

```python
# Agent's chain-of-thought goes to shared state
def agent_node(state):
    result = agent.invoke(state)  # Includes thinking steps
    return {"messages": result["messages"]}  # All of it shared!
```

**Fix:** Extract only final output, keep reasoning private.

### 4. Inconsistent Message Attribution

```python
# Who said this?
return {"messages": [AIMessage(content="Done")]}  # No name!

# Better:
return {"messages": [HumanMessage(content="Done", name="researcher")]}
```

**Fix:** Always set `name` on messages for attribution.

---

## Key Takeaways

1. **Context loss is inevitable:** Agent B only knows what A explicitly sends. Design handoffs deliberately.
    
2. **Shared `messages` is the default:** Simple but leads to context bloat. Use private state or structured data for complex workflows.
    
3. **Handoff payload design matters:** Include confidence, reasoning, and open questions when downstream agents need them.
    
4. **State explosion is real:** Long multi-agent workflows hit context limits. Use summary handoffs, trimming, or structured state.
    
5. **Wrappers enable schema heterogeneity:** Transform state at boundaries when agents have different schemas.
    
6. **Reducers control merging:** Understand how `add_messages` works, define custom reducers for non-message state.
    
7. **Private scratchpads prevent confusion:** Agent-specific keys keep internal reasoning separate from shared communication.
    

---

## References

**Documentation referenced for this note:**

- LangGraph Graph API Overview (https://docs.langchain.com/oss/python/langgraph/graph-api)
- LangGraph Swarm: Customizing agent implementation (GitHub README)
- LangChain Blog: "LangGraph: Multi-Agent Workflows"
- LangGraph State Management patterns (various Medium articles, 2025)

**Key API elements:**

- `add_messages` — default reducer for message lists
- `Annotated[list, reducer]` — custom reducers for state keys
- `trim_messages` — utility for context management
- `HumanMessage(content=..., name=...)` — attributed messages
- `TypedDict` — state schema definition