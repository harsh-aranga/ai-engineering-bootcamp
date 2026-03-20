# Note 3: Swarm Pattern — Decentralized Handoffs

> **Week 6 Agent Track — Days 1-2**  
> **Focus:** The swarm pattern for peer-to-peer agent collaboration without central control

---

## Mental Model: No Boss, Just Peers

The swarm pattern is fundamentally different from the supervisor pattern. There's no central coordinator — agents hand off directly to each other based on their own judgment.

```
     ┌─────────────┐         ┌─────────────┐
     │   Alice     │◄───────►│    Bob      │
     │  (Math)     │         │  (Pirate)   │
     │             │         │             │
     │ Can hand    │         │ Can hand    │
     │ off to Bob  │         │ off to Alice│
     └──────┬──────┘         └──────┬──────┘
            │                       │
            │    ┌─────────────┐    │
            └───►│   Charlie   │◄───┘
                 │  (Research) │
                 │             │
                 │ Can hand    │
                 │ off to both │
                 └─────────────┘
```

**Key characteristics:**

- **No hierarchy:** All agents are peers, no central supervisor
- **Direct handoffs:** Agent A hands off directly to Agent B
- **Agent decides routing:** Each agent determines when and whom to hand off to
- **State remembers last active:** The system tracks `active_agent` for conversation resumption

Think of it like a team of specialists passing a problem around until the right person handles it, rather than a manager dispatching work.

---

## The `langgraph-swarm` Library

LangGraph provides a dedicated library for this pattern:

```bash
pip install langgraph-swarm
```

**Released:** March 2025  
**Current version:** 0.1.0

---

## Core Implementation

### Basic Swarm Setup

**Reference:** GitHub langchain-ai/langgraph-swarm-py (current as of 2025)

```python
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent
from langgraph_swarm import create_handoff_tool, create_swarm

model = ChatOpenAI(model="gpt-4o")

# Define Alice's tools — including handoff to Bob
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

alice = create_agent(
    model,
    tools=[
        add,
        create_handoff_tool(
            agent_name="Bob",
            description="Transfer to Bob, he speaks like a pirate",
        ),
    ],
    system_prompt="You are Alice, an addition expert.",
    name="Alice",
)

# Define Bob's tools — including handoff to Alice
bob = create_agent(
    model,
    tools=[
        create_handoff_tool(
            agent_name="Alice",
            description="Transfer to Alice, she can help with math",
        ),
    ],
    system_prompt="You are Bob, you speak like a pirate.",
    name="Bob",
)

# Create the swarm — no supervisor, just peer agents
checkpointer = InMemorySaver()
workflow = create_swarm(
    [alice, bob],
    default_active_agent="Alice"  # Who handles the first message
)
app = workflow.compile(checkpointer=checkpointer)

# Use thread_id for conversation continuity
config = {"configurable": {"thread_id": "user-123"}}

# Turn 1: User asks to speak to Bob
turn_1 = app.invoke(
    {"messages": [{"role": "user", "content": "i'd like to speak to Bob"}]},
    config,
)
# Alice sees this, uses handoff tool to transfer to Bob
# Bob responds (as a pirate)

# Turn 2: User asks a math question
turn_2 = app.invoke(
    {"messages": [{"role": "user", "content": "what's 5 + 7?"}]},
    config,
)
# Bob is still active (remembered from turn 1)
# Bob realizes he can't do math, hands off to Alice
# Alice calculates and responds
```

### What Happens Under the Hood

Let's trace through turn 1:

1. **Message arrives:** "i'd like to speak to Bob"
    
2. **Router checks `active_agent`:** State shows `active_agent="Alice"` (default)
    
3. **Alice receives message:** Alice's agent processes the request
    
4. **Alice decides to hand off:** Based on the user's request, Alice calls `handoff_to_Bob` tool
    
5. **Handoff tool returns `Command`:** The tool explicitly updates state: The `active_agent` change happens because the handoff tool includes it in `Command.update` — LangGraph doesn't track this automatically. If you build custom handoff tools, you must set `"active_agent"` yourself or resumption breaks.
```python
   return Command(
       goto="Bob",
       graph=Command.PARENT,
       update={
           "messages": state["messages"] + [tool_message],
           "active_agent": "Bob",  # Explicit update — not automatic
       }
   )
```
   
6. **Bob receives control:** Bob's agent now handles the conversation
    
7. **Bob responds:** "Ahoy, matey! What can I do for ye?"
    

Now for turn 2:

1. **Message arrives:** "what's 5 + 7?"
    
2. **Router checks `active_agent`:** State shows `active_agent="Bob"` (remembered!)
    
3. **Bob receives message:** Bob sees the math question
    
4. **Bob decides to hand off:** Bob's tools include `handoff_to_Alice` with description "she can help with math". Bob calls it.
    
5. **Alice receives control:** Alice now handles the conversation
    
6. **Alice responds:** "5 + 7 = 12"
    

---

## The `active_agent` State: Memory of Last Active

The critical difference from supervisor: **the swarm remembers who was last active**.

### Why This Matters

Without `active_agent` tracking:

- Every new message would go to the default agent
- User says "hi Bob" → goes to Alice → Alice hands to Bob
- User says "thanks" → goes to Alice again (wrong!)

With `active_agent` tracking:

- User says "hi Bob" → Alice → hands to Bob → `active_agent = "Bob"`
- User says "thanks" → goes directly to Bob (correct!)

### The State Schema

The swarm uses a `SwarmState` that includes:

```python
from typing_extensions import TypedDict, Annotated
from langchain.messages import AnyMessage
from langgraph.graph import add_messages

class SwarmState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    active_agent: str  # Tracks who should handle the next message
```

### Checkpointer Is Critical

**Important:** Without a checkpointer, the swarm forgets which agent was active:

```python
# BAD: No checkpointer — forgets active agent between turns
workflow = create_swarm([alice, bob], default_active_agent="Alice")
app = workflow.compile()  # No checkpointer!

# Every turn starts fresh with Alice, regardless of handoffs

# GOOD: With checkpointer — remembers active agent
checkpointer = InMemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# Now active_agent persists across turns
```

Always compile with a checkpointer for multi-turn conversations.

---

## Key Difference from Supervisor

### Supervisor Pattern (Note 2)

```
User → Supervisor (LLM call: decides routing)
              ↓
       Worker Agent (LLM call: does work)
              ↓
     Supervisor (LLM call: decides next step or responds)
```

Every routing decision requires a supervisor LLM call.

### Swarm Pattern

```
User → Active Agent (LLM call: does work OR hands off)
              ↓
       [If handoff] Next Agent (LLM call: does work OR hands off)
              ↓
       [If done] Response
```

No separate routing call — the agent doing work also decides routing.

### The Latency Difference

**Supervisor (3 agents, 2-step task):**

```
Supervisor decides → Agent A works → Supervisor decides → Agent B works → Supervisor responds
= 5 LLM calls minimum
```

**Swarm (same task):**

```
Agent A works + decides to hand off → Agent B works + responds
= 2 LLM calls minimum
```

That's roughly **40-60% fewer LLM calls** for the same task — directly translates to latency reduction.

---

## Handoff Tools: Each Agent's Routing Power

In a swarm, each agent carries its own handoff tools. This is how agents know about each other:

```python
# Alice knows about Bob and Charlie
alice = create_agent(
    model,
    tools=[
        add,
        create_handoff_tool(agent_name="Bob", description="Transfer to Bob for pirate speak"),
        create_handoff_tool(agent_name="Charlie", description="Transfer to Charlie for research"),
    ],
    name="Alice",
)

# Bob only knows about Alice
bob = create_agent(
    model,
    tools=[
        create_handoff_tool(agent_name="Alice", description="Transfer to Alice for math"),
    ],
    name="Bob",
)

# Charlie knows about both
charlie = create_agent(
    model,
    tools=[
        web_search,
        create_handoff_tool(agent_name="Alice", description="Transfer to Alice for math"),
        create_handoff_tool(agent_name="Bob", description="Transfer to Bob for creative writing"),
    ],
    name="Charlie",
)
```

### Handoff Topology

This creates an explicit topology — who can hand off to whom:

```
Alice ──► Bob
  │         │
  ▼         │
Charlie ◄───┘
  │
  └──► Alice, Bob
```

Not all agents need to know about all other agents. You can create:

- **Linear chains:** A → B → C (each only knows the next)
- **Hub and spoke:** All agents know central agent, central knows all
- **Fully connected:** Everyone knows everyone
- **Restricted paths:** Enforce workflow by limiting handoff options

---

## Adding Memory (Persistence)

Just like the supervisor, swarm supports short-term and long-term memory:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# Short-term: conversation state + active_agent across turns
checkpointer = InMemorySaver()

# Long-term: cross-conversation knowledge
store = InMemoryStore()

workflow = create_swarm(
    [alice, bob, charlie],
    default_active_agent="Alice"
)

