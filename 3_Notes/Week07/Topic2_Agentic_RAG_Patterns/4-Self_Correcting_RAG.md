# Note 4: Self-Correcting RAG (CRAG) — Verify Before You Trust

## The CRAG Insight

Standard RAG trusts retrieval implicitly: whatever comes back from the vector store gets passed to generation. But retrieval can fail — irrelevant documents, missing context, wrong information.

**CRAG (Corrective Retrieval Augmented Generation)** adds verification loops:

```
START
  │
  ▼
┌──────────┐
│ retrieve │
└────┬─────┘
     │
     ▼
┌──────────────────┐
│ grade_documents  │
└────────┬─────────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
correct   ambiguous    incorrect
    │         │            │
    ▼         ▼            ▼
generate  web_search   reformulate
    │         │            │
    │         └──────┬─────┘
    │                │
    ▼◄───────────────┘
┌──────────┐
│ generate │
└────┬─────┘
     │
     ▼
┌──────────┐
│  verify  │◄────────┐
└────┬─────┘         │
     │               │
 supported?          │
     │               │
  ┌──┴──┐           │
 Yes    No          │
  │      │          │
  │      ▼          │
  │  ┌─────────┐    │
  │  │ correct │────┘
  │  └─────────┘
  │
  ▼
┌──────────┐
│ finalize │
└────┬─────┘
     │
     ▼
    END
```

**Key insight from the paper (Yan et al., 2024):** RAG systems fail silently when retrieval returns irrelevant documents. The model generates confidently, but the answer is wrong. CRAG catches these failures by evaluating retrieval quality before generation and answer grounding after.

---

## Two Evaluation Points

CRAG introduces verification at two critical junctures:

### 1. Document Grading (Before Generation)

**Question:** Are the retrieved documents actually relevant to the query?

- Grade each retrieved document for relevance
- If all documents grade low → don't generate, try a different strategy
- Filters out irrelevant context before it can pollute generation

### 2. Answer Verification (After Generation)

**Question:** Is the generated answer actually supported by the retrieved context?

- Check if each claim in the answer has backing in the context
- Catches hallucinations that sneak past retrieval
- Triggers correction if answer contains unsupported claims

These are complementary, not redundant. Document grading catches retrieval failures. Answer verification catches generation failures.

---

## Document Grading: Filter Before You Generate

### The Problem Document Grading Solves

Vector similarity isn't semantic relevance. A document might score highly because of surface-level word overlap while being completely off-topic for the actual question.

**Example:**

- Query: "What is our refund policy for enterprise customers?"
- Retrieved doc: "Enterprise customers receive dedicated support and priority onboarding." (mentions "enterprise" but nothing about refunds)

Without grading, this irrelevant document gets passed to generation, potentially leading to hallucinated refund policies.

### LLM-Based Document Grading

```python
# Doc reference: Anthropic Python SDK (platform.claude.com/docs/en/api/sdks/python)

import anthropic
from dataclasses import dataclass

@dataclass
class GradedDocument:
    content: str
    is_relevant: bool
    relevance_reasoning: str

GRADING_PROMPT = """You are grading the relevance of a document to a question.

Question: {question}

Document:
{document}

Is this document relevant to answering the question?
A document is relevant if it contains information that would help answer the question.

Respond in this format:
RELEVANT: YES or NO
REASONING: [Brief explanation of why]"""

def grade_document(
    question: str,
    document: str,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> GradedDocument:
    """
    Grade a single document for relevance to the question.
    """
    message = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": GRADING_PROMPT.format(
                question=question,
                document=document
            )
        }]
    )
    
    response = message.content[0].text
    
    is_relevant = "RELEVANT: YES" in response.upper()
    reasoning = ""
    for line in response.split("\n"):
        if line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()
    
    return GradedDocument(
        content=document,
        is_relevant=is_relevant,
        relevance_reasoning=reasoning
    )

def grade_all_documents(
    question: str,
    documents: list[str],
    client: anthropic.Anthropic
) -> tuple[list[str], list[str]]:
    """
    Grade all documents and return (relevant, irrelevant) split.
    """
    relevant = []
    irrelevant = []
    
    for doc in documents:
        graded = grade_document(question, doc, client)
        if graded.is_relevant:
            relevant.append(doc)
        else:
            irrelevant.append(doc)
    
    return relevant, irrelevant
```

