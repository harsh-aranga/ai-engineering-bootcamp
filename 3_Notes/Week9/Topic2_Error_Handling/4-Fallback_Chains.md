# Fallback Chains: Degraded Responses Over No Response

## The Principle: Something > Nothing

When your full pipeline fails, you have two choices:

1. **Hard failure**: Show an error page, apologize, ask them to try again
2. **Graceful degradation**: Provide reduced functionality, be transparent about limitations

Users overwhelmingly prefer option 2. A partial answer with caveats beats "Service Unavailable" every time.

### The Mental Model

Think of your system like a commercial airplane:

- **Full power**: All engines, full speed, optimal route
- **One engine out**: Reduced speed, still flies, lands safely
- **Hydraulics issue**: Manual controls, careful landing, everyone survives
- **Total failure**: Crash

Your LLM system should have the same philosophy. Each degradation level removes features but keeps the core promise: _give the user something useful_.

### What Graceful Degradation Looks Like

```
Full RAG + Agent Pipeline
├── Retrieves relevant documents
├── Reranks for quality
├── Agent decides if more info needed
├── Generates grounded response
└── User gets: Perfect answer with citations

Simplified RAG (retrieval down)
├── Basic vector search only
├── No reranking
├── Direct generation from results
└── User gets: Good answer, maybe less precise

LLM Only (retrieval totally down)
├── No documents retrieved
├── LLM uses training knowledge
├── Strong disclaimer added
└── User gets: Possibly useful answer with "not verified" warning

Static Fallback (LLM down too)
├── Pre-written helpful message
├── Guidance on what to do
├── Alternative resources
└── User gets: "We're having issues, here's what you can do"
```

Each level is worse than the one above, but infinitely better than a crash.

---

## The Fallback Hierarchy

### Level 1: Full Pipeline

Everything works. This is your target state.

```
┌─────────────────────────────────────────────────────────┐
│ LEVEL 1: FULL PIPELINE                                   │
├─────────────────────────────────────────────────────────┤
│ Components:                                              │
│   ✓ Query transformation (HyDE, expansion)               │
│   ✓ Hybrid retrieval (dense + sparse)                    │
│   ✓ Reranking                                            │
│   ✓ Agent reasoning (decide if more retrieval needed)    │
│   ✓ Full generation with citations                       │
│                                                          │
│ Timeout: 30 seconds                                      │
│ Quality: Highest                                         │
│ Fallback trigger: Any component failure, timeout         │
└─────────────────────────────────────────────────────────┘
```

### Level 2: Simplified RAG

Remove expensive or fragile components. Core retrieval + generation still works.

```
┌─────────────────────────────────────────────────────────┐
│ LEVEL 2: SIMPLIFIED RAG                                  │
├─────────────────────────────────────────────────────────┤
│ Components:                                              │
│   ✗ Query transformation (disabled)                      │
│   ✓ Basic vector retrieval (dense only)                  │
│   ✗ Reranking (disabled)                                 │
│   ✗ Agent reasoning (disabled)                           │
│   ✓ Direct generation from top-k results                 │
│                                                          │
│ Timeout: 15 seconds                                      │
│ Quality: Good (less precise retrieval)                   │
│ Fallback trigger: Retrieval failure, timeout             │
│                                                          │
│ User sees: Normal response (no visible degradation)      │
└─────────────────────────────────────────────────────────┘
```

### Level 3: Cached Response

If we've answered this question before (or something similar), use the cached answer.

```
┌─────────────────────────────────────────────────────────┐
│ LEVEL 3: CACHED RESPONSE                                 │
├─────────────────────────────────────────────────────────┤
│ Components:                                              │
│   ✓ Semantic cache lookup                                │
│   ✗ Live retrieval (skipped)                             │
│   ✗ Live generation (skipped)                            │
│                                                          │
│ Timeout: 2 seconds                                       │
│ Quality: Depends on cache freshness                      │
│ Fallback trigger: Cache miss, stale cache                │
│                                                          │
│ User sees: "This response was cached on [date]"          │
└─────────────────────────────────────────────────────────┘
```

