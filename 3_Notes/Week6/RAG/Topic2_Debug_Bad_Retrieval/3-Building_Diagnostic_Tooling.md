# Building Diagnostic Tooling

## The Core Insight

Ad-hoc debugging means adding print statements, running queries, reading logs, removing print statements. Every debug session starts from scratch.

Built-in diagnostic tooling means your RAG system is _always_ ready to explain itself. Flip a switch, get full visibility.

```
┌─────────────────────────────────────────────────────────────────────┐
│                 Ad-hoc vs. Built-in Diagnostics                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Ad-hoc debugging:                                                 │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  1. Add print("retrieved:", results)                        │   │
│   │  2. Run query                                               │   │
│   │  3. Read terminal output                                    │   │
│   │  4. Add more prints for reranking                           │   │
│   │  5. Run again                                               │   │
│   │  6. Forget to remove prints before commit                   │   │
│   │  7. Production logs now full of debug spam                  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Built-in diagnostics:                                             │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  result = rag.query("question", debug=True)                 │   │
│   │                                                             │   │
│   │  result.trace.retrieval      # All retrieved docs + scores  │   │
│   │  result.trace.reranking      # Reranker decisions           │   │
│   │  result.trace.context        # What LLM saw                 │   │
│   │  result.trace.generation     # Full prompt + response       │   │
│   │                                                             │   │
│   │  debugger.diagnose(result)   # Automatic failure detection  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Investment: Build once. Use forever.                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The goal: Make your RAG system introspectable by default.

---

## Debug Mode Architecture

Debug mode should be:

- **Opt-in** — No overhead when disabled
- **Non-invasive** — Doesn't change pipeline behavior
- **Complete** — Captures everything needed for diagnosis
- **Structured** — Data, not print statements

### The Pattern

```python
class RAGPipeline:
    def query(
        self,
        question: str,
        debug: bool = False
    ) -> RAGResult:
        """
        Query with optional debug trace.
        """
        # Initialize trace collector if debug enabled
        trace = PipelineTrace() if debug else None
        
        # Each stage optionally records to trace
        retrieved = self._retrieve(question, trace)
        reranked = self._rerank(retrieved, question, trace)
        context = self._assemble_context(reranked, trace)
        answer = self._generate(question, context, trace)
        
        return RAGResult(
            answer=answer,
            trace=trace  # None if debug=False
        )
```

### Separating Concerns

Keep debug logic separate from business logic:

```python
# BAD: Debug logic mixed in
def _retrieve(self, question):
    results = self.retriever.search(question)
    if self.debug:
        print(f"Retrieved {len(results)} docs")
        for r in results:
            print(f"  {r['id']}: {r['score']}")
    return results

# GOOD: Debug logic isolated
def _retrieve(self, question, trace=None):
    results = self.retriever.search(question)
    
    if trace:
        trace.record_retrieval(results)
    
    return results
```

---

## The Trace Object

A structured container for all pipeline data:

```python
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class RetrievalTrace:
    """Trace data from retrieval stage."""
    query: str
    query_embedding: list[float] = None
    
    # BM25 results (if hybrid)
    bm25_results: list[dict] = field(default_factory=list)
    bm25_time_ms: float = 0
    
    # Dense results
    dense_results: list[dict] = field(default_factory=list)
    dense_time_ms: float = 0
    
    # Fused results (after RRF or other fusion)
    fused_results: list[dict] = field(default_factory=list)
    fusion_method: str = None


@dataclass
class RerankingTrace:
    """Trace data from reranking stage."""
    input_chunks: list[dict] = field(default_factory=list)
    output_chunks: list[dict] = field(default_factory=list)
    model: str = None
    time_ms: float = 0
    
    # Score changes for analysis
    score_changes: list[dict] = field(default_factory=list)


@dataclass
class ContextTrace:
    """Trace data from context assembly stage."""
    selected_chunks: list[dict] = field(default_factory=list)
    dropped_chunks: list[dict] = field(default_factory=list)
    drop_reason: dict = field(default_factory=dict)  # chunk_id -> reason
    
    final_context: str = ""
    token_count: int = 0
    token_limit: int = 0
    truncated: bool = False


@dataclass
class GenerationTrace:
    """Trace data from generation stage."""
    system_prompt: str = ""
    user_prompt: str = ""
    full_prompt: str = ""  # Complete prompt sent to LLM
    
    raw_response: str = ""
    parsed_answer: str = ""
    
    model: str = ""
    temperature: float = 0
    time_ms: float = 0
    token_usage: dict = field(default_factory=dict)