### Routing Based on Grading Results

The CRAG paper defines three confidence levels based on grading:

|Confidence|Condition|Action|
|---|---|---|
|**CORRECT**|At least one doc highly relevant|Proceed to generation with relevant docs|
|**AMBIGUOUS**|Docs partially relevant|Combine retrieval with web search|
|**INCORRECT**|All docs irrelevant|Abandon retrieval, use web search only|

```python
from typing import Literal

def classify_retrieval_quality(
    relevant_docs: list[str],
    total_docs: int
) -> Literal["correct", "ambiguous", "incorrect"]:
    """
    Classify overall retrieval quality based on grading results.
    """
    if len(relevant_docs) == 0:
        return "incorrect"
    
    relevance_ratio = len(relevant_docs) / total_docs
    
    if relevance_ratio >= 0.5:
        return "correct"
    else:
        return "ambiguous"
```

---

## Answer Verification: Check After You Generate

### The Problem Verification Solves

Even with good retrieval, generation can hallucinate. The model might:

- Add details not present in context
- Misinterpret or misquote context
- Confidently state things that contradict context

**Example:**

- Context: "Our refund policy allows returns within a reasonable timeframe."
- Generated answer: "You can return items within 30 days for a full refund."
- **Problem:** The 30-day timeframe was hallucinated — context never specified a number.

### LLM-Based Answer Verification

```python
@dataclass
class VerificationResult:
    is_supported: bool
    unsupported_claims: list[str]
    reasoning: str

VERIFICATION_PROMPT = """You are verifying if an answer is fully supported by the provided context.

Question: {question}

Context:
{context}

Generated Answer:
{answer}

Check if EVERY claim in the answer is supported by the context.
A claim is unsupported if:
- It adds specific details not in the context (dates, numbers, names)
- It contradicts the context
- It makes assertions the context doesn't make

Respond in this format:
SUPPORTED: YES or NO
UNSUPPORTED_CLAIMS: [List specific claims not supported, or "None"]
REASONING: [Brief explanation]"""

def verify_answer(
    question: str,
    context: str,
    answer: str,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> VerificationResult:
    """
    Verify if the generated answer is supported by context.
    """
    message = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": VERIFICATION_PROMPT.format(
                question=question,
                context=context,
                answer=answer
            )
        }]
    )
    
    response = message.content[0].text
    
    is_supported = "SUPPORTED: YES" in response.upper()
    
    unsupported_claims = []
    reasoning = ""
    
    for line in response.split("\n"):
        if line.startswith("UNSUPPORTED_CLAIMS:"):
            claims_text = line.replace("UNSUPPORTED_CLAIMS:", "").strip()
            if claims_text.lower() != "none":
                unsupported_claims = [c.strip() for c in claims_text.split(",")]
        elif line.startswith("REASONING:"):
            reasoning = line.replace("REASONING:", "").strip()
    
    return VerificationResult(
        is_supported=is_supported,
        unsupported_claims=unsupported_claims,
        reasoning=reasoning
    )
```

---

## Fallback Strategies

When verification fails, what do you do? CRAG and similar systems offer several fallback strategies:

### Strategy 1: Re-Retrieve with Different Query

If grading shows documents are irrelevant, the query might be poorly formulated.

```python
def reformulate_query(
    original_query: str,
    failed_docs: list[str],
    client: anthropic.Anthropic
) -> str:
    """
    Generate a reformulated query when original retrieval failed.
    """
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""The following query returned irrelevant documents.

Original query: {original_query}

Generate a reformulated search query that might find more relevant information.
Be more specific or try different terminology.

New query:"""
        }]
    )
    
    return message.content[0].text.strip()
```

