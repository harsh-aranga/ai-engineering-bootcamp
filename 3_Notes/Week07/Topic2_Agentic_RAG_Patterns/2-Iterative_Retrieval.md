# Note 2: Iterative Retrieval — Retrieve Until Sufficient

## The Pattern

Iterative retrieval adds a feedback loop to standard RAG:

```
START
  │
  ▼
┌─────────┐
│retrieve │◄──────────┐
└────┬────┘           │
     │                │
     ▼                │
┌─────────┐           │
│evaluate │           │
└────┬────┘           │
     │                │
     ▼                │
 sufficient? ──No──► refine
     │
    Yes
     │
     ▼
┌─────────┐
│generate │
└────┬────┘
     │
     ▼
    END
```

The key difference from single-shot RAG: **after retrieval, we evaluate whether we have enough context before generating**. If not, we refine the query and retrieve again.

This is fundamentally different from query decomposition (Note 3), which breaks a complex query into sub-queries upfront. Iterative retrieval keeps the same query intent but refines the search angle based on what's missing.

---

## The Sufficiency Check Problem

The core challenge: **how does the agent know if it has enough context?**

A human researcher knows when they've gathered enough material. They recognize gaps, identify missing perspectives, sense when they're ready to write. We need to give the agent similar judgment.

### LLM-Based Sufficiency Evaluation

The most practical approach: ask the LLM to evaluate whether the retrieved context is sufficient to answer the question.

**Prompt Structure for Sufficiency Check:**

```python
SUFFICIENCY_PROMPT = """You are evaluating whether retrieved information is sufficient to answer a question.

Question: {question}

Retrieved Information:
{retrieved_context}

Evaluate:
1. Can this question be FULLY answered with the retrieved information?
2. What specific information is MISSING (if any)?

Respond in this exact format:
SUFFICIENT: YES or NO
MISSING: [List what's missing, or "Nothing" if sufficient]
CONFIDENCE: HIGH, MEDIUM, or LOW
"""
```

**Why this structure works:**

1. **Binary decision (YES/NO)**: Forces a clear routing decision
2. **Explicit gap identification**: If not sufficient, tells us what to search for next
3. **Confidence signal**: Helps with stopping criteria — low confidence even with "YES" might warrant another iteration

### Implementation with Anthropic API

```python
# Doc reference: Anthropic Python SDK (platform.claude.com/docs/en/api/sdks/python)
# Pattern: client.messages.create() with structured prompt

import anthropic
from dataclasses import dataclass

@dataclass
class SufficiencyResult:
    is_sufficient: bool
    missing: list[str]
    confidence: str
    raw_response: str

def check_sufficiency(
    question: str,
    retrieved_docs: list[str],
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> SufficiencyResult:
    """
    Evaluate whether retrieved context is sufficient to answer the question.
    
    Returns structured result with sufficiency decision and gap analysis.
    """
    context = "\n\n---\n\n".join(retrieved_docs)
    
    prompt = f"""You are evaluating whether retrieved information is sufficient to answer a question.

Question: {question}

Retrieved Information:
{context}

Evaluate:
1. Can this question be FULLY answered with the retrieved information?
2. What specific information is MISSING (if any)?

Respond in this exact format:
SUFFICIENT: YES or NO
MISSING: [List what's missing, or "Nothing" if sufficient]
CONFIDENCE: HIGH, MEDIUM, or LOW"""

    message = client.messages.create(
        model=model,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text
    return _parse_sufficiency_response(response_text)

def _parse_sufficiency_response(response: str) -> SufficiencyResult:
    """Parse the structured sufficiency response."""
    lines = response.strip().split("\n")
    
    is_sufficient = False
    missing = []
    confidence = "MEDIUM"
    
    for line in lines:
        if line.startswith("SUFFICIENT:"):
            is_sufficient = "YES" in line.upper()
        elif line.startswith("MISSING:"):
            missing_text = line.replace("MISSING:", "").strip()
            if missing_text.lower() != "nothing":
                # Parse comma or bullet-separated items
                missing = [m.strip().strip("-•") for m in missing_text.split(",")]
        elif line.startswith("CONFIDENCE:"):
            confidence = line.replace("CONFIDENCE:", "").strip().upper()
    
    return SufficiencyResult(
        is_sufficient=is_sufficient,
        missing=missing,
        confidence=confidence,
        raw_response=response
    )
```