@dataclass
class PipelineTrace:
    """Complete trace of RAG pipeline execution."""
    
    # Metadata
    trace_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Original input
    query: str = ""
    
    # Stage traces
    retrieval: RetrievalTrace = None
    reranking: RerankingTrace = None
    context: ContextTrace = None
    generation: GenerationTrace = None
    
    # Timing
    total_time_ms: float = 0
    
    # Config snapshot
    config: dict = field(default_factory=dict)
    
    def record_retrieval(
        self,
        query: str,
        bm25_results: list = None,
        dense_results: list = None,
        fused_results: list = None,
        **kwargs
    ):
        """Record retrieval stage results."""
        self.query = query
        self.retrieval = RetrievalTrace(
            query=query,
            bm25_results=bm25_results or [],
            dense_results=dense_results or [],
            fused_results=fused_results or [],
            **kwargs
        )
    
    def record_reranking(
        self,
        input_chunks: list,
        output_chunks: list,
        **kwargs
    ):
        """Record reranking stage results."""
        # Calculate score changes
        input_scores = {c["id"]: c.get("score", 0) for c in input_chunks}
        score_changes = []
        
        for i, chunk in enumerate(output_chunks):
            chunk_id = chunk["id"]
            old_score = input_scores.get(chunk_id, 0)
            new_score = chunk.get("score", 0)
            
            # Find old position
            old_pos = next(
                (j for j, c in enumerate(input_chunks) if c["id"] == chunk_id),
                -1
            )
            
            score_changes.append({
                "chunk_id": chunk_id,
                "old_position": old_pos,
                "new_position": i,
                "position_change": old_pos - i,  # Positive = moved up
                "old_score": old_score,
                "new_score": new_score
            })
        
        self.reranking = RerankingTrace(
            input_chunks=input_chunks,
            output_chunks=output_chunks,
            score_changes=score_changes,
            **kwargs
        )
    
    def record_context(
        self,
        selected_chunks: list,
        dropped_chunks: list = None,
        final_context: str = "",
        token_count: int = 0,
        token_limit: int = 0,
        **kwargs
    ):
        """Record context assembly results."""
        self.context = ContextTrace(
            selected_chunks=selected_chunks,
            dropped_chunks=dropped_chunks or [],
            final_context=final_context,
            token_count=token_count,
            token_limit=token_limit,
            truncated=token_count >= token_limit * 0.95,
            **kwargs
        )
    
    def record_generation(
        self,
        system_prompt: str,
        user_prompt: str,
        raw_response: str,
        parsed_answer: str,
        **kwargs
    ):
        """Record generation results."""
        self.generation = GenerationTrace(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            full_prompt=f"{system_prompt}\n\n{user_prompt}",
            raw_response=raw_response,
            parsed_answer=parsed_answer,
            **kwargs
        )
```

---

## Instrumenting Each Pipeline Stage

How to add trace recording to each stage:

### Retrieval Stage

```python
import time


class InstrumentedRetriever:
    """Retriever with built-in tracing."""
    
    def __init__(self, dense_retriever, bm25_retriever=None):
        self.dense = dense_retriever
        self.bm25 = bm25_retriever
    
    def search(
        self,
        query: str,
        top_k: int = 20,
        trace: PipelineTrace = None
    ) -> list[dict]:
        """
        Search with optional trace recording.
        """
        bm25_results = []
        dense_results = []
        bm25_time = 0
        dense_time = 0
        
        # BM25 search
        if self.bm25:
            start = time.perf_counter()
            bm25_results = self.bm25.search(query, top_k)
            bm25_time = (time.perf_counter() - start) * 1000
        
        # Dense search
        start = time.perf_counter()
        dense_results = self.dense.search(query, top_k)
        dense_time = (time.perf_counter() - start) * 1000
        
        # Fusion
        fused_results = self._fuse(bm25_results, dense_results, top_k)
        
        # Record trace
        if trace:
            trace.record_retrieval(
                query=query,
                bm25_results=bm25_results,
                dense_results=dense_results,
                fused_results=fused_results,
                bm25_time_ms=bm25_time,
                dense_time_ms=dense_time,
                fusion_method="rrf"
            )
        
        return fused_results
    
    def _fuse(self, bm25: list, dense: list, top_k: int) -> list:
        """RRF fusion."""
        # ... fusion logic ...
        pass
```

### Reranking Stage

```python
class InstrumentedReranker:
    """Reranker with built-in tracing."""
    
    def __init__(self, reranker_model):
        self.model = reranker_model
    
    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 5,
        trace: PipelineTrace = None
    ) -> list[dict]:
        """
        Rerank with optional trace recording.
        """
        # Keep original order for comparison
        input_chunks = [dict(c) for c in chunks]  # Copy
        
        start = time.perf_counter()
        
        # Score all chunks
        scored = []
        for chunk in chunks:
            score = self.model.score(query, chunk["text"])
            scored.append({**chunk, "rerank_score": score})
        
        # Sort by rerank score
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        output_chunks = scored[:top_k]
        
        rerank_time = (time.perf_counter() - start) * 1000
        
        # Record trace
        if trace:
            trace.record_reranking(
                input_chunks=input_chunks,
                output_chunks=output_chunks,
                model=self.model.name,
                time_ms=rerank_time
            )
        
        return output_chunks
