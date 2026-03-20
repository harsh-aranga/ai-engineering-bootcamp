# Note 1: Why Agentic RAG — Beyond Single-Shot Retrieval

## The Single-Shot RAG Limitation

Standard RAG follows a simple pipeline:

```
Query → Retrieve → Generate → Done
```

One query. One retrieval pass. One generation. No second chances.

This works beautifully for straightforward questions where:

- The query maps directly to retrievable content
- Top-k results contain everything needed
- No synthesis across multiple topics required

But production systems encounter questions that break this model.

---

## Questions That Break Single-Shot RAG

### Problem 1: Scope Exceeds Single Retrieval

**Query:** "Summarize all customer complaints from Q3"

Single-shot retrieval returns maybe 5-10 chunks. But Q3 complaints span hundreds of tickets across multiple categories. The model generates a "summary" from a tiny, possibly biased sample.

**What's needed:** Multiple retrievals across the complaint corpus, possibly with different filters (by month, by category, by severity), then synthesis.

### Problem 2: Comparison Requires Multiple Targets

**Query:** "What changed between policy v1 and v2?"

Single retrieval might return chunks from v1, or chunks from v2, or a random mix. It won't systematically retrieve both versions for comparison.

**What's needed:** Targeted retrieval of v1 content, targeted retrieval of v2 content, then structured comparison.

### Problem 3: Multi-Perspective Analysis

**Query:** "Find evidence for and against this proposal"

Single retrieval optimizes for relevance to "proposal." It doesn't distinguish supporting vs. opposing content. You get whatever chunks rank highest — likely skewed toward one perspective.

**What's needed:** Separate retrievals for supporting evidence and opposing evidence, then balanced synthesis.

### Problem 4: Insufficient Context Detection

**Query:** "What's our refund policy for enterprise customers?"

Single retrieval returns 5 chunks. Three are about general refund policy. Two are about enterprise pricing. None specifically address enterprise refund terms.

The model generates an answer anyway — hallucinating or interpolating from incomplete context.

**What's needed:** Evaluation of retrieval quality before generation. If context is insufficient, retrieve more or reformulate the query.

---

## What Agentic RAG Adds

Agentic RAG wraps retrieval in a reasoning loop. Instead of "retrieve and done," the agent:

### 1. Evaluates Retrieval Quality

"Do these results actually answer the question? Is the context sufficient? Are there obvious gaps?"

### 2. Decides on Next Action

- **Sufficient:** Proceed to generation
- **Insufficient:** Retrieve more with same query
- **Wrong angle:** Reformulate query and retry
- **Complex question:** Decompose into sub-queries
- **Unsupported answer:** Flag uncertainty or abstain

### 3. Acts and Iterates

Execute the decision, evaluate again, repeat until satisfied or max iterations reached.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Query ──► Retrieve ──► Evaluate ──► Sufficient? ──No──►   │
│                             │                    │          │
│                            Yes                Refine        │
│                             │                 Query         │
│                             ▼                   │           │
│                         Generate ◄──────────────┘           │
│                             │                               │
│                             ▼                               │
│                    Verify Answer                            │
│                             │                               │
│                    Supported? ──No──► Re-retrieve           │
│                             │              or Abstain       │
│                            Yes                              │
│                             │                               │
│                             ▼                               │
│                      Return Answer                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The key insight: **retrieval is no longer a single step but a loop with evaluation and correction.**

---

## The Four Core Patterns

Agentic RAG isn't one technique — it's a family of patterns. Each addresses different failure modes:

### Pattern 1: Iterative Retrieval

**Problem it solves:** Single retrieval doesn't return enough relevant content.

**How it works:** Retrieve, evaluate sufficiency, retrieve more if needed. Repeat until sufficient or max iterations.

**Example use case:** "Summarize all Q3 complaints" — keep retrieving until you've covered the space.

_Detailed implementation: Note 2_

### Pattern 2: Query Decomposition

**Problem it solves:** Complex queries that require information from multiple distinct topics.

**How it works:** Break complex query into simpler sub-queries. Retrieve for each sub-query independently. Synthesize sub-answers into final response.

**Example use case:** "Compare 2023 and 2024 roadmaps" → Sub-queries: "2023 roadmap details," "2024 roadmap details," then compare.

_Detailed implementation: Note 3_

### Pattern 3: Self-Correcting RAG (CRAG)

**Problem it solves:** Generated answers that aren't actually supported by retrieved context.