### Level 4: LLM Only

No retrieval at all. LLM answers from its training knowledge with a strong disclaimer.

```
┌─────────────────────────────────────────────────────────┐
│ LEVEL 4: LLM ONLY                                        │
├─────────────────────────────────────────────────────────┤
│ Components:                                              │
│   ✗ All retrieval (disabled)                             │
│   ✓ LLM generation from training knowledge               │
│   ✓ Strong disclaimer prepended                          │
│                                                          │
│ Timeout: 10 seconds                                      │
│ Quality: Unknown (no grounding in your documents)        │
│ Fallback trigger: LLM failure                            │
│                                                          │
│ User sees: "⚠️ Our document system is unavailable.       │
│            This response is based on general knowledge   │
│            and may not reflect your specific data."      │
└─────────────────────────────────────────────────────────┘
```

### Level 5: Static Fallback

Everything is down. Return a pre-written helpful message.

```
┌─────────────────────────────────────────────────────────┐
│ LEVEL 5: STATIC FALLBACK                                 │
├─────────────────────────────────────────────────────────┤
│ Components:                                              │
│   ✗ All dynamic components (disabled)                    │
│   ✓ Pre-written error message                            │
│   ✓ Guidance and alternatives                            │
│                                                          │
│ Timeout: 0 seconds (instant)                             │
│ Quality: N/A                                             │
│ Fallback trigger: N/A (this is the last resort)          │
│                                                          │
│ User sees: "We're experiencing technical difficulties.   │
│            Our team has been notified. In the meantime:  │
│            • Check our status page: status.example.com   │
│            • Try again in a few minutes                  │
│            • Contact support: support@example.com"       │
└─────────────────────────────────────────────────────────┘
```

---

## When to Fallback

Fallback triggers aren't just exceptions. Four conditions should trigger fallback to the next level:

### 1. Explicit Error

Something threw an exception and couldn't be handled.

```python
try:
    result = current_level.execute(query)
except Exception as e:
    logger.error(f"Level {current_level.name} failed: {e}")
    return try_next_level(query)
```

### 2. Timeout Exceeded

The level is taking too long. Don't wait forever.

```python
try:
    result = await asyncio.wait_for(
        current_level.execute(query),
        timeout=current_level.timeout_seconds
    )
except asyncio.TimeoutError:
    logger.warning(f"Level {current_level.name} timed out")
    return try_next_level(query)
```

### 3. Circuit Breaker Open

The service is known to be failing. Don't even try.

```python
if not current_level.circuit.can_execute():
    logger.info(f"Level {current_level.name} circuit is open, skipping")
    return try_next_level(query)
```

### 4. Quality Check Failed

The level "worked" but the result quality is too low.

```python
result = current_level.execute(query)

# Check quality
if result.confidence < 0.3:
    logger.warning(f"Level {current_level.name} returned low confidence: {result.confidence}")
    return try_next_level(query)

if not result.documents:  # Retrieval returned nothing
    logger.warning(f"Level {current_level.name} returned no documents")
    return try_next_level(query)
```

---

## Fallback Execution Pattern

### The Algorithm

