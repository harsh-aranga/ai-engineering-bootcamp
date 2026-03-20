# Note 3: Query Decomposition — Breaking Down Complex Questions

## The Pattern

Query decomposition breaks a complex question into simpler sub-queries, retrieves for each independently, then synthesizes the results:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Complex Query: "Compare 2023 and 2024 product roadmaps"        │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │   Decompose     │                          │
│                    └────────┬────────┘                          │
│                             │                                   │
│              ┌──────────────┼──────────────┐                    │
│              ▼              ▼              ▼                    │
│        "2023 product   "2024 product   "major changes           │
│         roadmap"        roadmap"        between versions"       │
│              │              │              │                    │
│              ▼              ▼              ▼                    │
│           Retrieve       Retrieve       Retrieve                │
│              │              │              │                    │
│              ▼              ▼              ▼                    │
│           Answer 1       Answer 2       Answer 3                │
│              │              │              │                    │
│              └──────────────┼──────────────┘                    │
│                             │                                   │
│                             ▼                                   │
│                    ┌─────────────────┐                          │
│                    │   Synthesize    │                          │
│                    └────────┬────────┘                          │
│                             │                                   │
│                             ▼                                   │
│                      Final Answer                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Decomposition vs. Iterative Retrieval

These patterns solve different problems:

|Aspect|Query Decomposition|Iterative Retrieval|
|---|---|---|
|**Problem**|Complex query needs info from multiple distinct topics|Single topic, but need more depth|
|**Sub-queries**|Different aspects of the question|Same intent, different angles|
|**Retrieval**|Parallel (independent sub-queries)|Sequential (each refines based on gaps)|
|**When to use**|"Compare A and B", multi-part questions|"Tell me everything about X", sparse initial results|

**Key distinction:** Iterative retrieval keeps digging on the _same_ topic until sufficient. Decomposition splits into _different_ topics that are retrieved independently.

**Example:**

- "What's our refund policy for enterprise customers?" → **Iterative**. One topic, may need multiple retrieval passes to find all details.
- "Compare our refund policy to competitor X's refund policy" → **Decomposition**. Two distinct topics: our policy, their policy.

---

## LLM-Based Query Decomposition

The decomposition step uses an LLM to break the complex query into searchable sub-queries.

### Decomposition Prompt Design

```python
# Doc reference: Anthropic Python SDK (platform.claude.com/docs/en/api/sdks/python)

import anthropic

DECOMPOSITION_PROMPT = """You are breaking down a complex question into simpler sub-questions.

Complex Question: {question}

Break this into 2-4 simpler sub-questions that:
1. Can each be answered independently
2. Are specific enough to search in a document database
3. Together, provide all information needed to answer the original question

Return as a numbered list:
1. [first sub-question]
2. [second sub-question]
...

Sub-questions:"""

def decompose_query(
    question: str,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> list[str]:
    """
    Break a complex question into simpler sub-questions.
    
    Returns list of sub-queries suitable for retrieval.
    """
    message = client.messages.create(
        model=model,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": DECOMPOSITION_PROMPT.format(question=question)
        }]
    )
    
    response = message.content[0].text
    return _parse_numbered_list(response)

def _parse_numbered_list(response: str) -> list[str]:
    """Parse numbered list from LLM response."""
    lines = response.strip().split("\n")
    sub_queries = []
    
    for line in lines:
        # Match lines starting with number + period or parenthesis
        line = line.strip()
        if line and line[0].isdigit():
            # Remove number prefix: "1. " or "1) " or "1: "
            for sep in [". ", ") ", ": "]:
                if sep in line:
                    sub_queries.append(line.split(sep, 1)[1].strip())
                    break
    
    return sub_queries
```

### What Makes a Good Sub-Query

The decomposition prompt must produce sub-queries that are:

1. **Independently searchable**: Each sub-query should retrieve relevant chunks on its own, without needing context from other sub-queries.
    
2. **Specific enough**: "information about 2023" is too vague. "2023 product roadmap features and timeline" is searchable.
    
3. **Collectively exhaustive**: Together, sub-queries should cover all aspects needed to answer the original question.
    
4. **Minimal overlap**: Avoid sub-queries that retrieve the same chunks.
    

**Good decomposition example:**

Original: "Compare engineering and sales team approaches to remote work policy"

Sub-queries:

