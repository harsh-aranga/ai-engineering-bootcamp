# Query Expansion: Casting a Wider Net

## The Core Problem

Your user types:

> "climate change effects"

Your documents contain:

> "global warming impacts on ecosystems" "environmental temperature rise consequences"  
> "anthropogenic heating outcomes"

All three documents are relevant. But with pure keyword matching (BM25), you miss them entirely — no overlapping terms. With embedding similarity, you might catch one or two, but the vocabulary gap still hurts your scores.

Query expansion solves this by adding related terms _before_ retrieval:

```
Original: "climate change effects"
Expanded: "climate change effects" OR "global warming impacts" OR 
          "environmental temperature consequences" OR "heating outcomes"
```

Now you're searching with multiple phrasings. Your net is wider. Recall goes up.

---

## How Query Expansion Differs from HyDE

Both techniques modify the query before retrieval, but they work differently:

|Aspect|HyDE|Query Expansion|
|---|---|---|
|**What it generates**|A hypothetical answer paragraph|Additional query terms/variations|
|**What gets embedded**|The hypothetical document|Original query + expanded terms (separately or combined)|
|**Best for**|Dense retrieval (embeddings)|BM25/keyword search (primarily)|
|**Mechanism**|Document-to-document similarity|Multiple keyword/phrase coverage|
|**Output**|Single embedding|Multiple queries OR enriched single query|

Query expansion is especially powerful for **BM25/keyword retrieval** where exact term matching matters. HyDE is designed for **dense retrieval** where semantic similarity matters.

In hybrid search (BM25 + dense), query expansion helps the BM25 side while HyDE helps the dense side. They're complementary.

---

## Types of Query Expansion

### 1. Synonym Expansion

Add words with the same meaning:

```
"fix" → "fix", "repair", "resolve", "troubleshoot"
"fast" → "fast", "quick", "rapid", "speedy"
"error" → "error", "bug", "issue", "problem", "failure"
```

**Sources for synonyms:**

- **WordNet**: Classic linguistic database
- **Domain-specific dictionaries**: Medical, legal, technical glossaries
- **Embedding similarity**: Find terms with similar vectors

### 2. Acronym/Abbreviation Expansion

Expand abbreviations to full forms (or vice versa):

```
"ML" → "ML", "machine learning"
"PTO" → "PTO", "paid time off"
"SLA" → "SLA", "service level agreement"
"AWS" → "AWS", "Amazon Web Services"
```

This is critical for enterprise RAG where internal acronyms are everywhere.

### 3. Related Concept Expansion

Add semantically related terms that aren't synonyms:

```
"solar energy" → "solar energy", "photovoltaic", "renewable power", "solar panels"
"database performance" → "database performance", "query optimization", "indexing", "slow queries"
```

### 4. LLM-Based Expansion

Use an LLM to generate expansions contextually:

```
Original: "how to make API faster"
LLM generates: "API performance optimization", "reduce API latency", 
               "API response time improvement", "caching strategies"
```

This is the most flexible approach — the LLM understands context and can generate domain-relevant expansions.

---

## Implementation: LLM-Based Query Expansion

Here's a minimal implementation without framework dependencies:

```python
from openai import OpenAI

client = OpenAI()


def expand_query_llm(
    query: str,
    n_expansions: int = 3,
    model: str = "gpt-4o-mini"
) -> list[str]:
    """
    Use an LLM to generate query expansions.
    Returns a list of expanded queries including the original.
    """
    prompt = f"""You are a search query expansion assistant.

Given the following search query, generate {n_expansions} alternative phrasings 
that would help find relevant documents. Include:
- Synonyms for key terms
- Related technical terms
- Different ways to phrase the same question

Original query: {query}

Return ONLY the expanded queries, one per line. Do not include numbering or explanations.
Do not repeat the original query."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200
    )
    
    expansions = response.choices[0].message.content.strip().split("\n")
    expansions = [q.strip() for q in expansions if q.strip()]
    
    # Always include the original query
    return [query] + expansions


# Example usage
query = "how to fix slow database queries"
expanded = expand_query_llm(query, n_expansions=3)

for q in expanded:
    print(f"  - {q}")
```

Output:

```
  - how to fix slow database queries
  - database query optimization techniques
  - improve SQL query performance
  - troubleshooting slow database response times
```

---

## Implementation: Synonym-Based Expansion (No LLM)

For high-throughput systems where LLM latency is unacceptable, use pre-built synonym mappings:

```python
from typing import Optional

# Domain-specific synonym dictionary
SYNONYMS = {
    "fix": ["repair", "resolve", "troubleshoot", "debug"],
    "fast": ["quick", "rapid", "speedy", "performant"],
    "slow": ["sluggish", "lagging", "delayed", "poor performance"],
    "error": ["bug", "issue", "problem", "failure", "exception"],
    "database": ["db", "datastore", "data store"],
    "api": ["endpoint", "service", "interface"],
    "deploy": ["release", "ship", "push", "publish"],
    # Add your domain-specific terms here
}

# Acronym expansions
ACRONYMS = {
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "api": "application programming interface",
    "db": "database",
    "sql": "structured query language",
    "pto": "paid time off",
    "sla": "service level agreement",
    # Add your company-specific acronyms
}


def expand_query_synonyms(query: str) -> list[str]:
    """
    Expand query using pre-built synonym dictionary.
    Fast, no LLM call required.
    """
    words = query.lower().split()
    expanded_queries = [query]  # Always include original
    
    for word in words:
        # Check synonyms
        if word in SYNONYMS:
            for synonym in SYNONYMS[word]:
                expanded = query.lower().replace(word, synonym)
                if expanded not in expanded_queries:
                    expanded_queries.append(expanded)
        
        # Check acronyms
        if word in ACRONYMS:
            expanded = query.lower().replace(word, ACRONYMS[word])
            if expanded not in expanded_queries:
                expanded_queries.append(expanded)
    
    return expanded_queries


# Example
query = "how to fix slow api"
expanded = expand_query_synonyms(query)
for q in expanded:
    print(f"  - {q}")
```

Output:

```
  - how to fix slow api
  - how to repair slow api
  - how to resolve slow api
  - how to troubleshoot slow api
  - how to debug slow api
  - how to fix sluggish api
  - how to fix lagging api
  - how to fix slow application programming interface
```

---

## Using Expanded Queries for Retrieval

Once you have multiple queries, you need to retrieve and combine results. Two main strategies:

### Strategy 1: Union with Deduplication

Retrieve for each query, union the results, deduplicate:

```python
def retrieve_with_expansion(
    query: str,
    retriever,  # Your retrieval function
    top_k: int = 5,
    expand_fn=expand_query_llm
) -> list[dict]:
    """
    Retrieve using expanded queries, deduplicate results.
    """
    expanded_queries = expand_fn(query)
    
    all_results = []
    seen_ids = set()
    
    for exp_query in expanded_queries:
        results = retriever.retrieve(exp_query, top_k=top_k)
        for result in results:
            doc_id = result.get("id") or hash(result.get("content"))
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_results.append(result)
    
    # Sort by score and return top-k
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_results[:top_k]
```

### Strategy 2: Reciprocal Rank Fusion (RRF)

A smarter combination that weights results by their rank across queries:

```python
def reciprocal_rank_fusion(
    results_lists: list[list[dict]],
    k: int = 60  # RRF constant, typically 60
) -> list[dict]:
    """
    Combine multiple result lists using Reciprocal Rank Fusion.
    
    RRF score = sum(1 / (k + rank)) across all result lists
    
    This gives higher scores to documents that appear highly ranked
    across multiple queries.
    """
    doc_scores = {}  # doc_id -> cumulative RRF score
    doc_content = {}  # doc_id -> document content
    
    for results in results_lists:
        for rank, doc in enumerate(results):
            doc_id = doc.get("id") or hash(doc.get("content"))
            rrf_score = 1.0 / (k + rank + 1)  # +1 because rank is 0-indexed
            
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + rrf_score
            doc_content[doc_id] = doc
    
    # Sort by RRF score
    sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Return documents with their RRF scores
    return [
        {**doc_content[doc_id], "rrf_score": score}
        for doc_id, score in sorted_docs
    ]


def retrieve_with_rrf(
    query: str,
    retriever,
    top_k: int = 5,
    retrieval_k: int = 10,  # Retrieve more per query, then fuse
    expand_fn=expand_query_llm
) -> list[dict]:
    """
    Retrieve using expanded queries, combine with RRF.
    """
    expanded_queries = expand_fn(query)
    
    # Retrieve for each expanded query
    all_results = []
    for exp_query in expanded_queries:
        results = retriever.retrieve(exp_query, top_k=retrieval_k)
        all_results.append(results)
    
    # Fuse with RRF
    fused = reciprocal_rank_fusion(all_results)
    
    return fused[:top_k]
```

