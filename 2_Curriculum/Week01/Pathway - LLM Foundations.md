# Week 1: Foundations — LLM Mechanics

> **Track:** Foundational (Sequential) 
> **Time:** 2 hours/day 
> **Goal:** Understand how LLMs actually work under the hood — the mechanics that, if misunderstood, cause costly mistakes in production.

---

## Overview

| Days | Topic                           | Output                               |
| ---- | ------------------------------- | ------------------------------------ |
| 1-2  | Tokenization                    | Mini Challenge complete              |
| 3-4  | Embeddings                      | Mini Challenge complete              |
| 5-6  | Prompt Engineering Fundamentals | Mini Challenge complete              |
| 7    | Mini Build                      | Working CLI tool combining all three |

---

## Days 1-2: Tokenization

### Why This Matters

Every API call costs money per token. Every context window has a token limit. If you don't understand tokenization, you will:

- Miscalculate costs by 2-3x
- Hit context limits unexpectedly
- Break your system with special characters or non-English text
- Fail to optimize prompt length

### What to Learn

**Core Concepts:**

- What tokens are (subword units, not words)
- BPE (Byte Pair Encoding) — the algorithm behind most tokenizers
- Why different models have different tokenizers
- Token ≠ word ≠ character relationship
- Special tokens (BOS, EOS, PAD, system tokens)
- Context window = max tokens (input + output combined)
- Why emojis bloat token costs

**Practical Skills:**

- Count tokens before API calls
- Estimate costs accurately
- Handle token limits gracefully (truncation strategies)
- Understand why some inputs are "expensive"

### Resources

**Primary (Read/Do These):**

- OpenAI Tokenizer Tool: https://platform.openai.com/tokenizer — Experiment here first
- OpenAI Cookbook - Counting Tokens: https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken
- `tiktoken` library documentation: https://github.com/openai/tiktoken

**Secondary (If Concepts Unclear):**

- Search: "Byte Pair Encoding explained" — pick a blog post or video that clicks for you
- Anthropic's token counting: https://docs.anthropic.com/en/docs/build-with-claude/token-counting

### Day 1 Tasks (1 hour learning, 1 hour experimenting)

**Hour 1 — Learn:**

1. Read OpenAI tokenizer page, play with the interactive tool (15 min)
2. Read tiktoken cookbook example (20 min)
3. Install tiktoken locally: `pip install tiktoken` (5 min)
4. Read about different encodings (cl100k_base for GPT-4, o200k_base for GPT-4o) (20 min)

**Hour 2 — Experiment:**

1. Tokenize 10 different sentences — predict count first, then verify
2. Compare: "Hello" vs "hello" vs "HELLO"
3. Compare: "ChatGPT" vs "chatgpt" vs "chat gpt"
4. Tokenize a paragraph in English, then same meaning in Hindi or another language
5. Find a sentence where token count surprises you — understand why

### Day 2 Tasks (1 hour challenge, 1 hour reflection)

**Hour 1 — Mini Challenge:**

Build a Python function that:

```
Input: A string + model name
Output: Token count, estimated cost (input), warning if > 50% of context window
```

**Success Criteria:**

- [ ] Correctly counts tokens for GPT-4o (o200k_base encoding)
- [ ] Correctly counts tokens for GPT-3.5 (cl100k_base encoding)
- [ ] Returns accurate cost estimate (use current pricing: GPT-4o ~$2.50/1M input tokens)
- [ ] Warns when input exceeds 50% of context window (GPT-4o = 128K context)
- [ ] Handles empty string, very long string (10K+ chars), and non-English text without crashing

**Hour 2 — Solidify + Ponder**

Review your code. Run edge cases. Then sit with these:

### 5 Things to Ponder

1. You have a 4000-token context window. Your system prompt is 500 tokens. User sends a message. You retrieve 5 documents of ~400 tokens each. How much room is left for the model's response? What breaks first?
    
2. A user complains your app is expensive. You check — their messages average 50 words but cost 3x what you estimated. What's the most likely cause, and how would you debug it?
    
3. Why do you think OpenAI created a NEW tokenizer (o200k_base) for GPT-4o instead of keeping cl100k_base? What problem were they solving?
    
