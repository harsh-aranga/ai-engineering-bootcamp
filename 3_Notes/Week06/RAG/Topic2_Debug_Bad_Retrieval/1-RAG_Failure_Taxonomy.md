# RAG Failure Taxonomy

## The Core Insight

Your RAG system returns a wrong answer. Now what?

The failure could be anywhere in the pipeline — bad chunking, bad retrieval, bad context assembly, bad generation. Without classification, you're guessing. You might spend days tuning your embedding model when the problem is actually the LLM ignoring relevant context.

**The taxonomy exists because different failures need different fixes:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Why Taxonomy Matters                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Symptom: "RAG gave wrong answer about Q3 revenue"                 │
│                                                                     │
│   Without taxonomy:                                                 │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  "Let's try different chunking"                             │   │
│   │  "Maybe we need a better embedding model"                   │   │
│   │  "Should we increase top-k?"                                │   │
│   │  "Let's rewrite the prompt"                                 │   │
│   │                                                             │   │
│   │  → Random fixes, no systematic approach                     │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   With taxonomy:                                                    │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Step 1: Was relevant doc retrieved? → YES                  │   │
│   │  Step 2: Was it in final context?    → YES                  │   │
│   │  Step 3: Did LLM use it correctly?   → NO                   │   │
│   │                                                             │   │
│   │  Diagnosis: GENERATION FAILURE                              │   │
│   │  Fix: Prompt engineering, not retrieval tuning              │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

Classification before fixing. Always.

---

## The Four Failure Categories

RAG failures map to pipeline stages. Each stage can independently fail:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         RAG Pipeline Stages                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   DOCUMENTS                                                              │
│       │                                                                  │
│       ▼                                                                  │
│   ┌────────────────┐                                                     │
│   │   INDEXING     │ ◄── Failure Type 1: Content never makes it in      │
│   │   (chunking,   │     or is split/mangled during ingestion           │
│   │   embedding)   │                                                     │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │   RETRIEVAL    │ ◄── Failure Type 2: Wrong documents retrieved      │
│   │   (search,     │     or relevant ones ranked too low                │
│   │   ranking)     │                                                     │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │   CONTEXT      │ ◄── Failure Type 3: Right docs retrieved but       │
│   │   ASSEMBLY     │     wrong context sent to LLM                      │
│   │   (reranking,  │                                                     │
│   │   selection)   │                                                     │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │   GENERATION   │ ◄── Failure Type 4: Right context but LLM          │
│   │   (LLM call)   │     produces wrong answer anyway                   │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│       ANSWER                                                             │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

|Category|Pipeline Stage|Core Question|
|---|---|---|
|**Indexing**|Before retrieval|Did the relevant content make it into the index correctly?|
|**Retrieval**|Search & ranking|Did we find and rank the relevant documents?|
|**Context Assembly**|Post-retrieval|Did we send the right context to the LLM?|
|**Generation**|LLM response|Did the LLM use the context correctly?|

---

## Indexing Failures

**What breaks:** Problems occur _before_ any query is ever made. The content is either missing, corrupted, or split in ways that destroy meaning.

### Failure Subtypes

|Subtype|Description|Example|
|---|---|---|
|**Document not indexed**|File skipped, parsing failed, or filtered out|PDF with scanned images (no OCR) never extracted|
|**Chunking split key info**|Critical information spans chunk boundary|"Revenue was $50M" in chunk 1, "in Q3 2024" in chunk 2|
|**Metadata not extracted**|Important context lost during ingestion|Date, author, document type not captured|
|**Embedding distortion**|Content embedded poorly due to format issues|Table data embedded as garbled text|

### How to Detect

```
Symptoms of indexing failures:
─────────────────────────────────────────────────────────────
• Query returns zero results for content you KNOW exists
• Relevant doc never appears regardless of query phrasing
• Retrieved chunks are incomplete or nonsensical
• Metadata filters return unexpected results (or nothing)
─────────────────────────────────────────────────────────────
```

### Detection Approach