RRF is the foundation of **RAG-Fusion**, a popular technique that combines query expansion with rank fusion.

---

## The Query Drift Problem

Query expansion can backfire. Adding too many terms — or the wrong terms — can pull in irrelevant results:

```
Original: "python programming"
Naive expansion: "python programming", "python snake", "programming languages"
```

Now you're retrieving documents about snakes.

```
Original: "bank account"
Naive expansion: "bank account", "river bank", "financial institution"
```

Now you're retrieving geography documents.

### Mitigations

**1. Context-Aware Expansion**

Use the full query context when expanding:

```python
def expand_query_contextual(query: str, model: str = "gpt-4o-mini") -> list[str]:
    """
    Context-aware expansion that avoids polysemy issues.
    """
    prompt = f"""You are a search query expansion assistant.

Given the following search query, generate 3 alternative phrasings.
Be careful to maintain the ORIGINAL MEANING AND CONTEXT.
Do NOT add terms that could introduce ambiguity or different meanings.

For example:
- "python programming" should NOT expand to anything about snakes
- "bank account" should NOT expand to anything about rivers
- "apple support" should NOT expand to anything about fruit

Original query: {query}

Return ONLY the expanded queries, one per line."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,  # Lower temperature for more focused expansions
        max_tokens=150
    )
    
    expansions = response.choices[0].message.content.strip().split("\n")
    expansions = [q.strip() for q in expansions if q.strip()]
    
    return [query] + expansions
```

**2. Domain-Restricted Synonyms**

Only use synonyms from your domain's vocabulary:

```python
# Instead of a generic synonym dictionary,
# build one from YOUR document corpus
DOMAIN_SYNONYMS = {
    # Only terms that appear in your actual documents
    "authentication": ["auth", "login", "sign-in"],
    "authorization": ["permissions", "access control", "rbac"],
    # These are controlled, domain-specific mappings
}
```

**3. Expansion Validation**

Use a classifier or embedding check to validate expansions:

```python
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


def validate_expansions(
    original_query: str,
    expansions: list[str],
    embed_fn,
    similarity_threshold: float = 0.7
) -> list[str]:
    """
    Filter out expansions that drift too far from the original query.
    """
    original_embedding = np.array(embed_fn(original_query)).reshape(1, -1)
    
    valid_expansions = [original_query]
    
    for expansion in expansions:
        if expansion == original_query:
            continue
        
        exp_embedding = np.array(embed_fn(expansion)).reshape(1, -1)
        similarity = cosine_similarity(original_embedding, exp_embedding)[0][0]
        
        if similarity >= similarity_threshold:
            valid_expansions.append(expansion)
        else:
            print(f"Filtered out '{expansion}' (similarity: {similarity:.3f})")
    
    return valid_expansions
```

---

## When to Use Query Expansion

### Best For:

**1. BM25/Keyword Search**

Query expansion directly addresses BM25's weakness: exact term matching. If your docs say "troubleshoot" but the user says "fix," BM25 misses it. Expansion bridges this gap.

**2. Short Queries**

A 2-word query has limited semantic content. Expansion enriches it:

```
"api latency" → "api latency", "api response time", "slow api calls", 
                "api performance issues"
```

**3. Domain-Specific Vocabulary**

When users don't know your domain's terminology:

```
User: "change my password"
Expanded: "change my password", "reset credentials", "update authentication"
```

**4. Hybrid Search Systems**

In BM25 + dense retrieval, expansion helps the BM25 side while embeddings handle semantic similarity on the dense side.

### Avoid When:

**1. Already-Specific Queries**

```
"How do I configure the OIDC callback URL in version 2.3.1"
```

This query is already specific. Expansion adds noise, not signal.

**2. Pure Dense Retrieval**

If you're only using embedding similarity with no BM25, expansion helps less. The embedding model already captures semantic similarity. (Though expansion can still help by creating multiple embedding queries.)

**3. High-Volume, Latency-Sensitive Systems**

LLM-based expansion adds 200-500ms. For autocomplete or real-time search, use pre-built synonym dictionaries instead.

---

## Query Expansion vs. Multi-Query

These terms are sometimes used interchangeably, but there's a distinction:

|Aspect|Query Expansion|Multi-Query|
|---|---|---|
|**Focus**|Add terms to enrich the query|Generate different perspectives on the query|
|**Output**|Enriched single query OR multiple term variations|Multiple distinct queries|
|**Goal**|Cover vocabulary gaps (synonyms, acronyms)|Cover conceptual gaps (different angles)|
|**Example**|"fix api" → "fix api", "repair api", "resolve api"|"ML best practices" → "machine learning tips", "ML guidelines", "AI development standards"|