```python
def execute_with_fallback(query: str, levels: list) -> FallbackResult:
    """
    Execute query through fallback chain.
    
    Returns result from first successful level,
    or static fallback if all fail.
    """
    errors = []
    
    for level in levels:
        # Check circuit breaker
        if not level.circuit.can_execute():
            errors.append({
                "level": level.name,
                "error": "circuit_open",
                "skipped": True
            })
            continue
        
        try:
            # Execute with timeout
            result = execute_with_timeout(
                level.execute,
                query,
                timeout=level.timeout_seconds
            )
            
            # Quality check
            if not level.quality_check(result):
                errors.append({
                    "level": level.name,
                    "error": "quality_check_failed",
                    "details": result.quality_info
                })
                level.circuit.record_failure()
                continue
            
            # Success!
            level.circuit.record_success()
            return FallbackResult(
                content=result.content,
                level_used=level.name,
                fallback_path=errors,
                is_degraded=level.name != levels[0].name,
                metadata=result.metadata
            )
            
        except TimeoutError:
            errors.append({
                "level": level.name,
                "error": "timeout",
                "timeout_seconds": level.timeout_seconds
            })
            level.circuit.record_failure()
            
        except Exception as e:
            errors.append({
                "level": level.name,
                "error": str(e),
                "error_type": type(e).__name__
            })
            level.circuit.record_failure()
    
    # All levels failed - return static fallback
    return FallbackResult(
        content=generate_static_fallback(query, errors),
        level_used="static_fallback",
        fallback_path=errors,
        is_degraded=True,
        metadata={"all_levels_failed": True}
    )
```

### Per-Level Timeouts

Each level gets its own timeout, reflecting its expected performance:

```python
LEVEL_CONFIGS = [
    {
        "name": "full_pipeline",
        "timeout_seconds": 30,
        "description": "Complete RAG + agent pipeline"
    },
    {
        "name": "simplified_rag",
        "timeout_seconds": 15,
        "description": "Basic retrieval + generation"
    },
    {
        "name": "cached_response",
        "timeout_seconds": 2,
        "description": "Semantic cache lookup"
    },
    {
        "name": "llm_only",
        "timeout_seconds": 10,
        "description": "LLM without retrieval"
    },
    {
        "name": "static_fallback",
        "timeout_seconds": 0,
        "description": "Pre-written error message"
    }
]
```

Why different timeouts?

- **Full pipeline (30s)**: Complex, involves multiple services
- **Simplified RAG (15s)**: Faster, fewer components
- **Cached response (2s)**: Should be instant, something's wrong if slow
- **LLM only (10s)**: Single LLM call, should be quick
- **Static (0s)**: Instant, no external calls

---

## Designing Each Fallback Level

### Level 1: Full Pipeline

**What's enabled:**

- Query transformation (HyDE, query expansion, decomposition)
- Hybrid retrieval (dense vectors + BM25)
- Reranking (cross-encoder)
- Agent reasoning (iterative retrieval if needed)
- Full citation generation

**Quality guarantees:**

- Highest accuracy
- Best grounding in source documents
- Most complete answers

**Implementation:**

```python
class FullPipelineLevel:
    def __init__(
        self,
        query_transformer,
        hybrid_retriever,
        reranker,
        agent,
        generator,
        circuit: CircuitBreaker
    ):
        self.name = "full_pipeline"
        self.timeout_seconds = 30
        self.circuit = circuit
        
        self.query_transformer = query_transformer
        self.hybrid_retriever = hybrid_retriever
        self.reranker = reranker
        self.agent = agent
        self.generator = generator
    
    def execute(self, query: str) -> LevelResult:
        # Transform query
        transformed = self.query_transformer.transform(query)
        
        # Hybrid retrieval
        candidates = self.hybrid_retriever.retrieve(
            transformed,
            top_k=20
        )
        
        # Rerank
        reranked = self.reranker.rerank(query, candidates, top_k=5)
        
        # Agent decides if more retrieval needed
        final_docs = self.agent.iterative_retrieve(query, reranked)
        
        # Generate response
        response = self.generator.generate(
            query=query,
            documents=final_docs,
            include_citations=True
        )
        
        return LevelResult(
            content=response.text,
            documents=final_docs,
            citations=response.citations,
            confidence=response.confidence,
            metadata={"pipeline": "full"}
        )
    
    def quality_check(self, result: LevelResult) -> bool:
        # Full pipeline should return high-quality results
        return (
            result.confidence >= 0.5 and
            len(result.documents) > 0
        )
```

### Level 2: Simplified RAG

**What's disabled:**

- Query transformation
- Sparse retrieval (BM25)
- Reranking
- Agent reasoning

**What remains:**