### Strategy 2: Fall Back to Web Search

The CRAG paper specifically uses web search when corpus retrieval fails. This is practical for many domains where the corpus might not have complete coverage.

```python
def web_search_fallback(
    query: str,
    search_client  # Your search API client
) -> list[str]:
    """
    Fall back to web search when corpus retrieval is insufficient.
    
    Note: Requires integration with search API (e.g., Tavily, SerpAPI, Brave).
    """
    results = search_client.search(query, num_results=5)
    return [r.content for r in results]
```

### Strategy 3: Honest Uncertainty

Sometimes the right answer is "I don't know." If retrieval fails and fallbacks don't help, acknowledge uncertainty.

```python
def generate_with_uncertainty(
    question: str,
    partial_context: str,
    client: anthropic.Anthropic
) -> str:
    """
    Generate a response that acknowledges uncertainty.
    """
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Answer this question based on limited context.
Be explicit about what you can and cannot answer.

Question: {question}

Available Context (may be incomplete):
{partial_context}

Instructions:
- Answer what you can based on the context
- Explicitly state what information is missing
- Don't make up specifics not in the context

Answer:"""
        }]
    )
    
    return message.content[0].text
```

### Strategy 4: Ask for Clarification

If the query is ambiguous, asking the user might be better than guessing.

```python
def request_clarification(
    question: str,
    ambiguity: str
) -> str:
    """
    Generate a clarification request for the user.
    """
    return f"""I'm not sure I have the right information to answer your question.

Your question: {question}

The ambiguity: {ambiguity}

Could you clarify what you're looking for? For example:
- Are you asking about [specific interpretation A]?
- Or are you asking about [specific interpretation B]?"""
```

---

## LangGraph Implementation

A full CRAG implementation in LangGraph with conditional routing:

```python
# Doc reference: LangGraph (docs.langchain.com/oss/python/langgraph/use-graph-api)
# Pattern: Conditional edges for grade-based routing, cycles for correction

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
import operator
import anthropic

client = anthropic.Anthropic()

class CRAGState(TypedDict):
    """State for CRAG workflow."""
    question: str
    retrieved_docs: list[str]
    relevant_docs: list[str]
    retrieval_quality: str  # "correct", "ambiguous", "incorrect"
    generated_answer: str
    is_verified: bool
    correction_attempts: int
    final_answer: str

def retrieve_node(state: CRAGState) -> dict:
    """Initial retrieval from vector store."""
    docs = retrieve_from_vectorstore(state["question"], k=5)
    return {"retrieved_docs": docs}

def grade_documents_node(state: CRAGState) -> dict:
    """Grade each document for relevance."""
    relevant = []
    
    for doc in state["retrieved_docs"]:
        graded = grade_document(state["question"], doc, client)
        if graded.is_relevant:
            relevant.append(doc)
    
    # Classify overall quality
    quality = classify_retrieval_quality(relevant, len(state["retrieved_docs"]))
    
    return {
        "relevant_docs": relevant,
        "retrieval_quality": quality
    }

def route_after_grading(state: CRAGState) -> Literal["generate", "web_search", "reformulate"]:
    """Route based on document grading results."""
    if state["retrieval_quality"] == "correct":
        return "generate"
    elif state["retrieval_quality"] == "ambiguous":
        return "web_search"  # Supplement with web search
    else:  # incorrect
        return "reformulate"  # Try different query

def web_search_node(state: CRAGState) -> dict:
    """Supplement retrieval with web search."""
    # In production, integrate with actual search API
    web_results = web_search_fallback(state["question"], search_client)
    
    # Combine with any relevant docs we have
    combined = state["relevant_docs"] + web_results
    
    return {"relevant_docs": combined}

def reformulate_node(state: CRAGState) -> dict:
    """Reformulate query and re-retrieve."""
    new_query = reformulate_query(
        state["question"],
        state["retrieved_docs"],
        client
    )
    
    # Re-retrieve with new query
    new_docs = retrieve_from_vectorstore(new_query, k=5)
    
    # Grade new docs
    relevant = []
    for doc in new_docs:
        graded = grade_document(state["question"], doc, client)
        if graded.is_relevant:
            relevant.append(doc)
    
    return {"relevant_docs": relevant}

def generate_node(state: CRAGState) -> dict:
    """Generate answer from relevant documents."""
    context = "\n\n".join(state["relevant_docs"])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Answer based on the provided context.
Only include information that is directly supported by the context.

Question: {state["question"]}

Context:
{context}

Answer:"""
        }]
    )
    
    return {"generated_answer": message.content[0].text}

def verify_node(state: CRAGState) -> dict:
    """Verify answer is supported by context."""
    context = "\n\n".join(state["relevant_docs"])
    
    result = verify_answer(
        state["question"],
        context,
        state["generated_answer"],
        client
    )
    
    return {
        "is_verified": result.is_supported,
        "correction_attempts": state["correction_attempts"] + 1
    }

def route_after_verification(state: CRAGState) -> Literal["finalize", "correct"]:
    """Route based on verification result."""
    if state["is_verified"]:
        return "finalize"
    
    # Limit correction attempts to avoid loops
    if state["correction_attempts"] >= 2:
        return "finalize"  # Give up, return best effort
    
    return "correct"

def correct_node(state: CRAGState) -> dict:
    """Attempt to correct unsupported answer."""
    context = "\n\n".join(state["relevant_docs"])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Your previous answer contained claims not supported by the context.

Question: {state["question"]}

Context:
{context}

Previous Answer (contains unsupported claims):
{state["generated_answer"]}

Generate a new answer that ONLY includes information directly stated in the context.
If you cannot fully answer the question with the available context, say so.

Corrected Answer:"""
        }]
    )
    
    return {"generated_answer": message.content[0].text}

def finalize_node(state: CRAGState) -> dict:
    """Finalize the answer."""
    # Add uncertainty marker if not verified
    if not state["is_verified"]:
        answer = f"{state['generated_answer']}\n\n[Note: Some claims may not be fully verified against source documents.]"
    else:
        answer = state["generated_answer"]
    
    return {"final_answer": answer}

# Build the graph
workflow = StateGraph(CRAGState)

# Add nodes
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade_documents", grade_documents_node)
workflow.add_node("web_search", web_search_node)
workflow.add_node("reformulate", reformulate_node)
workflow.add_node("generate", generate_node)
workflow.add_node("verify", verify_node)
workflow.add_node("correct", correct_node)
workflow.add_node("finalize", finalize_node)

# Define edges
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "grade_documents")

# Conditional routing after grading
workflow.add_conditional_edges(
    "grade_documents",
    route_after_grading,
    {
        "generate": "generate",
        "web_search": "web_search",
        "reformulate": "reformulate"
    }
)

# After fallbacks, proceed to generate
workflow.add_edge("web_search", "generate")
workflow.add_edge("reformulate", "generate")

# After generation, verify
workflow.add_edge("generate", "verify")

# Conditional routing after verification
workflow.add_conditional_edges(
    "verify",
    route_after_verification,
    {
        "finalize": "finalize",
        "correct": "correct"
    }
)

# Correction loops back to verify
workflow.add_edge("correct", "verify")

# Finalize ends the graph
workflow.add_edge("finalize", END)

crag_graph = workflow.compile()
```

### Graph Visualization