1. "Engineering team remote work policy and preferences"
2. "Sales team remote work policy and requirements"
3. "Differences in remote work needs between engineering and sales"

**Bad decomposition example:**

Sub-queries:

1. "Remote work policy" (too vague, will retrieve mixed results)
2. "Team approaches" (not specific to any team)
3. "Engineering and sales" (not specific to remote work)

---

## Execution Strategies

Once you have sub-queries, you need to retrieve and generate answers for each. Two main approaches:

### Sequential Execution

Retrieve for Q1, then Q2, then Q3. Each sub-query is processed one at a time.

```python
def sequential_decomposed_rag(
    question: str,
    sub_queries: list[str],
    retriever,
    client: anthropic.Anthropic
) -> dict[str, str]:
    """
    Execute sub-queries sequentially.
    
    Returns dict mapping sub-query -> sub-answer.
    """
    sub_answers = {}
    
    for sub_query in sub_queries:
        # Retrieve for this sub-query
        docs = retriever.retrieve(sub_query, k=5)
        context = "\n\n".join(docs)
        
        # Generate sub-answer
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Answer this question based on the context.

Question: {sub_query}

Context:
{context}

Answer:"""
            }]
        )
        
        sub_answers[sub_query] = message.content[0].text
    
    return sub_answers
```

**When to use sequential:**

- Sub-queries depend on each other (later queries refine based on earlier answers)
- Rate limits are a concern
- Debugging: easier to trace issues step by step

**Downside:** Slow. Total time = sum of all sub-query times.

### Parallel Execution

Retrieve for all sub-queries simultaneously. Each is independent.

```python
import asyncio

async def parallel_decomposed_rag(
    question: str,
    sub_queries: list[str],
    retriever,
    client: anthropic.AsyncAnthropic
) -> dict[str, str]:
    """
    Execute sub-queries in parallel.
    
    Returns dict mapping sub-query -> sub-answer.
    """
    async def process_sub_query(sub_query: str) -> tuple[str, str]:
        # Retrieve for this sub-query
        docs = await retriever.aretrieve(sub_query, k=5)
        context = "\n\n".join(docs)
        
        # Generate sub-answer
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Answer this question based on the context.

Question: {sub_query}

Context:
{context}

Answer:"""
            }]
        )
        
        return sub_query, message.content[0].text
    
    # Execute all sub-queries in parallel
    tasks = [process_sub_query(sq) for sq in sub_queries]
    results = await asyncio.gather(*tasks)
    
    return dict(results)
```

**When to use parallel:**

- Sub-queries are truly independent (most decomposition cases)
- Latency matters
- No rate limit concerns

**Advantage:** Total time = max of individual sub-query times (much faster).

---

## Synthesis: Combining Sub-Answers

After retrieving and answering each sub-query, we synthesize into a final answer.

```python
SYNTHESIS_PROMPT = """You need to synthesize multiple sub-answers into a complete response.

Original Question: {original_question}

Sub-questions and their answers:
{sub_qa_formatted}

Synthesize these into a coherent, complete answer to the original question.
- Integrate information from all sub-answers
- Resolve any contradictions by noting them
- Don't just concatenate — create a unified response

Final Answer:"""

def synthesize_answers(
    original_question: str,
    sub_answers: dict[str, str],
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> str:
    """
    Synthesize sub-answers into a final response.
    """
    # Format sub-Q&A pairs
    sub_qa_formatted = ""
    for i, (sub_q, sub_a) in enumerate(sub_answers.items(), 1):
        sub_qa_formatted += f"\nSub-question {i}: {sub_q}\nAnswer: {sub_a}\n"
    
    message = client.messages.create(
        model=model,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": SYNTHESIS_PROMPT.format(
                original_question=original_question,
                sub_qa_formatted=sub_qa_formatted
            )
        }]
    )
    
    return message.content[0].text
```

### Synthesis Challenges

**1. Contradictory sub-answers** Sub-query 1 says "policy allows 3 days remote." Sub-query 2 says "policy allows 2 days remote." Which is correct?

**Mitigation:** Include source documents in synthesis prompt. Ask the model to note contradictions explicitly.

**2. Losing nuance** Each sub-answer has details. Synthesis compresses them. Important nuance may be lost.

**Mitigation:** Increase synthesis token limit. Instruct model to preserve specifics.