```python
def detect_indexing_failure(
    query: str,
    known_relevant_doc_ids: list[str],
    retrieved_doc_ids: list[str],
    index_doc_ids: set[str]
) -> dict:
    """
    Check if relevant documents even exist in the index.
    """
    missing_from_index = []
    in_index_but_not_retrieved = []
    
    for doc_id in known_relevant_doc_ids:
        if doc_id not in index_doc_ids:
            missing_from_index.append(doc_id)
        elif doc_id not in retrieved_doc_ids:
            in_index_but_not_retrieved.append(doc_id)
    
    if missing_from_index:
        return {
            "failure_type": "indexing",
            "subtype": "document_not_indexed",
            "missing_docs": missing_from_index,
            "recommendation": "Check ingestion pipeline for these documents"
        }
    
    return None  # Not an indexing failure
```

### Example Symptom

```
Query: "What is our refund policy for enterprise customers?"

Expected: Policy document from legal folder
Retrieved: Generic FAQ, unrelated support articles

Investigation:
  - Check index: legal/enterprise-refund-policy.pdf → NOT FOUND
  - Check ingestion logs: "Skipped: PDF contains only images"
  
Diagnosis: INDEXING FAILURE (document not indexed)
Fix: Add OCR to ingestion pipeline
```

---

## Retrieval Failures

**What breaks:** The relevant document exists in the index, but the retrieval system doesn't find it — or ranks it too low to be included in top-k results.

### Failure Subtypes

|Subtype|Description|Example|
|---|---|---|
|**Vocabulary mismatch**|Query uses different terms than document|Query: "laptop" → Doc uses: "notebook computer"|
|**Embedding misses intent**|Semantic similarity fails to capture meaning|Query about exceptions retrieves general rules|
|**Ranked too low**|Relevant doc retrieved but below top-k cutoff|Relevant doc at position 47, top-k=20|
|**Wrong semantic match**|Superficially similar but actually irrelevant|"Java coffee" matches "Java programming"|

### How to Detect

```
Symptoms of retrieval failures:
─────────────────────────────────────────────────────────────
• Document IS in index (verified) but not in retrieved set
• Relevant doc appears at position 30+ in full ranking
• Query reformulation suddenly retrieves the right doc
• BM25 finds it but dense retrieval doesn't (or vice versa)
─────────────────────────────────────────────────────────────
```

### Detection Approach

```python
def detect_retrieval_failure(
    query: str,
    known_relevant_doc_ids: list[str],
    retrieved_doc_ids: list[str],
    full_ranking: list[tuple[str, float]],  # (doc_id, score) for all docs
    top_k: int
) -> dict:
    """
    Check if relevant documents exist but weren't retrieved in top-k.
    """
    # Find position of relevant docs in full ranking
    doc_positions = {doc_id: pos for pos, (doc_id, _) in enumerate(full_ranking, 1)}
    
    buried_docs = []
    for doc_id in known_relevant_doc_ids:
        if doc_id in doc_positions:
            position = doc_positions[doc_id]
            if position > top_k:
                buried_docs.append({
                    "doc_id": doc_id,
                    "position": position,
                    "score": next(s for d, s in full_ranking if d == doc_id)
                })
    
    if buried_docs:
        return {
            "failure_type": "retrieval",
            "subtype": "ranked_too_low",
            "buried_docs": buried_docs,
            "top_k": top_k,
            "recommendation": "Increase top-k, add hybrid search, or improve query"
        }
    
    return None  # Not a retrieval failure
```

### Example Symptom

```
Query: "How do I fix error code E-4012?"

Expected: Troubleshooting guide mentioning E-4012
Retrieved: General error handling docs, FAQ about errors

Investigation:
  - Check index: troubleshooting/error-codes.md → FOUND
  - Check full ranking: error-codes.md at position 34
  - Check top-k: 20
  
Diagnosis: RETRIEVAL FAILURE (ranked too low)
Why: Dense embedding doesn't capture exact error code match

Fix options:
  1. Add BM25 hybrid search (exact match helps)
  2. Increase top-k (but adds noise)
  3. Add error code to metadata and filter
```

---

## Context Assembly Failures

**What breaks:** The retrieval worked — relevant documents were found. But the context sent to the LLM is wrong. Either too much noise drowns the signal, or the reranker made bad decisions.

### Failure Subtypes

|Subtype|Description|Example|
|---|---|---|
|**Relevant info diluted**|Too many chunks, signal lost in noise|15 chunks sent, relevant one buried at position 12|
|**Reranker wrong choice**|Cross-encoder demoted relevant chunk|Reranker preferred longer, less relevant chunk|
|**Context truncation**|Relevant content cut off due to token limits|Answer was in chunk that got truncated|
|**Chunks lack context**|Individual chunk meaningful only with surrounding text|"See above for exceptions" — but "above" not included|

