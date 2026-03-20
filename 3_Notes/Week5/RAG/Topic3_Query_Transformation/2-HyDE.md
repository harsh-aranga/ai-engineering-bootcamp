# HyDE (Hypothetical Document Embeddings)

## The Core Insight

When a user asks "how do I fix login problems," they're writing a _question_. Your documentation contains _answers_: "To resolve authentication failures, verify credentials, check session tokens, and review the authentication middleware configuration."

Questions and answers live in different regions of embedding space. The embedding model tries to bridge this gap, but it's fundamentally comparing apples to oranges.

HyDE's insight: **What if we converted the question into an answer first, then searched for similar answers?**

Instead of:

```
Question embedding → search → find similar documents
```

HyDE does:

```
Question → LLM generates hypothetical answer → embed the answer → search → find similar documents
```

Now you're comparing answer-to-answer. Document-to-document. The semantic similarity is much stronger.

---

## How HyDE Works

### Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         HyDE Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User Query                                                  │
│     "how do I fix login problems"                               │
│              │                                                  │
│              ▼                                                  │
│  2. LLM Generates Hypothetical Document                         │
│     "To resolve login issues, first verify that the user's     │
│      credentials are correct. Check if the session has         │
│      expired. Review the authentication middleware for         │
│      any configuration errors. Ensure the database             │
│      connection is active and user records exist..."           │
│              │                                                  │
│              ▼                                                  │
│  3. Embed the Hypothetical Document                             │
│     [0.023, -0.156, 0.089, ...]  (dense vector)                │
│              │                                                  │
│              ▼                                                  │
│  4. Vector Search Against Document Store                        │
│     Find chunks similar to the hypothetical answer             │
│              │                                                  │
│              ▼                                                  │
│  5. Return Retrieved Documents                                  │
│     Actual documentation about authentication troubleshooting  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why the Hypothetical Document Works

The hypothetical answer doesn't need to be _correct_. It needs to be _stylistically similar_ to your actual documents.

The LLM generates text that:

- Uses formal, documentation-style language
- Contains relevant terminology ("authentication," "credentials," "session")
- Has the structure and length of a real document chunk
- Lives in "document space" rather than "query space"

The embedding model then converts this hypothetical document into a dense vector. This is where something useful happens: embedding is a *lossy* process. A 200-word paragraph gets reduced to 1536 numbers — the model can't preserve every detail, so it keeps the topical/semantic essence and discards specifics.

This lossy nature is why HyDE tolerates hallucination. If the LLM says "check Redis on port 6380" but your docs say "verify Memcached on port 11211," those specific details get compressed away. What survives in both embeddings is the semantic neighborhood: "session storage + authentication + troubleshooting." The vectors land near each other despite the factual mismatch.

The original HyDE paper calls the embedding model a "lossy compressor" — and that compression is a feature, not a bug.

---

## Minimal Implementation (No Framework)

Here's HyDE implemented from scratch using OpenAI's API:

```python
from openai import OpenAI
import numpy as np

client = OpenAI()

def generate_hypothetical_document(query: str, model: str = "gpt-4o-mini") -> str:
    """
    Generate a hypothetical answer to the query.
    This answer doesn't need to be correct — it needs to be
    stylistically similar to your document corpus.
    """
    prompt = f"""You are an expert technical writer. 
Given the following question, write a short paragraph that would answer it.
Write as if this is from official documentation — factual, clear, and direct.
Do not say "I don't know" or ask clarifying questions. Just write the answer.

Question: {query}

Answer:"""
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,  # Some creativity helps generate diverse content
        max_tokens=200
    )
    
    return response.choices[0].message.content


def embed_text(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Embed text using OpenAI's embedding model."""
    response = client.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding


def hyde_embed(query: str) -> list[float]:
    """
    HyDE: Generate hypothetical document, then embed that
    instead of embedding the query directly.
    """
    hypothetical_doc = generate_hypothetical_document(query)
    return embed_text(hypothetical_doc)


# Usage comparison
query = "how do I fix login problems"

# Traditional: embed the query
traditional_embedding = embed_text(query)

# HyDE: embed a hypothetical answer
hyde_embedding = hyde_embed(query)

# Both are now dense vectors you can use for similarity search
print(f"Query embedding dimensions: {len(traditional_embedding)}")
print(f"HyDE embedding dimensions: {len(hyde_embedding)}")
```