In practice, they overlap and are often combined. The Multi-Query note (next) will cover generating distinct perspectives.

---

## Putting It Together: Expansion Pipeline

Here's a complete pipeline that combines expansion strategies:

```python
from openai import OpenAI
from typing import Callable

client = OpenAI()


class QueryExpander:
    def __init__(
        self,
        use_llm: bool = True,
        use_synonyms: bool = True,
        use_acronyms: bool = True,
        synonym_dict: dict = None,
        acronym_dict: dict = None,
        llm_model: str = "gpt-4o-mini"
    ):
        self.use_llm = use_llm
        self.use_synonyms = use_synonyms
        self.use_acronyms = use_acronyms
        self.synonym_dict = synonym_dict or {}
        self.acronym_dict = acronym_dict or {}
        self.llm_model = llm_model
    
    def expand(self, query: str, max_expansions: int = 5) -> list[str]:
        """
        Expand query using all configured strategies.
        """
        expansions = {query}  # Use set for deduplication
        
        # Dictionary-based expansion (fast)
        if self.use_synonyms:
            expansions.update(self._expand_synonyms(query))
        
        if self.use_acronyms:
            expansions.update(self._expand_acronyms(query))
        
        # LLM-based expansion (slower, but more contextual)
        if self.use_llm and len(expansions) < max_expansions:
            remaining = max_expansions - len(expansions)
            llm_expansions = self._expand_llm(query, n=remaining)
            expansions.update(llm_expansions)
        
        # Convert to list, ensure original is first
        result = [query] + [q for q in expansions if q != query]
        return result[:max_expansions]
    
    def _expand_synonyms(self, query: str) -> set[str]:
        """Expand using synonym dictionary."""
        expanded = set()
        words = query.lower().split()
        
        for word in words:
            if word in self.synonym_dict:
                for synonym in self.synonym_dict[word]:
                    expanded.add(query.lower().replace(word, synonym))
        
        return expanded
    
    def _expand_acronyms(self, query: str) -> set[str]:
        """Expand acronyms to full forms."""
        expanded = set()
        words = query.lower().split()
        
        for word in words:
            if word in self.acronym_dict:
                full_form = self.acronym_dict[word]
                expanded.add(query.lower().replace(word, full_form))
        
        return expanded
    
    def _expand_llm(self, query: str, n: int = 3) -> set[str]:
        """Use LLM to generate contextual expansions."""
        prompt = f"""Generate {n} alternative phrasings for this search query.
Maintain the original meaning. Include synonyms and related technical terms.

Query: {query}

Return only the alternative queries, one per line."""

        try:
            response = client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=150
            )
            
            lines = response.choices[0].message.content.strip().split("\n")
            return {line.strip() for line in lines if line.strip()}
        
        except Exception as e:
            print(f"LLM expansion failed: {e}")
            return set()


# Usage
expander = QueryExpander(
    use_llm=True,
    use_synonyms=True,
    use_acronyms=True,
    synonym_dict={
        "fix": ["repair", "resolve", "troubleshoot"],
        "slow": ["sluggish", "lagging", "poor performance"],
    },
    acronym_dict={
        "api": "application programming interface",
        "db": "database",
    }
)

query = "how to fix slow api"
expanded = expander.expand(query, max_expansions=5)

print("Expanded queries:")
for q in expanded:
    print(f"  - {q}")
```

---

## Key Takeaways

1. **Query expansion adds related terms before retrieval** — synonyms, acronyms, and contextually related phrases that increase your chances of matching relevant documents.
    
2. **Expansion is especially powerful for BM25/keyword search** where exact term matching matters. It directly addresses vocabulary mismatch.
    
3. **Two main implementation approaches:** dictionary-based (fast, no LLM, limited coverage) and LLM-based (slower, contextual, flexible).
    
4. **Query drift is the main risk** — adding wrong terms can pull in irrelevant results. Mitigate with context-aware prompts, domain-restricted dictionaries, and similarity validation.
    
5. **Use Reciprocal Rank Fusion (RRF)** to combine results from multiple expanded queries intelligently.
    
6. **Expansion complements HyDE** — HyDE helps dense retrieval, expansion helps keyword retrieval. In hybrid search, use both.
    
7. **Consider your latency budget** — LLM expansion adds 200-500ms. For real-time applications, pre-built dictionaries are faster.