### How to Detect

```
Symptoms of context assembly failures:
─────────────────────────────────────────────────────────────
• Relevant doc in retrieved set but not in final LLM context
• Reranker scores show relevant chunk demoted
• Answer exists in retrieved chunks but LLM didn't see it
• Token count shows context was truncated
─────────────────────────────────────────────────────────────
```

### Detection Approach

```python
def detect_context_failure(
    retrieved_chunks: list[dict],  # [{"id": ..., "text": ..., "score": ...}]
    final_context_chunks: list[dict],  # What actually went to LLM
    known_relevant_chunk_ids: list[str],
    token_limit: int,
    actual_token_count: int
) -> dict:
    """
    Check if relevant chunks were retrieved but not included in final context.
    """
    retrieved_ids = {c["id"] for c in retrieved_chunks}
    final_ids = {c["id"] for c in final_context_chunks}
    
    # Relevant chunks that were retrieved but didn't make it to LLM
    lost_in_assembly = []
    for chunk_id in known_relevant_chunk_ids:
        if chunk_id in retrieved_ids and chunk_id not in final_ids:
            lost_in_assembly.append(chunk_id)
    
    if lost_in_assembly:
        # Determine why
        if actual_token_count >= token_limit * 0.95:
            subtype = "context_truncation"
            recommendation = "Reduce chunk count or summarize"
        else:
            subtype = "reranker_wrong_choice"
            recommendation = "Review reranker scores, consider different reranker"
        
        return {
            "failure_type": "context_assembly",
            "subtype": subtype,
            "lost_chunks": lost_in_assembly,
            "recommendation": recommendation
        }
    
    return None  # Not a context assembly failure
```

### Example Symptom

```
Query: "What are the pricing tiers for our API?"

Retrieved (top 10):
  1. General product overview (score: 0.89)
  2. API authentication guide (score: 0.87)
  3. API rate limits (score: 0.85)
  ...
  4. API pricing tiers (score: 0.72)  ← THE ANSWER
  ...

Final context (top 5 after reranking):
  1. General product overview
  2. API getting started
  3. API authentication guide
  4. API rate limits
  5. API versioning
  
  → Pricing tiers chunk DROPPED by reranker

Diagnosis: CONTEXT ASSEMBLY FAILURE (reranker wrong choice)
Fix: Adjust reranker, increase context window, or use different selection strategy
```

---

## Generation Failures

**What breaks:** The LLM received the right context — the answer was literally in the input — but it still produced a wrong response.

### Failure Subtypes

|Subtype|Description|Example|
|---|---|---|
|**Hallucination despite context**|LLM made up info even with correct context present|Invented statistics not in any document|
|**Ignored relevant context**|LLM used parametric knowledge instead of context|Answered from training data, ignored retrieved docs|
|**Misunderstood question**|LLM answered a different question|Asked about "current policy," answered about "old policy"|
|**Lost in the middle**|Relevant info in middle of context, LLM missed it|Answer in chunk 7 of 15, LLM focused on first/last|
|**Reasoning error**|LLM had all info but drew wrong conclusion|Correct numbers, wrong arithmetic|

### How to Detect

```
Symptoms of generation failures:
─────────────────────────────────────────────────────────────
• Answer contradicts information in the provided context
• Correct answer is literally in context but LLM said something else
• LLM response uses facts not present in any retrieved doc
• LLM answered a subtly different question than asked
─────────────────────────────────────────────────────────────
```

### Detection Approach