**3. Over-reliance on one sub-answer** Synthesis might weight one sub-answer heavily, ignoring others.

**Mitigation:** Explicit instruction: "Integrate information from ALL sub-answers."

---

## LangGraph Implementation

LangGraph supports parallel execution through fan-out patterns. Multiple edges from one node execute concurrently.

```python
# Doc reference: LangGraph docs (docs.langchain.com/oss/python/langgraph/use-graph-api)
# Pattern: Fan-out with multiple edges, fan-in with Send API for dynamic sub-queries

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
import operator
import anthropic

# Initialize client
client = anthropic.Anthropic()

class DecomposedRAGState(TypedDict):
    """State for decomposed RAG workflow."""
    question: str
    sub_queries: list[str]
    sub_answers: Annotated[dict[str, str], lambda a, b: {**a, **b}]  # Merge dicts
    final_answer: str

def decompose_node(state: DecomposedRAGState) -> dict:
    """Break question into sub-queries."""
    sub_queries = decompose_query(state["question"], client)
    return {"sub_queries": sub_queries}

def retrieve_and_answer_node(state: dict) -> dict:
    """
    Retrieve and answer for a single sub-query.
    Note: This node receives partial state with just the sub-query.
    """
    sub_query = state["sub_query"]
    
    # Retrieve (replace with your retriever)
    docs = retrieve_from_vectorstore(sub_query, k=5)
    context = "\n\n".join(docs)
    
    # Generate sub-answer
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Answer based on context.

Question: {sub_query}

Context:
{context}

Answer:"""
        }]
    )
    
    return {"sub_answers": {sub_query: message.content[0].text}}

def continue_to_retrieval(state: DecomposedRAGState) -> list[Send]:
    """
    Fan out to retrieval nodes for each sub-query.
    Uses Send API for dynamic number of parallel branches.
    """
    return [
        Send("retrieve_and_answer", {"sub_query": sq})
        for sq in state["sub_queries"]
    ]

def synthesize_node(state: DecomposedRAGState) -> dict:
    """Synthesize sub-answers into final answer."""
    final = synthesize_answers(
        state["question"],
        state["sub_answers"],
        client
    )
    return {"final_answer": final}

# Build graph
workflow = StateGraph(DecomposedRAGState)

workflow.add_node("decompose", decompose_node)
workflow.add_node("retrieve_and_answer", retrieve_and_answer_node)
workflow.add_node("synthesize", synthesize_node)

workflow.add_edge(START, "decompose")

# Fan-out: decompose -> multiple retrieve_and_answer nodes (parallel)
workflow.add_conditional_edges(
    "decompose",
    continue_to_retrieval,
    ["retrieve_and_answer"]
)

# Fan-in: all retrieve_and_answer nodes -> synthesize
workflow.add_edge("retrieve_and_answer", "synthesize")
workflow.add_edge("synthesize", END)

decomposed_rag = workflow.compile()
```

### Graph Structure

```
START
  │
  ▼
┌─────────────┐
│  decompose  │
└──────┬──────┘
       │
       ▼ (fan-out via Send)
┌──────┴──────┐──────┐──────────────┐
│  retrieve   │ retrieve │ retrieve │  (parallel)
│  sub-q-1    │ sub-q-2  │ sub-q-3  │
└──────┬──────┘──────┬────┘──────┬──┘
       │             │           │
       └──────┬──────┘──────┬────┘
              │ (fan-in)
              ▼
       ┌─────────────┐
       │  synthesize │
       └──────┬──────┘
              │
              ▼
             END
```

**Key LangGraph patterns used:**

1. **Send API for dynamic fan-out**: `Send("node_name", partial_state)` creates parallel branches at runtime. Number of branches determined by `len(sub_queries)`.
    
2. **Reducer for merging**: `Annotated[dict, merge_fn]` combines sub_answers from parallel branches into single dict.
    
3. **Automatic fan-in**: LangGraph waits for all parallel branches to complete before proceeding to synthesize node.
    

---

## Limitations of Decomposition

### 1. Missing Cross-Cutting Context

Some information spans multiple sub-queries and gets lost in decomposition.

**Example:**

- Original: "How did the policy changes affect both engineering and sales teams?"
- Sub-queries: "Engineering team policy changes", "Sales team policy changes"
- **Problem:** A document that discusses how both teams reacted to the same change might not rank highly for either sub-query.