```
START
  │
  ▼
┌──────────┐
│ retrieve │
└────┬─────┘
     │
     ▼
┌──────────────────┐
│ grade_documents  │
└────────┬─────────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
correct   ambiguous    incorrect
    │         │            │
    ▼         ▼            ▼
generate  web_search   reformulate
    │         │            │
    │         └──────┬─────┘
    │                │
    ▼◄───────────────┘
┌──────────┐
│ generate │
└────┬─────┘
     │
     ▼
┌──────────┐
│  verify  │◄────────┐
└────┬─────┘         │
     │               │
 supported?          │
     │               │
  ┌──┴──┐           │
 Yes    No          │
  │      │          │
  │      ▼          │
  │  ┌─────────┐    │
  │  │ correct │────┘
  │  └─────────┘
  │
  ▼
┌──────────┐
│ finalize │
└────┬─────┘
     │
     ▼
    END
```

---

## The LLM-Checking-Itself Problem

A fundamental tension in CRAG: **the LLM is evaluating its own work.**

### Why Self-Verification Is Problematic

1. **Confirmation bias**: The same model that generated an answer may be predisposed to verify it as correct.
    
2. **Shared blind spots**: If the model hallucinates because of a knowledge gap, it may not recognize the hallucination during verification.
    
3. **Confident errors**: LLMs can be confidently wrong. A verification check might confidently approve a hallucinated answer.
    

**Example:**