### Using the HyDE Embedding for Retrieval

```python
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def retrieve_with_hyde(
    query: str,
    document_embeddings: np.ndarray,  # Pre-computed embeddings of your chunks
    documents: list[str],              # The actual chunk texts
    top_k: int = 5
) -> list[tuple[str, float]]:
    """
    Retrieve documents using HyDE.
    """
    # Generate and embed hypothetical document
    hyde_embedding = np.array(hyde_embed(query)).reshape(1, -1)
    
    # Compute similarities
    similarities = cosine_similarity(hyde_embedding, document_embeddings)[0]
    
    # Get top-k indices
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    
    # Return documents with scores
    results = [(documents[i], similarities[i]) for i in top_indices]
    return results


# Compare retrieval results
def compare_retrieval(query: str, document_embeddings: np.ndarray, documents: list[str]):
    """Compare traditional vs HyDE retrieval."""
    
    # Traditional retrieval
    query_embedding = np.array(embed_text(query)).reshape(1, -1)
    trad_similarities = cosine_similarity(query_embedding, document_embeddings)[0]
    trad_top = np.argsort(trad_similarities)[-3:][::-1]
    
    # HyDE retrieval
    hyde_results = retrieve_with_hyde(query, document_embeddings, documents, top_k=3)
    
    print("=== Traditional Retrieval ===")
    for idx in trad_top:
        print(f"  [{trad_similarities[idx]:.3f}] {documents[idx][:100]}...")
    
    print("\n=== HyDE Retrieval ===")
    for doc, score in hyde_results:
        print(f"  [{score:.3f}] {doc[:100]}...")
```

---

## When HyDE Helps

HyDE is most effective in these scenarios:

### 1. Short, Keyword-Style Queries

```
User: "PTO policy"
```

A 2-word query has very little semantic content. The embedding is sparse and generic. HyDE expands this into a rich paragraph about paid time off policies, vacation accrual, and leave procedures — giving the embedding model much more to work with.

### 2. Casual Language vs. Formal Documentation

```
User: "what's the deal with refunds"
Docs: "Return Policy and Reimbursement Procedures"
```

The user's casual phrasing doesn't match the formal documentation language. HyDE generates a formal answer that uses the vocabulary actually present in your docs.

### 3. Questions Where User Doesn't Know the Terminology

```
User: "my app keeps forgetting who I am"
Docs: "Session Management and Authentication Token Expiration"
```

The user doesn't know to say "session" or "authentication token." HyDE's generated answer likely _will_ use these terms, bridging the vocabulary gap.

### 4. Zero-Shot / New Domains

When you have no training data for query-document pairs, HyDE provides a way to bootstrap retrieval quality using the LLM's general knowledge.

---

## When HyDE Hurts

HyDE is not always the right choice. It can actively harm retrieval in these cases:

### 1. Domain-Specific Knowledge the LLM Lacks

```
User: "what's our SLA escalation process"
```

If the LLM doesn't know your company's specific SLA process, it will hallucinate a generic one. That generic answer might be _semantically distant_ from your actual internal documentation, leading to worse retrieval than the original query.

**Symptom:** HyDE retrieves generic content instead of your company-specific docs.

### 2. Highly Specific / Factual Queries

```
User: "what is the maximum file size for uploads in v2.3.1"
```

The LLM might guess "10MB" or "100MB." If your docs say "25MB," the hypothetical answer is now searching for the wrong number.

**Symptom:** HyDE misses exact matches that traditional retrieval would find.

### 3. Queries Already Well-Formed

```
User: "Authentication troubleshooting steps for credential verification failures"
```

This query is _already_ written in document language. Generating a hypothetical answer adds latency without improving retrieval.

**Symptom:** Same results as traditional retrieval, but slower.

### 4. When the LLM Confidently Hallucinates

The most dangerous case: the LLM generates a plausible-sounding but completely wrong answer. You're now searching for content that matches the wrong answer.

**Example:**

```
User: "what database does our analytics service use"
LLM hallucinates: "The analytics service uses PostgreSQL for data storage..."
Reality: Your analytics service uses ClickHouse.
```

The HyDE embedding now points toward PostgreSQL documentation, missing the ClickHouse content entirely.

---

## Mitigating HyDE's Risks

### 1. Hybrid Approach: Try Traditional First, Fall Back to HyDE

