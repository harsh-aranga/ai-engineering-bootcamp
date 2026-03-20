# Note 4: Query Reformulation Before Retrieval

## Why Raw User Queries Fail

Vector search works by finding chunks semantically similar to the query. This breaks down when user queries are:

1. **Vague**: "What about that thing?"
2. **Context-dependent**: "Tell me more about it"
3. **Conversational**: "Hey, so I was wondering if you could find..."
4. **Poorly phrased for retrieval**: "John mentioned something in the meeting"

Documents don't contain "that thing" or "it". They contain "vacation policy", "expense reimbursement procedure", "Q3 revenue projections". The semantic gap between conversational queries and document language hurts retrieval.

```
User: "What did John say about it?"

Direct embedding search:
┌─────────────────────────────────────────┐
│ Query: "What did John say about it?"    │
│                                          │
│ Best matches (wrong):                    │
│ - "John Smith, Director of Sales..."    │
│ - "About section: Company history..."    │
│ - "It is important to note that..."     │
└─────────────────────────────────────────┘
                    ↓
            Irrelevant chunks retrieved
            Poor answer generated
```

The agent has context the RAG tool doesn't. The agent knows:

- Previous messages mentioned "Project Alpha"
- "It" refers to the budget proposal
- John is John Chen from Engineering

The agent can reformulate the query to include this context before passing to RAG.

---

## Common Reformulation Needs

### 1. Pronoun Resolution

|User Says|Pronoun|Context|Should Search For|
|---|---|---|---|
|"What about it?"|"it"|Discussing vacation policy|"vacation policy details"|
|"Tell me more"|(implicit)|Asked about expense limits|"expense reimbursement policy details"|
|"That thing John mentioned"|"that thing"|Meeting about Q3 targets|"Q3 targets John mentioned"|

### 2. Adding Conversational Context

When users have multi-turn conversations, they assume context:

```
Turn 1: User: "What's the parental leave policy?"
        Agent: "Our parental leave policy provides 12 weeks paid leave..."

Turn 2: User: "What about for part-time employees?"
```

Turn 2 alone is meaningless. Reformulated: "parental leave policy for part-time employees"

### 3. Removing Conversational Fluff

Documents don't start with "Hey" or contain "I was wondering":

|User Query|After Reformulation|
|---|---|
|"Hey, can you look up the vacation policy for me?"|"vacation policy"|
|"I was just wondering what the deal is with expense reports"|"expense report policy procedures"|
|"So like, how does the 401k matching work exactly?"|"401k matching contribution details"|

### 4. Making Queries More Specific and Keyword-Rich

Users speak naturally. Documents are written formally:

|Natural Query|Document-Optimized Query|
|---|---|
|"How much time off do I get?"|"PTO accrual vacation days annual leave policy"|
|"What happens if I'm sick?"|"sick leave policy medical absence procedure"|
|"Can I work from home?"|"remote work policy work from home WFH guidelines"|

---

## Implementing Reformulation

### Core Pattern: LLM Rewrites Query

```python
# This is a conceptual pattern — no specific doc reference needed
# as it's a standard prompt-based transformation

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

def reformulate_query(
    current_query: str,
    conversation_history: list[BaseMessage],
    llm: ChatOpenAI = None
) -> str:
    """
    Reformulate a user query for better RAG retrieval.
    
    Takes the current query and conversation history,
    returns a search-optimized query string.
    """
    if llm is None:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Format conversation history
    history_text = format_conversation_history(conversation_history)
    
    prompt = f"""You are a query rewriter for a document search system.

Given the conversation history and current user query, rewrite the query to be 
optimal for searching an internal document database.

Rewriting rules:
1. Resolve pronouns ("it", "that", "this") using conversation context
2. Include relevant context from the conversation that the query depends on
3. Remove conversational fluff ("hey", "I was wondering", "can you")
4. Use keywords likely to appear in formal documents
5. Be specific and include relevant entities (names, projects, departments)
6. Keep the rewritten query concise (under 30 words)

If the query is already clear and specific, return it unchanged.

Conversation history:
{history_text}

Current user query: {current_query}

Rewritten search query (just the query, no explanation):"""

    response = llm.invoke(prompt)
    return response.content.strip()


def format_conversation_history(messages: list[BaseMessage], max_turns: int = 5) -> str:
    """Format recent conversation history for the prompt."""
    recent = messages[-(max_turns * 2):]  # Last N turns (user + assistant)
    
    formatted = []
    for msg in recent:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        # Truncate long messages
        content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)
```

### Production-Ready Version with Structured Output