---

## Query Refinement for Next Iteration

When context is insufficient, we need to generate a refined query that targets the gap.

**The refinement prompt needs three inputs:**

1. Original question (the goal we're trying to achieve)
2. What we already retrieved (avoid redundant retrieval)
3. What's missing (from sufficiency check)

```python
REFINEMENT_PROMPT = """You need to generate a search query to find missing information.

Original Question: {question}

Information Already Retrieved:
{retrieved_summary}

Information Still Missing:
{missing_info}

Generate a concise search query (3-7 words) that would find the missing information.
Focus on the GAP, not on re-retrieving what we already have.

Search Query:"""

def generate_refined_query(
    question: str,
    retrieved_docs: list[str],
    missing_info: list[str],
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> str:
    """
    Generate a refined search query targeting identified gaps.
    """
    # Summarize what we have (don't send full docs, too expensive)
    retrieved_summary = _summarize_retrieved(retrieved_docs)
    missing_str = ", ".join(missing_info)
    
    prompt = f"""You need to generate a search query to find missing information.

Original Question: {question}

Information Already Retrieved:
{retrieved_summary}

Information Still Missing:
{missing_str}

Generate a concise search query (3-7 words) that would find the missing information.
Focus on the GAP, not on re-retrieving what we already have.

Search Query:"""

    message = client.messages.create(
        model=model,
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text.strip()

def _summarize_retrieved(docs: list[str], max_chars: int = 500) -> str:
    """Create a brief summary of retrieved content for the refinement prompt."""
    combined = " | ".join([doc[:100] + "..." for doc in docs[:5]])
    return combined[:max_chars]
```

### Query Refinement Strategies

Different missing information requires different query angles:

|Gap Type|Refinement Strategy|Example|
|---|---|---|
|Missing specifics|Add specificity terms|"refund policy" → "refund policy enterprise customers timeframe"|
|Missing timeframe|Add temporal markers|"product roadmap" → "2024 product roadmap Q3 Q4"|
|Missing perspective|Change angle|"benefits of X" → "drawbacks limitations X"|
|Sparse results|Broaden terms|"ChromaDB embedding indexing" → "vector database indexing strategies"|
|Wrong domain|Redirect domain|"pricing" (got consumer) → "enterprise pricing B2B"|

---

## Stopping Criteria

**Critical for avoiding infinite loops.** Without proper stopping criteria, iterative retrieval can:

- Loop forever
- Burn through API costs
- Never converge on an answer

### Four Stopping Conditions

```python
@dataclass
class IterationState:
    iteration: int
    all_docs: list[str]
    queries_tried: list[str]
    last_sufficiency: SufficiencyResult | None

def should_stop(
    state: IterationState,
    max_iterations: int = 3,
    min_new_docs: int = 1
) -> tuple[bool, str]:
    """
    Determine if we should stop iterating.
    
    Returns: (should_stop, reason)
    """
    # 1. Max iterations reached
    if state.iteration >= max_iterations:
        return True, "max_iterations"
    
    # 2. Sufficiency achieved
    if state.last_sufficiency and state.last_sufficiency.is_sufficient:
        return True, "sufficient"
    
    # 3. High confidence even if not fully sufficient
    if (state.last_sufficiency and 
        state.last_sufficiency.confidence == "HIGH" and
        state.iteration >= 2):
        return True, "high_confidence"
    
    # 4. Diminishing returns (no new docs in last iteration)
    if state.iteration > 1:
        prev_count = len(state.all_docs) - min_new_docs  # Approximate
        if len(state.all_docs) <= prev_count:
            return True, "diminishing_returns"
    
    return False, "continue"
```

### Stopping Criteria Breakdown

|Criterion|Why It Matters|Typical Threshold|
|---|---|---|
|**Max iterations**|Hard ceiling to prevent runaway costs|3-5 iterations|
|**Sufficiency achieved**|Goal met, stop immediately|SUFFICIENT: YES|
|**High confidence**|Good enough, diminishing returns likely|HIGH confidence + 2+ iterations|
|**Diminishing returns**|New retrieval adds nothing new|0 new unique docs|
|**Query exhaustion**|Can't think of new angles|Refined query matches previous query|

**Production tuning:** Start with max_iterations=3. Monitor how often you hit max vs. achieve sufficiency. If most queries hit max without achieving sufficiency, your retrieval or chunking might be the problem — not the iteration count.

---

## LangGraph Implementation

LangGraph makes iterative retrieval natural: the cycle is explicit in the graph structure.

```python
# Doc reference: LangGraph StateGraph, add_conditional_edges
# (docs.langchain.com, blog.langchain.com/langgraph/)
# Current API uses: StateGraph, add_node, add_edge, add_conditional_edges, START, END

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
import operator

class IterativeRAGState(TypedDict):
    """State that accumulates across iterations."""
    question: str
    retrieved_docs: Annotated[list[str], operator.add]  # Accumulates across iterations
    queries_tried: Annotated[list[str], operator.add]
    iteration: int
    is_sufficient: bool
    missing_info: list[str]
    final_answer: str

def retrieve_node(state: IterativeRAGState) -> dict:
    """Retrieve documents for current query."""
    # Use latest query (original question or refined)
    if state["queries_tried"]:
        query = state["queries_tried"][-1]
    else:
        query = state["question"]
    
    # Your retrieval logic here
    new_docs = retrieve_from_vectorstore(query, k=5)
    
    return {
        "retrieved_docs": new_docs,  # Will be appended due to operator.add
        "queries_tried": [query] if not state["queries_tried"] else [],
        "iteration": state["iteration"] + 1
    }

def evaluate_node(state: IterativeRAGState) -> dict:
    """Evaluate sufficiency of retrieved context."""
    result = check_sufficiency(
        question=state["question"],
        retrieved_docs=state["retrieved_docs"],
        client=anthropic_client
    )
    
    return {
        "is_sufficient": result.is_sufficient,
        "missing_info": result.missing
    }

def refine_query_node(state: IterativeRAGState) -> dict:
    """Generate refined query for next iteration."""
    new_query = generate_refined_query(
        question=state["question"],
        retrieved_docs=state["retrieved_docs"],
        missing_info=state["missing_info"],
        client=anthropic_client
    )
    
    return {
        "queries_tried": [new_query]
    }

def generate_node(state: IterativeRAGState) -> dict:
    """Generate final answer from accumulated context."""
    context = "\n\n".join(state["retrieved_docs"])
    
    prompt = f"""Answer this question based on the provided context.

Question: {state["question"]}

Context:
{context}

Answer:"""

    message = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return {"final_answer": message.content[0].text}

def should_continue(state: IterativeRAGState) -> Literal["refine", "generate"]:
    """Route based on sufficiency check."""
    # Check stopping conditions
    if state["iteration"] >= 3:
        return "generate"  # Max iterations
    
    if state["is_sufficient"]:
        return "generate"  # Sufficient context
    
    return "refine"  # Need more

# Build the graph
workflow = StateGraph(IterativeRAGState)

# Add nodes
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("evaluate", evaluate_node)
workflow.add_node("refine", refine_query_node)
workflow.add_node("generate", generate_node)

# Add edges
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "evaluate")

# Conditional edge: creates the cycle
workflow.add_conditional_edges(
    "evaluate",
    should_continue,
    {
        "refine": "refine",
        "generate": "generate"
    }
)

# Refine loops back to retrieve
workflow.add_edge("refine", "retrieve")

# Generate ends the graph
workflow.add_edge("generate", END)

# Compile
iterative_rag = workflow.compile()
```

### Graph Visualization

```
START
  │
  ▼
┌─────────┐
│retrieve │◄──────────┐
└────┬────┘           │
     │                │
     ▼                │
┌─────────┐           │
│evaluate │           │
└────┬────┘           │
     │                │
     ▼                │
 sufficient? ──No──► refine
     │
    Yes
     │
     ▼
┌─────────┐
│generate │
└────┬────┘
     │
     ▼
    END
```

**Key Implementation Details:**

1. **State accumulation**: `Annotated[list[str], operator.add]` means each node's returned docs get appended to existing docs, not replaced
2. **Cycle via conditional edge**: `add_conditional_edges` routes back to "refine" when not sufficient
3. **Stopping in routing function**: The `should_continue` function enforces max iterations
4. **Query tracking**: `queries_tried` prevents repeating the same search

---

## When Iterative Beats Single-Shot

### Good Candidates for Iterative Retrieval

**1. Exploratory Questions**

- "Tell me everything about our refund policy"
- "What do we know about competitor X?"
- User doesn't know exactly what they're looking for

**2. Sparse Initial Results**

- Query returns only 1-2 relevant chunks
- High-value question deserves thorough search
- First query angle might not be optimal

**3. Broad Topics Requiring Multiple Angles**

- "Summarize Q3 customer feedback"
- Need to retrieve across categories, time periods, or sources
- Single query can't capture full scope

**4. High-Stakes Answers**

- Legal/compliance questions
- Customer-facing responses
- Worth extra latency for completeness

### When to Avoid Iterative Retrieval

**1. Simple Factual Lookups**

- "What's the return address?"
- "What are the office hours?"
- Single retrieval is sufficient

**2. Time-Sensitive Queries**

- User waiting for quick answer
- Chatbot latency matters
- 2-3x latency isn't acceptable

**3. Well-Indexed Content**

- Clean, well-chunked knowledge base
- High retrieval precision
- Single-shot already works well

**4. Cost-Sensitive Applications**

- High query volume
- 3-5x token cost per query adds up
- Simple RAG handles 80% of queries

---

## Cost Analysis

Iterative retrieval multiplies costs:

|Component|Single-Shot|Iterative (3 iter)|
|---|---|---|
|Retrieval calls|1|3|
|Sufficiency checks|0|3|
|Query refinement|0|2|
|Generation|1|1|
|**Total LLM calls**|**1**|**6**|
|**Latency**|~1-2s|~4-8s|

**Token breakdown per iteration:**

- Sufficiency check: ~500-1000 tokens (context + prompt + response)
- Query refinement: ~200-400 tokens
- Each additional retrieval: embedding call + vector search

**Production recommendation:** Use iterative retrieval selectively. Route simple queries to standard RAG, reserve iterative for complex queries where quality justifies cost.

---

## Complete Working Example

```python
"""
Iterative RAG with LangGraph - Complete Implementation

Doc references:
- Anthropic SDK: platform.claude.com/docs/en/api/sdks/python
- LangGraph: docs.langchain.com, StateGraph pattern
"""

from typing import TypedDict, Annotated, Literal
from dataclasses import dataclass
import operator
import anthropic
from langgraph.graph import StateGraph, START, END

# Initialize client
client = anthropic.Anthropic()

# Mock retrieval function - replace with your vector store
def retrieve_from_vectorstore(query: str, k: int = 5) -> list[str]:
    """Replace with actual ChromaDB/Pinecone/etc retrieval."""
    # Simulated retrieval
    return [f"Document about {query} - chunk {i}" for i in range(k)]

@dataclass
class SufficiencyResult:
    is_sufficient: bool
    missing: list[str]
    confidence: str

class IterativeRAGState(TypedDict):
    question: str
    retrieved_docs: Annotated[list[str], operator.add]
    queries_tried: Annotated[list[str], operator.add]
    iteration: int
    is_sufficient: bool
    missing_info: list[str]
    final_answer: str

def check_sufficiency(question: str, docs: list[str]) -> SufficiencyResult:
    """Evaluate if retrieved docs are sufficient."""
    context = "\n\n---\n\n".join(docs)
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Evaluate if this context can fully answer the question.

Question: {question}

Context:
{context}

Respond exactly as:
SUFFICIENT: YES or NO
MISSING: [what's missing, or "Nothing"]
CONFIDENCE: HIGH, MEDIUM, or LOW"""
        }]
    )
    
    response = message.content[0].text
    is_sufficient = "SUFFICIENT: YES" in response.upper()
    
    # Parse missing info
    missing = []
    for line in response.split("\n"):
        if line.startswith("MISSING:"):
            missing_text = line.replace("MISSING:", "").strip()
            if missing_text.lower() != "nothing":
                missing = [m.strip() for m in missing_text.split(",")]
    
    confidence = "MEDIUM"
    if "CONFIDENCE: HIGH" in response.upper():
        confidence = "HIGH"
    elif "CONFIDENCE: LOW" in response.upper():
        confidence = "LOW"
    
    return SufficiencyResult(is_sufficient, missing, confidence)

def generate_refined_query(question: str, docs: list[str], missing: list[str]) -> str:
    """Generate a query targeting the identified gaps."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": f"""Generate a search query to find: {', '.join(missing)}
            
Original question: {question}
Already have info about: {docs[0][:100] if docs else 'nothing'}...

Search query (3-7 words):"""
        }]
    )
    return message.content[0].text.strip()

# Node functions
def retrieve_node(state: IterativeRAGState) -> dict:
    query = state["queries_tried"][-1] if state["queries_tried"] else state["question"]
    new_docs = retrieve_from_vectorstore(query, k=5)
    
    return {
        "retrieved_docs": new_docs,
        "queries_tried": [state["question"]] if not state["queries_tried"] else [],
        "iteration": state["iteration"] + 1
    }

def evaluate_node(state: IterativeRAGState) -> dict:
    result = check_sufficiency(state["question"], state["retrieved_docs"])
    return {
        "is_sufficient": result.is_sufficient,
        "missing_info": result.missing
    }

def refine_node(state: IterativeRAGState) -> dict:
    new_query = generate_refined_query(
        state["question"],
        state["retrieved_docs"],
        state["missing_info"]
    )
    return {"queries_tried": [new_query]}

def generate_node(state: IterativeRAGState) -> dict:
    context = "\n\n".join(state["retrieved_docs"])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Answer based on this context:

Question: {state["question"]}

Context:
{context}

Answer:"""
        }]
    )
    
    return {"final_answer": message.content[0].text}

def route_after_evaluate(state: IterativeRAGState) -> Literal["refine", "generate"]:
    if state["iteration"] >= 3:
        return "generate"
    if state["is_sufficient"]:
        return "generate"
    return "refine"

# Build graph
workflow = StateGraph(IterativeRAGState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("evaluate", evaluate_node)
workflow.add_node("refine", refine_node)
workflow.add_node("generate", generate_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "evaluate")
workflow.add_conditional_edges(
    "evaluate",
    route_after_evaluate,
    {"refine": "refine", "generate": "generate"}
)
workflow.add_edge("refine", "retrieve")
workflow.add_edge("generate", END)

iterative_rag = workflow.compile()

# Usage
def run_iterative_rag(question: str) -> dict:
    """Run iterative RAG and return result with trace."""
    initial_state = {
        "question": question,
        "retrieved_docs": [],
        "queries_tried": [],
        "iteration": 0,
        "is_sufficient": False,
        "missing_info": [],
        "final_answer": ""
    }
    
    result = iterative_rag.invoke(initial_state)
    
    return {
        "answer": result["final_answer"],
        "iterations": result["iteration"],
        "queries_used": result["queries_tried"],
        "docs_retrieved": len(result["retrieved_docs"]),
        "achieved_sufficiency": result["is_sufficient"]
    }

# Example
if __name__ == "__main__":
    result = run_iterative_rag(
        "What is our complete refund policy including timeframes and exceptions?"
    )
    print(f"Answer: {result['answer'][:200]}...")
    print(f"Iterations: {result['iterations']}")
    print(f"Queries: {result['queries_used']}")
    print(f"Achieved sufficiency: {result['achieved_sufficiency']}")
```

---

## Key Takeaways

1. **Iterative retrieval adds a feedback loop** — retrieve, evaluate sufficiency, refine query if needed, repeat.
    
2. **Sufficiency checking is the core challenge** — use LLM-based evaluation with structured prompts that output YES/NO + what's missing.
    
3. **Query refinement targets gaps** — the refined query should search for what's missing, not re-retrieve what we have.
    
4. **Stopping criteria prevent infinite loops** — max iterations, sufficiency achieved, diminishing returns, query exhaustion.
    
5. **LangGraph makes cycles explicit** — `add_conditional_edges` routes back to retrieval when not sufficient.
    
6. **State accumulates across iterations** — use `Annotated[list, operator.add]` to append docs rather than replace.
    
7. **Cost is 3-6x single-shot RAG** — use iterative retrieval selectively for complex queries, not as default.
    
8. **Different from query decomposition** — iterative refines the same query intent; decomposition breaks into independent sub-queries upfront.