```python
def adaptive_retrieval(
    query: str,
    document_embeddings: np.ndarray,
    documents: list[str],
    confidence_threshold: float = 0.75,
    top_k: int = 5
) -> list[tuple[str, float]]:
    """
    Try traditional retrieval first.
    If top result confidence is low, fall back to HyDE.
    """
    # Traditional retrieval
    query_embedding = np.array(embed_text(query)).reshape(1, -1)
    similarities = cosine_similarity(query_embedding, document_embeddings)[0]
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    
    top_score = similarities[top_indices[0]]
    
    # If confident, return traditional results
    if top_score >= confidence_threshold:
        return [(documents[i], similarities[i]) for i in top_indices]
    
    # Otherwise, try HyDE
    print(f"Low confidence ({top_score:.3f}), falling back to HyDE...")
    return retrieve_with_hyde(query, document_embeddings, documents, top_k)
```

This saves the LLM call cost for queries that traditional retrieval handles well, and only invokes HyDE when needed.

### 2. Post-Retrieval Reranking

Even if HyDE retrieves some irrelevant chunks due to hallucination, a cross-encoder reranker can filter them out:

```python
def hyde_with_reranking(
    query: str,
    document_embeddings: np.ndarray,
    documents: list[str],
    reranker,  # A cross-encoder model
    retrieve_k: int = 20,
    final_k: int = 5
) -> list[tuple[str, float]]:
    """
    Use HyDE for broad recall, then rerank with the original query.
    """
    # HyDE retrieval (cast a wide net)
    candidates = retrieve_with_hyde(query, document_embeddings, documents, top_k=retrieve_k)
    
    # Rerank using the ORIGINAL query (not the hypothetical doc)
    # This grounds the final selection in what the user actually asked
    candidate_docs = [doc for doc, _ in candidates]
    pairs = [(query, doc) for doc in candidate_docs]
    
    rerank_scores = reranker.predict(pairs)
    
    # Sort by rerank score and return top-k
    ranked = sorted(zip(candidate_docs, rerank_scores), key=lambda x: x[1], reverse=True)
    return ranked[:final_k]
```

The key insight: use HyDE for recall (finding candidates), but rerank with the _original query_ for precision.

### 3. Domain-Conditioned Prompts

Generic HyDE prompts produce generic answers. Domain-specific prompts produce domain-relevant answers:

```python
def generate_hypothetical_document_domain(
    query: str,
    domain_context: str,
    model: str = "gpt-4o-mini"
) -> str:
    """
    Generate hypothetical document with domain conditioning.
    """
    prompt = f"""You are a technical writer for {domain_context}.

Given the following question from a user of this system, write a short paragraph 
that would answer it. Use terminology and style consistent with {domain_context} documentation.

Question: {query}

Answer:"""
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200
    )
    
    return response.choices[0].message.content


# Usage
hypothetical = generate_hypothetical_document_domain(
    query="how do I escalate an SLA breach",
    domain_context="Acme Corp's internal IT support ticketing system"
)
```

### 4. Multiple Hypothetical Documents

The original HyDE paper generates multiple hypothetical documents and averages their embeddings:

```python
def hyde_multi_embed(query: str, n_hypotheticals: int = 5) -> list[float]:
    """
    Generate multiple hypothetical documents and average their embeddings.
    Reduces the impact of any single hallucination.
    """
    hypotheticals = [generate_hypothetical_document(query) for _ in range(n_hypotheticals)]
    embeddings = [embed_text(h) for h in hypotheticals]
    
    # Average the embeddings
    avg_embedding = np.mean(embeddings, axis=0)
    return avg_embedding.tolist()
```

This "ensemble" approach smooths out individual hallucinations, but at 5x the LLM and embedding cost.

---

## The Latency and Cost Reality

HyDE adds an LLM call _before_ retrieval. Here's what that means in practice:

|Component|Latency|Cost (per query)|
|---|---|---|
|Traditional embedding|~50ms|~$0.00001|
|HyDE LLM call|~200-500ms|~$0.0002 (gpt-4o-mini)|
|HyDE embedding|~50ms|~$0.00001|
|**Total HyDE overhead**|**~250-550ms**|**~$0.0002**|

For a system handling 10,000 queries/day:

- Traditional: ~$0.10/day in embedding costs
- HyDE: ~$2.00/day in LLM + embedding costs

The cost is manageable, but the **latency** is the killer. Adding 300ms to every query is significant for real-time applications.

