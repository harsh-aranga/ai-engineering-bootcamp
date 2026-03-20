# The Debugging Workflow

## The Core Insight

Debugging RAG is not troubleshooting — it's investigation. You have a crime scene (wrong answer), evidence (pipeline trace), and suspects (four failure types). Random fixes are like arresting everyone and hoping the guilty party is among them.

A systematic workflow forces discipline:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Ad-hoc vs. Systematic Debugging                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Ad-hoc debugging:                                                 │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  "Answer is wrong"                                          │   │
│   │       ↓                                                     │   │
│   │  "Let me try increasing top-k"                              │   │
│   │       ↓                                                     │   │
│   │  Still wrong → "Maybe different chunking?"                  │   │
│   │       ↓                                                     │   │
│   │  Still wrong → "Let me tune the prompt"                     │   │
│   │       ↓                                                     │   │
│   │  Hours later: maybe fixed, maybe not, no idea why           │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Systematic debugging:                                             │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  "Answer is wrong"                                          │   │
│   │       ↓                                                     │   │
│   │  Capture full trace                                         │   │
│   │       ↓                                                     │   │
│   │  Walk decision tree → RETRIEVAL FAILURE (ranked #35)        │   │
│   │       ↓                                                     │   │
│   │  Hypothesis: BM25 would catch this keyword query            │   │
│   │       ↓                                                     │   │
│   │  Add hybrid search → verify fix → done                      │   │
│   │                                                             │   │
│   │  Time: 20 minutes. Root cause identified. Fix verified.     │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The workflow is: **Reproduce → Classify → Hypothesize → Fix → Verify**

---

## The Workflow Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     RAG Debugging Workflow                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐                                                        │
│   │  TRIGGER    │  Bad answer reported (user feedback, eval failure)     │
│   └──────┬──────┘                                                        │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │  STEP 1: REPRODUCE                                              │    │
│   │  • Capture exact query                                          │    │
│   │  • Record expected answer                                       │    │
│   │  • Run with debug=True to get full trace                        │    │
│   │  • Save trace for comparison after fix                          │    │
│   └──────┬──────────────────────────────────────────────────────────┘    │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │  STEP 2: CLASSIFY                                               │    │
│   │  • Walk the decision tree (taxonomy)                            │    │
│   │  • Identify failure stage: indexing/retrieval/context/generation│    │
│   │  • Note the subtype (e.g., "ranked too low", "hallucination")   │    │
│   └──────┬──────────────────────────────────────────────────────────┘    │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │  STEP 3: HYPOTHESIZE                                            │    │
│   │  • Form ONE hypothesis about root cause                         │    │
│   │  • State it explicitly: "The failure is because X"              │    │
│   │  • Identify the specific fix that would address X               │    │
│   └──────┬──────────────────────────────────────────────────────────┘    │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │  STEP 4: FIX                                                    │    │
│   │  • Apply targeted fix (one change at a time)                    │    │
│   │  • Fix should map directly to hypothesis                        │    │
│   │  • Document what you changed                                    │    │
│   └──────┬──────────────────────────────────────────────────────────┘    │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────────┐    │
│   │  STEP 5: VERIFY                                                 │    │
│   │  • Re-run same query with same trace capture                    │    │
│   │  • Confirm original failure is resolved                         │    │
│   │  • Check for regressions on related queries                     │    │
│   │  • If not fixed → back to Step 2 with new evidence              │    │
│   └──────┬──────────────────────────────────────────────────────────┘    │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────┐                                                        │
│   │   DONE      │  Document fix, add to regression test suite            │
│   └─────────────┘                                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Reproduce the Failure

You can't debug what you can't reproduce. Capture everything needed to replay the exact failure.

### What to Capture

|Element|Why It Matters|
|---|---|
|**Exact query**|Character-for-character, not paraphrased|
|**Expected answer**|What should have been returned|
|**Actual answer**|What was returned|
|**Timestamp**|Index state may have changed|
|**Full pipeline trace**|Every intermediate result|

### The Debug Trace

Your RAG system needs a debug mode that exposes internals:

```python
@dataclass
class DebugTrace:
    """Complete trace of a RAG pipeline execution."""
    
    # Input
    query: str
    timestamp: str
    
    # Query processing
    original_query: str
    transformed_query: str | None  # If using HyDE, expansion, etc.
    query_embedding: list[float]
    
    # Retrieval
    bm25_results: list[dict]  # [{"chunk_id": ..., "score": ...}]
    dense_results: list[dict]
    fused_results: list[dict]  # After RRF or other fusion
    
    # Context assembly
    reranked_results: list[dict]
    selected_chunks: list[dict]  # What made it to final context
    final_context: str
    token_count: int
    
    # Generation
    prompt_sent: str  # Full prompt including system message
    raw_response: str
    parsed_answer: str
    
    # Metadata
    config: dict  # top_k, model, temperature, etc.


def query_with_debug(rag_system, query: str) -> tuple[str, DebugTrace]:
    """
    Run query and capture full debug trace.
    """
    trace = DebugTrace(
        query=query,
        timestamp=datetime.now().isoformat(),
        original_query=query,
        # ... populated by each pipeline stage
    )
    
    # Each stage appends to trace
    answer = rag_system.query(query, trace=trace)
    
    return answer, trace
```

### Saving Traces for Comparison

```python
import json
from pathlib import Path


def save_debug_session(
    trace: DebugTrace,
    expected_answer: str,
    session_name: str
) -> Path:
    """
    Save debug session for later comparison.
    """
    session_dir = Path("debug_sessions") / session_name
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Save trace
    with open(session_dir / "trace.json", "w") as f:
        json.dump(trace.__dict__, f, indent=2, default=str)
    
    # Save expected answer
    with open(session_dir / "expected.txt", "w") as f:
        f.write(expected_answer)
    
    # Save summary for quick reference
    summary = {
        "query": trace.query,
        "expected": expected_answer,
        "actual": trace.parsed_answer,
        "retrieved_count": len(trace.fused_results),
        "context_tokens": trace.token_count,
        "timestamp": trace.timestamp
    }
    
    with open(session_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    return session_dir
```

### Reproduction Checklist

Before moving to classification:

```
□ Exact query captured (copy-paste, not retyped)
□ Expected answer documented with source
□ Full trace captured (all pipeline stages)
□ Trace saved to disk for comparison
□ Config recorded (which models, what parameters)
□ Timestamp noted (in case index changes)
```

---

## Step 2: Classify the Failure

Walk the decision tree from the Taxonomy note. Answer questions in order:

### The Questions

```
Q1: Is the relevant document in the index?
    │
    ├── NO → INDEXING FAILURE
    │        Stop here. Fix ingestion.
    │
    └── YES → Continue to Q2

Q2: Was the relevant document retrieved (any position)?
    │
    ├── NO → RETRIEVAL FAILURE (vocabulary/embedding mismatch)
    │        The search didn't find it at all.
    │
    ├── YES, but position > top_k → RETRIEVAL FAILURE (ranking)
    │        Found but ranked too low.
    │
    └── YES, in top_k → Continue to Q3

Q3: Was the relevant chunk in the final context sent to LLM?
    │
    ├── NO → CONTEXT ASSEMBLY FAILURE
    │        Lost in reranking or truncation.
    │
    └── YES → Continue to Q4

Q4: Did the LLM use the context correctly?
    │
    ├── NO → GENERATION FAILURE
    │        Right context, wrong answer.
    │
    └── YES → GROUND TRUTH or EDGE CASE
             Check if expected answer is actually correct.
```

### Answering the Questions

Each question requires specific inspection:

|Question|How to Answer|
|---|---|
|Q1: In index?|Query index directly by doc ID. Check ingestion logs.|
|Q2: Retrieved?|Examine `fused_results` in trace. Search for relevant doc ID.|
|Q3: In context?|Examine `selected_chunks` and `final_context`. Is it there?|
|Q4: Used correctly?|Read `final_context` and `parsed_answer`. Does answer follow from context?|

### Classification Output

Document your classification clearly:

```python
@dataclass
class FailureClassification:
    """Result of Step 2: Classification."""
    
    failure_type: str  # indexing, retrieval, context, generation, ground_truth
    subtype: str       # e.g., "ranked_too_low", "hallucination"
    confidence: str    # high, medium, low
    evidence: str      # What you observed that led to this classification
    
    def __str__(self):
        return f"{self.failure_type}/{self.subtype} ({self.confidence} confidence)\nEvidence: {self.evidence}"


# Example
classification = FailureClassification(
    failure_type="retrieval",
    subtype="ranked_too_low",
    confidence="high",
    evidence="Relevant doc 'pricing-guide.md' found at position 34, top_k=20"
)
```

---

## Step 3: Formulate Hypothesis

Classification tells you _where_ the failure occurred. Now hypothesize _why_.

### The Discipline

**One hypothesis at a time.** Not "maybe it's X or Y or Z." Pick one.

```
BAD:  "It might be the embedding model, or maybe the chunking, 
       or perhaps we need more context."

GOOD: "The failure is because dense embeddings don't capture 
       exact error code 'E-4012'. BM25 would match this exactly."
```

### Hypothesis Template

```
The failure is [FAILURE_TYPE/SUBTYPE] because [SPECIFIC CAUSE].

The fix is [SPECIFIC ACTION] which will [EXPECTED OUTCOME].
```

### Examples by Failure Type

|Classification|Hypothesis Example|
|---|---|
|retrieval/ranked_too_low|"Dense embedding doesn't weight error codes. BM25 hybrid search will boost exact matches."|
|retrieval/vocabulary_mismatch|"Query says 'laptop' but docs say 'notebook'. Query expansion with synonyms will help."|
|context/reranker_wrong_choice|"Reranker prefers longer chunks over more relevant short ones. Adjusting length normalization will fix."|
|context/truncation|"15 chunks at 500 tokens each exceeds limit. Reducing to top-8 after reranking will include relevant content."|
|generation/hallucination|"LLM generated plausible but wrong numbers. Adding 'only quote exact figures from context' to prompt will ground it."|
|generation/lost_in_middle|"Answer is in chunk 8 of 12. Moving highest-relevance chunks to start and end of context will help."|

### Recording the Hypothesis

```python
@dataclass
class Hypothesis:
    """Explicit hypothesis about failure cause."""
    
    classification: FailureClassification
    root_cause: str      # Why this failure happened
    proposed_fix: str    # Specific change to make
    expected_result: str # What should happen after fix
    
    def __str__(self):
        return f"""
Hypothesis for {self.classification.failure_type}/{self.classification.subtype}:

ROOT CAUSE: {self.root_cause}

PROPOSED FIX: {self.proposed_fix}

EXPECTED RESULT: {self.expected_result}
"""


# Example
hypothesis = Hypothesis(
    classification=classification,
    root_cause="Dense embeddings don't capture exact error code matches",
    proposed_fix="Add BM25 hybrid search with 0.3 BM25 / 0.7 dense weighting",
    expected_result="Error code query will match exactly via BM25, pushing relevant doc into top-20"
)
```

---

## Step 4: Apply the Fix

Make exactly ONE change that addresses your hypothesis.

### The Rules

1. **One change at a time** — If you change three things and it works, you don't know which one fixed it.
    
2. **Change matches hypothesis** — If you hypothesized "BM25 needed", don't also change the prompt "just in case."
    
3. **Document the change** — Write down exactly what you modified.
    
4. **Keep the original** — Don't overwrite. Create a new version or config.
    

### Fix Mapping

Quick reference for hypothesis → fix:

|Hypothesis|Fix|
|---|---|
|Exact match needed|Add BM25 hybrid search|
|Vocabulary mismatch|Add query expansion or synonyms|
|Ranked too low|Increase top_k or tune retrieval weights|
|Reranker wrong choice|Adjust reranker or selection logic|
|Context truncated|Reduce chunks or increase context window|
|LLM hallucinated|Strengthen grounding in prompt|
|Lost in middle|Reorder chunks (relevant at start/end)|
|Document not indexed|Fix ingestion pipeline|

### Change Documentation

```python
@dataclass
class AppliedFix:
    """Record of what was changed."""
    
    hypothesis: Hypothesis
    change_description: str
    file_changed: str
    before_value: str
    after_value: str
    timestamp: str
    
    def __str__(self):
        return f"""
FIX APPLIED at {self.timestamp}

CHANGE: {self.change_description}
FILE: {self.file_changed}

BEFORE: {self.before_value}
AFTER: {self.after_value}
"""


# Example
fix = AppliedFix(
    hypothesis=hypothesis,
    change_description="Added BM25 hybrid search",
    file_changed="rag_pipeline.py",
    before_value="search_mode='dense'",
    after_value="search_mode='hybrid', bm25_weight=0.3",
    timestamp=datetime.now().isoformat()
)
```

---

## Step 5: Verify the Fix

The fix isn't done until you've verified it works AND doesn't break other things.

### Verification Checklist

```
□ Re-run original query with same debug trace capture
□ Compare before/after traces
□ Confirm failure is resolved (correct answer now)
□ Run regression set (related queries that were working)
□ Check no new failures introduced
□ If still failing → back to Step 2 with new evidence
```

### Before/After Comparison

```python
def compare_traces(
    before: DebugTrace,
    after: DebugTrace,
    expected_answer: str
) -> dict:
    """
    Compare traces before and after fix.
    """
    comparison = {
        "query": before.query,
        "expected": expected_answer,
        
        # Answer comparison
        "before_answer": before.parsed_answer,
        "after_answer": after.parsed_answer,
        "answer_fixed": expected_answer.lower() in after.parsed_answer.lower(),
        
        # Retrieval comparison
        "before_retrieved_ids": [r["chunk_id"] for r in before.fused_results[:10]],
        "after_retrieved_ids": [r["chunk_id"] for r in after.fused_results[:10]],
        
        # Ranking changes
        "ranking_changed": (
            [r["chunk_id"] for r in before.fused_results[:10]] !=
            [r["chunk_id"] for r in after.fused_results[:10]]
        ),
        
        # Context comparison
        "before_context_chunks": len(before.selected_chunks),
        "after_context_chunks": len(after.selected_chunks),
        "context_changed": before.final_context != after.final_context,
    }
    
    return comparison


def print_comparison(comparison: dict):
    """Pretty print the comparison."""
    print(f"Query: {comparison['query']}")
    print(f"Expected: {comparison['expected']}")
    print()
    print(f"Before: {comparison['before_answer']}")
    print(f"After:  {comparison['after_answer']}")
    print()
    print(f"✓ Answer fixed: {comparison['answer_fixed']}")
    print(f"✓ Ranking changed: {comparison['ranking_changed']}")
    print(f"✓ Context changed: {comparison['context_changed']}")
```

### Regression Testing

Don't just test the fixed query. Test related queries:

```python
def run_regression_check(
    rag_system,
    fixed_query: str,
    regression_set: list[dict]  # [{"query": ..., "expected": ...}]
) -> dict:
    """
    Check that fix didn't break other queries.
    """
    results = {
        "total": len(regression_set),
        "passed": 0,
        "failed": 0,
        "failures": []
    }
    
    for case in regression_set:
        answer, _ = query_with_debug(rag_system, case["query"])
        
        # Simple check — expected answer in response
        if case["expected"].lower() in answer.lower():
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["failures"].append({
                "query": case["query"],
                "expected": case["expected"],
                "actual": answer
            })
    
    results["regression_detected"] = results["failed"] > 0
    
    return results
```

### When Verification Fails

If the fix didn't work:

```
Fix didn't resolve the issue
        │
        ▼
Was hypothesis wrong?
        │
        ├── YES → Back to Step 2: Re-classify with new evidence
        │         (The trace after "fix" is new evidence)
        │
        └── NO, hypothesis correct but fix insufficient
                  │
                  ▼
            Strengthen the fix or try alternative approach
            (Still same hypothesis, different implementation)
```

---

## Implementation: Debug Session Runner

Putting it all together — a helper that runs the full workflow:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class SessionStatus(Enum):
    IN_PROGRESS = "in_progress"
    FIXED = "fixed"
    UNRESOLVED = "unresolved"


@dataclass
class DebugSession:
    """
    A complete debug session tracking the workflow.
    """
    session_id: str
    query: str
    expected_answer: str
    
    # Step 1: Reproduce
    initial_trace: Optional[DebugTrace] = None
    initial_answer: Optional[str] = None
    
    # Step 2: Classify
    classification: Optional[FailureClassification] = None
    
    # Step 3: Hypothesize
    hypothesis: Optional[Hypothesis] = None
    
    # Step 4: Fix
    applied_fix: Optional[AppliedFix] = None
    
    # Step 5: Verify
    final_trace: Optional[DebugTrace] = None
    final_answer: Optional[str] = None
    regression_results: Optional[dict] = None
    
    # Meta
    status: SessionStatus = SessionStatus.IN_PROGRESS
    iterations: int = 0
    history: list = field(default_factory=list)
    
    def log(self, message: str):
        """Add to session history."""
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })


class DebugSessionRunner:
    """
    Helper to run the debugging workflow.
    """
    
    def __init__(self, rag_system, regression_set: list[dict] = None):
        self.rag = rag_system
        self.regression_set = regression_set or []
        self.sessions: dict[str, DebugSession] = {}
    
    def start_session(
        self,
        query: str,
        expected_answer: str,
        session_id: str = None
    ) -> DebugSession:
        """
        Step 1: Start a debug session by reproducing the failure.
        """
        session_id = session_id or f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = DebugSession(
            session_id=session_id,
            query=query,
            expected_answer=expected_answer
        )
        
        # Reproduce
        answer, trace = query_with_debug(self.rag, query)
        session.initial_trace = trace
        session.initial_answer = answer
        session.log(f"Session started. Initial answer: {answer[:100]}...")
        
        self.sessions[session_id] = session
        return session
    
    def classify(
        self,
        session: DebugSession,
        failure_type: str,
        subtype: str,
        evidence: str,
        confidence: str = "high"
    ) -> DebugSession:
        """
        Step 2: Record classification.
        """
        session.classification = FailureClassification(
            failure_type=failure_type,
            subtype=subtype,
            confidence=confidence,
            evidence=evidence
        )
        session.log(f"Classified as {failure_type}/{subtype}")
        return session
    
    def hypothesize(
        self,
        session: DebugSession,
        root_cause: str,
        proposed_fix: str,
        expected_result: str
    ) -> DebugSession:
        """
        Step 3: Record hypothesis.
        """
        session.hypothesis = Hypothesis(
            classification=session.classification,
            root_cause=root_cause,
            proposed_fix=proposed_fix,
            expected_result=expected_result
        )
        session.log(f"Hypothesis: {root_cause}")
        return session
    
    def record_fix(
        self,
        session: DebugSession,
        change_description: str,
        file_changed: str,
        before_value: str,
        after_value: str
    ) -> DebugSession:
        """
        Step 4: Record what fix was applied.
        (Actual code change is manual — this just documents it)
        """
        session.applied_fix = AppliedFix(
            hypothesis=session.hypothesis,
            change_description=change_description,
            file_changed=file_changed,
            before_value=before_value,
            after_value=after_value,
            timestamp=datetime.now().isoformat()
        )
        session.log(f"Fix applied: {change_description}")
        return session
    
    def verify(self, session: DebugSession) -> DebugSession:
        """
        Step 5: Verify the fix.
        """
        session.iterations += 1
        
        # Re-run query
        answer, trace = query_with_debug(self.rag, session.query)
        session.final_trace = trace
        session.final_answer = answer
        
        # Check if fixed
        fixed = session.expected_answer.lower() in answer.lower()
        
        # Run regressions
        if self.regression_set:
            session.regression_results = run_regression_check(
                self.rag, session.query, self.regression_set
            )
        
        if fixed and not session.regression_results.get("regression_detected", False):
            session.status = SessionStatus.FIXED
            session.log("✓ Fix verified. No regressions detected.")
        elif fixed:
            session.log("⚠ Answer fixed but regressions detected.")
        else:
            session.log(f"✗ Still failing. Answer: {answer[:100]}...")
        
        return session
    
    def get_summary(self, session: DebugSession) -> str:
        """Get human-readable session summary."""
        lines = [
            f"=== Debug Session: {session.session_id} ===",
            f"Status: {session.status.value}",
            f"Iterations: {session.iterations}",
            f"",
            f"Query: {session.query}",
            f"Expected: {session.expected_answer}",
            f"",
            f"Initial answer: {session.initial_answer}",
            f"Final answer: {session.final_answer}",
            f"",
        ]
        
        if session.classification:
            lines.append(f"Classification: {session.classification.failure_type}/{session.classification.subtype}")
            lines.append(f"Evidence: {session.classification.evidence}")
            lines.append("")
        
        if session.hypothesis:
            lines.append(f"Root cause: {session.hypothesis.root_cause}")
            lines.append(f"Fix: {session.hypothesis.proposed_fix}")
            lines.append("")
        
        if session.applied_fix:
            lines.append(f"Change: {session.applied_fix.change_description}")
            lines.append(f"File: {session.applied_fix.file_changed}")
            lines.append("")
        
        lines.append("History:")
        for entry in session.history:
            lines.append(f"  [{entry['timestamp']}] {entry['message']}")
        
        return "\n".join(lines)