```python
def detect_generation_failure(
    query: str,
    final_context: str,
    generated_answer: str,
    expected_answer: str,
    llm_client  # For verification
) -> dict:
    """
    Check if LLM failed despite having correct context.
    
    Uses LLM-as-judge to verify if expected answer is in context
    and if generated answer contradicts context.
    """
    # Step 1: Verify expected answer IS in context
    verification_prompt = f"""
    Is the following expected answer supported by the context?
    
    Context:
    {final_context}
    
    Expected answer: {expected_answer}
    
    Respond with only: SUPPORTED or NOT_SUPPORTED
    """
    
    support_check = llm_client.complete(verification_prompt).strip()
    
    if support_check != "SUPPORTED":
        return None  # Not a generation failure — context didn't have answer
    
    # Step 2: Check if generated answer contradicts or ignores context
    contradiction_prompt = f"""
    Compare the generated answer to the context.
    
    Context:
    {final_context}
    
    Generated answer: {generated_answer}
    Expected answer: {expected_answer}
    
    Classify the generation issue:
    - HALLUCINATION: Generated answer contains facts not in context
    - IGNORED_CONTEXT: Generated answer contradicts context
    - MISUNDERSTOOD: Generated answer addresses different question
    - REASONING_ERROR: Used context but reached wrong conclusion
    - CORRECT: Generated answer aligns with expected
    
    Respond with only one of the above categories.
    """
    
    issue_type = llm_client.complete(contradiction_prompt).strip()
    
    if issue_type != "CORRECT":
        return {
            "failure_type": "generation",
            "subtype": issue_type.lower(),
            "context_had_answer": True,
            "recommendation": get_generation_fix(issue_type)
        }
    
    return None


def get_generation_fix(issue_type: str) -> str:
    fixes = {
        "HALLUCINATION": "Add explicit instruction to only use provided context",
        "IGNORED_CONTEXT": "Strengthen system prompt to prioritize retrieved docs",
        "MISUNDERSTOOD": "Clarify question in prompt, add few-shot examples",
        "REASONING_ERROR": "Add chain-of-thought prompting, show calculation steps"
    }
    return fixes.get(issue_type, "Review prompt engineering")
```

### Example Symptom

```
Query: "What was our Q3 2024 revenue?"

Context sent to LLM:
  "Q3 2024 Financial Summary: Total revenue reached $47.2M,
   representing a 12% increase over Q3 2023..."

Generated answer: "Based on the financial reports, Q3 2024 
                   revenue was approximately $52M."

Expected answer: "$47.2M"

Investigation:
  - Context contains correct answer: YES ($47.2M clearly stated)
  - Generated answer matches: NO ($52M vs $47.2M)
  
Diagnosis: GENERATION FAILURE (hallucination despite context)
Fix: Strengthen prompt to quote exact figures from context
```

---

## The Fifth Category: Ground Truth & Ambiguity

Some failures don't fit the four categories. The pipeline worked correctly, but something else is wrong.

### Edge Cases

|Case|Description|Example|
|---|---|---|
|**Wrong ground truth**|Your expected answer is actually incorrect|Eval set has outdated information|
|**Ambiguous query**|Question has multiple valid interpretations|"What's our policy?" — which policy?|
|**Temporal mismatch**|Query assumes timeframe not in docs|"Current pricing" but docs are from 2023|
|**Unanswerable query**|Answer genuinely doesn't exist in corpus|Asked about a product you don't sell|
|**Correct but different**|Answer is right but phrased differently|Expected "$47.2 million", got "47.2M dollars"|

### How to Detect

```
Symptoms of ground truth / ambiguity issues:
─────────────────────────────────────────────────────────────
• Pipeline trace shows everything worked, but answer "wrong"
• Multiple human annotators disagree on correct answer
• Query could reasonably mean different things
• Expected answer can't be found in any document (legitimately)
─────────────────────────────────────────────────────────────
```

### Detection Questions

Before classifying as a pipeline failure, verify:

```python
def check_ground_truth_issues(
    query: str,
    expected_answer: str,
    generated_answer: str,
    corpus_docs: list[str]
) -> dict:
    """
    Check if the 'failure' is actually a ground truth or ambiguity issue.
    """
    issues = []
    
    # 1. Can expected answer be found in corpus at all?
    answer_in_corpus = any(expected_answer.lower() in doc.lower() for doc in corpus_docs)
    if not answer_in_corpus:
        issues.append({
            "type": "unanswerable",
            "detail": "Expected answer not found in any document"
        })
    
    # 2. Is query ambiguous? (would need LLM or human check)
    ambiguous_signals = ["the policy", "our product", "the process", "current"]
    if any(signal in query.lower() for signal in ambiguous_signals):
        issues.append({
            "type": "potentially_ambiguous",
            "detail": "Query may have multiple interpretations"
        })
    
    # 3. Are answers semantically equivalent? (needs LLM check)
    # "$47.2M" vs "47.2 million dollars" — same answer, different format
    
    return {"ground_truth_issues": issues} if issues else None
```

---

## Detecting Failure Type