- Basic dense vector retrieval
- Direct generation from top-k

**Implementation:**

```python
class SimplifiedRAGLevel:
    def __init__(
        self,
        vector_store,
        generator,
        circuit: CircuitBreaker
    ):
        self.name = "simplified_rag"
        self.timeout_seconds = 15
        self.circuit = circuit
        
        self.vector_store = vector_store
        self.generator = generator
    
    def execute(self, query: str) -> LevelResult:
        # Simple vector search
        documents = self.vector_store.similarity_search(
            query,
            k=5
        )
        
        # Direct generation
        response = self.generator.generate(
            query=query,
            documents=documents,
            include_citations=True
        )
        
        return LevelResult(
            content=response.text,
            documents=documents,
            citations=response.citations,
            confidence=response.confidence,
            metadata={"pipeline": "simplified"}
        )
    
    def quality_check(self, result: LevelResult) -> bool:
        # Accept slightly lower quality
        return (
            result.confidence >= 0.3 and
            len(result.documents) > 0
        )
```

### Level 3: Cached Response

**What's disabled:**

- All live retrieval
- All live generation

**What remains:**

- Semantic cache lookup

**Implementation:**

```python
class CachedResponseLevel:
    def __init__(
        self,
        cache: SemanticCache,
        circuit: CircuitBreaker,
        max_cache_age_hours: int = 24
    ):
        self.name = "cached_response"
        self.timeout_seconds = 2
        self.circuit = circuit
        
        self.cache = cache
        self.max_age_hours = max_cache_age_hours
    
    def execute(self, query: str) -> LevelResult:
        # Semantic cache lookup
        cached = self.cache.get_similar(
            query,
            similarity_threshold=0.9,
            max_age_hours=self.max_age_hours
        )
        
        if not cached:
            raise CacheMissError("No cached response found")
        
        return LevelResult(
            content=self._add_cache_notice(cached.content, cached.timestamp),
            documents=[],
            citations=[],
            confidence=cached.original_confidence,
            metadata={
                "pipeline": "cached",
                "cached_at": cached.timestamp.isoformat(),
                "original_query": cached.original_query,
                "similarity": cached.similarity_score
            }
        )
    
    def _add_cache_notice(self, content: str, timestamp: datetime) -> str:
        age = datetime.now() - timestamp
        if age.total_seconds() < 3600:
            age_str = f"{int(age.total_seconds() / 60)} minutes"
        else:
            age_str = f"{int(age.total_seconds() / 3600)} hours"
        
        notice = f"📋 *This response was cached {age_str} ago.*\n\n"
        return notice + content
    
    def quality_check(self, result: LevelResult) -> bool:
        # Cache hit with high similarity is good enough
        return result.metadata.get("similarity", 0) >= 0.9
```

### Level 4: LLM Only

**What's disabled:**

- All retrieval
- All document grounding

**What remains:**

- LLM generation from training knowledge
- Strong disclaimer

**Implementation:**

```python
class LLMOnlyLevel:
    def __init__(
        self,
        llm_client,
        circuit: CircuitBreaker
    ):
        self.name = "llm_only"
        self.timeout_seconds = 10
        self.circuit = circuit
        
        self.llm = llm_client
    
    def execute(self, query: str) -> LevelResult:
        # Generate without retrieval
        prompt = self._build_disclaimer_prompt(query)
        response = self.llm.generate(prompt)
        
        return LevelResult(
            content=self._format_with_disclaimer(response.text),
            documents=[],
            citations=[],
            confidence=0.3,  # Low confidence, ungrounded
            metadata={"pipeline": "llm_only", "grounded": False}
        )
    
    def _build_disclaimer_prompt(self, query: str) -> str:
        return f"""Answer the following question based on your general knowledge.
Be helpful but acknowledge uncertainty where appropriate.
Do not make up specific facts, statistics, or quotes.

Question: {query}

Answer:"""
    
    def _format_with_disclaimer(self, content: str) -> str:
        disclaimer = """⚠️ **Notice**: Our document retrieval system is currently unavailable. 
This response is based on general knowledge and may not reflect your organization's specific data or policies. 
Please verify important information once the system is restored.

---

"""
        return disclaimer + content
    
    def quality_check(self, result: LevelResult) -> bool:
        # Always pass quality check - LLM response is better than nothing
        # The disclaimer handles user expectations
        return True
```

