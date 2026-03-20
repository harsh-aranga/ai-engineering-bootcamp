# Note 5: Adaptive RAG — Choosing Strategy Per Query

## The Core Insight

Not all queries need the same treatment. A simple factual lookup doesn't need multi-step iteration. A complex comparative analysis shouldn't be handled with single-shot retrieval.

**Adaptive RAG routes queries to the appropriate strategy based on complexity:**

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                          User Query                             │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                          │
│                    │  Classification │                          │
│                    └────────┬────────┘                          │
│                             │                                   │
│         ┌───────────────────┼───────────────────┐               │
│         ▼                   ▼                   ▼               │
│     [Simple]           [Multi-part]        [Exploratory]        │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│   Single-Shot RAG      Decomposition       Iterative RAG        │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             │                                   │
│                             ▼                                   │
│                          Answer                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The Adaptive RAG paper (2024) showed this approach outperforms both fixed single-step and fixed multi-step systems because it matches strategy to query complexity.

---

## Query Complexity Classification

The first step is classifying what kind of query we're dealing with.

### Classification Categories

|Category|Characteristics|Best Strategy|Example|
|---|---|---|---|
|**Simple**|Single topic, fact-based, direct lookup|Single-shot RAG|"What's our refund policy?"|
|**Multi-part**|Multiple distinct aspects to address|Decomposition|"Compare 2023 and 2024 roadmaps"|
|**Exploratory**|Broad scope, comprehensive coverage needed|Iterative retrieval|"Everything about customer complaints"|
|**Comparative**|Requires multiple perspectives|Multi-perspective retrieval|"Pros and cons of approach X"|

### Why Classification Matters

**Without classification:**

- Simple queries get expensive multi-step treatment (wasted cost)
- Complex queries get inadequate single-step treatment (poor quality)

**With classification:**

- Simple queries: fast, cheap, effective
- Complex queries: thorough, higher cost, justified by quality

---

## Implementing Classification

Three approaches, in order of complexity:

### Approach 1: Rule-Based Heuristics

Fast, no LLM call required. Works for obvious cases.

```python
import re
from typing import Literal

QueryType = Literal["simple", "multi_part", "exploratory", "comparative"]

def classify_query_rules(query: str) -> QueryType:
    """
    Rule-based query classification.
    Fast but handles only obvious patterns.
    """
    query_lower = query.lower()
    
    # Comparative signals
    comparative_patterns = [
        r'\bcompare\b', r'\bvs\.?\b', r'\bversus\b',
        r'\bdifference between\b', r'\bpros and cons\b',
        r'\badvantages and disadvantages\b', r'\bbetter\b.*\bor\b'
    ]
    for pattern in comparative_patterns:
        if re.search(pattern, query_lower):
            return "comparative"
    
    # Exploratory signals
    exploratory_patterns = [
        r'\beverything about\b', r'\ball\b.*\babout\b',
        r'\bsummarize all\b', r'\bcomplete overview\b',
        r'\bcomprehensive\b', r'\btell me about\b'
    ]
    for pattern in exploratory_patterns:
        if re.search(pattern, query_lower):
            return "exploratory"
    
    # Multi-part signals (multiple question words, conjunctions)
    multi_part_patterns = [
        r'\band\b.*\?',  # "What is X and how does Y work?"
        r'\balso\b', r'\badditionally\b',
        r'\bfirst\b.*\bthen\b', r'\bboth\b'
    ]
    question_word_count = len(re.findall(r'\b(what|how|why|when|where|who)\b', query_lower))
    if question_word_count >= 2:
        return "multi_part"
    for pattern in multi_part_patterns:
        if re.search(pattern, query_lower):
            return "multi_part"
    
    # Default: simple
    return "simple"
```

**Pros:**

- Zero latency
- Zero cost
- Deterministic

**Cons:**

- Misses nuanced cases
- Requires maintenance as patterns evolve
- Can't understand semantic complexity