```

### Usage Example

```python
# Initialize
runner = DebugSessionRunner(
    rag_system=my_rag,
    regression_set=[
        {"query": "What is our refund policy?", "expected": "30 days"},
        {"query": "How do I contact support?", "expected": "support@company.com"},
    ]
)

# Step 1: Reproduce
session = runner.start_session(
    query="How do I fix error code E-4012?",
    expected_answer="Clear the cache and restart the service"
)

# Inspect trace manually...
print(session.initial_trace.fused_results[:5])
# See that relevant doc is at position 34

# Step 2: Classify
runner.classify(
    session,
    failure_type="retrieval",
    subtype="ranked_too_low",
    evidence="Doc 'troubleshooting/error-codes.md' at position 34, top_k=20"
)

# Step 3: Hypothesize
runner.hypothesize(
    session,
    root_cause="Dense embeddings don't capture exact error code match",
    proposed_fix="Add BM25 hybrid search",
    expected_result="BM25 will match 'E-4012' exactly, boosting rank"
)

# Step 4: Apply fix (manual code change)
# ... edit rag_pipeline.py to add hybrid search ...

runner.record_fix(
    session,
    change_description="Added BM25 hybrid search with weight 0.3",
    file_changed="rag_pipeline.py",
    before_value="search_mode='dense'",
    after_value="search_mode='hybrid', bm25_weight=0.3"
)