### Level 5: Static Fallback

**What's disabled:**

- Everything dynamic

**What remains:**

- Pre-written helpful message

**Implementation:**

```python
class StaticFallbackLevel:
    def __init__(
        self,
        status_page_url: str = None,
        support_email: str = None
    ):
        self.name = "static_fallback"
        self.timeout_seconds = 0
        self.circuit = None  # No circuit for static content
        
        self.status_page_url = status_page_url
        self.support_email = support_email
    
    def execute(self, query: str) -> LevelResult:
        content = self._generate_static_message(query)
        
        return LevelResult(
            content=content,
            documents=[],
            citations=[],
            confidence=0,
            metadata={"pipeline": "static_fallback"}
        )
    
    def _generate_static_message(self, query: str) -> str:
        message = """## We're experiencing technical difficulties

I apologize, but I'm unable to process your request right now due to a system issue. Our team has been automatically notified.

### What you can do:

"""
        if self.status_page_url:
            message += f"- **Check system status**: [{self.status_page_url}]({self.status_page_url})\n"
        
        message += "- **Try again in a few minutes** — many issues resolve quickly\n"
        
        if self.support_email:
            message += f"- **Contact support**: [{self.support_email}](mailto:{self.support_email})\n"
        
        message += """
### Your question has been saved

We've logged your question so you won't need to re-type it once the system recovers.

Thank you for your patience.
"""
        return message
    
    def quality_check(self, result: LevelResult) -> bool:
        return True  # Static fallback always passes
```

---

## Degradation Transparency

### The Anti-Pattern: Hiding Degradation

Don't do this:

```python
# BAD: User thinks they got a full answer
def handle_query(query):
    try:
        return full_pipeline(query)
    except:
        return llm_only(query)  # No indication this is degraded!
```

The user trusts your answer, doesn't know it's ungrounded, makes decisions based on wrong information.

### The Right Approach: Clear Indicators

```python
# GOOD: User knows exactly what they're getting
def handle_query(query):
    result = execute_with_fallback(query)
    
    if result.is_degraded:
        result.content = add_degradation_indicator(
            result.content,
            result.level_used,
            result.metadata
        )
    
    return result

def add_degradation_indicator(content: str, level: str, metadata: dict) -> str:
    """Add clear indicator of degradation to response."""
    
    indicators = {
        "simplified_rag": None,  # Close enough to full, no indicator needed
        
        "cached_response": (
            "📋 *This is a cached response from "
            f"{metadata.get('cached_at', 'earlier')}. "
            "It may not reflect the latest information.*"
        ),
        
        "llm_only": (
            "⚠️ **Note**: Document retrieval is currently unavailable. "
            "This response is based on general knowledge and should be "
            "verified against your organization's specific information."
        ),
        
        "static_fallback": None  # Already has full explanation
    }
    
    indicator = indicators.get(level)
    if indicator:
        return f"{indicator}\n\n---\n\n{content}"
    return content
```

### Degradation Severity Levels

|Level|User-Visible Indicator|Why|
|---|---|---|
|Full pipeline|None|This is the normal state|
|Simplified RAG|None or subtle|Still grounded, just less optimized|
|Cached|Clear timestamp|User should know freshness|
|LLM only|Strong warning|Ungrounded, could be wrong|
|Static|Full explanation|System is down, user needs alternatives|

---

## Fallback Response Quality

### Quality Guidelines by Level

**Cached Response Quality:**

- Note the cache timestamp
- Note the original query if different
- Consider cache freshness in response