### Approach 2: LLM-Based Classification

More accurate, handles nuance, but adds latency and cost.

```python
# Doc reference: Anthropic Python SDK (platform.claude.com/docs/en/api/sdks/python)

import anthropic
from dataclasses import dataclass

@dataclass
class ClassificationResult:
    query_type: QueryType
    reasoning: str
    confidence: str

CLASSIFICATION_PROMPT = """Classify this query by complexity type.

Query: {query}

Categories:
- SIMPLE: Single topic, direct factual lookup, can be answered with one retrieval
- MULTI_PART: Contains multiple distinct aspects that should be addressed separately
- EXPLORATORY: Requires comprehensive coverage, broad scope, "everything about X"
- COMPARATIVE: Requires comparing multiple items, perspectives, or approaches

Respond in this format:
TYPE: [SIMPLE/MULTI_PART/EXPLORATORY/COMPARATIVE]
REASONING: [Brief explanation]
CONFIDENCE: [HIGH/MEDIUM/LOW]"""

def classify_query_llm(
    query: str,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> ClassificationResult:
    """
    LLM-based query classification.
    More accurate but adds latency.
    """
    message = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": CLASSIFICATION_PROMPT.format(query=query)
        }]
    )
    
    response = message.content[0].text
    
    # Parse response
    query_type: QueryType = "simple"
    reasoning = ""
    confidence = "MEDIUM"
    
    for line in response.split("\n"):
        if line.startswith("TYPE:"):
            type_str = line.replace("TYPE:", "").strip().lower()
            if type_str in ["simple", "multi_part", "exploratory", "comparative"]:
                query_type = type_str
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()
        elif line.startswith("CONFIDENCE:"):
            confidence = line.replace("CONFIDENCE:", "").strip().upper()
    
    return ClassificationResult(query_type, reasoning, confidence)
```

**Pros:**

- Handles semantic nuance
- Catches non-obvious patterns
- Self-explanatory with reasoning

**Cons:**

- Adds ~500ms latency
- Costs tokens
- Can occasionally misclassify

### Approach 3: Hybrid Classification

Best of both worlds: rules for obvious cases, LLM for ambiguous ones.

```python
def classify_query_hybrid(
    query: str,
    client: anthropic.Anthropic
) -> ClassificationResult:
    """
    Hybrid approach: rules first, LLM for ambiguous cases.
    """
    # Try rules first
    rule_result = classify_query_rules(query)
    
    # High-confidence rule matches skip LLM
    query_lower = query.lower()
    
    # Very obvious comparative
    if "compare" in query_lower or "vs" in query_lower:
        return ClassificationResult(
            query_type="comparative",
            reasoning="Contains explicit comparison keyword",
            confidence="HIGH"
        )
    
    # Very obvious exploratory
    if "everything about" in query_lower or "summarize all" in query_lower:
        return ClassificationResult(
            query_type="exploratory",
            reasoning="Contains explicit comprehensive scope keyword",
            confidence="HIGH"
        )
    
    # Very short simple queries
    if len(query.split()) < 8 and "?" in query:
        if not any(word in query_lower for word in ["and", "also", "compare", "all"]):
            return ClassificationResult(
                query_type="simple",
                reasoning="Short, single-focus question",
                confidence="HIGH"
            )
    
    # Ambiguous case: use LLM
    return classify_query_llm(query, client)
```

**Production recommendation:** Start with hybrid. Track classification accuracy over time. Adjust rule thresholds based on observed misclassifications.

---

## Routing to Strategies in LangGraph

Once classified, route to the appropriate strategy subgraph.