- Generated answer: "The company was founded in 2015."
- Context: Silent on founding date
- Verification: "Yes, this is supported" (model may "recognize" the date from training data, not notice it's not in context)

### Mitigation Strategies

**1. Use Different Models**

Use a different model for verification than generation. Different models have different failure modes.

```python
def verify_with_different_model(
    question: str,
    context: str,
    answer: str,
    client: anthropic.Anthropic
) -> VerificationResult:
    """
    Use a different model for verification to reduce shared biases.
    """
    # Generate with Sonnet
    # Verify with a different model (Haiku for speed, or Opus for thoroughness)
    return verify_answer(
        question, 
        context, 
        answer, 
        client,
        model="claude-haiku-4-5-20251001"  # Different from generation model
    )
```

**2. Structured Verification Prompts**

Force the verifier to cite specific context for each claim:

```python
STRICT_VERIFICATION_PROMPT = """Verify each claim in the answer by citing the exact context that supports it.

Question: {question}

Context:
{context}

Answer to verify:
{answer}

For EACH claim in the answer:
1. State the claim
2. Quote the EXACT text from context that supports it
3. If no exact text supports it, mark as UNSUPPORTED

Format:
CLAIM: [claim text]
SUPPORTING QUOTE: [exact quote from context] or UNSUPPORTED
---

After checking all claims:
VERDICT: FULLY_SUPPORTED, PARTIALLY_SUPPORTED, or UNSUPPORTED"""
```

This forces explicit grounding rather than vibes-based verification.

**3. Don't Rely Solely on Self-Verification**

For high-stakes answers, self-verification is a filter, not a guarantee.

- Use it to catch obvious errors
- Don't trust it for subtle hallucinations
- Consider human review for critical decisions
- Log verification results for monitoring

---

## When CRAG Helps

### High-Stakes Answers Requiring Accuracy

- Legal/compliance queries
- Medical information
- Financial advice
- Customer-facing statements that could create liability

The cost of hallucination exceeds the cost of verification.

### Domains Prone to Hallucination

- Technical details (version numbers, config syntax)
- Specific dates and numbers
- Proper names and quotes
- Anything with precise right/wrong answers

### Inconsistent Retrieval Quality

- Mixed-quality document corpus
- Documents of varying relevance to domain
- Corpus with outdated information mixed with current
- User queries that often miss the indexed terminology

---

## When CRAG Adds Overhead Without Benefit

### Simple Factual Lookups

"What's the office address?" — If retrieval works, verification overhead isn't needed.

### High-Quality Curated Corpus

If your document corpus is well-maintained and highly relevant, document grading catches few issues.

### Latency-Critical Applications

CRAG adds 2-4 LLM calls per query:

- Document grading: 1 per document (can batch)
- Generation: 1
- Verification: 1
- Potential correction: 1

For real-time chat, this latency may be unacceptable.

### When Abstaining Isn't Acceptable

If the system must produce an answer (even with caveats), CRAG's "I don't know" fallback may not be appropriate.

---

## Cost Analysis

|Component|LLM Calls|Tokens (approx)|
|---|---|---|
|Document grading (5 docs)|5|~1000 total|
|Generation|1|~500-1500|
|Verification|1|~800|
|Correction (if needed)|1|~1000|
|**Total (happy path)**|**7**|**~2500**|
|**Total (with correction)**|**8**|**~3500**|

**Compare to standard RAG:**

- Standard RAG: 1 LLM call, ~500-1500 tokens
- CRAG: 7-8 LLM calls, ~2500-3500 tokens
- **~5-7x cost increase**

**Optimization: Batch document grading**

Instead of grading each document separately, grade all in one call:

```python
def grade_documents_batched(
    question: str,
    documents: list[str],
    client: anthropic.Anthropic
) -> list[bool]:
    """
    Grade all documents in a single LLM call.
    """
    docs_formatted = "\n\n---\n\n".join([
        f"Document {i+1}:\n{doc}" 
        for i, doc in enumerate(documents)
    ])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Grade each document's relevance to the question.

Question: {question}

{docs_formatted}

For each document, respond YES (relevant) or NO (not relevant).
Format: 1: YES/NO, 2: YES/NO, ..."""
        }]
    )
    
    # Parse response
    response = message.content[0].text
    relevances = []
    for part in response.split(","):
        relevances.append("YES" in part.upper())
    
    return relevances
```

This reduces grading from 5 calls to 1.

---

## Complete Working Example

```python
"""
CRAG Implementation with LangGraph — Complete Example

Doc references:
- Anthropic SDK: platform.claude.com/docs/en/api/sdks/python
- LangGraph: docs.langchain.com/oss/python/langgraph/use-graph-api
- CRAG paper: arxiv.org/abs/2401.15884
"""

from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
import anthropic

client = anthropic.Anthropic()

# Mock retriever
def retrieve_from_vectorstore(query: str, k: int = 5) -> list[str]:
    return [f"Document about {query} - chunk {i}" for i in range(k)]

class CRAGState(TypedDict):
    question: str
    retrieved_docs: list[str]
    relevant_docs: list[str]
    retrieval_quality: str
    generated_answer: str
    is_verified: bool
    correction_attempts: int
    final_answer: str

def grade_documents_batched(question: str, documents: list[str]) -> list[bool]:
    """Batch grade all documents in one call."""
    docs_text = "\n---\n".join([f"Doc {i+1}: {doc[:200]}" for i, doc in enumerate(documents)])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""Grade each document's relevance to: {question}

{docs_text}

Reply format: 1:YES/NO, 2:YES/NO, ..."""
        }]
    )
    
    response = message.content[0].text.upper()
    return ["YES" in part for part in response.split(",")]

def retrieve_node(state: CRAGState) -> dict:
    docs = retrieve_from_vectorstore(state["question"], k=5)
    return {"retrieved_docs": docs, "correction_attempts": 0}

def grade_node(state: CRAGState) -> dict:
    relevances = grade_documents_batched(state["question"], state["retrieved_docs"])
    relevant = [doc for doc, rel in zip(state["retrieved_docs"], relevances) if rel]
    
    ratio = len(relevant) / len(state["retrieved_docs"]) if state["retrieved_docs"] else 0
    quality = "correct" if ratio >= 0.5 else ("ambiguous" if ratio > 0 else "incorrect")
    
    return {"relevant_docs": relevant, "retrieval_quality": quality}

def route_after_grade(state: CRAGState) -> Literal["generate", "fallback"]:
    if state["retrieval_quality"] == "correct":
        return "generate"
    return "fallback"

def fallback_node(state: CRAGState) -> dict:
    """Simplified fallback: acknowledge limited info."""
    return {"relevant_docs": state["relevant_docs"] or ["No relevant documents found."]}

def generate_node(state: CRAGState) -> dict:
    context = "\n".join(state["relevant_docs"])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Answer based only on context. If context is insufficient, say so.

Question: {state["question"]}
Context: {context}

Answer:"""
        }]
    )
    
    return {"generated_answer": message.content[0].text}

def verify_node(state: CRAGState) -> dict:
    context = "\n".join(state["relevant_docs"])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""Is this answer supported by the context? Reply SUPPORTED or UNSUPPORTED.

Context: {context}
Answer: {state["generated_answer"]}

Verdict:"""
        }]
    )
    
    is_supported = "SUPPORTED" in message.content[0].text.upper() and "UNSUPPORTED" not in message.content[0].text.upper()
    
    return {
        "is_verified": is_supported,
        "correction_attempts": state["correction_attempts"] + 1
    }

def route_after_verify(state: CRAGState) -> Literal["finalize", "correct"]:
    if state["is_verified"] or state["correction_attempts"] >= 2:
        return "finalize"
    return "correct"

def correct_node(state: CRAGState) -> dict:
    context = "\n".join(state["relevant_docs"])
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Rewrite this answer to ONLY include claims from the context.

Context: {context}
Original answer: {state["generated_answer"]}

Corrected answer:"""
        }]
    )
    
    return {"generated_answer": message.content[0].text}

def finalize_node(state: CRAGState) -> dict:
    answer = state["generated_answer"]
    if not state["is_verified"]:
        answer += "\n\n[Note: Answer could not be fully verified against sources.]"
    return {"final_answer": answer}

# Build graph
workflow = StateGraph(CRAGState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade", grade_node)
workflow.add_node("fallback", fallback_node)
workflow.add_node("generate", generate_node)
workflow.add_node("verify", verify_node)
workflow.add_node("correct", correct_node)
workflow.add_node("finalize", finalize_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "grade")
workflow.add_conditional_edges("grade", route_after_grade, {"generate": "generate", "fallback": "fallback"})
workflow.add_edge("fallback", "generate")
workflow.add_edge("generate", "verify")
workflow.add_conditional_edges("verify", route_after_verify, {"finalize": "finalize", "correct": "correct"})
workflow.add_edge("correct", "verify")
workflow.add_edge("finalize", END)

crag = workflow.compile()

# Usage
def run_crag(question: str) -> dict:
    initial = {
        "question": question,
        "retrieved_docs": [],
        "relevant_docs": [],
        "retrieval_quality": "",
        "generated_answer": "",
        "is_verified": False,
        "correction_attempts": 0,
        "final_answer": ""
    }
    
    result = crag.invoke(initial)
    
    return {
        "answer": result["final_answer"],
        "verified": result["is_verified"],
        "retrieval_quality": result["retrieval_quality"],
        "corrections_made": result["correction_attempts"] - 1
    }

if __name__ == "__main__":
    result = run_crag("What is our refund policy for enterprise customers?")
    print(f"Answer: {result['answer']}")
    print(f"Verified: {result['verified']}")
    print(f"Retrieval quality: {result['retrieval_quality']}")
```

---

## Key Takeaways

1. **CRAG adds verification loops to RAG** — grade documents before generation, verify answer after.
    
2. **Two evaluation points serve different purposes** — document grading catches retrieval failures; answer verification catches generation failures.
    
3. **Fallback strategies provide graceful degradation** — re-retrieve, web search, admit uncertainty, or ask for clarification.
    
4. **Self-verification has fundamental limits** — the LLM checking its own work may share the same blind spots. Use different models, structured prompts, and don't rely solely on self-verification for high stakes.
    
5. **CRAG is expensive** — 5-7x the LLM calls of standard RAG. Use it selectively where accuracy justifies cost.
    
6. **Batch document grading reduces cost** — grade all documents in one call instead of separately.
    
7. **Best for high-stakes, hallucination-prone domains** — legal, medical, financial, technical details where errors are costly.
    
8. **Limit correction attempts** — bound the correction loop to avoid infinite cycles (typically max 2 attempts).