**Mitigation:** Include a sub-query that explicitly targets cross-cutting context: "Joint engineering and sales response to policy changes."

### 2. Decomposition Can Be Wrong

The LLM might decompose poorly:

- Too many sub-queries (over-decomposition)
- Too few sub-queries (under-decomposition)
- Wrong angles (sub-queries miss the actual information needed)

**Mitigation:**

- Validate decomposition before retrieval (check for 2-4 sub-queries)
- Include examples in decomposition prompt
- Fall back to standard RAG if decomposition looks poor

### 3. Synthesis Can Lose Nuance

Each sub-answer has details. Synthesis must compress. Details get lost.

**Example:**

- Sub-answer 1 has 5 specific data points about engineering team
- Sub-answer 2 has 4 specific data points about sales team
- Synthesis keeps 3 points from each, loses the rest

**Mitigation:**

- Increase synthesis token limit
- Return sub-answers alongside final answer for reference
- Use longer context models for synthesis

### 4. Independent Sub-Queries Assumption

Decomposition assumes sub-queries are independent. Sometimes they're not.

**Example:**

- "What was our 2023 revenue and how did Q4 compare to projections?"
- Sub-queries: "2023 revenue", "Q4 comparison to projections"
- **Problem:** Q4 projections might only make sense with context from overall 2023 revenue.

**Mitigation:** Consider sequential execution when sub-queries build on each other.

---

## When Decomposition Fits

### Comparative Questions

"Compare X and Y" naturally decomposes into:

- What is X?
- What is Y?
- What are the differences?

**Examples:**

- "Compare our pricing to competitor pricing"
- "How does the 2024 policy differ from 2023?"
- "What are the pros and cons of approach A vs approach B?"

### Multi-Part Questions

Questions with multiple distinct parts:

- "What is X, why does it matter, and how do we use it?"
- "Explain the architecture, deployment process, and monitoring setup"

Each part is a separate sub-query.

### Aggregation Questions

"All mentions of X" or "everything about Y across documents":

- "Summarize all customer feedback about shipping"
- "What do we know about competitor X from all sources?"
- "List all action items from Q3 meetings"

Decompose by source, time period, or category.

---

## When to Avoid Decomposition

### Simple Questions

If a question can be answered with a single retrieval, decomposition adds unnecessary overhead.

**Don't decompose:** "What's the return address?" **Just retrieve:** It's a single fact.

### Sequential Reasoning

When parts depend on each other:

- "Based on Q3 results, what should Q4 strategy be?"
- Q4 strategy sub-query makes no sense without Q3 results context.

**Better approach:** Iterative retrieval or multi-turn conversation.

### Already Specific Questions

If the question is already specific and searchable:

- "What is the refund timeframe for enterprise customers?"

Decomposition would just create one sub-query identical to the original.

---

## Complete Working Example

