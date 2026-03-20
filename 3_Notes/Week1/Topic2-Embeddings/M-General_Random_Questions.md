# 1. Do general privacy rules apply to embeddings as well for organizational data?

Yes, **embeddings are organizational data** and the same privacy rules apply, but there's a critical nuance you need to understand:
## The Privacy Risk
**Embeddings can leak the original text.**
This isn't theoretical — it's demonstrated:
1. **Inversion attacks exist**: Researchers have shown you can reconstruct approximate original text from embeddings with enough compute
2. **Embeddings preserve semantic structure**: If your docs contain PII, trade secrets, or sensitive info — that structure is encoded in the vectors
3. **Vector databases are data stores**: Treat them like you'd treat a database with raw text

**Bottom line:** Yes, treat embeddings like organizational data. No, don't assume they're "anonymized" just because they're vectors.
This is especially important in RAG systems where you're embedding customer data, internal docs, or anything regulated.

---
# 2. Do embedding models need to know about recent events?
**Short answer:** Not really — but they need to know recent **language patterns**.
Embeddings don't "know facts" like LLMs do. But if trained on old data (pre-2021), they won't understand:
- New slang/terms ("skibidi," "delulu," "rizz")
- New product names ("ChatGPT," recent startups)
- Shifted meanings ("Web3," "climate tech")

**Impact:** Weak embeddings for new terms = worse semantic search.

**When it matters:** Social media analysis, trend detection, rapidly evolving domains (crypto, AI, TikTok culture).

**When it doesn't:** Most business docs use timeless concepts. Sept 2021 cutoff is fine for 90% of RAG systems.

---
# 3. How do embeddings handle internal company jargon (UTS, CND, SevOne)?
**Short answer:** They don't — and this breaks semantic search.
If the embedding model never saw "UTS" or "SevOne" during training:
- It assigns weak/generic embeddings
- Semantic search fails: "Which team handles network monitoring?" won't match "SevOne" even if that's the right answer

**Why:** Embeddings learn by co-occurrence. If "SevOne" never appeared with "network monitoring" in training data → no learned association.

**Real fix:** Hybrid search (BM25 + embeddings). BM25 catches exact "UTS" match, embeddings catch semantic meaning. You'll learn this in Week 5.

**Workarounds until then:**
- Expand acronyms in docs: "UTS (Unified Telephony Services)"
- Add glossaries to chunks
- Accept that pure semantic search will miss some jargon matches
---