```python
from pydantic import BaseModel, Field
from typing import Optional

class ReformulatedQuery(BaseModel):
    """Structured output for query reformulation."""
    original_query: str = Field(description="The original user query")
    rewritten_query: str = Field(description="The search-optimized query")
    changes_made: list[str] = Field(
        description="List of changes made (e.g., 'resolved pronoun it to vacation policy')"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence that reformulation improves the query"
    )
    needs_clarification: bool = Field(
        description="True if query is too ambiguous even after reformulation"
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Question to ask user if clarification needed"
    )

# Use structured output for better control
reformulator_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
reformulator = reformulator_llm.with_structured_output(ReformulatedQuery)

REFORMULATION_PROMPT = """You are a query rewriter for a document search system.

Given the conversation history and current query, analyze whether the query 
needs reformulation for optimal document retrieval.

Conversation history:
{history}

Current query: {query}

Analyze and rewrite the query. If the query references things from the conversation
that you cannot identify (e.g., "that thing" but multiple things were mentioned),
set needs_clarification to True and provide a clarification question."""

def reformulate_with_structure(
    query: str,
    history: list[BaseMessage]
) -> ReformulatedQuery:
    """
    Reformulate query with structured output for better downstream handling.
    """
    history_text = format_conversation_history(history)
    prompt = REFORMULATION_PROMPT.format(history=history_text, query=query)
    
    result = reformulator.invoke(prompt)
    return result
```

### Example Reformulations

```python
# Example 1: Pronoun resolution
history = [
    HumanMessage(content="What's our vacation policy?"),
    AIMessage(content="Our vacation policy provides 15 days PTO annually..."),
]
query = "What about for new employees?"

result = reformulate_with_structure(query, history)
# ReformulatedQuery(
#     original_query="What about for new employees?",
#     rewritten_query="vacation policy PTO accrual for new employees first year",
#     changes_made=["added context: vacation policy", "specified: new employees"],
#     confidence=0.9,
#     needs_clarification=False
# )

# Example 2: Ambiguous reference
history = [
    HumanMessage(content="Tell me about Project Alpha and Project Beta"),
    AIMessage(content="Project Alpha is our Q3 initiative... Project Beta is..."),
]
query = "What's the timeline for that?"

result = reformulate_with_structure(query, history)
# ReformulatedQuery(
#     original_query="What's the timeline for that?",
#     rewritten_query="Project Alpha Project Beta timeline",  # Best effort
#     changes_made=["resolved 'that' to both projects (ambiguous)"],
#     confidence=0.5,
#     needs_clarification=True,
#     clarification_question="Which project are you asking about - Alpha or Beta?"
# )
```

---

## When to Reformulate vs. Use Query As-Is

Not every query needs reformulation. Adding an LLM call for clear queries wastes latency and cost.

### Decision Framework

```python
def should_reformulate(query: str, history: list[BaseMessage]) -> bool:
    """
    Quick heuristic check: does this query need reformulation?
    
    Returns True if reformulation likely helps.
    Returns False if query is already clear and specific.
    """
    query_lower = query.lower()
    
    # Signals that reformulation is needed
    needs_reformulation = False
    
    # 1. Contains pronouns that need resolution
    pronouns = ["it", "this", "that", "they", "them", "those", "these"]
    if any(f" {p} " in f" {query_lower} " for p in pronouns):
        needs_reformulation = True
    
    # 2. Very short query (likely context-dependent)
    if len(query.split()) < 4:
        needs_reformulation = True
    
    # 3. Starts with conversational patterns
    conversational_starts = [
        "what about", "how about", "tell me more", 
        "and ", "but ", "also ", "so ",
    ]
    if any(query_lower.startswith(pattern) for pattern in conversational_starts):
        needs_reformulation = True
    
    # 4. Contains fluff words
    fluff = ["hey", "please", "could you", "can you", "i was wondering"]
    if any(f in query_lower for f in fluff):
        needs_reformulation = True
    
    # 5. References to conversation
    conversation_refs = ["you said", "you mentioned", "earlier", "before"]
    if any(ref in query_lower for ref in conversation_refs):
        needs_reformulation = True
    
    # Skip reformulation if query is already clear
    # (contains specific keywords, proper nouns, policy names)
    specific_signals = [
        # Domain-specific terms suggest clear query
        "policy", "procedure", "form", "process",
        # Numbers/codes suggest specific lookup
        any(char.isdigit() for char in query),
    ]
    
    if not needs_reformulation and len(query.split()) >= 5:
        # Longer, clear queries can skip reformulation
        return False
    
    return needs_reformulation


def reformulate_if_needed(
    query: str,
    history: list[BaseMessage],
    llm: ChatOpenAI
) -> tuple[str, bool]:
    """
    Reformulate query only if heuristics suggest it's needed.
    
    Returns (query_to_use, was_reformulated)
    """
    if not history:
        # No conversation history, minimal reformulation possible
        # Just clean up fluff
        cleaned = clean_conversational_fluff(query)
        return cleaned, cleaned != query
    
    if should_reformulate(query, history):
        reformulated = reformulate_query(query, history, llm)
        return reformulated, True
    
    return query, False


def clean_conversational_fluff(query: str) -> str:
    """Remove conversational fluff without LLM call."""
    import re
    
    # Remove common fluff patterns
    patterns = [
        r'^hey[,\s]+',
        r'^hi[,\s]+',
        r'^please[,\s]+',
        r'^can you[,\s]+',
        r'^could you[,\s]+',
        r'^i was wondering[,\s]+',
        r'^i want to know[,\s]+',
        r'^tell me[,\s]+',
        r'\s+please$',
        r'\s+thanks$',
    ]
    
    result = query.lower()
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    return result.strip()
```

