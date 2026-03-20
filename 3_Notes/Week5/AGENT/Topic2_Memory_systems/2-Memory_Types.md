# Memory Types: Semantic, Episodic, Procedural

## The Cognitive Psychology Foundation

AI agent memory systems borrow terminology from cognitive psychology. Understanding these concepts helps you design memory architectures that serve specific purposes rather than dumping everything into a single store.

The three primary memory types:

|Memory Type|What It Stores|Human Example|Agent Example|
|---|---|---|---|
|**Semantic**|Facts and knowledge|"Paris is the capital of France"|"User prefers dark mode"|
|**Episodic**|Specific experiences|"My first day at work"|"Last week we debugged the auth flow together"|
|**Procedural**|Skills and behaviors|Knowing how to ride a bike|"Always respond with code examples first"|

These aren't just academic categories—they map to different implementation patterns in your agent.

---

## Semantic Memory: Facts and Knowledge

Semantic memory stores **declarative knowledge**—facts that are true independent of when or how you learned them. You don't remember _when_ you learned that water boils at 100°C; you just know it.

### What Agents Store as Semantic Memory

- User preferences: "Prefers concise answers"
- Personal facts: "Works at Acme Corp in the ML team"
- Relationships: "Alice is Bob's manager"
- Domain knowledge: "Project X uses PostgreSQL 15"

### Two Storage Patterns

**1. Collections (Unbounded Facts)**

Store individual facts as separate documents. Good when:

- You don't know in advance what facts matter
- Facts accumulate over time
- Retrieval is based on relevance to current query

```python
# Conceptual structure
memories = [
    {"id": "1", "content": "User works at Acme Corp"},
    {"id": "2", "content": "User prefers Python over JavaScript"},
    {"id": "3", "content": "User's manager is Alice"},
]

# At query time: semantic search for relevant facts
relevant = search(memories, query="What company does the user work for?")
```

**2. Profiles (Structured Schema)**

Store a single document that represents current state. Good when:

- You know exactly what information matters
- Only latest state is relevant (not history)
- You want user-editable memory

```python
from pydantic import BaseModel

class UserProfile(BaseModel):
    name: str
    preferred_name: str
    company: str | None
    role: str | None
    communication_style: str  # "formal", "casual", "technical"
    interests: list[str]

# Single document, updated on each conversation
profile = UserProfile(
    name="Harsh",
    preferred_name="Harsh",
    company="Independent Consultant",
    role="AI Engineer",
    communication_style="direct, no-fluff",
    interests=["distributed systems", "RAG", "agents"]
)
```

### The Reconciliation Challenge

With collections, new information may conflict with existing memories:

- "User works at Acme Corp" vs "User just joined BigTech Inc"

Your memory system must decide:

- **Delete** the old memory?
- **Update** it with a timestamp?
- **Consolidate** into a new memory that captures the transition?

LangMem handles this via an "enrichment" process that prompts an LLM to reconcile conflicts. Over-extraction leads to noise; under-extraction leads to missed information.

---

## Episodic Memory: Past Experiences

Episodic memory stores **specific events**—not just what happened, but when, where, why, and with whom. You remember your first day at work not as abstract facts but as a lived experience with context.

### What Agents Store as Episodic Memory

- Successful problem-solving sessions (few-shot examples)
- Key decisions and their rationale
- User interactions worth learning from
- Project milestones and context

### The Structure of an Episode

An episode isn't just "what happened." It captures the full context:

```python
from pydantic import BaseModel, Field

class Episode(BaseModel):
    """A complete record of a significant interaction."""
    
    observation: str = Field(
        description="The situation and relevant context"
    )
    thoughts: str = Field(
        description="Key reasoning process that led to success"
    )
    action: str = Field(
        description="What was done in response"
    )
    result: str = Field(
        description="Outcome and why it worked"
    )
    timestamp: str
```

### Why Episodic Memory Matters for Agents

**Few-shot learning from experience:**

When facing a new problem, the agent retrieves similar past episodes and uses them as examples. This is more powerful than generic few-shot prompting because the examples come from _this agent's actual successes_.

```
User asks: "How do I debug this async issue?"

Agent retrieves episode:
- Observation: "User had race condition in async code"
- Thoughts: "Identified shared state being modified without locks"
- Action: "Added asyncio.Lock, showed before/after behavior"
- Result: "User understood; similar approach worked on their specific case"

Agent uses this as implicit guidance for current response.
```

**The consolidation path:**

Over time, episodic memories can _consolidate_ into semantic memories:

- Multiple episodes of "user prefers code examples" → semantic fact: "Always include code"
- Several debugging sessions on auth → semantic knowledge about the codebase

This mimics how humans learn: specific experiences become general knowledge.

---

## Procedural Memory: Skills and Behaviors

Procedural memory encodes **how to do things**—not facts about the world, but patterns of behavior. When you ride a bike, you don't consciously recall instructions; your procedural memory executes the skill.

### What Agents Store as Procedural Memory

- Response patterns: "Start with the answer, then explain"
- Communication style: "Be direct, avoid hedging"
- Domain-specific behaviors: "Always validate SQL before suggesting"
- Learned preferences: "This user likes Mermaid diagrams"

### Where Procedural Memory Lives

Unlike semantic and episodic memory (which live in external stores), procedural memory often lives in the **system prompt itself**:

