# Query Transformation: Bridging the Query-Document Gap

## The Problem You're Solving

You've built a RAG system. Documents are chunked well, embeddings are solid, retrieval is fast. A user asks:

> "how do I fix login problems"

Your documentation says:

> "Authentication troubleshooting procedures for resolving credential verification failures"

The semantic similarity score? Mediocre. The relevant chunk? Buried at position 7. The LLM? Working with suboptimal context.

This is the **query-document language gap** — and it's one of the most common silent failures in production RAG.

---

## Why This Gap Exists

Three forces create this mismatch:

**1. Users speak casually; documents speak formally**

|User Query|Document Language|
|---|---|
|"what's the deal with refunds"|"return policy and reimbursement guidelines"|
|"app keeps crashing"|"application stability and error handling procedures"|
|"how much PTO do I get"|"paid time off accrual schedule"|

**2. Users are terse; documents are verbose**

A user types 4-6 words. A document chunk contains 200-500 words. When you embed both into the same vector space, you're comparing a sketch to a detailed painting. The embedding model does its best, but the information density mismatch works against you.

**3. Users don't know the vocabulary**

Your internal docs use "SLA escalation matrix." The user asks about "how to complain when support is slow." Same concept, zero vocabulary overlap. Embedding models help here — but they have limits, as you learned in Week 1. Vocabulary overlap still dominates semantic similarity scores.

---

## What Query Transformation Does

Query transformation is a **pre-retrieval optimization** — you modify the query before it hits the vector store.

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Transformation │  ← This is what we're adding
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Retrieval     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Generation    │
└─────────────────┘
```

The goal: make the query look more like the documents, or search from multiple angles to increase your chances of hitting relevant chunks.

---

## The Four Main Approaches

There are four established techniques. Each attacks the gap differently:

### HyDE (Hypothetical Document Embeddings)

**Core idea:** Instead of embedding the query, ask an LLM to generate a hypothetical answer, then embed _that_.

Why it works: The hypothetical answer is verbose, uses formal language, and lives in "document space" rather than "query space." You're now comparing document-to-document instead of query-to-document.

Trade-off: You're adding an LLM call before retrieval. If the LLM hallucinates a wrong answer, you're now searching for the wrong thing.

### Query Expansion

**Core idea:** Take the original query and add synonyms, related terms, or alternative phrasings.

"return policy" → "return policy OR refund policy OR exchange guidelines OR money back"

Why it works: Casts a wider net. Especially useful for keyword-based (BM25) retrieval where exact term matching matters.

Trade-off: Can introduce noise. "python programming" expanded carelessly might pull in "python snake species."

### Query Rewriting

**Core idea:** Use an LLM to rephrase the casual user query into formal document language.

"how do I fix login problems" → "authentication troubleshooting steps for credential verification failures"

Why it works: Directly addresses the casual-vs-formal gap. The rewritten query uses vocabulary that actually appears in your documents.

Trade-off: Requires the LLM to know (or guess) your document vocabulary. Generic rewriting might miss domain-specific terms.

### Multi-Query

**Core idea:** Generate multiple query variations, retrieve for each, merge and deduplicate results.

"ML best practices" → ["machine learning best practices", "ML guidelines", "AI model development standards"]

Why it works: Different phrasings surface different chunks. Merging results (often via reciprocal rank fusion) combines the best of each.

Trade-off: 3 queries = 3x embedding cost, 3x retrieval latency. You're trading speed for recall.

---

## The Universal Trade-off

Every query transformation technique adds **latency** and/or **cost**:

|Technique|Added LLM Calls|Added Embeddings|Added Retrievals|
|---|---|---|---|
|HyDE|1|1 (the hypothetical doc)|0|
|Query Expansion|0-1|0 (usually BM25)|0|
|Query Rewriting|1|1|0|
|Multi-Query|1|N (one per variation)|N|

For a high-traffic production system, these costs compound. A 200ms LLM call before retrieval might be acceptable for a research assistant but unacceptable for a customer support chatbot handling 10,000 queries/hour.

The decision framework:

- **High-stakes, low-volume:** Transform aggressively. Get the best possible retrieval.
- **High-volume, latency-sensitive:** Transform selectively. Maybe only for queries that fail initial retrieval.
- **Hybrid approach:** Try retrieval first. If confidence is low (e.g., top result similarity < threshold), then apply transformation and retry.

---

## How This Connects to What You've Learned

Query transformation doesn't replace what you've already built — it complements it:

**Chunking (Week 3):** You control how documents are split. Good chunking reduces the gap from the document side. Query transformation reduces the gap from the query side.

**Embeddings (Week 1):** You learned that embedding similarity is dominated by vocabulary overlap and sentence structure. Query transformation directly addresses this by rewriting queries to share vocabulary with documents.

**Hybrid Search (Week 5):** BM25 + dense retrieval gives you two angles of attack. Query expansion is particularly powerful with BM25 because exact keyword matches matter. These techniques stack.

**Reranking (Week 5):** Transformation improves recall (finding relevant chunks). Reranking improves precision (surfacing the best ones). They solve different problems and work well together.

---

## The Production Reality

Query transformation sounds elegant in theory. In production, you'll hit these realities:

**1. You're adding a failure point**

An LLM call that times out, hallucinates badly, or returns garbage now breaks your retrieval pipeline. You need fallbacks: if transformation fails, use the original query.

**2. Domain-specific terminology is hard**

Generic query rewriting might turn "what's our SLA" into "service level agreement" — but your company calls it "Customer Commitment Standards." Effective transformation often requires domain adaptation: custom prompts, fine-tuning, or terminology dictionaries.

**3. Latency adds up fast**

In a pipeline that already has: embedding (50ms) + retrieval (30ms) + generation (500ms), adding a 200ms transformation step increases your P95 latency by 30%+. Measure before and after.

**4. Not all queries need transformation**

"What is our refund policy" is already clear. Transforming it might actually hurt by introducing noise. The best systems detect when transformation is needed rather than applying it blindly.

---

## Key Takeaways

1. **The query-document gap is a primary cause of retrieval failure** — users speak differently than documents, and embeddings can't fully bridge this gap.
    
2. **Query transformation is pre-retrieval optimization** — you modify the query before it hits the vector store, not the documents.
    
3. **Four main techniques exist:** HyDE (embed a hypothetical answer), expansion (add related terms), rewriting (rephrase in document language), multi-query (search multiple variations).
    
4. **Every technique has a cost** — additional LLM calls, embeddings, or retrievals. The right choice depends on your latency budget and query volume.
    
5. **Transformation complements, not replaces** — it works alongside good chunking, hybrid search, and reranking to build a robust retrieval stack.