```python
"""
Decomposed RAG with LangGraph — Complete Implementation

Doc references:
- Anthropic SDK: platform.claude.com/docs/en/api/sdks/python
- LangGraph: docs.langchain.com/oss/python/langgraph/use-graph-api
  (Send API for map-reduce, fan-out/fan-in patterns)
"""

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
import anthropic

# Initialize client
client = anthropic.Anthropic()

# Mock retriever — replace with your vector store
def retrieve_from_vectorstore(query: str, k: int = 5) -> list[str]:
    return [f"Document about {query} - chunk {i}" for i in range(k)]

class DecomposedRAGState(TypedDict):
    question: str
    sub_queries: list[str]
    sub_answers: Annotated[dict[str, str], lambda a, b: {**a, **b}]
    final_answer: str

def decompose_query(question: str) -> list[str]:
    """Break question into sub-queries."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Break this question into 2-4 simpler sub-questions.
Each should be independently searchable.

Question: {question}

Return as numbered list:
1. [sub-question]
2. [sub-question]
..."""
        }]
    )
    
    response = message.content[0].text
    sub_queries = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ". " in line:
            sub_queries.append(line.split(". ", 1)[1])
    
    return sub_queries if sub_queries else [question]  # Fallback to original

def decompose_node(state: DecomposedRAGState) -> dict:
    sub_queries = decompose_query(state["question"])
    return {"sub_queries": sub_queries}

def retrieve_and_answer_node(state: dict) -> dict:
    """Process single sub-query."""
    sub_query = state["sub_query"]
    
    docs = retrieve_from_vectorstore(sub_query, k=5)
    context = "\n\n".join(docs)
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Answer based on context:

Question: {sub_query}

Context:
{context}

Answer:"""
        }]
    )
    
    return {"sub_answers": {sub_query: message.content[0].text}}

def fan_out_to_retrieval(state: DecomposedRAGState) -> list[Send]:
    """Create parallel retrieval branches."""
    return [
        Send("retrieve_and_answer", {"sub_query": sq})
        for sq in state["sub_queries"]
    ]

def synthesize_node(state: DecomposedRAGState) -> dict:
    """Combine sub-answers into final answer."""
    sub_qa = "\n".join([
        f"Q: {q}\nA: {a}\n"
        for q, a in state["sub_answers"].items()
    ])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Synthesize these sub-answers into a complete response.

Original Question: {state["question"]}

Sub-questions and answers:
{sub_qa}

Create a unified answer:"""
        }]
    )
    
    return {"final_answer": message.content[0].text}

# Build graph
workflow = StateGraph(DecomposedRAGState)

workflow.add_node("decompose", decompose_node)
workflow.add_node("retrieve_and_answer", retrieve_and_answer_node)
workflow.add_node("synthesize", synthesize_node)

workflow.add_edge(START, "decompose")
workflow.add_conditional_edges(
    "decompose",
    fan_out_to_retrieval,
    ["retrieve_and_answer"]
)
workflow.add_edge("retrieve_and_answer", "synthesize")
workflow.add_edge("synthesize", END)

decomposed_rag = workflow.compile()

# Usage
def run_decomposed_rag(question: str) -> dict:
    """Run decomposed RAG and return result with trace."""
    initial_state = {
        "question": question,
        "sub_queries": [],
        "sub_answers": {},
        "final_answer": ""
    }
    
    result = decomposed_rag.invoke(initial_state)
    
    return {
        "answer": result["final_answer"],
        "sub_queries": result["sub_queries"],
        "sub_answers": result["sub_answers"],
        "num_sub_queries": len(result["sub_queries"])
    }

# Example
if __name__ == "__main__":
    result = run_decomposed_rag(
        "Compare the engineering and sales team approaches to remote work policy"
    )
    print(f"Sub-queries: {result['sub_queries']}")
    print(f"Final answer: {result['answer'][:200]}...")
```

---

## Cost Analysis

Decomposition multiplies costs proportionally to sub-query count:

|Component|Standard RAG|Decomposed (3 sub-queries)|
|---|---|---|
|Decomposition call|0|1|
|Retrieval calls|1|3|
|Generation calls|1|3 (sub-answers)|
|Synthesis call|0|1|
|**Total LLM calls**|**1**|**5**|

**Token breakdown:**

- Decomposition: ~200-400 tokens
- Per sub-query retrieval + generation: ~800-1500 tokens each
- Synthesis: ~1000-2000 tokens (includes all sub-answers)

**Latency advantage of parallel:** With parallel execution, latency is max(sub-query times) + decomposition + synthesis. Sequential would be sum(sub-query times) + decomposition + synthesis.

For 3 sub-queries at 2 seconds each:

- Sequential: 2 + 2 + 2 + 1 + 1 = 8 seconds
- Parallel: 2 + 1 + 1 = 4 seconds (50% faster)

---

## Key Takeaways

1. **Decomposition breaks complex queries into independent sub-queries** — each retrieved and answered separately, then synthesized.
    
2. **Different from iterative retrieval** — decomposition is for multi-topic questions; iterative is for more depth on single topic.
    
3. **Sub-queries must be independently searchable** — each should retrieve relevant content without context from other sub-queries.
    
4. **Parallel execution for speed** — use LangGraph's Send API or async to run sub-queries concurrently.
    
5. **Synthesis combines sub-answers** — requires explicit prompt to integrate, not just concatenate.
    
6. **Limitations exist** — cross-cutting context gets lost, decomposition can be wrong, synthesis loses nuance.
    
7. **Best for comparative and multi-part questions** — "Compare A and B", "What is X, why does it matter, how do we use it?"
    
8. **Avoid for simple or dependent questions** — if parts depend on each other, use iterative or sequential reasoning instead.