4. If you're building a system that handles both English and Japanese users, how would tokenization affect your pricing strategy? Should you charge per-word or per-token?
    
5. You're truncating a document to fit context limits. You cut at exactly 3000 tokens. But when you send it to the API, it errors saying you exceeded the limit. What went wrong?
    

---

## Days 3-4: Embeddings

### Why This Matters

Embeddings are how machines understand meaning. Every RAG system, every semantic search, every "find similar" feature runs on embeddings. If you don't understand them, you will:

- Pick wrong embedding models for your use case
- Not understand why retrieval returns garbage
- Fail to debug "it's finding the wrong documents" issues
- Waste money on expensive embeddings when cheap ones work

### What to Learn

**Core Concepts:**

- What embeddings represent (semantic meaning as vectors)
- Vector dimensions (384, 768, 1536, 3072 — what they mean)
- Similarity metrics: cosine similarity, dot product, euclidean distance
- Why cosine similarity is standard for text
- Embedding models: OpenAI ada-002, text-embedding-3-small/large, open-source (BGE, E5, Nomic)
- Trade-offs: dimension size vs. cost vs. quality

**Practical Skills:**

- Generate embeddings via API and locally
- Compare similarity between texts
- Understand when embeddings will work vs. fail
- Choose the right model for your use case

### Resources

**Primary:**

- OpenAI Embeddings Guide: https://platform.openai.com/docs/guides/embeddings
- Sentence Transformers docs: https://www.sbert.net/
- Pinecone's Embedding Guide (conceptual): https://www.pinecone.io/learn/vector-embeddings/

**Secondary:**

- MTEB Leaderboard (compare models): https://huggingface.co/spaces/mteb/leaderboard
- Search: "BGE embedding model" — understand the open-source alternative

### Day 3 Tasks (1 hour learning, 1 hour experimenting)

**Hour 1 — Learn:**

1. Read OpenAI embeddings guide (20 min)
2. Read Pinecone conceptual guide on embeddings (20 min)
3. Understand cosine similarity — what does 0.95 vs 0.70 vs 0.30 actually mean? (10 min)
4. Browse MTEB leaderboard — see what models exist, what dimensions they output (10 min)

**Hour 2 — Experiment:**

1. Get OpenAI API key if you don't have one
2. Generate embeddings for 5 sentences about the same topic (e.g., 5 ways to say "the weather is nice")
3. Generate embeddings for 5 sentences about completely different topics
4. Calculate cosine similarity between all pairs
5. Verify: similar meanings = high similarity, different meanings = low similarity

### Day 4 Tasks (1 hour challenge, 1 hour reflection)

**Hour 1 — Mini Challenge:**

Build a Python script that:

```
Input: A list of 20 sentences (you create them — mix of similar and different topics)
Output: A similarity matrix + identification of the 3 most similar pairs
```

**Success Criteria:**

- [ ] Uses OpenAI text-embedding-3-small (or free alternative: sentence-transformers locally)
- [ ] Correctly computes cosine similarity between all pairs
- [ ] Identifies top 3 most similar pairs — and they should make semantic sense
- [ ] Identifies the least similar pair — should be obviously different topics
- [ ] Prints similarity scores alongside the pairs

**Bonus (if time):**

- [ ] Visualize the 20 embeddings in 2D using UMAP or t-SNE (search: "visualize embeddings umap python")

**Hour 2 — Solidify + Ponder**

### 5 Things to Ponder

1. You embed the question "What is the capital of France?" and the sentence "Paris is the capital of France." These are semantically related but structurally different (question vs. statement). Will their similarity be high or low? Why?
    
2. OpenAI's text-embedding-3-large outputs 3072 dimensions. text-embedding-3-small outputs 1536. If you're storing 1 million documents, how much more storage does the large model require? At what point does this cost matter?
    
3. You're building a search system for legal documents. Users search in casual English ("can my landlord kick me out?") but documents are in formal legal language ("grounds for eviction pursuant to..."). Will embeddings handle this well? Why or why not?
    