```python
# Doc reference: LangGraph (docs.langchain.com/oss/python/langgraph/use-graph-api)

from typing import TypedDict, Literal, Annotated
from langgraph.graph import StateGraph, START, END
import operator
import anthropic

client = anthropic.Anthropic()

class AdaptiveRAGState(TypedDict):
    """State for adaptive RAG workflow."""
    question: str
    query_type: str
    retrieved_docs: Annotated[list[str], operator.add]
    sub_queries: list[str]
    sub_answers: dict[str, str]
    iteration_count: int
    final_answer: str

def classify_node(state: AdaptiveRAGState) -> dict:
    """Classify the query complexity."""
    result = classify_query_hybrid(state["question"], client)
    return {"query_type": result.query_type}

def route_by_type(state: AdaptiveRAGState) -> Literal[
    "simple_rag", "decomposition", "iterative_rag", "comparative_rag"
]:
    """Route to appropriate strategy based on classification."""
    type_to_strategy = {
        "simple": "simple_rag",
        "multi_part": "decomposition",
        "exploratory": "iterative_rag",
        "comparative": "comparative_rag"
    }
    return type_to_strategy.get(state["query_type"], "simple_rag")

# Strategy implementations (simplified - see notes 2-4 for full implementations)

def simple_rag_node(state: AdaptiveRAGState) -> dict:
    """Single-shot retrieval and generation."""
    docs = retrieve_from_vectorstore(state["question"], k=5)
    answer = generate_answer(state["question"], docs, client)
    return {
        "retrieved_docs": docs,
        "final_answer": answer
    }

def decomposition_node(state: AdaptiveRAGState) -> dict:
    """Decompose, retrieve for each sub-query, synthesize."""
    # Decompose
    sub_queries = decompose_query(state["question"], client)
    
    # Retrieve and answer each
    sub_answers = {}
    all_docs = []
    for sq in sub_queries:
        docs = retrieve_from_vectorstore(sq, k=3)
        all_docs.extend(docs)
        answer = generate_answer(sq, docs, client)
        sub_answers[sq] = answer
    
    # Synthesize
    final = synthesize_answers(state["question"], sub_answers, client)
    
    return {
        "sub_queries": sub_queries,
        "sub_answers": sub_answers,
        "retrieved_docs": all_docs,
        "final_answer": final
    }

def iterative_rag_node(state: AdaptiveRAGState) -> dict:
    """Iteratively retrieve until sufficient context."""
    all_docs = []
    current_query = state["question"]
    max_iterations = 3
    
    for i in range(max_iterations):
        docs = retrieve_from_vectorstore(current_query, k=5)
        all_docs.extend(docs)
        
        # Check sufficiency
        if is_sufficient(state["question"], all_docs, client):
            break
        
        # Refine query for next iteration
        current_query = refine_query(state["question"], all_docs, client)
    
    answer = generate_answer(state["question"], all_docs, client)
    
    return {
        "retrieved_docs": all_docs,
        "iteration_count": i + 1,
        "final_answer": answer
    }

def comparative_rag_node(state: AdaptiveRAGState) -> dict:
    """Retrieve multiple perspectives and compare."""
    # Extract comparison targets
    perspectives = extract_comparison_targets(state["question"], client)
    
    all_docs = []
    perspective_docs = {}
    
    for perspective in perspectives:
        docs = retrieve_from_vectorstore(
            f"{state['question']} {perspective}", 
            k=3
        )
        all_docs.extend(docs)
        perspective_docs[perspective] = docs
    
    # Generate comparative answer
    answer = generate_comparative_answer(
        state["question"], 
        perspective_docs, 
        client
    )
    
    return {
        "retrieved_docs": all_docs,
        "final_answer": answer
    }

# Build the graph
workflow = StateGraph(AdaptiveRAGState)

# Classification node
workflow.add_node("classify", classify_node)

# Strategy nodes
workflow.add_node("simple_rag", simple_rag_node)
workflow.add_node("decomposition", decomposition_node)
workflow.add_node("iterative_rag", iterative_rag_node)
workflow.add_node("comparative_rag", comparative_rag_node)

# Edges
workflow.add_edge(START, "classify")

# Route based on classification
workflow.add_conditional_edges(
    "classify",
    route_by_type,
    {
        "simple_rag": "simple_rag",
        "decomposition": "decomposition",
        "iterative_rag": "iterative_rag",
        "comparative_rag": "comparative_rag"
    }
)

# All strategies end the graph
workflow.add_edge("simple_rag", END)
workflow.add_edge("decomposition", END)
workflow.add_edge("iterative_rag", END)
workflow.add_edge("comparative_rag", END)

adaptive_rag = workflow.compile()
```