```python
def format_cached_response(cached: CachedItem) -> str:
    age = datetime.now() - cached.timestamp
    
    header = f"📋 **Cached response** (from {format_age(age)} ago)"
    
    if cached.original_query != cached.matched_query:
        header += f"\n*Original question: \"{cached.original_query}\"*"
    
    return f"{header}\n\n---\n\n{cached.content}"
```

**LLM-Only Quality:**

- Strong disclaimer at the top
- Avoid specific facts/numbers that can't be verified
- Use hedging language ("generally", "typically", "often")
- Suggest verification

```python
LLM_ONLY_SYSTEM_PROMPT = """You are answering without access to the organization's documents.

Rules:
1. Acknowledge this limitation at the start
2. Provide general, helpful information
3. Avoid specific statistics, quotes, or facts you can't verify
4. Use hedging language: "typically", "generally", "often"
5. Suggest the user verify important details once the system is restored
6. Don't pretend to have access to specific documents or data"""
```

**Static Fallback Quality:**

- Be genuinely helpful, not just apologetic
- Provide actionable alternatives
- Set expectations for recovery
- Offer human support options

```python
def generate_helpful_static_response(query: str, context: dict) -> str:
    """Generate a static response that's actually useful."""
    
    response = "## System Currently Unavailable\n\n"
    
    # Acknowledge their question
    response += f"I received your question but can't process it right now.\n\n"
    
    # Provide actionable alternatives
    response += "### What you can do:\n\n"
    
    # Time-based suggestion
    if context.get("expected_recovery_minutes"):
        mins = context["expected_recovery_minutes"]
        response += f"- **Wait briefly**: We expect to be back in ~{mins} minutes\n"
    else:
        response += "- **Try again soon**: Most issues resolve within a few minutes\n"
    
    # Alternative resources
    if context.get("faq_url"):
        response += f"- **Check our FAQ**: {context['faq_url']}\n"
    
    if context.get("docs_url"):
        response += f"- **Browse documentation**: {context['docs_url']}\n"
    
    # Human support
    if context.get("support_email"):
        response += f"- **Contact support**: {context['support_email']}\n"
    
    if context.get("support_phone"):
        response += f"- **Call us**: {context['support_phone']}\n"
    
    # Status transparency
    if context.get("status_url"):
        response += f"\n**Current status**: {context['status_url']}\n"
    
    return response
```

---

## Complete Implementation

### Data Structures

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any, Dict
from abc import ABC, abstractmethod


@dataclass
class LevelResult:
    """Result from a single fallback level."""
    content: str
    documents: List[Any]
    citations: List[dict]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def quality_info(self) -> dict:
        return {
            "confidence": self.confidence,
            "document_count": len(self.documents),
            "has_citations": len(self.citations) > 0
        }


@dataclass
class FallbackResult:
    """Final result from fallback chain."""
    content: str
    level_used: str
    fallback_path: List[dict]  # Errors from each tried level
    is_degraded: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def required_fallback(self) -> bool:
        """True if we fell back from the primary level."""
        return len(self.fallback_path) > 0
    
    @property
    def levels_tried(self) -> int:
        """Number of levels attempted before success."""
        return len(self.fallback_path) + 1
    
    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "level_used": self.level_used,
            "is_degraded": self.is_degraded,
            "levels_tried": self.levels_tried,
            "fallback_path": self.fallback_path,
            "metadata": self.metadata
        }


class FallbackLevel(ABC):
    """Abstract base class for fallback levels."""
    
    name: str
    timeout_seconds: float
    circuit: Optional['CircuitBreaker']
    
    @abstractmethod
    def execute(self, query: str) -> LevelResult:
        """Execute this level's logic."""
        pass
    
    @abstractmethod
    def quality_check(self, result: LevelResult) -> bool:
        """Check if result meets quality threshold."""
        pass
```

### FallbackHandler

```python
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

logger = logging.getLogger(__name__)