app = workflow.compile(
    checkpointer=checkpointer,
    store=store
)
```

**Short-term memory is especially critical for swarm** because it preserves:

1. Conversation history
2. `active_agent` state — which agent should handle the next turn

---

## When Swarm Pattern Fits

### Good Use Cases

1. **Real-time conversations:**
    
    - User chats with support bot
    - Bot hands off to specialist (billing, technical, sales) as needed
    - No supervisor overhead — feels like talking to one adaptive agent
2. **Dynamic, unpredictable routing:**
    
    - Task could go in many directions
    - Agents self-organize based on conversation flow
    - Hard to pre-define a workflow
3. **Latency-sensitive applications:**
    
    - Every millisecond matters
    - Eliminating supervisor LLM calls is worth the trade-off
4. **Persona-based systems:**
    
    - Different "personalities" for different topics
    - User can ask to speak to specific agents
    - Natural handoffs between personas
5. **Emergent collaboration:**
    
    - Agents discover optimal routing through interaction
    - No predetermined workflow
    - Good for creative or exploratory tasks

### Poor Use Cases

1. **Strict workflow enforcement:**
    
    - "Research MUST happen before writing"
    - Swarm agents might skip steps
    - Supervisor is better for enforcing order
2. **Quality gates:**
    
    - Need approval before proceeding
    - Want to review intermediate outputs
    - Supervisor provides natural checkpoints
3. **Audit requirements:**
    
    - Need to know exactly why routing happened
    - Supervisor's explicit routing decisions are easier to log/explain
4. **Unreliable agents:**
    
    - If agents make poor handoff decisions, there's no supervisor to correct
    - Agents must be well-prompted and reliable

---

## The Trade-Off: Decentralization vs. Control

### What You Gain

1. **Lower latency:** ~40% fewer LLM calls for multi-agent tasks
    
2. **Simpler mental model:** No separate supervisor to reason about
    
3. **Natural conversation flow:** Handoffs feel organic, not dispatched
    
4. **Scalability:** Adding a new agent just means giving existing agents handoff tools to it
    

### What You Lose

1. **Workflow guarantees:** Can't enforce "A before B before C"
    
2. **Centralized oversight:** No single point that sees all routing decisions
    
3. **Error correction:** No supervisor to catch bad handoff decisions
    
4. **Explicit decomposition:** Agents decompose tasks themselves, not always optimally
    

### The Fundamental Difference

**Supervisor:** "The supervisor decides routing, workers just execute."

**Swarm:** "Each worker decides its own routing, there is no supervisor."

This is a control vs. latency trade-off. Choose based on your requirements.

---

## Custom Handoff Tools

For more control over what happens during handoffs, create custom tools:

```python
from typing import Annotated
from langchain.tools import tool, BaseTool, InjectedToolCallId
from langchain.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import InjectedState