### Graph Visualization

```
START
  │
  ▼
┌──────────┐
│ classify │
└────┬─────┘
     │
     ├─────────────┬──────────────┬──────────────┐
     ▼             ▼              ▼              ▼
 simple        multi_part    exploratory    comparative
     │             │              │              │
     ▼             ▼              ▼              ▼
┌──────────┐ ┌────────────┐ ┌─────────────┐ ┌─────────────┐
│simple_rag│ │decomposition│ │iterative_rag│ │comparative_ │
└────┬─────┘ └──────┬─────┘ └──────┬──────┘ │    rag      │
     │              │              │        └──────┬──────┘
     │              │              │               │
     └──────────────┴──────────────┴───────────────┘
                           │
                           ▼
                          END
```

---

## Combining Patterns

Individual patterns can be combined for more sophisticated handling.

### Pattern 1: Decomposition + Self-Correction

Decompose the query, but verify each sub-answer before synthesis.

```python
def decomposition_with_verification_node(state: AdaptiveRAGState) -> dict:
    """
    Decompose → Retrieve for each → Verify each → Synthesize verified.
    """
    sub_queries = decompose_query(state["question"], client)
    
    verified_answers = {}
    all_docs = []
    
    for sq in sub_queries:
        docs = retrieve_from_vectorstore(sq, k=3)
        all_docs.extend(docs)
        
        # Generate sub-answer
        answer = generate_answer(sq, docs, client)
        
        # Verify sub-answer
        verification = verify_answer(sq, "\n".join(docs), answer, client)
        
        if verification.is_supported:
            verified_answers[sq] = answer
        else:
            # Try to correct
            corrected = correct_answer(sq, docs, answer, client)
            verified_answers[sq] = corrected
    
    # Synthesize only verified answers
    final = synthesize_answers(state["question"], verified_answers, client)
    
    return {
        "sub_queries": sub_queries,
        "sub_answers": verified_answers,
        "retrieved_docs": all_docs,
        "final_answer": final
    }
```

**When to use:** High-stakes multi-part questions where each component must be accurate.

### Pattern 2: Iterative + Self-Correction

Iterate until sufficient, then verify the final answer.

```python
def iterative_with_verification_node(state: AdaptiveRAGState) -> dict:
    """
    Iterate retrieval → Generate → Verify → Correct if needed.
    """
    all_docs = []
    current_query = state["question"]
    
    # Iterative retrieval phase
    for i in range(3):
        docs = retrieve_from_vectorstore(current_query, k=5)
        all_docs.extend(docs)
        
        if is_sufficient(state["question"], all_docs, client):
            break
        
        current_query = refine_query(state["question"], all_docs, client)
    
    # Generate
    answer = generate_answer(state["question"], all_docs, client)
    
    # Verify and correct
    verification = verify_answer(
        state["question"], 
        "\n".join(all_docs), 
        answer, 
        client
    )
    
    if not verification.is_supported:
        answer = correct_answer(
            state["question"], 
            all_docs, 
            answer, 
            client
        )
    
    return {
        "retrieved_docs": all_docs,
        "iteration_count": i + 1,
        "final_answer": answer
    }
```

**When to use:** Exploratory queries where comprehensive coverage AND accuracy both matter.

### Pattern 3: Adaptive Entry + Escalation

Start simple, escalate if results are poor.

