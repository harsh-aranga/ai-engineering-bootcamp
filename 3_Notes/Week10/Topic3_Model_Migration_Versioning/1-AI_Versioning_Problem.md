# Note 1: The AI Versioning Problem — Why It's Harder Than Traditional Software

## The Core Problem

Traditional software versioning is straightforward:

```
Code v1.2.3 → Deterministic behavior
Same input → Same output
Version control captures everything that matters
```

AI application versioning is fundamentally different:

```
Code v1.2.3
  + Prompt v2.1
  + Model gpt-4o-mini
  + Temperature 0.7
  + Embedding model text-embedding-3-small
  + Vector index built 2024-01-15
  = Probabilistic behavior (and STILL may vary due to provider updates)
```

The difference isn't just complexity — it's that multiple independent components all affect output behavior, and some of those components are outside your control.

---

## What Needs Versioning in AI Applications

### 1. Code (Traditional — You Know This)

Version control via git. Same as any software project.

```
git log --oneline
a3f2b1c Add reranking to retrieval pipeline
8d4e5f2 Fix context window overflow
...
```

### 2. Prompts (Text That Changes Behavior Dramatically)

A single word change can shift output quality significantly:

```python
# v1.0 — Original
SYSTEM_PROMPT = "You are a helpful assistant."

# v1.1 — Added constraint
SYSTEM_PROMPT = "You are a helpful assistant. Be concise."

# v2.0 — Complete rewrite
SYSTEM_PROMPT = """You are a technical documentation specialist.
Respond with structured markdown. Include code examples where relevant.
Never use phrases like 'I think' or 'probably'."""
```

Each of these produces meaningfully different outputs for the same user query. Prompts need versioning just like code.

### 3. Models (Provider May Update Without Notice)

This is the silent killer. When you call `gpt-4o-mini`, you're calling whatever version OpenAI is currently serving — not a pinned snapshot.

**Current reality (as of March 2026, per OpenAI deprecation docs):**

|Model Alias|What You Get|Risk|
|---|---|---|
|`gpt-4o-mini`|Latest version|Changes without warning|
|`gpt-4o-mini-2024-07-18`|Pinned snapshot|Will be deprecated eventually|
|`gpt-4o`|Latest version|Already deprecated in ChatGPT, API timeline announced|

**The deprecation cycle:**

1. OpenAI releases a new model version
2. The alias (`gpt-4o-mini`) starts pointing to the new version
3. Old pinned versions continue working (for now)
4. Eventually, old versions get deprecated (3-12 months notice typical)
5. Your pinned version stops working — you must migrate

**Real examples from 2025-2026:**

- `gpt-4.5-preview` deprecated April 2025, removal July 2025
- `o1-preview` and `o1-mini` deprecated April 2025, removal within 3-6 months
- `gpt-4o` versions (2024-05-13, 2024-08-06) deprecated, retirement by late 2026

**The tradeoff:**

- **Pin versions** → Reproducibility now, forced migration later
- **Use aliases** → Always current, but behavior may change unexpectedly

Neither is perfect. You need a strategy for both.

### 4. Embeddings (Can't Mix Models in Same Index)

This is non-negotiable:

```
text-embedding-ada-002 → 1536-dimensional vectors
text-embedding-3-small → 1536-dimensional vectors (DIFFERENT space!)

Cosine similarity between them: MEANINGLESS
```

If you indexed documents with `ada-002`, you cannot query with `3-small`. The vectors exist in different mathematical spaces. Same dimensionality doesn't mean compatible.

**What needs tracking:**

- Which embedding model was used to build the index
- When the index was last rebuilt
- Which documents are in the index (and their versions)

### 5. Configuration (Temperature, top_k, Thresholds)

These affect output in ways that interact with prompts and models:

```yaml
# config/v1.0.yaml
llm:
  temperature: 0.7      # More creative
  max_tokens: 1000
  
retrieval:
  top_k: 10
  similarity_threshold: 0.75

# config/v1.1.yaml  
llm:
  temperature: 0.3      # More deterministic
  max_tokens: 2000      # Allow longer responses
  
retrieval:
  top_k: 5              # Fewer but higher-quality chunks
  similarity_threshold: 0.80  # Stricter relevance filter
```

A temperature change from 0.7 to 0.3 can completely change the character of responses. These aren't just "settings" — they're part of your application's behavior specification.

### 6. Data/Index State (When Was Index Built, From What Data)

Your RAG system's behavior depends on what's in the index:

```
Index v1: Built 2024-01-15, 50,000 documents, ada-002
Index v2: Built 2024-03-20, 75,000 documents, ada-002 (added Q1 reports)
Index v3: Built 2024-06-01, 75,000 documents, text-embedding-3-small (migrated)
```

Same query, same code, same prompts — different results because the retrieval corpus changed.

---

## The "What Changed?" Problem

Output quality dropped. Why?

```
Monday: Users rate responses 4.2/5
Tuesday: Users rate responses 3.1/5

What happened?

Possibility 1: Someone deployed a code change
Possibility 2: OpenAI updated gpt-4o-mini
Possibility 3: A prompt was edited in production
Possibility 4: Retrieval quality degraded (index issue?)
Possibility 5: Combination of the above
```