A systematic decision tree for diagnosis:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG Failure Decision Tree                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   START: RAG returned wrong answer                                  │
│       │                                                             │
│       ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │ Q1: Is the relevant document in the index?                  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ├── NO ──► INDEXING FAILURE                                   │
│       │          Check: ingestion logs, parsing errors              │
│       │                                                             │
│       ▼ YES                                                         │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │ Q2: Was relevant doc in retrieved results (any position)?   │   │
│   └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ├── NO ──► RETRIEVAL FAILURE (vocabulary/embedding)           │
│       │          Check: query-doc similarity, try BM25              │
│       │                                                             │
│       ├── YES, but ranked > top-k ──► RETRIEVAL FAILURE (ranking)   │
│       │          Check: increase k, add hybrid search               │
│       │                                                             │
│       ▼ YES, in top-k                                               │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │ Q3: Was relevant chunk in final context sent to LLM?        │   │
│   └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ├── NO ──► CONTEXT ASSEMBLY FAILURE                           │
│       │          Check: reranker scores, token truncation           │
│       │                                                             │
│       ▼ YES                                                         │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │ Q4: Did LLM use the relevant context correctly?             │   │
│   └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ├── NO ──► GENERATION FAILURE                                 │
│       │          Check: prompt, position of info, LLM behavior      │
│       │                                                             │
│       ▼ YES                                                         │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │ Q5: Is the expected answer actually correct?                │   │
│   └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ├── NO ──► GROUND TRUTH ERROR                                 │
│       │          Fix: Update evaluation set                         │
│       │                                                             │
│       └── YES ──► EDGE CASE                                         │
│                   Check: ambiguity, temporal mismatch, formatting   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation

A complete failure classifier:

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FailureType(Enum):
    INDEXING = "indexing"
    RETRIEVAL = "retrieval"
    CONTEXT_ASSEMBLY = "context_assembly"
    GENERATION = "generation"
    GROUND_TRUTH = "ground_truth"
    UNKNOWN = "unknown"


@dataclass
class FailureDiagnosis:
    """Result of failure classification."""
    failure_type: FailureType
    subtype: str
    confidence: float
    evidence: dict
    recommendation: str
    
    def __repr__(self):
        return f"{self.failure_type.value}/{self.subtype} (confidence: {self.confidence:.0%})"


@dataclass 
class PipelineTrace:
    """Trace data from a RAG pipeline execution."""
    query: str
    
    # Indexing stage
    index_doc_ids: set[str]
    
    # Retrieval stage
    retrieved_chunks: list[dict]  # [{"id": ..., "doc_id": ..., "score": ...}]
    full_ranking: list[tuple[str, float]]  # Complete ranking with scores
    top_k: int
    
    # Context assembly stage
    reranked_chunks: list[dict]
    final_context_chunks: list[dict]
    final_context_text: str
    token_count: int
    token_limit: int
    
    # Generation stage
    generated_answer: str
    
    # Ground truth
    expected_answer: str
    relevant_doc_ids: list[str]
    relevant_chunk_ids: list[str]