# Step 5: Verify
runner.verify(session)

# Check result
print(runner.get_summary(session))
```

---

## Common Workflow Mistakes

What slows debugging down:

|Mistake|Why It's Bad|Fix|
|---|---|---|
|**Skipping reproduction**|"I remember the query was something like..." leads to debugging wrong problem|Always capture exact query and full trace|
|**Multiple changes at once**|Can't isolate what worked|One change per iteration|
|**Fixing wrong layer**|Tuning prompts when retrieval is broken|Complete the decision tree before fixing|
|**No hypothesis**|Random changes without theory|State explicit hypothesis before touching code|
|**No verification**|"It looks better" isn't evidence|Run same query, compare traces|
|**No regression check**|Fix one, break three|Always run regression set|
|**Giving up too early**|"It's just a bad query"|Most failures are systematic, not random|
|**Not documenting**|Same failure debugged twice|Log sessions, build knowledge base|

### The Biggest Mistake

**Fixing before classifying.**

```
"The answer is wrong, let me try a better prompt."

↓

30 minutes later: still wrong because it was a retrieval failure.
The relevant document was never in the context.
No prompt would have helped.
```

Always classify first. The fix must match the failure type.

---

## Key Takeaways

1. **Five steps: Reproduce → Classify → Hypothesize → Fix → Verify.** Don't skip any.
    
2. **Reproduction requires full trace** — You need visibility into every pipeline stage to classify correctly.
    
3. **Classification before fixing** — Walking the decision tree prevents fixing the wrong layer.
    
4. **One hypothesis, one fix** — State your theory explicitly. Make exactly one change. If it doesn't work, you have new evidence for a new hypothesis.
    
5. **Verification means comparison** — Compare before/after traces. Run regression checks. "It looks better" isn't proof.
    
6. **Document everything** — Debug sessions, hypotheses, fixes. Build a knowledge base of failure patterns.
    
7. **Most failures are systematic** — One error code query failing usually means all error code queries fail. Find the pattern, fix it once.
    
8. **The workflow is an investment** — It feels slow at first. But it prevents hours of random tuning that doesn't address the root cause.