class FallbackHandler:
    """
    Orchestrates fallback chain execution.
    
    Usage:
        handler = FallbackHandler(levels=[
            FullPipelineLevel(...),
            SimplifiedRAGLevel(...),
            CachedResponseLevel(...),
            LLMOnlyLevel(...),
            StaticFallbackLevel(...)
        ])
        
        result = handler.execute("What is our refund policy?")
        
        if result.is_degraded:
            logger.warning(f"Degraded response from {result.level_used}")
    """
    
    def __init__(
        self,
        levels: List[FallbackLevel],
        executor: ThreadPoolExecutor = None
    ):
        self.levels = levels
        self.executor = executor or ThreadPoolExecutor(max_workers=4)
        
        # Track statistics
        self._stats = {level.name: {"success": 0, "failure": 0} for level in levels}
    
    def execute(self, query: str) -> FallbackResult:
        """
        Execute query through fallback chain.
        
        Returns result from first successful level,
        or static fallback if all fail.
        """
        errors = []
        
        for i, level in enumerate(self.levels):
            is_primary = (i == 0)
            
            # Check circuit breaker
            if level.circuit and not level.circuit.can_execute():
                logger.info(f"Skipping {level.name}: circuit open")
                errors.append({
                    "level": level.name,
                    "error": "circuit_open",
                    "skipped": True
                })
                continue
            
            try:
                # Execute with timeout
                result = self._execute_with_timeout(level, query)
                
                # Quality check
                if not level.quality_check(result):
                    logger.warning(
                        f"{level.name} failed quality check: {result.quality_info}"
                    )
                    errors.append({
                        "level": level.name,
                        "error": "quality_check_failed",
                        "details": result.quality_info
                    })
                    if level.circuit:
                        level.circuit.record_failure()
                    self._stats[level.name]["failure"] += 1
                    continue
                
                # Success!
                if level.circuit:
                    level.circuit.record_success()
                self._stats[level.name]["success"] += 1
                
                return FallbackResult(
                    content=result.content,
                    level_used=level.name,
                    fallback_path=errors,
                    is_degraded=not is_primary,
                    metadata={
                        **result.metadata,
                        "confidence": result.confidence,
                        "documents_used": len(result.documents)
                    }
                )
                
            except FuturesTimeout:
                logger.warning(f"{level.name} timed out after {level.timeout_seconds}s")
                errors.append({
                    "level": level.name,
                    "error": "timeout",
                    "timeout_seconds": level.timeout_seconds
                })
                if level.circuit:
                    level.circuit.record_failure()
                self._stats[level.name]["failure"] += 1
                
            except Exception as e:
                logger.error(f"{level.name} failed: {e}", exc_info=True)
                errors.append({
                    "level": level.name,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                if level.circuit:
                    level.circuit.record_failure()
                self._stats[level.name]["failure"] += 1
        
        # All levels failed
        logger.error(f"All fallback levels failed for query: {query[:100]}...")
        
        return FallbackResult(
            content=self._generate_final_static_response(query, errors),
            level_used="static_fallback",
            fallback_path=errors,
            is_degraded=True,
            metadata={"all_levels_failed": True, "errors": errors}
        )
    
    def _execute_with_timeout(
        self, 
        level: FallbackLevel, 
        query: str
    ) -> LevelResult:
        """Execute level with timeout using thread pool."""
        if level.timeout_seconds <= 0:
            return level.execute(query)
        
        future = self.executor.submit(level.execute, query)
        return future.result(timeout=level.timeout_seconds)
    
    def _generate_final_static_response(
        self, 
        query: str, 
        errors: List[dict]
    ) -> str:
        """Generate static response when all levels fail."""
        return f"""## Unable to Process Your Request

I apologize, but all of our systems are currently experiencing issues and I cannot answer your question.

### System Status

Our team has been automatically notified of this outage. Here's what we tried:

{self._format_error_summary(errors)}

### What You Can Do

- **Try again in a few minutes** — our systems usually recover quickly
- **Save your question** — you may want to copy it for later
- **Contact support** if this persists

We apologize for the inconvenience.
"""
    
    def _format_error_summary(self, errors: List[dict]) -> str:
        """Format errors for user-friendly display."""
        lines = []
        for error in errors:
            level = error["level"].replace("_", " ").title()
            if error.get("skipped"):
                lines.append(f"- {level}: Skipped (service recovering)")
            elif error.get("error") == "timeout":
                lines.append(f"- {level}: Timed out")
            else:
                lines.append(f"- {level}: Unavailable")
        return "\n".join(lines)
    
    def get_stats(self) -> dict:
        """Get success/failure statistics by level."""
        return {
            name: {
                "success": stats["success"],
                "failure": stats["failure"],
                "success_rate": (
                    stats["success"] / (stats["success"] + stats["failure"])
                    if (stats["success"] + stats["failure"]) > 0
                    else 0
                )
            }
            for name, stats in self._stats.items()
        }
```

### Usage Example

```python
# Initialize components (your actual implementations)
query_transformer = QueryTransformer()
hybrid_retriever = HybridRetriever(vector_store, bm25_index)
reranker = CrossEncoderReranker()
agent = RAGAgent()
generator = LLMGenerator()
semantic_cache = SemanticCache()
llm_client = LLMClient()

# Create circuit breakers for each service
circuits = {
    "full": CircuitBreaker("full_pipeline", CircuitBreakerConfig(failure_threshold=3)),
    "simple": CircuitBreaker("simplified_rag", CircuitBreakerConfig(failure_threshold=3)),
    "cache": CircuitBreaker("cached", CircuitBreakerConfig(failure_threshold=5)),
    "llm": CircuitBreaker("llm_only", CircuitBreakerConfig(failure_threshold=3)),
}

# Create fallback levels
levels = [
    FullPipelineLevel(
        query_transformer=query_transformer,
        hybrid_retriever=hybrid_retriever,
        reranker=reranker,
        agent=agent,
        generator=generator,
        circuit=circuits["full"]
    ),
    SimplifiedRAGLevel(
        vector_store=vector_store,
        generator=generator,
        circuit=circuits["simple"]
    ),
    CachedResponseLevel(
        cache=semantic_cache,
        circuit=circuits["cache"],
        max_cache_age_hours=24
    ),
    LLMOnlyLevel(
        llm_client=llm_client,
        circuit=circuits["llm"]
    ),
    StaticFallbackLevel(
        status_page_url="https://status.example.com",
        support_email="support@example.com"
    )
]

# Create handler
fallback_handler = FallbackHandler(levels=levels)

# Process query
result = fallback_handler.execute("What is our refund policy?")

# Check result
if result.is_degraded:
    logger.warning(
        f"Degraded response from {result.level_used}",
        extra={"fallback_path": result.fallback_path}
    )

# Return to user
return {
    "answer": result.content,
    "metadata": {
        "level": result.level_used,
        "degraded": result.is_degraded,
        "confidence": result.metadata.get("confidence")
    }
}
```

---

## Summary

**The principle:**

- Something useful > nothing at all
- Graceful degradation > hard failure
- Transparency about limitations

**Fallback hierarchy:**

1. Full pipeline (all features)
2. Simplified RAG (basic retrieval)
3. Cached response (semantic cache)
4. LLM only (no retrieval, with disclaimer)
5. Static fallback (helpful error message)

**Fallback triggers:**

- Explicit errors
- Timeouts
- Circuit breaker open
- Quality check failure

**Key implementation details:**

- Per-level timeouts
- Per-level circuit breakers
- Unified response format with metadata
- Clear degradation indicators for users

**Transparency:**

- Tell users when they're getting degraded responses
- Don't pretend full quality when you can't deliver it
- Make static fallbacks genuinely helpful

---

## Connections

- **Note 1**: Failure taxonomy defines what triggers fallback
- **Note 2**: Retries happen within each level before fallback
- **Note 3**: Circuit breakers determine if a level should be skipped
- **Week 8**: LLMOps will track fallback rates as key metrics