**How it works:** After generation, verify the answer against the context. If answer contains claims not in context, re-retrieve or flag uncertainty.

**Example use case:** Catching hallucinated specifics — model says "refund within 30 days" but context only mentions "refund available" without timeframe.

_Detailed implementation: Note 4_

### Pattern 4: Adaptive Strategy Selection

**Problem it solves:** Not all queries need the same treatment. Simple queries don't need iteration overhead.

**How it works:** Classify query complexity first. Route simple queries to standard RAG, complex queries to appropriate agentic pattern.

**Example use case:** "What's our return address?" → Simple RAG. "Analyze trends across all support tickets" → Iterative + decomposition.

_Detailed implementation: Note 5_

---

## The Cost-Quality Trade-off

Agentic RAG isn't free. Each pattern adds overhead:

|Pattern|Additional LLM Calls|Latency Multiplier|Token Cost Multiplier|
|---|---|---|---|
|Simple RAG (baseline)|1|1x|1x|
|Iterative (3 iterations)|3-6|2-3x|2-4x|
|Decomposition (3 sub-queries)|4-5|2-3x|3-5x|
|Self-correction|2-3|1.5-2x|1.5-2x|
|Full agentic (combined)|5-10+|3-5x|3-6x|

**Additional LLM calls include:**

- Sufficiency evaluation ("Is this context enough?")
- Query refinement ("What should I search for next?")
- Decomposition ("Break this into sub-queries")
- Verification ("Is this answer supported?")
- Synthesis ("Combine these sub-answers")

### When Agentic Patterns Are Justified

**High-value, complex queries:**

- Research and analysis tasks
- Multi-document synthesis
- Comparative analysis
- Comprehensive summaries

**High-stakes answers:**

- Legal or compliance questions where hallucination is costly
- Customer-facing responses where errors damage trust
- Decision-support where accuracy matters more than speed

**Exploratory queries:**

- User doesn't know exactly what they're looking for
- Query requires discovering related information
- Answer quality improves with broader retrieval

### When to Stay Simple

**The 80/20 reality:** Most production queries don't need agentic patterns.

- "What's the return policy?" → Simple RAG
- "How do I reset my password?" → Simple RAG
- "What are your office hours?" → Simple RAG

For these queries, agentic patterns add latency and cost without improving answer quality. The simple RAG pipeline handles them perfectly.

**The decision heuristic:**

```
IF query is:
  - Single topic
  - Fact-based lookup
  - Likely answered in 1-3 chunks
THEN: Simple RAG

IF query requires:
  - Multiple information sources
  - Synthesis or comparison
  - Comprehensive coverage
  - High confidence in completeness
THEN: Consider agentic patterns
```

---

## Mental Model: RAG as Information Retrieval Agent

Think of the shift like this:

**Simple RAG:** A library search that returns the top 5 results for your query. You read what you get.

**Agentic RAG:** A research assistant who:

1. Searches for initial results
2. Evaluates: "Is this what you actually need?"
3. Refines: "Let me try a different search angle"
4. Expands: "This question has three parts — let me search each"
5. Verifies: "Let me make sure my summary is actually supported by what I found"

The agent adds judgment to retrieval. It knows when to keep looking, when to change strategy, and when to admit uncertainty.

---

## What's Coming Next

The remaining notes implement each pattern:

- **Note 2:** Iterative retrieval — the retrieve-evaluate-refine loop
- **Note 3:** Query decomposition — breaking complex queries into sub-queries
- **Note 4:** Self-correcting RAG (CRAG) — verifying answers against context
- **Note 5:** Adaptive RAG agent — combining patterns with intelligent routing

Each pattern builds on this foundation: retrieval is a loop, not a step.

---

## Key Takeaways

1. **Single-shot RAG fails on complex queries** — questions requiring multiple retrievals, comparisons, or comprehensive coverage break the simple pipeline.
    
2. **Agentic RAG adds reasoning loops** — evaluate retrieval quality, decide on next action, iterate until satisfied.
    
3. **Four core patterns exist** — iterative retrieval, query decomposition, self-correction, and adaptive strategy selection.
    
4. **Cost-quality trade-off is real** — agentic patterns add 2-5x latency and cost. Use them where the quality improvement justifies the overhead.
    
5. **Most queries don't need agentic patterns** — simple RAG handles 80%+ of production traffic. Know when to stay simple.
    
6. **The key insight:** Retrieval becomes a loop with evaluation and correction, not a single step.