def classify_failure(trace: PipelineTrace) -> FailureDiagnosis:
    """
    Classify RAG failure based on pipeline trace.
    
    Walks through decision tree to identify failure stage.
    """
    
    # Step 1: Check indexing
    missing_docs = [
        doc_id for doc_id in trace.relevant_doc_ids 
        if doc_id not in trace.index_doc_ids
    ]
    
    if missing_docs:
        return FailureDiagnosis(
            failure_type=FailureType.INDEXING,
            subtype="document_not_indexed",
            confidence=0.95,
            evidence={"missing_docs": missing_docs},
            recommendation="Check ingestion pipeline for failed documents"
        )
    
    # Step 2: Check retrieval
    retrieved_doc_ids = {c["doc_id"] for c in trace.retrieved_chunks}
    retrieved_chunk_ids = {c["id"] for c in trace.retrieved_chunks}
    
    # Check if relevant docs were retrieved at all
    docs_not_retrieved = [
        doc_id for doc_id in trace.relevant_doc_ids
        if doc_id not in retrieved_doc_ids
    ]
    
    if docs_not_retrieved:
        # Check if they're in full ranking (just ranked low)
        full_ranking_ids = {doc_id for doc_id, _ in trace.full_ranking}
        buried = [d for d in docs_not_retrieved if d in full_ranking_ids]
        
        if buried:
            # Find their positions
            positions = {}
            for pos, (doc_id, score) in enumerate(trace.full_ranking, 1):
                if doc_id in buried:
                    positions[doc_id] = pos
            
            return FailureDiagnosis(
                failure_type=FailureType.RETRIEVAL,
                subtype="ranked_too_low",
                confidence=0.90,
                evidence={"buried_docs": positions, "top_k": trace.top_k},
                recommendation="Increase top-k or add hybrid search"
            )
        else:
            return FailureDiagnosis(
                failure_type=FailureType.RETRIEVAL,
                subtype="vocabulary_mismatch",
                confidence=0.85,
                evidence={"not_retrieved": docs_not_retrieved},
                recommendation="Add query expansion or hybrid BM25 search"
            )
    
    # Step 3: Check context assembly
    final_chunk_ids = {c["id"] for c in trace.final_context_chunks}
    
    chunks_lost_in_assembly = [
        chunk_id for chunk_id in trace.relevant_chunk_ids
        if chunk_id in retrieved_chunk_ids and chunk_id not in final_chunk_ids
    ]
    
    if chunks_lost_in_assembly:
        # Determine why — truncation or reranking?
        if trace.token_count >= trace.token_limit * 0.95:
            subtype = "context_truncation"
            recommendation = "Reduce chunk count or increase context window"
        else:
            subtype = "reranker_wrong_choice"
            recommendation = "Review reranker model or adjust selection logic"
        
        return FailureDiagnosis(
            failure_type=FailureType.CONTEXT_ASSEMBLY,
            subtype=subtype,
            confidence=0.88,
            evidence={"lost_chunks": chunks_lost_in_assembly},
            recommendation=recommendation
        )
    
    # Step 4: Check generation
    # At this point, relevant context made it to LLM
    # Check if answer is in context but LLM got it wrong
    
    expected_lower = trace.expected_answer.lower()
    context_lower = trace.final_context_text.lower()
    generated_lower = trace.generated_answer.lower()
    
    # Simple check: is expected answer in context?
    answer_in_context = expected_lower in context_lower
    
    # Is generated answer different from expected?
    answer_matches = expected_lower in generated_lower or generated_lower in expected_lower
    
    if answer_in_context and not answer_matches:
        # LLM had the answer but produced something different
        return FailureDiagnosis(
            failure_type=FailureType.GENERATION,
            subtype="ignored_or_hallucinated",
            confidence=0.80,
            evidence={
                "expected_in_context": True,
                "generated_matches": False
            },
            recommendation="Strengthen prompt to use only provided context"
        )
    
    # Step 5: Edge cases
    if not answer_in_context:
        return FailureDiagnosis(
            failure_type=FailureType.GROUND_TRUTH,
            subtype="answer_not_in_corpus",
            confidence=0.75,
            evidence={"expected_answer": trace.expected_answer},
            recommendation="Verify expected answer exists in corpus"
        )
    
    return FailureDiagnosis(
        failure_type=FailureType.UNKNOWN,
        subtype="needs_manual_review",
        confidence=0.50,
        evidence={},
        recommendation="Manual inspection required"
    )
```

### Usage Example

```python
# Create trace from your RAG pipeline debug output
trace = PipelineTrace(
    query="What is our Q3 2024 revenue?",
    index_doc_ids={"doc_1", "doc_2", "doc_3", "financials_q3"},
    retrieved_chunks=[
        {"id": "chunk_1", "doc_id": "doc_1", "score": 0.85},
        {"id": "chunk_2", "doc_id": "doc_2", "score": 0.82},
        # ... financials_q3 not in top-k
    ],
    full_ranking=[
        ("doc_1", 0.85), ("doc_2", 0.82), ("doc_3", 0.78),
        # ...
        ("financials_q3", 0.62),  # Position 25
    ],
    top_k=20,
    reranked_chunks=[...],
    final_context_chunks=[...],
    final_context_text="...",
    token_count=3500,
    token_limit=4000,
    generated_answer="Based on available information, Q3 revenue was $45M",
    expected_answer="$47.2M",
    relevant_doc_ids=["financials_q3"],
    relevant_chunk_ids=["financials_q3_chunk_1"]
)

diagnosis = classify_failure(trace)
print(diagnosis)
# retrieval/ranked_too_low (confidence: 90%)

print(f"Evidence: {diagnosis.evidence}")
# Evidence: {'buried_docs': {'financials_q3': 25}, 'top_k': 20}