### Cost/Latency Trade-off

|Approach|Latency|Cost|When to Use|
|---|---|---|---|
|Always reformulate|+200-400ms|+100-200 tokens/query|Multi-turn conversations, vague users|
|Never reformulate|+0ms|+0|Single-turn, specific queries|
|Heuristic-gated|+0-400ms|Variable|Production systems|
|Hybrid (rules + LLM)|+0-400ms|Variable|Best balance|

---

## Handling Ambiguity

Sometimes even reformulation can't save a query.

### The Problem

```
History:
- User: "Tell me about our cloud migration project and the new HR system"
- Agent: [explains both]

User: "What's the deadline for that?"
```

"That" could be either project. The agent can't know which one the user means.

### Option 1: Ask for Clarification

```python
def handle_ambiguous_query(result: ReformulatedQuery, state: AgentState):
    """Handle cases where query is too ambiguous."""
    if result.needs_clarification:
        # Ask user before proceeding
        return {
            "messages": [AIMessage(content=result.clarification_question)],
            "awaiting_clarification": True,
        }
    else:
        # Proceed with reformulated query
        return {"rag_query": result.rewritten_query}
```

**Pros**: Most accurate **Cons**: Interrupts flow, adds a turn

### Option 2: Try Multiple Reformulations

```python
def generate_query_variants(
    query: str,
    history: list[BaseMessage],
    ambiguous_entities: list[str]
) -> list[str]:
    """
    Generate multiple query variants for ambiguous references.
    
    Example: "What's the deadline for that?" where "that" could be
    Project Alpha or Project Beta → returns queries for both.
    """
    variants = []
    
    # Generate a variant for each possible interpretation
    for entity in ambiguous_entities:
        variant = query.replace("that", entity).replace("it", entity)
        variants.append(variant)
    
    return variants


def retrieve_with_variants(variants: list[str], retriever) -> list[dict]:
    """
    Retrieve documents for all variants, deduplicate, and combine.
    """
    all_docs = []
    seen_ids = set()
    
    for variant in variants:
        docs = retriever.invoke(variant)
        for doc in docs:
            doc_id = doc.metadata.get("id") or hash(doc.page_content)
            if doc_id not in seen_ids:
                all_docs.append(doc)
                seen_ids.add(doc_id)
    
    # Could also rank by frequency across variants
    return all_docs
```

**Pros**: No interruption, might find relevant docs **Cons**: Noisier retrieval, might confuse response

### Option 3: Retrieve Broadly, Let Agent Filter

```python
def broad_retrieval_approach(
    query: str,
    reformulated: str,
    retriever,
    llm
) -> str:
    """
    Retrieve more documents, let the agent decide relevance.
    """
    # Use broader query
    docs = retriever.invoke(reformulated, k=10)  # More than usual
    
    # Let LLM filter for relevance
    filter_prompt = f"""Given the user's question and retrieved documents,
    identify which documents are actually relevant.
    
    User question: {query}
    
    Documents:
    {format_docs(docs)}
    
    Return the indices of relevant documents (comma-separated):"""
    
    relevant_indices = llm.invoke(filter_prompt).content
    # Parse and filter...
```

**Pros**: Works without user interruption **Cons**: Uses more tokens, might miss the point

### Choosing an Approach