```

### Context Assembly Stage

```python
class InstrumentedContextAssembler:
    """Context assembler with built-in tracing."""
    
    def __init__(self, token_limit: int = 4000, tokenizer=None):
        self.token_limit = token_limit
        self.tokenizer = tokenizer
    
    def assemble(
        self,
        chunks: list[dict],
        trace: PipelineTrace = None
    ) -> str:
        """
        Assemble context with optional trace recording.
        """
        selected = []
        dropped = []
        drop_reasons = {}
        
        current_tokens = 0
        
        for chunk in chunks:
            chunk_tokens = self._count_tokens(chunk["text"])
            
            if current_tokens + chunk_tokens <= self.token_limit:
                selected.append(chunk)
                current_tokens += chunk_tokens
            else:
                dropped.append(chunk)
                drop_reasons[chunk["id"]] = f"token_limit_exceeded ({current_tokens + chunk_tokens} > {self.token_limit})"
        
        final_context = "\n\n---\n\n".join(c["text"] for c in selected)
        
        # Record trace
        if trace:
            trace.record_context(
                selected_chunks=selected,
                dropped_chunks=dropped,
                drop_reason=drop_reasons,
                final_context=final_context,
                token_count=current_tokens,
                token_limit=self.token_limit
            )
        
        return final_context
    
    def _count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        return len(text) // 4  # Rough estimate