4. Two sentences: "The bank was steep" and "The bank was closed." The word "bank" means different things. How do embedding models handle this compared to old-school word embeddings like Word2Vec?
    
5. Your RAG system retrieves documents about "Python programming" when the user asks about "python snakes." What went wrong, and how might you fix it without changing the embedding model?
    

---

## Days 5-6: Prompt Engineering Fundamentals

### Why This Matters

The prompt is your only interface with the model. Same model, different prompt = completely different results. If you don't understand prompt engineering:

- You'll blame the model for your bad prompts
- You'll waste tokens on verbose, inefficient prompts
- You'll get inconsistent outputs and not know why
- You'll miss easy wins that 10x your output quality

### What to Learn

**Core Concepts:**

- System prompt vs. user prompt vs. assistant response
- Zero-shot vs. few-shot prompting
- Instruction clarity (specific > vague)
- Output format specification (JSON, markdown, etc.)
- Temperature and its effect on outputs
- Chain-of-thought prompting (when and why it helps)
- Prompt structure patterns that work

**Practical Skills:**

- Write clear, unambiguous instructions
- Use few-shot examples effectively
- Control output format reliably
- Debug prompts when outputs are wrong
- Iterate systematically (not randomly)

### Resources

**Primary:**

- Anthropic Prompt Engineering Guide: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview
- Anthropic Prompt Engineering Cookbook - https://github.com/anthropics/prompt-eng-interactive-tutorial
- OpenAI Prompt Engineering Guide: https://platform.openai.com/docs/guides/prompt-engineering
- OpenAI Cookbook - Techniques: https://cookbook.openai.com/articles/techniques_to_improve_reliability
- Reddit Example on Prompt Engineering - https://www.reddit.com/r/ClaudeAI/comments/1exy6re/the_people_who_are_having_amazing_results_with/

**Secondary:**

- Search: "few-shot prompting examples" — find practical examples in your domain of interest
- Experiment in ChatGPT or Claude directly before coding

### Day 5 Tasks (1 hour learning, 1 hour experimenting)

**Hour 1 — Learn:**

1. Read Anthropic's prompt engineering overview (30 min) — this is the best guide currently
2. Read OpenAI's guide focusing on the "Tactics" section (20 min)
3. Note down: 5 specific tactics you didn't know or haven't tried (10 min)

**Hour 2 — Experiment:**

Use ChatGPT, Claude, or API playground for these experiments:

1. **Vague vs. Specific:**
    
    - Vague: "Write about climate change"
    - Specific: "Write 3 bullet points explaining why sea levels rise due to climate change, suitable for a 10-year-old"
    - Compare outputs
2. **Zero-shot vs. Few-shot:**
    
    - Ask model to classify sentiment without examples
    - Then provide 3 examples first, ask again
    - Compare accuracy
3. **Temperature exploration:**
    
    - Same creative prompt at temperature 0, 0.5, and 1.0
    - Same factual prompt at temperature 0, 0.5, and 1.0
    - Note the differences
4. **Output format:**
    
    - Ask for "a list of 5 items" (vague format)
    - Ask for "a JSON array with exactly 5 strings" (specific format)
    - Which is more reliable for parsing programmatically?

### Day 6 Tasks (1 hour challenge, 1 hour reflection)

**Hour 1 — Mini Challenge:**

Build a prompt (not code, just the prompt) for this task:

**Task:** Extract structured information from job posting text.

Input: Raw job posting text (varies wildly in format) Output: JSON with fields: `title`, `company`, `location`, `salary_range` (null if not mentioned), `required_skills` (array), `experience_years` (null if not mentioned)

**Success Criteria:**

- [ ] Test your prompt on 5 different job postings (find real ones online)
- [ ] All 5 return valid JSON that parses without errors
- [ ] Fields are correctly extracted (manually verify each)
- [ ] Handles missing information gracefully (null, not made up)
- [ ] Works without modification across different job posting formats

**Deliverable:**

- Your final prompt (system + user template)
- Notes on iterations: what you tried that didn't work, what fixed it

**Hour 2 — Solidify + Ponder**

### 5 Things to Ponder

1. You write a prompt that works perfectly in ChatGPT. You copy it to your code using the API. It behaves differently. What are possible reasons?
    