```python
SYSTEM_PROMPT = """You are a technical assistant with the following behaviors:

1. Lead with the answer, then explain why
2. Include code examples for any technical concept
3. Use Mermaid diagrams for architecture discussions
4. Be direct—no hedging or excessive caveats
5. If uncertain, say so explicitly rather than guessing
"""
```

The procedural memory _is_ the prompt. When the agent learns to behave differently, it's updating the prompt.

### Procedural Memory Evolution

Unlike static prompts, procedural memory can **learn and adapt**:

```
Initial prompt: "You are a helpful assistant."

After feedback: "You are a helpful assistant. When explaining 
programming concepts, start with practical examples before theory."

After more feedback: "You are a helpful assistant with expertise 
in practical explanations. Lead with working code examples, then 
explain the underlying concepts. Avoid theoretical explanations 
without accompanying code."
```

This is what LangMem's `create_prompt_optimizer` does—it takes conversation trajectories and feedback, then proposes prompt improvements.

---

## How the Three Types Interact

The memory types aren't isolated; they form a system:

```
┌─────────────────────────────────────────────────────────────────┐
│                         AGENT                                    │
│                                                                  │
│  ┌──────────────────┐                                           │
│  │ PROCEDURAL       │  ← System prompt (how to behave)          │
│  │ "Be direct"      │                                           │
│  │ "Code first"     │                                           │
│  └──────────────────┘                                           │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │ SEMANTIC         │    │ EPISODIC         │                   │
│  │ User: prefers    │    │ "Last week we    │                   │
│  │ Python, works    │    │ debugged auth,   │                   │
│  │ at Acme Corp     │    │ used Lock..."    │                   │
│  └──────────────────┘    └──────────────────┘                   │
│           │                       │                              │
│           └───────────┬───────────┘                              │
│                       ▼                                          │
│              ┌─────────────────┐                                 │
│              │ CONTEXT WINDOW  │                                 │
│              │ (Working Memory)│                                 │
│              └─────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
```

**At runtime:**

1. Procedural memory shapes overall behavior (system prompt)
2. Semantic memory provides relevant facts (retrieved, injected)
3. Episodic memory provides relevant examples (retrieved, injected)
4. All three merge into the context window for the current turn

**Over time:**

- Episodic → Semantic: Specific experiences consolidate into facts
- Episodic → Procedural: Repeated patterns become behavioral rules
- Feedback → Procedural: User corrections update the system prompt

---

## Mapping to Implementation

|Memory Type|LangGraph Primitive|Typical Storage|Recall Trigger|
|---|---|---|---|
|Semantic|Store|Vector DB / KV store|Semantic search on query|
|Episodic|Store|Vector DB|Semantic search on situation|
|Procedural|System prompt|Prompt template / Store|Always present, or rule-based|

### LangMem's Approach

LangMem provides extractors for each type:

```python
from langmem import create_memory_manager
from pydantic import BaseModel

# Semantic: Extract facts
semantic_manager = create_memory_manager(
    "anthropic:claude-3-5-sonnet-latest",
    instructions="Extract all noteworthy facts about the user.",
    enable_inserts=True,
)

# Episodic: Extract experiences
class Episode(BaseModel):
    observation: str
    thoughts: str
    action: str
    result: str

episodic_manager = create_memory_manager(
    "anthropic:claude-3-5-sonnet-latest",
    schemas=[Episode],
    instructions="Extract successful problem-solving interactions.",
    enable_inserts=True,
)

# Procedural: Optimize behavior
from langmem import create_prompt_optimizer

procedural_optimizer = create_prompt_optimizer(
    "anthropic:claude-3-5-sonnet-latest",
    kind="metaprompt",
)
```

---

## Design Questions for Your Agent

When designing memory for your agent, ask:

**For Semantic Memory:**

- What facts about users/context do I need to remember?
- Should I use collections (unbounded) or profiles (structured)?
- How do I handle conflicting information?

**For Episodic Memory:**

- What constitutes a "significant" experience worth remembering?
- How will I retrieve relevant episodes at runtime?
- Should episodes consolidate into semantic facts over time?

**For Procedural Memory:**

- What behaviors should be hard-coded vs learned?
- How will the agent receive feedback to improve behavior?
- Should procedural updates require human approval?

---

## Key Takeaways

1. **Semantic memory** stores facts (what). Collections for unbounded knowledge; profiles for structured state.
    
2. **Episodic memory** stores experiences (what happened, when, why). Powers few-shot learning from the agent's own history.
    
3. **Procedural memory** stores behaviors (how). Often lives in the system prompt; can evolve via feedback.
    
4. **They interact:** Episodes consolidate into semantic facts; patterns become procedural rules.
    
5. **Different storage patterns:** Semantic and episodic typically use vector stores for retrieval; procedural often stays in the prompt.
    
6. **Design intentionally:** Not every agent needs all three. Choose based on what your agent needs to learn and remember.
    

---

## References

- LangMem Conceptual Guide: https://langchain-ai.github.io/langmem/concepts/conceptual_guide/
- Tulving, E. (1972). "Episodic and semantic memory" — the original cognitive psychology paper
- CoALA (Cognitive Architectures for Language Agents) — academic framework for agent memory
- Pink et al. (2025). "Position: Episodic Memory is the Missing Piece for Long-Term LLM Agents" — arXiv:2502.06975