### Optimization Strategies

**1. Cache hypothetical documents for common queries:**

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_hyde_embed(query: str) -> tuple[float, ...]:
    """Cache HyDE embeddings for repeated queries."""
    return tuple(hyde_embed(query))
```

**2. Use a smaller/faster model for hypothesis generation:**

```python
# gpt-4o-mini is fast and cheap
# For even faster: consider a local model like Llama-3.2-3B via Ollama
```

**3. Parallelize when using multi-hypothetical:**

```python
import asyncio

async def hyde_multi_embed_async(query: str, n: int = 5) -> list[float]:
    """Generate hypotheticals in parallel."""
    async def generate_one():
        return await asyncio.to_thread(generate_hypothetical_document, query)
    
    hypotheticals = await asyncio.gather(*[generate_one() for _ in range(n)])
    embeddings = [embed_text(h) for h in hypotheticals]
    return np.mean(embeddings, axis=0).tolist()
```

---

## Using LangChain's HyDE Implementation

LangChain provides a `HypotheticalDocumentEmbedder` that wraps this pattern:

```python
from langchain.embeddings import HypotheticalDocumentEmbedder, OpenAIEmbeddings
from langchain.llms import OpenAI

# Create base embeddings
base_embeddings = OpenAIEmbeddings()

# Create HyDE embeddings
hyde_embeddings = HypotheticalDocumentEmbedder.from_llm(
    llm=OpenAI(temperature=0.7),
    base_embeddings=base_embeddings,
    prompt_key="web_search"  # Built-in prompt templates
)

# Use like any other embeddings
query = "how do I fix login problems"
embedding = hyde_embeddings.embed_query(query)
```

**Built-in prompt keys:** `web_search`, `sci_fact`, `arguana`, `trec_covid`, `fiqa`, `dbpedia_entity`, `trec_news`, `mr_tydi`

You can also provide a custom prompt:

```python
from langchain.prompts import PromptTemplate

custom_prompt = PromptTemplate(
    input_variables=["question"],
    template="""You are an expert in enterprise software.
Given this question, write a documentation paragraph that would answer it.

Question: {question}
Documentation:"""
)

hyde_embeddings = HypotheticalDocumentEmbedder.from_llm(
    llm=OpenAI(temperature=0.7),
    base_embeddings=base_embeddings,
    prompt=custom_prompt
)
```

---

## Decision Framework: Should You Use HyDE?

```
┌─────────────────────────────────────────────────────────────────┐
│                    Should You Use HyDE?                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Is your retrieval quality already good?                        │
│  ├── YES → Don't add HyDE complexity                           │
│  └── NO ↓                                                       │
│                                                                 │
│  Are queries typically short/casual?                            │
│  ├── YES → HyDE likely helps                                   │
│  └── NO ↓                                                       │
│                                                                 │
│  Does the LLM know your domain well?                            │
│  ├── YES → HyDE likely helps                                   │
│  └── NO → HyDE may hallucinate wrong direction                 │
│                                                                 │
│  Can you tolerate 200-500ms extra latency?                      │
│  ├── YES → Consider HyDE                                       │
│  └── NO → Use adaptive/conditional HyDE only                   │
│                                                                 │
│  Do you have reranking in your pipeline?                        │
│  ├── YES → HyDE + reranking is a strong combo                  │
│  └── NO → HyDE alone may retrieve irrelevant content           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **HyDE bridges the query-document gap** by converting questions into answer-style text before embedding. You're comparing document-to-document instead of question-to-document.
    
2. **The hypothetical answer doesn't need to be correct** — it needs to be stylistically similar to your documents. The embedding acts as a lossy compressor that captures topical relevance while filtering out hallucinated details.
    
3. **HyDE shines for short, casual, or vocabulary-mismatched queries** where the user doesn't use the same language as the documentation.
    
4. **HyDE can hurt when the LLM lacks domain knowledge** and hallucinates answers that point retrieval in the wrong direction.
    
5. **Mitigate risks with:** adaptive retrieval (try traditional first), reranking (ground final selection in original query), domain-conditioned prompts, and multi-hypothetical averaging.
    
6. **The cost is latency** — 200-500ms per query for the LLM call. For high-throughput systems, use HyDE selectively, not universally.
    
7. **Combine HyDE with reranking** for the best results: HyDE for broad recall, reranking with the original query for precision.