2. Few-shot prompting uses tokens for examples. If you have a 4000-token limit and your 3 examples use 800 tokens total, is it worth it? How would you decide?
    
3. You ask the model to "never make things up." It still makes things up. Why doesn't this instruction work, and what actually helps reduce hallucination?
    
4. Your prompt asks for JSON output. 95% of the time it works. 5% of the time the model adds explanation text before the JSON, breaking your parser. How do you get to 99.9%?
    
5. Chain-of-thought prompting ("let's think step by step") improves accuracy on math problems. But it uses more tokens and is slower. For a production system handling 10,000 requests/day, how would you decide when to use it vs. not?
    

---

## Day 7: Mini Build — Token-Aware Prompt Optimizer

### What to Build

A CLI tool that takes a prompt and:

1. Counts tokens (using your Day 1-2 knowledge)
2. Analyzes the prompt structure (using your Day 5-6 knowledge)
3. Estimates embedding cost if the prompt were embedded (using your Day 3-4 knowledge)
4. Provides optimization suggestions

### Specifications

**Input:**

```
python prompt_analyzer.py --prompt "your prompt here" --model gpt-4o
```

Or read from file:

```
python prompt_analyzer.py --file prompt.txt --model gpt-4o
```

**Output:**

```
=== PROMPT ANALYSIS ===

Token Count: 347
Estimated Cost (input): $0.00087
Context Usage: 0.27% of 128K window

Structure Analysis:
- Has system instruction: Yes/No
- Has examples (few-shot): Yes/No (count: X)
- Specifies output format: Yes/No
- Uses delimiters: Yes/No

If Embedded:
- text-embedding-3-small: $0.000007
- text-embedding-3-large: $0.000043

Suggestions:
- [Any issues detected: too vague, no output format, etc.]
```

### Success Criteria

- [ ] Accurately counts tokens for specified model
- [ ] Correctly identifies presence of few-shot examples (look for input/output patterns)
- [ ] Correctly identifies if output format is specified (JSON, markdown, list, etc.)
- [ ] Calculates embedding costs correctly
- [ ] Provides at least 2 actionable suggestions when prompt has issues
- [ ] Handles edge cases: empty prompt, very long prompt (>10K tokens), non-English prompt
- [ ] Code is clean enough that you could explain any function to someone

### Things to Ponder (After completing the build)

1. Your tool analyzes prompts statically. But prompt quality really depends on the outputs. How would you extend this tool to also evaluate prompt effectiveness, not just structure?
    
2. You analyze token count for cost. But latency also matters — and it roughly correlates with tokens. How would you add latency estimation to your tool?
    
3. Your "suggestions" are rule-based (if no output format, suggest adding one). What would it take to make the suggestions AI-powered — using an LLM to critique the prompt?
    
4. You built this for single prompts. In a real system, you have prompt templates with variables. How would your analysis change for a template like: "Summarize this document: {document}"?
    
5. This tool helps developers write better prompts. But in production, prompts are often auto-generated or combined with RAG context. Does static analysis still help there? What's different?
    

---

## Week 1 Checklist

### Completion Criteria

- [ ] **Tokenization:** Can count tokens, estimate costs, explain why two similar-looking strings have different token counts
- [ ] **Embeddings:** Can generate embeddings, compute similarity, explain why two texts have high/low similarity
- [ ] **Prompts:** Can write effective prompts with format control, use few-shot when needed, iterate systematically
- [ ] **Mini Build:** Working prompt analyzer tool on your GitHub
- [ ] **Pondering:** Written notes (even brief) on all "Things to Ponder" — your thoughts, not answers

### What's Next

Week 2 begins the parallel tracks:

- **RAG Track:** Document loading, chunking strategies, vector stores
- **Agent Track:** Tool use, function calling, basic agent loop

You'll spend 1 hour on each, same day.

---

## Notes Section

Use this space to capture your learnings, answers to ponder questions, and gotchas you discover.

### Day 1-2 Notes (Tokenization)

### Day 3-4 Notes (Embeddings)

### Day 5-6 Notes (Prompts)

### Day 7 Notes (Mini Build)