```

### Generation Stage

```python
class InstrumentedGenerator:
    """Generator with built-in tracing."""
    
    def __init__(self, llm_client, model: str = "gpt-4o-mini"):
        self.client = llm_client
        self.model = model
    
    def generate(
        self,
        query: str,
        context: str,
        system_prompt: str = None,
        trace: PipelineTrace = None
    ) -> str:
        """
        Generate answer with optional trace recording.
        """
        system_prompt = system_prompt or "Answer based only on the provided context."
        
        user_prompt = f"""Context:
{context}

Question: {query}

Answer:"""
        
        start = time.perf_counter()
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        
        gen_time = (time.perf_counter() - start) * 1000
        
        raw_response = response.choices[0].message.content
        parsed_answer = raw_response.strip()
        
        # Record trace
        if trace:
            trace.record_generation(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=raw_response,
                parsed_answer=parsed_answer,
                model=self.model,
                temperature=0,
                time_ms=gen_time,
                token_usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
        
        return parsed_answer
```

---

## The RAGDebugger Class

A wrapper that adds diagnosis capabilities to any RAG system:

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class FailureType(Enum):
    INDEXING = "indexing"
    RETRIEVAL = "retrieval"
    CONTEXT = "context"
    GENERATION = "generation"
    GROUND_TRUTH = "ground_truth"
    NONE = "none"


@dataclass
class Diagnosis:
    """Result of failure diagnosis."""
    failure_type: FailureType
    subtype: str
    confidence: float
    evidence: dict
    recommendation: str
    trace: PipelineTrace
    
    def __repr__(self):
        if self.failure_type == FailureType.NONE:
            return "No failure detected"
        return f"{self.failure_type.value}/{self.subtype} (confidence: {self.confidence:.0%})"


class RAGDebugger:
    """
    Wrapper that adds debugging capabilities to a RAG system.
    """
    
    def __init__(
        self,
        rag_system,
        index_doc_ids: set[str] = None
    ):
        """
        Args:
            rag_system: RAG pipeline with query(question, debug=True) support
            index_doc_ids: Set of all document IDs in the index (for indexing failure detection)
        """
        self.rag = rag_system
        self.index_doc_ids = index_doc_ids or set()
    
    def query_with_trace(self, question: str) -> tuple[str, PipelineTrace]:
        """
        Run query and return answer with full trace.
        """
        result = self.rag.query(question, debug=True)
        return result.answer, result.trace
    
    def diagnose_failure(
        self,
        question: str,
        expected_answer: str,
        relevant_doc_ids: list[str] = None,
        relevant_chunk_ids: list[str] = None
    ) -> Diagnosis:
        """
        Diagnose why RAG failed for a specific question.
        
        Args:
            question: The query that failed
            expected_answer: What the answer should have been
            relevant_doc_ids: IDs of documents that contain the answer
            relevant_chunk_ids: IDs of specific chunks with the answer
        
        Returns:
            Diagnosis with failure type, evidence, and recommendations
        """
        # Run query with trace
        answer, trace = self.query_with_trace(question)
        
        relevant_doc_ids = relevant_doc_ids or []
        relevant_chunk_ids = relevant_chunk_ids or []
        
        # Check if answer is actually correct
        if self._answer_matches(answer, expected_answer):
            return Diagnosis(
                failure_type=FailureType.NONE,
                subtype="correct",
                confidence=1.0,
                evidence={"answer": answer, "expected": expected_answer},
                recommendation="No fix needed",
                trace=trace
            )
        
        # Walk the decision tree
        
        # Step 1: Check indexing
        if relevant_doc_ids:
            missing = [d for d in relevant_doc_ids if d not in self.index_doc_ids]
            if missing:
                return Diagnosis(
                    failure_type=FailureType.INDEXING,
                    subtype="document_not_indexed",
                    confidence=0.95,
                    evidence={"missing_docs": missing},
                    recommendation="Check ingestion pipeline for these documents",
                    trace=trace
                )
        
        # Step 2: Check retrieval
        retrieved_ids = self._get_retrieved_ids(trace)
        
        if relevant_chunk_ids:
            not_retrieved = [c for c in relevant_chunk_ids if c not in retrieved_ids]
            
            if not_retrieved:
                # Check if they're in full ranking (just ranked low)
                full_ranking_ids = self._get_full_ranking_ids(trace)
                buried = [c for c in not_retrieved if c in full_ranking_ids]
                
                if buried:
                    positions = self._get_positions(trace, buried)
                    return Diagnosis(
                        failure_type=FailureType.RETRIEVAL,
                        subtype="ranked_too_low",
                        confidence=0.90,
                        evidence={
                            "buried_chunks": positions,
                            "top_k": len(trace.retrieval.fused_results)
                        },
                        recommendation="Increase top-k or add hybrid search",
                        trace=trace
                    )
                else:
                    return Diagnosis(
                        failure_type=FailureType.RETRIEVAL,
                        subtype="not_retrieved",
                        confidence=0.85,
                        evidence={"missing_chunks": not_retrieved},
                        recommendation="Check embedding quality, add query expansion",
                        trace=trace
                    )
        
        # Step 3: Check context assembly
        context_ids = self._get_context_ids(trace)
        
        if relevant_chunk_ids:
            retrieved_but_dropped = [
                c for c in relevant_chunk_ids
                if c in retrieved_ids and c not in context_ids
            ]
            
            if retrieved_but_dropped:
                if trace.context.truncated:
                    return Diagnosis(
                        failure_type=FailureType.CONTEXT,
                        subtype="truncated",
                        confidence=0.88,
                        evidence={
                            "dropped_chunks": retrieved_but_dropped,
                            "token_count": trace.context.token_count,
                            "token_limit": trace.context.token_limit
                        },
                        recommendation="Reduce chunk count or increase context window",
                        trace=trace
                    )
                else:
                    return Diagnosis(
                        failure_type=FailureType.CONTEXT,
                        subtype="reranker_dropped",
                        confidence=0.85,
                        evidence={
                            "dropped_chunks": retrieved_but_dropped,
                            "rerank_scores": self._get_rerank_scores(trace, retrieved_but_dropped)
                        },
                        recommendation="Review reranker model or adjust selection",
                        trace=trace
                    )
        
        # Step 4: Check generation
        # At this point, relevant content should be in context
        context_has_answer = self._context_contains_answer(trace, expected_answer)
        
        if context_has_answer:
            return Diagnosis(
                failure_type=FailureType.GENERATION,
                subtype="ignored_context",
                confidence=0.80,
                evidence={
                    "expected_in_context": True,
                    "generated_answer": answer,
                    "expected_answer": expected_answer
                },
                recommendation="Strengthen prompt to use only provided context",
                trace=trace
            )
        
        # Step 5: Ground truth / edge case
        return Diagnosis(
            failure_type=FailureType.GROUND_TRUTH,
            subtype="answer_not_in_corpus",
            confidence=0.70,
            evidence={
                "expected_answer": expected_answer,
                "context_preview": trace.context.final_context[:500]
            },
            recommendation="Verify expected answer exists in corpus",
            trace=trace
        )
    
    def _answer_matches(self, actual: str, expected: str) -> bool:
        """Check if answer matches expected (fuzzy)."""
        actual_lower = actual.lower().strip()
        expected_lower = expected.lower().strip()
        return expected_lower in actual_lower or actual_lower in expected_lower
    
    def _get_retrieved_ids(self, trace: PipelineTrace) -> set[str]:
        """Get IDs of all retrieved chunks."""
        if trace.retrieval and trace.retrieval.fused_results:
            return {r["id"] for r in trace.retrieval.fused_results}
        return set()
    
    def _get_full_ranking_ids(self, trace: PipelineTrace) -> set[str]:
        """Get IDs from full ranking (before top-k cutoff)."""
        # This requires storing full ranking in trace
        # For now, use fused results
        return self._get_retrieved_ids(trace)
    
    def _get_positions(self, trace: PipelineTrace, chunk_ids: list[str]) -> dict:
        """Get positions of chunks in retrieval results."""
        positions = {}
        for i, r in enumerate(trace.retrieval.fused_results):
            if r["id"] in chunk_ids:
                positions[r["id"]] = i + 1
        return positions
    
    def _get_context_ids(self, trace: PipelineTrace) -> set[str]:
        """Get IDs of chunks in final context."""
        if trace.context and trace.context.selected_chunks:
            return {c["id"] for c in trace.context.selected_chunks}
        return set()
    
    def _get_rerank_scores(self, trace: PipelineTrace, chunk_ids: list[str]) -> dict:
        """Get rerank scores for specific chunks."""
        scores = {}
        if trace.reranking and trace.reranking.score_changes:
            for change in trace.reranking.score_changes:
                if change["chunk_id"] in chunk_ids:
                    scores[change["chunk_id"]] = change
        return scores
    
    def _context_contains_answer(self, trace: PipelineTrace, expected: str) -> bool:
        """Check if expected answer appears in context."""
        if trace.context and trace.context.final_context:
            return expected.lower() in trace.context.final_context.lower()
        return False
```

---

## Single Query Diagnosis

Using the debugger for a single failure:

```python
# Setup
debugger = RAGDebugger(
    rag_system=my_rag,
    index_doc_ids={"doc_1", "doc_2", "doc_3", "pricing_guide"}
)

# Diagnose a failure
diagnosis = debugger.diagnose_failure(
    question="What are the pricing tiers for enterprise?",
    expected_answer="Enterprise pricing starts at $10,000/month",
    relevant_doc_ids=["pricing_guide"],
    relevant_chunk_ids=["pricing_guide_chunk_3"]
)

print(diagnosis)
# retrieval/ranked_too_low (confidence: 90%)

print(f"Evidence: {diagnosis.evidence}")
# Evidence: {'buried_chunks': {'pricing_guide_chunk_3': 25}, 'top_k': 20}

print(f"Fix: {diagnosis.recommendation}")
# Fix: Increase top-k or add hybrid search

# Access full trace for deeper inspection
print(f"Retrieved {len(diagnosis.trace.retrieval.fused_results)} chunks")
print(f"Context tokens: {diagnosis.trace.context.token_count}")
```

---

## Configuration Comparison

Test different RAG configurations on the same query:

```python
@dataclass
class ConfigComparison:
    """Result of comparing configurations."""
    query: str
    expected_answer: str
    results: list[dict]  # One per config
    best_config: str
    
    def summary(self) -> str:
        lines = [f"Query: {self.query}", f"Expected: {self.expected_answer}", ""]
        for r in self.results:
            status = "✓" if r["correct"] else "✗"
            lines.append(f"{status} {r['config_name']}: {r['answer'][:50]}...")
        lines.append(f"\nBest: {self.best_config}")
        return "\n".join(lines)


class RAGDebugger:
    # ... previous methods ...
    
    def compare_configs(
        self,
        question: str,
        expected_answer: str,
        configs: list[dict]
    ) -> ConfigComparison:
        """
        Compare different RAG configurations on the same question.
        
        Args:
            question: Query to test
            expected_answer: Expected answer
            configs: List of config dicts with 'name' and parameters
        
        Returns:
            ConfigComparison with results for each config
        """
        results = []
        
        for config in configs:
            config_name = config.pop("name", f"config_{len(results)}")
            
            # Apply config
            original_config = self._get_current_config()
            self._apply_config(config)
            
            # Run query
            answer, trace = self.query_with_trace(question)
            correct = self._answer_matches(answer, expected_answer)
            
            results.append({
                "config_name": config_name,
                "config": config,
                "answer": answer,
                "correct": correct,
                "trace": trace,
                "retrieval_time_ms": trace.retrieval.dense_time_ms + trace.retrieval.bm25_time_ms,
                "generation_time_ms": trace.generation.time_ms,
                "total_time_ms": trace.total_time_ms
            })
            
            # Restore original config
            self._apply_config(original_config)
        
        # Find best config (correct + fastest)
        correct_results = [r for r in results if r["correct"]]
        if correct_results:
            best = min(correct_results, key=lambda r: r["total_time_ms"])
            best_config = best["config_name"]
        else:
            best_config = "none (all failed)"
        
        return ConfigComparison(
            query=question,
            expected_answer=expected_answer,
            results=results,
            best_config=best_config
        )
    
    def _get_current_config(self) -> dict:
        """Get current RAG configuration."""
        return self.rag.get_config()  # Assumes RAG has this method
    
    def _apply_config(self, config: dict):
        """Apply configuration to RAG."""
        self.rag.set_config(config)  # Assumes RAG has this method
```

### Usage Example

```python
comparison = debugger.compare_configs(
    question="How do I fix error E-4012?",
    expected_answer="Clear cache and restart",
    configs=[
        {"name": "dense_only", "search_mode": "dense", "top_k": 20},
        {"name": "hybrid_30", "search_mode": "hybrid", "bm25_weight": 0.3, "top_k": 20},
        {"name": "hybrid_50", "search_mode": "hybrid", "bm25_weight": 0.5, "top_k": 20},
        {"name": "dense_topk_50", "search_mode": "dense", "top_k": 50},
    ]
)

print(comparison.summary())
# Query: How do I fix error E-4012?
# Expected: Clear cache and restart
#
# ✗ dense_only: Based on the documentation, error handling...
# ✓ hybrid_30: To fix error E-4012, clear cache and restart...
# ✓ hybrid_50: Clear the cache and restart the service...
# ✓ dense_topk_50: Error E-4012 can be resolved by clearing...
#
# Best: hybrid_30

# Deeper analysis
for r in comparison.results:
    print(f"{r['config_name']}: {r['total_time_ms']:.0f}ms, correct={r['correct']}")
# dense_only: 450ms, correct=False
# hybrid_30: 520ms, correct=True
# hybrid_50: 510ms, correct=True
# dense_topk_50: 680ms, correct=True
```

---

## Trace Visualization

Simple text output for quick inspection:

```python
class TraceVisualizer:
    """
    Visualize pipeline traces for debugging.
    """
    
    @staticmethod
    def summary(trace: PipelineTrace) -> str:
        """One-line summary of trace."""
        return (
            f"Query: '{trace.query[:50]}...' | "
            f"Retrieved: {len(trace.retrieval.fused_results)} | "
            f"Context: {trace.context.token_count} tokens | "
            f"Time: {trace.total_time_ms:.0f}ms"
        )
    
    @staticmethod
    def retrieval_table(trace: PipelineTrace, top_n: int = 10) -> str:
        """Table of top retrieval results."""
        lines = [
            "RETRIEVAL RESULTS",
            "-" * 70,
            f"{'Pos':<4} {'ID':<30} {'Score':<10} {'Preview':<25}",
            "-" * 70
        ]
        
        for i, r in enumerate(trace.retrieval.fused_results[:top_n], 1):
            preview = r.get("text", "")[:25].replace("\n", " ")
            lines.append(f"{i:<4} {r['id']:<30} {r['score']:<10.4f} {preview}")
        
        if len(trace.retrieval.fused_results) > top_n:
            lines.append(f"... and {len(trace.retrieval.fused_results) - top_n} more")
        
        return "\n".join(lines)
    
    @staticmethod
    def reranking_changes(trace: PipelineTrace) -> str:
        """Show how reranking changed positions."""
        if not trace.reranking or not trace.reranking.score_changes:
            return "No reranking data"
        
        lines = [
            "RERANKING CHANGES",
            "-" * 60,
            f"{'ID':<30} {'Old Pos':<10} {'New Pos':<10} {'Change':<10}",
            "-" * 60
        ]
        
        # Sort by position change (biggest movers first)
        changes = sorted(
            trace.reranking.score_changes,
            key=lambda x: abs(x["position_change"]),
            reverse=True
        )
        
        for change in changes[:10]:
            direction = "↑" if change["position_change"] > 0 else "↓" if change["position_change"] < 0 else "="
            lines.append(
                f"{change['chunk_id']:<30} "
                f"{change['old_position']:<10} "
                f"{change['new_position']:<10} "
                f"{direction} {abs(change['position_change'])}"
            )
        
        return "\n".join(lines)
    
    @staticmethod
    def context_summary(trace: PipelineTrace) -> str:
        """Summary of context assembly."""
        lines = [
            "CONTEXT ASSEMBLY",
            "-" * 60,
            f"Selected chunks: {len(trace.context.selected_chunks)}",
            f"Dropped chunks: {len(trace.context.dropped_chunks)}",
            f"Token count: {trace.context.token_count} / {trace.context.token_limit}",
            f"Truncated: {trace.context.truncated}",
            "",
            "Selected:",
        ]
        
        for c in trace.context.selected_chunks[:5]:
            lines.append(f"  - {c['id']}")
        
        if trace.context.dropped_chunks:
            lines.append("")
            lines.append("Dropped:")
            for c in trace.context.dropped_chunks[:5]:
                reason = trace.context.drop_reason.get(c["id"], "unknown")
                lines.append(f"  - {c['id']}: {reason}")
        
        return "\n".join(lines)
    
    @staticmethod
    def full_report(trace: PipelineTrace) -> str:
        """Complete debug report."""
        sections = [
            "=" * 70,
            f"PIPELINE TRACE: {trace.trace_id}",
            "=" * 70,
            "",
            TraceVisualizer.summary(trace),
            "",
            TraceVisualizer.retrieval_table(trace),
            "",
            TraceVisualizer.reranking_changes(trace),
            "",
            TraceVisualizer.context_summary(trace),
            "",
            "GENERATION",
            "-" * 60,
            f"Model: {trace.generation.model}",
            f"Time: {trace.generation.time_ms:.0f}ms",
            f"Tokens: {trace.generation.token_usage}",
            "",
            "Answer:",
            trace.generation.parsed_answer[:500],
            "",
            "=" * 70,
        ]
        
        return "\n".join(sections)
```

### Usage

```python
answer, trace = debugger.query_with_trace("What is the refund policy?")

# Quick summary
print(TraceVisualizer.summary(trace))
# Query: 'What is the refund policy?...' | Retrieved: 20 | Context: 2500 tokens | Time: 850ms

# Detailed retrieval
print(TraceVisualizer.retrieval_table(trace))
# RETRIEVAL RESULTS
# ----------------------------------------------------------------------
# Pos  ID                             Score      Preview
# ----------------------------------------------------------------------
# 1    policies/refund_v2_chunk_1     0.8934     Our refund policy allows...
# 2    faq/returns_chunk_3            0.8521     For returns and refunds...
# ...

# Full report
print(TraceVisualizer.full_report(trace))
```

---

## Storage and Retrieval

Save traces for later analysis and comparison:

```python
import json
from pathlib import Path
from datetime import datetime


class TraceStorage:
    """
    Store and retrieve debug traces.
    """
    
    def __init__(self, storage_dir: str = "debug_traces"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save(
        self,
        trace: PipelineTrace,
        metadata: dict = None
    ) -> str:
        """
        Save trace to disk.
        
        Returns:
            Path to saved trace
        """
        # Create filename from trace ID
        filename = f"{trace.trace_id}.json"
        filepath = self.storage_dir / filename
        
        # Serialize trace
        data = {
            "trace": self._serialize_trace(trace),
            "metadata": metadata or {},
            "saved_at": datetime.now().isoformat()
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        return str(filepath)
    
    def load(self, trace_id: str) -> tuple[PipelineTrace, dict]:
        """
        Load trace from disk.
        
        Returns:
            (trace, metadata) tuple
        """
        filepath = self.storage_dir / f"{trace_id}.json"
        
        with open(filepath) as f:
            data = json.load(f)
        
        trace = self._deserialize_trace(data["trace"])
        return trace, data.get("metadata", {})
    
    def list_traces(
        self,
        query_filter: str = None,
        limit: int = 100
    ) -> list[dict]:
        """
        List stored traces with optional filtering.
        """
        traces = []
        
        for filepath in sorted(self.storage_dir.glob("*.json"), reverse=True):
            if len(traces) >= limit:
                break
            
            with open(filepath) as f:
                data = json.load(f)
            
            query = data["trace"].get("query", "")
            
            if query_filter and query_filter.lower() not in query.lower():
                continue
            
            traces.append({
                "trace_id": filepath.stem,
                "query": query,
                "timestamp": data["trace"].get("timestamp"),
                "metadata": data.get("metadata", {})
            })
        
        return traces
    
    def compare_traces(
        self,
        trace_ids: list[str]
    ) -> dict:
        """
        Compare multiple traces side by side.
        """
        traces = [self.load(tid)[0] for tid in trace_ids]
        
        comparison = {
            "trace_ids": trace_ids,
            "queries": [t.query for t in traces],
            "retrieval_counts": [len(t.retrieval.fused_results) for t in traces],
            "context_tokens": [t.context.token_count for t in traces],
            "answers": [t.generation.parsed_answer for t in traces],
            "times_ms": [t.total_time_ms for t in traces]
        }
        
        return comparison
    
    def _serialize_trace(self, trace: PipelineTrace) -> dict:
        """Convert trace to JSON-serializable dict."""
        # Use dataclass asdict or manual conversion
        return {
            "trace_id": trace.trace_id,
            "timestamp": trace.timestamp,
            "query": trace.query,
            "retrieval": self._serialize_dataclass(trace.retrieval),
            "reranking": self._serialize_dataclass(trace.reranking),
            "context": self._serialize_dataclass(trace.context),
            "generation": self._serialize_dataclass(trace.generation),
            "total_time_ms": trace.total_time_ms,
            "config": trace.config
        }
    
    def _serialize_dataclass(self, obj) -> dict:
        """Serialize a dataclass to dict."""
        if obj is None:
            return None
        from dataclasses import asdict
        return asdict(obj)
    
    def _deserialize_trace(self, data: dict) -> PipelineTrace:
        """Convert dict back to PipelineTrace."""
        # Simplified — full implementation would reconstruct all nested dataclasses
        trace = PipelineTrace()
        trace.trace_id = data.get("trace_id")
        trace.timestamp = data.get("timestamp")
        trace.query = data.get("query")
        trace.total_time_ms = data.get("total_time_ms", 0)
        trace.config = data.get("config", {})
        # ... reconstruct nested objects ...
        return trace
```

### Usage

```python
storage = TraceStorage("./debug_traces")

# Save trace after debugging
answer, trace = debugger.query_with_trace("What is the refund policy?")
path = storage.save(trace, metadata={
    "expected": "30-day refund policy",
    "status": "investigating",
    "notes": "User reported wrong answer"
})

# Later: list recent traces
recent = storage.list_traces(limit=10)
for t in recent:
    print(f"{t['trace_id']}: {t['query'][:50]}")

# Load and inspect a specific trace
trace, meta = storage.load("20240115_143022_123456")
print(TraceVisualizer.full_report(trace))

# Compare two traces (before/after fix)
comparison = storage.compare_traces([
    "20240115_143022_123456",  # Before fix
    "20240115_150000_789012"   # After fix
])
print(comparison)
```

---

## Performance Considerations

Debug mode adds overhead. Manage it carefully:

### Overhead Sources

|Source|Overhead|Mitigation|
|---|---|---|
|Trace object allocation|Minimal|Only allocate if `debug=True`|
|Copying results to trace|Low|Copy references, not deep copies|
|Timing measurements|Minimal|Use `time.perf_counter()`|
|Embedding storage|High (memory)|Store only if explicitly requested|
|Saving to disk|Medium|Async save, don't block response|

### Production Debug Mode

Never enable full debug in production by default. Options:

```python
class DebugLevel(Enum):
    OFF = 0       # No tracing
    MINIMAL = 1   # Timing + counts only
    STANDARD = 2  # Full trace without embeddings
    VERBOSE = 3   # Everything including embeddings


class RAGPipeline:
    def query(
        self,
        question: str,
        debug: DebugLevel = DebugLevel.OFF
    ) -> RAGResult:
        """
        Query with configurable debug level.
        """
        if debug == DebugLevel.OFF:
            trace = None
        elif debug == DebugLevel.MINIMAL:
            trace = MinimalTrace()  # Just timing
        elif debug == DebugLevel.STANDARD:
            trace = PipelineTrace()  # Full trace, no embeddings
        else:
            trace = VerboseTrace()  # Include embeddings
        
        # ... pipeline execution ...
```

### Sampling in Production

Debug a sample of production requests:

```python
import random


class SampledDebugger:
    """Debug a sample of production traffic."""
    
    def __init__(self, rag_system, sample_rate: float = 0.01):
        self.rag = rag_system
        self.sample_rate = sample_rate
        self.storage = TraceStorage()
    
    def query(self, question: str) -> str:
        """
        Query with probabilistic debug tracing.
        """
        should_trace = random.random() < self.sample_rate
        
        result = self.rag.query(question, debug=should_trace)
        
        if should_trace and result.trace:
            # Async save to not block response
            self._async_save(result.trace)
        
        return result.answer
    
    def _async_save(self, trace: PipelineTrace):
        """Save trace asynchronously."""
        import threading
        thread = threading.Thread(
            target=self.storage.save,
            args=(trace,)
        )
        thread.start()
```

---

## Key Takeaways

1. **Build debug mode in from the start** — Adding it later means touching every pipeline stage. Build it during initial development.
    
2. **Structured traces, not print statements** — Traces are data you can analyze, compare, and store. Print statements are noise you have to read.
    
3. **Instrument every stage** — Retrieval, reranking, context assembly, generation. A gap in visibility is a blind spot in debugging.
    
4. **The RAGDebugger wraps, doesn't modify** — Keep diagnosis logic separate from pipeline logic. The debugger uses the trace; it doesn't change how the pipeline works.
    
5. **Configuration comparison is powerful** — Same query, different configs, side-by-side results. Finds optimal settings fast.
    
6. **Store traces for later** — Today's weird failure might be tomorrow's pattern. Persistent storage enables trend analysis.
    
7. **Visualize for humans, structure for code** — `TraceVisualizer` for quick inspection, raw trace data for automated analysis.
    
8. **Mind the overhead** — Full tracing has costs. Use debug levels, sampling, and async storage in production.
    
9. **Traces are evidence** — When you diagnose a failure, the trace is your proof. Save it with the diagnosis.