|Scenario|Recommended Approach|
|---|---|
|High-stakes (legal, medical)|Ask for clarification|
|Casual chat|Try multiple variants|
|Known ambiguity patterns|Broad retrieval + filter|
|Real-time/low-latency|Best-effort reformulation|

---

## Integration with Agent Graph

Adding reformulation as a node in the agent graph:

```python
# Doc reference: https://docs.langchain.com/oss/python/langgraph/graph-api

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    original_query: str
    reformulated_query: str
    was_reformulated: bool
    needs_clarification: bool
    clarification_question: str | None

def reformulation_node(state: AgentState) -> dict:
    """
    Reformulate the user query before passing to RAG.
    """
    # Get the latest user message
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    if not user_messages:
        return {}
    
    current_query = user_messages[-1].content
    history = state["messages"][:-1]  # All messages except the current one
    
    # Check if reformulation is needed
    if should_reformulate(current_query, history):
        result = reformulate_with_structure(current_query, history)
        
        return {
            "original_query": current_query,
            "reformulated_query": result.rewritten_query,
            "was_reformulated": True,
            "needs_clarification": result.needs_clarification,
            "clarification_question": result.clarification_question,
        }
    else:
        # Use query as-is (maybe just clean fluff)
        cleaned = clean_conversational_fluff(current_query)
        return {
            "original_query": current_query,
            "reformulated_query": cleaned,
            "was_reformulated": cleaned != current_query,
            "needs_clarification": False,
            "clarification_question": None,
        }

def route_after_reformulation(state: AgentState) -> str:
    """Route based on whether clarification is needed."""
    if state.get("needs_clarification"):
        return "ask_clarification"
    else:
        return "rag_node"

def ask_clarification_node(state: AgentState) -> dict:
    """Ask user for clarification when query is ambiguous."""
    question = state.get("clarification_question", "Could you be more specific?")
    return {"messages": [AIMessage(content=question)]}

def rag_node(state: AgentState) -> dict:
    """Execute RAG with the reformulated query."""
    query = state.get("reformulated_query") or state.get("original_query")
    
    result = rag_tool.invoke({"query": query})
    
    return {"rag_result": result}

# Build graph
builder = StateGraph(AgentState)

builder.add_node("reformulate", reformulation_node)
builder.add_node("ask_clarification", ask_clarification_node)
builder.add_node("rag", rag_node)
builder.add_node("respond", response_node)

builder.add_edge(START, "reformulate")
builder.add_conditional_edges(
    "reformulate",
    route_after_reformulation,
    {
        "ask_clarification": "ask_clarification",
        "rag_node": "rag",
    }
)
builder.add_edge("ask_clarification", END)  # Wait for user response
builder.add_edge("rag", "respond")
builder.add_edge("respond", END)

graph = builder.compile()
```

---

## Reformulation vs. Other Query Transformation Techniques

This note covers **conversational reformulation** — resolving context from the conversation.

**Distinct from** (covered in Week 5 RAG):

|Technique|Purpose|When Applied|
|---|---|---|
|**Reformulation** (this note)|Resolve pronouns, add context, clean fluff|Before RAG, using conversation history|
|**HyDE**|Generate hypothetical document, embed that|Before retrieval, no history needed|
|**Query expansion**|Generate synonyms, related terms|Before retrieval, vocabulary enrichment|
|**Multi-query**|Generate multiple sub-questions|Before retrieval, decompose complex queries|
|**Step-back prompting**|Generate higher-level question|Before retrieval, for concept questions|

These techniques are **complementary**. A production system might:

1. **Reformulate** (resolve "it" → "vacation policy")
2. **Expand** (add synonyms: "PTO", "time off", "leave")
3. **Retrieve** (search with enriched query)

---

## Summary

|Reformulation Need|Solution|
|---|---|
|Pronouns ("it", "that")|Resolve using conversation history|
|Implicit context|Add context from previous turns|
|Conversational fluff|Remove with regex or LLM|
|Vague queries|Make specific with keywords|
|Ambiguous references|Clarify, try variants, or retrieve broadly|

**When to reformulate:**

- Pronouns present
- Very short query
- Conversational starts ("what about...")
- References to prior conversation

**When to skip:**

- Clear, specific query
- Contains domain keywords
- No conversation history
- Single-turn interaction

**Cost consideration:**

- Reformulation = ~100-200 tokens, ~200-400ms
- Gate with heuristics to avoid unnecessary calls
- Worth it for multi-turn conversations with vague queries

**What's Next:**

- **Note 5**: Multi-tool orchestration (combining RAG with web search, calculator, etc.)