```python
def adaptive_escalation_node(state: AdaptiveRAGState) -> dict:
    """
    Start with simple RAG. Escalate if insufficient.
    """
    # Try simple first
    docs = retrieve_from_vectorstore(state["question"], k=5)
    
    # Check if simple retrieval is sufficient
    if is_sufficient(state["question"], docs, client):
        answer = generate_answer(state["question"], docs, client)
        return {
            "retrieved_docs": docs,
            "query_type": "simple_escalated_to_simple",
            "final_answer": answer
        }
    
    # Escalate: try decomposition
    sub_queries = decompose_query(state["question"], client)
    
    if len(sub_queries) > 1:
        # Query was decomposable
        all_docs = list(docs)  # Keep original docs
        sub_answers = {}
        
        for sq in sub_queries:
            sq_docs = retrieve_from_vectorstore(sq, k=3)
            all_docs.extend(sq_docs)
            sub_answers[sq] = generate_answer(sq, sq_docs, client)
        
        final = synthesize_answers(state["question"], sub_answers, client)
        
        return {
            "retrieved_docs": all_docs,
            "sub_queries": sub_queries,
            "sub_answers": sub_answers,
            "query_type": "simple_escalated_to_decomposition",
            "final_answer": final
        }
    
    # Escalate: try iterative
    all_docs = list(docs)
    current_query = refine_query(state["question"], docs, client)
    
    for i in range(2):  # 2 more iterations
        new_docs = retrieve_from_vectorstore(current_query, k=5)
        all_docs.extend(new_docs)
        
        if is_sufficient(state["question"], all_docs, client):
            break
        
        current_query = refine_query(state["question"], all_docs, client)
    
    answer = generate_answer(state["question"], all_docs, client)
    
    return {
        "retrieved_docs": all_docs,
        "query_type": "simple_escalated_to_iterative",
        "final_answer": answer
    }
```

**When to use:** When you're unsure of query complexity upfront and want to minimize cost for truly simple queries while still handling complex ones well.

---

## When to Stay Simple

### The 80/20 Reality

In most production RAG systems:

- **80%+ of queries are simple** — direct lookups, single-topic questions
- **Agentic patterns add 2-10x cost and latency**
- **Over-engineering simple queries wastes resources**

**Default to simple unless you have evidence the query needs more.**

### Cost of Over-Engineering

|Strategy|LLM Calls|Latency|Token Cost|
|---|---|---|---|
|Simple RAG|1|~1-2s|1x|
|Classification + Simple|2|~2-3s|1.5x|
|Decomposition|5-8|~4-8s|3-5x|
|Iterative (3 iter)|6-9|~5-10s|3-6x|
|Full CRAG|7-10|~6-12s|4-7x|

**If simple RAG handles 90% of queries correctly, only route 10% to agentic patterns.**

### When Simple Is Enough

- Factual lookups: "What's the return address?"
- Definition queries: "What is our refund policy?"
- Single-topic questions: "How do I configure X?"
- Well-indexed content: Your corpus covers the topic well
- Latency-critical: User expects fast response

### When to Escalate

- Simple RAG fails frequently on this query type
- Query shows clear complexity signals
- Stakes justify the cost (legal, compliance, customer-facing)
- User explicitly requests comprehensive answer

---

## Production Decision Framework

### Step 1: Measure Baseline

Before adding complexity, measure simple RAG performance:

```python
def evaluate_simple_rag(
    test_queries: list[dict],  # {"query": str, "expected": str}
    retriever,
    llm_client
) -> dict:
    """
    Evaluate simple RAG baseline on test set.
    """
    results = {
        "correct": 0,
        "incorrect": 0,
        "failed_queries": []
    }
    
    for test in test_queries:
        docs = retriever.retrieve(test["query"], k=5)
        answer = generate_answer(test["query"], docs, llm_client)
        
        # Evaluate (use LLM-as-judge or human labels)
        is_correct = evaluate_answer(
            test["query"], 
            test["expected"], 
            answer
        )
        
        if is_correct:
            results["correct"] += 1
        else:
            results["incorrect"] += 1
            results["failed_queries"].append({
                "query": test["query"],
                "expected": test["expected"],
                "got": answer
            })
    
    results["accuracy"] = results["correct"] / len(test_queries)
    return results
```