**Without versioning:** You have no idea. You're debugging blind.

**With versioning:** You can diff Monday's configuration against Tuesday's and identify exactly what changed.

```python
# Monday's request log
{
    "request_id": "req_abc123",
    "config": {
        "model": "gpt-4o-mini-2024-07-18",
        "prompt_version": "v2.1",
        "embedding_model": "text-embedding-3-small",
        "index_version": "v3",
        "temperature": 0.7
    },
    "quality_score": 4.2
}

# Tuesday's request log
{
    "request_id": "req_def456",
    "config": {
        "model": "gpt-4o-mini-2024-07-18",
        "prompt_version": "v2.2",  # <-- Changed
        "embedding_model": "text-embedding-3-small",
        "index_version": "v3",
        "temperature": 0.7
    },
    "quality_score": 3.1
}
```

Now you know: the prompt changed. You can look at the diff between v2.1 and v2.2.

---

## Provider Model Updates: The Silent Drift Problem

OpenAI (and other providers) update models without changing the model name:

```python
# Your code hasn't changed in 6 months
response = client.responses.create(
    model="gpt-4o-mini",  # Same string
    ...
)

# But the model behind "gpt-4o-mini" has changed 3 times
```

**Why providers do this:**

- Bug fixes and safety improvements
- Performance optimizations
- They want you on the latest version

**Why this is a problem for you:**

- Output characteristics change (tone, verbosity, instruction-following)
- Latency may change
- Edge case behavior differs
- Your carefully-tuned prompts may work worse with the new version

**Solution: Pin specific versions when reproducibility matters**

```python
# Instead of:
model = "gpt-4o-mini"

# Use:
model = "gpt-4o-mini-2024-07-18"
```

**But remember:** Pinned versions get deprecated. You're not avoiding migration — you're controlling when it happens.

---

## Reproducibility Requirements

Why does versioning matter? Four scenarios where you need to reproduce exact past behavior:

### 1. Debug Past Issues

User complaint from 2 weeks ago: "The system gave me wrong information about X."

**Without versioning:** You can't reproduce what they saw. You're guessing.

**With versioning:** You replay their exact query against the exact configuration they experienced.

### 2. Compliance and Audit

Regulated industries need to prove what was returned:

```
Auditor: "Show me what this user saw when they asked about their policy coverage."

You: "Here's the exact query, the exact configuration, the exact retrieved 
     context, and the exact response — all logged at request time."
```

### 3. A/B Test Analysis

You ran an experiment comparing two models. Now you need to analyze results:

```python
# Variant A: gpt-4o-mini, prompt v2.1, temp 0.7
# Variant B: gpt-4o, prompt v2.1, temp 0.5

# Without version logging:
"Which config did user X get?" → No idea

# With version logging:
experiment_results = db.query("""
    SELECT variant, config, avg(quality_score) 
    FROM requests 
    WHERE experiment='model_comparison_v2'
    GROUP BY variant
""")
```

### 4. Rollback

Something broke. You need to restore exactly what was working before:

```
Current (broken):  model v4o, prompt v2.3, temp 0.5
Previous (worked): model v4o-mini-2024-07-18, prompt v2.1, temp 0.7

Rollback = restore the exact previous configuration, not just "undo the last change"
```

---

## The Versioning Stack

Every AI application needs versioning at multiple layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Request-Level Logging                     │
│  (Capture exact configuration for every request)            │
└─────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────┬──────────────┼──────────────┬────────────────┐
│  Git         │  Prompt      │  Config      │  Index         │
│  (Code)      │  Versioning  │  Versioning  │  Versioning    │
│              │  System      │              │                │
│  a3f2b1c     │  v2.1        │  prod-v3     │  idx-2024-06   │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

|Layer|What It Captures|Storage|
|---|---|---|
|Git|Code changes|Repository|
|Prompt versioning|Prompt templates, system prompts|Files in git OR database with versions|
|Config versioning|Model names, temperatures, thresholds|YAML/JSON files tied to deployment|
|Index versioning|Embedding model, document set, build date|Metadata in vector store|
|Request logging|Exact state per request|Observability system (LangSmith, etc.)|

The key insight: **Git alone is not enough.** Code is just one component. You need versioning for prompts, configuration, and indexes — and you need request-level logging to tie them all together.

---

## Summary

|Traditional Software|AI Application|
|---|---|
|Code → Behavior|Code + Prompts + Model + Config + Index → Behavior|
|Deterministic|Probabilistic|
|You control all components|Provider controls model updates|
|Git captures everything|Git captures code only|
|"What version?" = one answer|"What version?" = 5+ answers|

**The bottom line:** If you can't reproduce a past response, you can't debug it, audit it, or roll it back. Versioning isn't optional — it's infrastructure.

---

## What's Next

- **Note 2:** Model Abstraction Layer — how to decouple your code from specific models
- **Note 3:** Prompt Versioning — storage strategies and the Prompt Registry pattern
- **Note 4:** Embedding Migration — blue-green deployment for vector indexes
- **Note 5:** A/B Testing and Shadow Mode — safely testing new models in production