def create_custom_handoff_tool(
    *, 
    agent_name: str, 
    name: str, 
    description: str
) -> BaseTool:
    
    @tool(name, description=description)
    def handoff_to_agent(
        # LLM populates this — context for the next agent
        task_description: Annotated[
            str, 
            "Detailed description of what the next agent should do"
        ],
        # Inject current state
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        tool_message = ToolMessage(
            content=f"Successfully transferred to {agent_name}",
            name=name,
            tool_call_id=tool_call_id,
        )
        
        messages = state["messages"]
        
        return Command(
            goto=agent_name,
            graph=Command.PARENT,
            update={
                "messages": messages + [tool_message],
                "active_agent": agent_name,
                # Pass task context to next agent
                "task_description": task_description,
            },
        )
    
    return handoff_to_agent
```

This lets you:

- Add custom arguments (like `task_description`)
- Control what state updates happen during handoff
- Filter or transform messages before passing them

---

## Private Message Histories

By default, all agents share a single `messages` list. Everyone sees everything. If you want agents to have private conversations:

### The Problem

```python
# Default: Shared messages
# Alice's internal reasoning visible to Bob
# Bob's pirate speak visible to Alice's next turn
```

### The Solution: Custom State Schema

```python
from typing_extensions import TypedDict, Annotated
from langchain.messages import AnyMessage
from langgraph.graph import StateGraph, add_messages
from langgraph_swarm import SwarmState, add_active_agent_router

# Alice has private message history
class AliceState(TypedDict):
    alice_messages: Annotated[list[AnyMessage], add_messages]

# Build Alice's agent with her private schema
alice = (
    StateGraph(AliceState)
    .add_node("model", ...)
    .add_node("tools", ...)
    ...
    .compile()
)

# Wrapper converts swarm state ↔ agent state
def call_alice(state: SwarmState):
    # Input: Extract what Alice needs from shared state
    response = alice.invoke({"alice_messages": state["messages"]})
    # Output: Return only what should be shared
    return {"messages": response["alice_messages"]}

def call_bob(state: SwarmState):
    ...

# Build swarm manually with custom wrappers
workflow = (
    StateGraph(SwarmState)
    .add_node("Alice", call_alice, destinations=("Bob",))
    .add_node("Bob", call_bob, destinations=("Alice",))
)

workflow = add_active_agent_router(
    builder=workflow,
    route_to=["Alice", "Bob"],
    default_active_agent="Alice",
)

app = workflow.compile()
```

This pattern:

- Gives each agent private internal state
- Controls exactly what crosses agent boundaries
- More complex but more flexible

---

## Common Mistakes

### 1. Forgetting the Checkpointer

```python
# BAD: No checkpointer
app = workflow.compile()

# Turn 1: Alice hands off to Bob
# Turn 2: Starts at Alice again (forgot Bob was active!)
```

Always use a checkpointer for multi-turn swarms.

### 2. Circular Handoff Loops

```python
# Alice: "I don't do math, ask Bob"
# Bob: "I don't do math either, ask Alice"
# Alice: "I don't do math, ask Bob"
# ... infinite loop
```

**Solutions:**

- Give at least one agent the capability to handle each task type
- Add "I can't help with this" fallback behavior
- Set max iterations in your agent config

### 3. Missing Handoff Descriptions

```python
# BAD: Vague description
create_handoff_tool(agent_name="Bob", description="Transfer to Bob")

# GOOD: Clear description helps agent decide when to use it
create_handoff_tool(
    agent_name="Bob", 
    description="Transfer to Bob for creative writing, storytelling, or pirate-themed responses"
)
```

The LLM uses the description to decide when to hand off. Be specific.

### 4. Inconsistent Agent Names

```python
# Agent defined with name "Bob"
bob = create_agent(..., name="Bob")

# But handoff tool references "bob" (lowercase)
create_handoff_tool(agent_name="bob", ...)  # Won't work!
```

Agent names must match exactly, including case.

---

## Key Takeaways

1. **No central controller:** Swarm agents are peers that hand off directly to each other.
    
2. **`active_agent` is critical:** The state tracks who's active, enabling multi-turn conversations to resume with the right agent.
    
3. **Checkpointer is mandatory:** Without it, `active_agent` resets every turn.
    
4. **Latency advantage:** ~40% fewer LLM calls than supervisor pattern for equivalent tasks.
    
5. **Agents carry their own routing:** Each agent has handoff tools defining who it can delegate to.
    
6. **Trade-off is control:** You lose workflow enforcement and centralized oversight in exchange for speed and flexibility.
    
7. **Well-prompted agents are essential:** Without a supervisor to correct, agents must make good routing decisions themselves.
    

---

## Supervisor vs. Swarm: Quick Comparison

|Aspect|Supervisor|Swarm|
|---|---|---|
|Routing decisions|Supervisor LLM decides|Each agent decides|
|LLM calls per hop|2 (supervisor + worker)|1 (just the agent)|
|Latency|Higher|~40% lower|
|Workflow control|Strong (supervisor enforces)|Weak (agents self-organize)|
|Audit trail|Clear (supervisor logs)|Distributed (each agent logs)|
|Complexity|Supervisor + workers|Just peers|
|Best for|Structured workflows|Dynamic conversations|

---

## What's Next

- **Note 4:** Network/Collaboration Pattern — when agents need to work together more flexibly
- **Note 5:** Handoffs Deep Dive — the `Command` object and implementing custom handoffs

---

## References

**Documentation referenced for this note:**

- GitHub: langchain-ai/langgraph-swarm-py (README, current as of 2025)
- PyPI: langgraph-swarm v0.1.0
- LangChain Changelog: LangGraph Swarm announcement (March 2025)

**Key API elements:**

- `create_swarm()` — main function to create swarm workflow
- `create_handoff_tool()` — creates handoff tools for agent-to-agent transfer
- `create_agent()` — creates agents (from `langchain.agents`)
- `SwarmState` — state schema with `messages` and `active_agent`
- `add_active_agent_router()` — utility for manual swarm construction
- `Command` — LangGraph primitive for state updates + graph navigation