### Step 2: Identify Failure Patterns

Analyze the queries where simple RAG fails:

```python
def analyze_failures(failed_queries: list[dict]) -> dict:
    """
    Categorize why simple RAG failed on these queries.
    """
    categories = {
        "retrieval_failure": [],  # Retrieved wrong docs
        "insufficient_context": [],  # Needed more info
        "complex_query": [],  # Query needed decomposition
        "comparison_needed": [],  # Needed multiple perspectives
        "other": []
    }
    
    for failure in failed_queries:
        # Classify failure type (could be LLM-based or manual)
        failure_type = classify_failure(failure)
        categories[failure_type].append(failure)
    
    return categories
```

### Step 3: Route Only Failing Types

Build routing rules based on observed failure patterns:

```python
def should_use_agentic(
    query: str,
    failure_analysis: dict
) -> tuple[bool, str]:
    """
    Decide if this query needs agentic treatment.
    Based on patterns learned from failure analysis.
    """
    # Extract patterns that led to failures
    complex_patterns = extract_patterns(failure_analysis["complex_query"])
    comparison_patterns = extract_patterns(failure_analysis["comparison_needed"])
    
    # Check if query matches failure patterns
    if matches_patterns(query, complex_patterns):
        return True, "decomposition"
    
    if matches_patterns(query, comparison_patterns):
        return True, "comparative"
    
    # Check for exploratory signals that failed before
    if is_exploratory(query) and failure_analysis.get("insufficient_context"):
        return True, "iterative"
    
    # Default: simple is fine
    return False, "simple"
```

### Step 4: Track and Iterate

Monitor the system in production:

```python
@dataclass
class QueryMetrics:
    query_type: str
    strategy_used: str
    latency_ms: int
    token_cost: int
    user_feedback: str  # thumbs up/down
    answer_quality: float  # if evaluated

def log_query_metrics(metrics: QueryMetrics, logger):
    """Log for analysis."""
    logger.info({
        "query_type": metrics.query_type,
        "strategy": metrics.strategy_used,
        "latency_ms": metrics.latency_ms,
        "cost": metrics.token_cost,
        "quality": metrics.answer_quality,
        "feedback": metrics.user_feedback
    })

def analyze_routing_effectiveness(logs: list[QueryMetrics]) -> dict:
    """
    Analyze if routing decisions are justified by quality improvement.
    """
    by_strategy = {}
    
    for log in logs:
        strategy = log.strategy_used
        if strategy not in by_strategy:
            by_strategy[strategy] = {
                "count": 0,
                "total_latency": 0,
                "total_cost": 0,
                "quality_scores": []
            }
        
        by_strategy[strategy]["count"] += 1
        by_strategy[strategy]["total_latency"] += log.latency_ms
        by_strategy[strategy]["total_cost"] += log.token_cost
        by_strategy[strategy]["quality_scores"].append(log.answer_quality)
    
    # Compute averages
    for strategy, data in by_strategy.items():
        data["avg_latency"] = data["total_latency"] / data["count"]
        data["avg_cost"] = data["total_cost"] / data["count"]
        data["avg_quality"] = sum(data["quality_scores"]) / len(data["quality_scores"])
        
        # Key metric: quality per cost
        data["quality_per_cost"] = data["avg_quality"] / data["avg_cost"]
    
    return by_strategy
```

**What to look for:**

- If iterative has same quality as simple but 3x cost → routing is wrong
- If decomposition significantly outperforms simple on certain queries → keep routing those
- If a strategy never gets used → consider removing to reduce complexity

---

## Complete Working Example

