## 1. Retrieval Failures (Garbage In, Garbage Out)

**The core problem:** If you retrieve wrong chunks, the LLM will confidently answer using wrong context. The LLM has no way to know the retrieved chunks are irrelevant — it just works with what it's given.

**Specific failure modes:**

**Vocabulary mismatch** User asks "how do I get my money back?" but your docs say "refund policy" and "reimbursement process." Dense retrieval helps, but doesn't fully solve it.

**Semantic similarity ≠ relevance** Two chunks can be semantically similar but one answers the question and one doesn't. "Our refund policy is 30 days" vs "Our competitor's refund policy is 14 days" — embedding similarity might be high for both.

**Chunk boundary problems** The answer spans two chunks, but you only retrieve one. Or the chunk cuts off mid-sentence. Or critical context (like "this applies only to enterprise customers") is in a different chunk.

**Keyword stuffing in source docs** If your source documents have repeated terms, those chunks get artificially boosted in retrieval.

**Top-k retrieves duplicates** You retrieve 5 chunks, but 3 of them say essentially the same thing (from different parts of the doc). You've wasted retrieval slots.

---

## 2. Chunking Failures

**Too small chunks:**

- Lose context — "it" refers to something in the previous chunk
- Higher retrieval noise — more chunks to search through
- Answer fragments scattered across chunks

**Too large chunks:**

- Diluted relevance — chunk has the answer buried in irrelevant text
- Wastes context window
- Embedding quality degrades (models have limits on what they can meaningfully compress)

**Naive splitting:**

- Cuts mid-sentence, mid-paragraph, mid-thought
- Separates headers from their content
- Breaks tables, code blocks, lists

---

## 3. Context Stuffing Failures

**Too much context:**

- Exceeds context window → truncation → lost information
- "Lost in the middle" problem — LLM pays less attention to middle chunks (you covered this in Week 2)
- More tokens = more cost = slower response

**Contradictory context:**

- You retrieve chunks that contradict each other (old policy vs new policy, different product versions)
- LLM either picks one arbitrarily or hedges unhelpfully

**Irrelevant context confuses the model:**

- Retrieved chunks are tangentially related but don't answer the question
- LLM tries to use them anyway, producing plausible-sounding wrong answers

---

## 4. Generation Failures (Even With Good Retrieval)

**Hallucination despite context:**

- LLM has the right chunk but ignores it in favor of its parametric knowledge
- Especially happens when training knowledge contradicts retrieved context
- More likely with weaker models or poorly structured prompts

**Over-reliance on context:**

- Opposite problem — LLM treats retrieved chunks as gospel even when they're outdated or wrong
- No critical evaluation of source quality

**Failure to synthesize:**

- Answer requires combining information from multiple chunks
- LLM summarizes each chunk separately instead of synthesizing

**Attribution failure:**

- LLM gives correct answer but can't point to which chunk it came from
- Makes verification impossible

---

## 5. Silent Failures (The Worst Kind)

These are dangerous because the system looks like it's working:

**Confident wrong answers:**

- Retrieved wrong chunks → LLM answers confidently → user trusts it
- No indication anything went wrong

**Partial answers:**

- Retrieved some relevant chunks but missed others
- Answer is technically correct but incomplete
- User doesn't know they're missing information

**Stale data:**

- Old versions of documents still in vector store
- System retrieves outdated information
- Answer was correct last month, wrong now

---

## How to Detect These (Preview of Week 6)

You can't fix what you can't measure:

|Failure Mode|Detection Approach|
|---|---|
|Bad retrieval|Retrieval metrics (precision, recall, MRR) on labeled test set|
|Chunk quality|Manual inspection, golden dataset comparison|
|Context issues|LLM-as-judge to evaluate if context supports answer|
|Hallucination|Citation verification, entailment checking|
|Silent failures|User feedback loops, random sampling + human review|

---

## What You Should Take Away

1. **Most RAG failures are retrieval failures** — the generation step is usually fine if retrieval is good
2. **You need observability** — logging what was retrieved, not just final answers
3. **Evaluation isn't optional** — without metrics, you're guessing
4. **There's no silver bullet** — each failure mode has different mitigations (hybrid search, reranking, better chunking, prompt engineering, etc.)