print(f"Fix: {diagnosis.recommendation}")
# Fix: Increase top-k or add hybrid search
```

---

## Failure Patterns in Practice

When you analyze failures in batch, patterns emerge. These patterns point to systemic issues:

|Pattern|Likely Cause|Fix|
|---|---|---|
|Technical queries with error codes consistently fail retrieval|Dense embeddings don't capture exact matches|Add BM25 hybrid search|
|Queries about recent events fail|Documents not yet indexed|Reduce indexing latency|
|Multi-part questions get partial answers|Chunks split related info|Adjust chunking strategy|
|Numeric questions hallucinate|LLM invents plausible numbers|Prompt to quote exact figures|
|"What is X?" works but "Compare X and Y" fails|Multi-hop reasoning weak|Add query decomposition|
|First/last chunks get used, middle ignored|Lost-in-the-middle effect|Reorder context or use ensemble|
|Same doc type always fails|Parser issue for that format|Fix ingestion for that type|

### Pattern Detection Code

```python
from collections import Counter
from typing import List


def detect_failure_patterns(
    diagnoses: List[FailureDiagnosis],
    traces: List[PipelineTrace]
) -> dict:
    """
    Analyze batch of failures to find systematic patterns.
    """
    # Count failure types
    type_counts = Counter(d.failure_type.value for d in diagnoses)
    subtype_counts = Counter(f"{d.failure_type.value}/{d.subtype}" for d in diagnoses)
    
    # Find query patterns in failures
    retrieval_failures = [
        (t, d) for t, d in zip(traces, diagnoses)
        if d.failure_type == FailureType.RETRIEVAL
    ]
    
    patterns = {
        "failure_distribution": dict(type_counts),
        "subtype_distribution": dict(subtype_counts),
        "systematic_issues": []
    }
    
    # Check for error code pattern
    error_code_failures = [
        t.query for t, d in retrieval_failures
        if any(c.isdigit() for c in t.query)  # Query contains numbers
    ]
    
    if len(error_code_failures) > len(retrieval_failures) * 0.3:
        patterns["systematic_issues"].append({
            "pattern": "error_code_queries_fail",
            "affected_queries": len(error_code_failures),
            "recommendation": "Add BM25 for exact match on codes/numbers"
        })
    
    return patterns
```

---

## What Each Failure Type Tells You

Quick reference for diagnosis → action:

|Failure Type|What It Means|Likely Fixes|
|---|---|---|
|**Indexing**|Content never made it in|Fix parser, add OCR, check file types|
|**Retrieval (vocab)**|Query ≠ document language|Hybrid search, query expansion, synonyms|
|**Retrieval (ranking)**|Right doc, wrong position|Increase top-k, tune embedding, add metadata|
|**Context (truncation)**|Too much context, got cut|Reduce chunks, summarize, increase window|
|**Context (reranker)**|Reranker made bad call|Different reranker, adjust scoring|
|**Generation (hallucination)**|LLM made stuff up|Stronger grounding prompt, temperature=0|
|**Generation (ignored)**|LLM used own knowledge|"Only use provided context" instruction|
|**Generation (lost-middle)**|Info in middle missed|Reorder chunks, use ensemble approach|
|**Ground truth**|Eval data is wrong|Audit and fix evaluation set|

---

## Key Takeaways

1. **Classify before fixing** — Random tuning wastes time. Identify the failure stage first.
    
2. **Four pipeline stages, four failure types** — Indexing → Retrieval → Context Assembly → Generation. Each needs different fixes.
    
3. **Walk the decision tree** — Is it in the index? Was it retrieved? Did it reach the LLM? Did the LLM use it? Answer these in order.
    
4. **Fifth category exists** — Sometimes the pipeline is fine but ground truth is wrong, query is ambiguous, or answers are equivalent but formatted differently.
    
5. **Patterns reveal systemic issues** — One failure is a bug. Ten similar failures are a pattern. Fix patterns, not individual cases.
    
6. **Traces are essential** — You can't diagnose without visibility. Log every stage: what was retrieved, what was sent to LLM, what was generated.
    
7. **Failure type determines fix priority** — Indexing failures are fundamental (content missing). Generation failures are surface-level (prompt tuning). Fix from the bottom up.
    
8. **Simple string matching goes far** — Before building complex verification, check if expected answer literally appears in context. Often that's enough to identify generation vs. retrieval failures.