```python
"""
Adaptive RAG with LangGraph — Complete Implementation

Doc references:
- Anthropic SDK: platform.claude.com/docs/en/api/sdks/python
- LangGraph: docs.langchain.com/oss/python/langgraph/use-graph-api
"""

from typing import TypedDict, Literal, Annotated
from dataclasses import dataclass
from langgraph.graph import StateGraph, START, END
import operator
import anthropic
import re

client = anthropic.Anthropic()

# Mock retriever
def retrieve_from_vectorstore(query: str, k: int = 5) -> list[str]:
    return [f"Document about {query} - chunk {i}" for i in range(k)]

# Helper functions (simplified versions)
def generate_answer(question: str, docs: list[str], client) -> str:
    context = "\n".join(docs)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Answer: {question}\nContext: {context}"}]
    )
    return message.content[0].text

def is_sufficient(question: str, docs: list[str], client) -> bool:
    # Simplified check
    return len(docs) >= 5

def decompose_query(question: str, client) -> list[str]:
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": f"Break into 2-3 sub-questions: {question}"}]
    )
    # Parse numbered list
    lines = message.content[0].text.split("\n")
    return [l.split(". ", 1)[1] for l in lines if l and l[0].isdigit()][:3]

def synthesize_answers(question: str, sub_answers: dict, client) -> str:
    formatted = "\n".join([f"Q: {q}\nA: {a}" for q, a in sub_answers.items()])
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Synthesize for: {question}\n\n{formatted}"}]
    )
    return message.content[0].text

# Classification
QueryType = Literal["simple", "multi_part", "exploratory", "comparative"]

@dataclass
class ClassificationResult:
    query_type: QueryType
    confidence: str

def classify_query_hybrid(query: str, client) -> ClassificationResult:
    """Hybrid classification: rules first, LLM for ambiguous."""
    query_lower = query.lower()
    
    # Rule-based for obvious cases
    if any(w in query_lower for w in ["compare", " vs ", "versus", "difference between"]):
        return ClassificationResult("comparative", "HIGH")
    
    if any(w in query_lower for w in ["everything about", "summarize all", "comprehensive"]):
        return ClassificationResult("exploratory", "HIGH")
    
    if len(query.split()) < 10 and query.count("?") <= 1:
        if not any(w in query_lower for w in ["and", "also", "both"]):
            return ClassificationResult("simple", "HIGH")
    
    # LLM for ambiguous
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": f"""Classify: {query}
Types: SIMPLE, MULTI_PART, EXPLORATORY, COMPARATIVE
Reply: TYPE: [type]"""}]
    )
    
    response = message.content[0].text.upper()
    for t in ["SIMPLE", "MULTI_PART", "EXPLORATORY", "COMPARATIVE"]:
        if t in response:
            return ClassificationResult(t.lower(), "MEDIUM")
    
    return ClassificationResult("simple", "LOW")

# State
class AdaptiveRAGState(TypedDict):
    question: str
    query_type: str
    retrieved_docs: list[str]
    sub_queries: list[str]
    sub_answers: dict[str, str]
    final_answer: str

# Nodes
def classify_node(state: AdaptiveRAGState) -> dict:
    result = classify_query_hybrid(state["question"], client)
    return {"query_type": result.query_type}

def route_by_type(state: AdaptiveRAGState) -> str:
    return {
        "simple": "simple_rag",
        "multi_part": "decomposition",
        "exploratory": "iterative_rag",
        "comparative": "comparative_rag"
    }.get(state["query_type"], "simple_rag")

def simple_rag_node(state: AdaptiveRAGState) -> dict:
    docs = retrieve_from_vectorstore(state["question"], k=5)
    answer = generate_answer(state["question"], docs, client)
    return {"retrieved_docs": docs, "final_answer": answer}

def decomposition_node(state: AdaptiveRAGState) -> dict:
    sub_queries = decompose_query(state["question"], client)
    sub_answers = {}
    all_docs = []
    
    for sq in sub_queries:
        docs = retrieve_from_vectorstore(sq, k=3)
        all_docs.extend(docs)
        sub_answers[sq] = generate_answer(sq, docs, client)
    
    final = synthesize_answers(state["question"], sub_answers, client)
    return {
        "sub_queries": sub_queries,
        "sub_answers": sub_answers,
        "retrieved_docs": all_docs,
        "final_answer": final
    }

def iterative_rag_node(state: AdaptiveRAGState) -> dict:
    all_docs = []
    for i in range(3):
        docs = retrieve_from_vectorstore(state["question"], k=5)
        all_docs.extend(docs)
        if len(all_docs) >= 10:
            break
    
    answer = generate_answer(state["question"], all_docs, client)
    return {"retrieved_docs": all_docs, "final_answer": answer}

def comparative_rag_node(state: AdaptiveRAGState) -> dict:
    # Extract items to compare (simplified)
    docs_a = retrieve_from_vectorstore(f"{state['question']} first option", k=3)
    docs_b = retrieve_from_vectorstore(f"{state['question']} second option", k=3)
    all_docs = docs_a + docs_b
    
    answer = generate_answer(state["question"], all_docs, client)
    return {"retrieved_docs": all_docs, "final_answer": answer}

# Build graph
workflow = StateGraph(AdaptiveRAGState)

workflow.add_node("classify", classify_node)
workflow.add_node("simple_rag", simple_rag_node)
workflow.add_node("decomposition", decomposition_node)
workflow.add_node("iterative_rag", iterative_rag_node)
workflow.add_node("comparative_rag", comparative_rag_node)

workflow.add_edge(START, "classify")
workflow.add_conditional_edges(
    "classify",
    route_by_type,
    {
        "simple_rag": "simple_rag",
        "decomposition": "decomposition",
        "iterative_rag": "iterative_rag",
        "comparative_rag": "comparative_rag"
    }
)
workflow.add_edge("simple_rag", END)
workflow.add_edge("decomposition", END)
workflow.add_edge("iterative_rag", END)
workflow.add_edge("comparative_rag", END)

adaptive_rag = workflow.compile()

# Usage
def run_adaptive_rag(question: str) -> dict:
    initial = {
        "question": question,
        "query_type": "",
        "retrieved_docs": [],
        "sub_queries": [],
        "sub_answers": {},
        "final_answer": ""
    }
    
    result = adaptive_rag.invoke(initial)
    
    return {
        "answer": result["final_answer"],
        "strategy_used": result["query_type"],
        "docs_retrieved": len(result["retrieved_docs"]),
        "sub_queries": result.get("sub_queries", [])
    }

# Test
if __name__ == "__main__":
    test_queries = [
        "What's our refund policy?",  # Simple
        "Compare 2023 and 2024 roadmaps",  # Comparative
        "What is X, why does it matter, and how do we use it?",  # Multi-part
        "Tell me everything about customer feedback"  # Exploratory
    ]
    
    for q in test_queries:
        result = run_adaptive_rag(q)
        print(f"\nQuery: {q}")
        print(f"Strategy: {result['strategy_used']}")
        print(f"Docs: {result['docs_retrieved']}")
```

---

## Key Takeaways

1. **Not all queries need the same strategy** — simple queries should stay simple; complex queries need more sophisticated handling.
    
2. **Classification is the entry point** — rule-based for obvious cases, LLM for ambiguous. Hybrid works best.
    
3. **Four main query types**: simple (single retrieval), multi-part (decomposition), exploratory (iterative), comparative (multi-perspective).
    
4. **Patterns can be combined** — decomposition + verification, iterative + correction, adaptive escalation.
    
5. **Default to simple** — 80%+ of queries are simple. Agentic patterns add 2-10x cost. Only route complex queries to complex strategies.
    
6. **Measure before you engineer** — baseline simple RAG performance first, identify failure patterns, route only failing types.
    
7. **Track cost vs. quality** — the goal is quality improvement that justifies the added cost. If iterative doesn't beat simple, don't use it.
    
8. **Production framework**: Baseline → Identify failures → Route failures to agentic → Track effectiveness → Iterate.