# Query Rewriting: Translating User Language to Document Language

## The Core Problem

Query expansion adds more terms. Query rewriting _transforms_ the query entirely.

Consider this user query:

> "my app keeps forgetting who I am after a few minutes"

Your documentation says:

> "Session timeout configuration and authentication token expiration policies"

The user doesn't know the words "session," "timeout," "authentication," or "token." They're describing the _symptom_. Your docs describe the _mechanism_.

Query rewriting bridges this gap by having an LLM translate the casual, symptom-based query into formal, mechanism-based language:

```
Original:  "my app keeps forgetting who I am after a few minutes"
Rewritten: "session timeout configuration authentication token expiration"
```

Now your retrieval has vocabulary overlap with the actual documents.

---

## Query Rewriting vs. Query Expansion vs. HyDE

These three techniques are often confused. Here's how they differ:

|Technique|What It Does|Output|Best For|
|---|---|---|---|
|**Expansion**|Adds synonyms and related terms|Multiple queries or enriched single query|BM25, vocabulary coverage|
|**Rewriting**|Transforms query into document language|Single rewritten query|Casual→formal translation|
|**HyDE**|Generates hypothetical answer|Embedding of hypothetical doc|Dense retrieval, semantic matching|

**Key distinction:**

- Expansion _adds_ to the query
- Rewriting _replaces_ the query
- HyDE _answers_ the query (then embeds that)

In practice, you might combine them: rewrite first, then expand the rewritten query.

---

## When Query Rewriting Helps

### 1. Casual/Conversational Queries → Formal Documentation

```
User: "what's the deal with our refund thing"
Rewritten: "refund policy terms and conditions return procedures"

User: "how do I make the dashboard load faster"
Rewritten: "dashboard performance optimization loading time improvement"

User: "the login thingy isn't working"
Rewritten: "authentication login failure troubleshooting sign-in errors"
```

### 2. Symptom Description → Technical Root Cause

```
User: "my code runs fine locally but breaks in production"
Rewritten: "environment configuration differences local production deployment issues"

User: "the page just sits there spinning forever"
Rewritten: "infinite loading request timeout network latency server response"

User: "numbers look wrong in my reports"
Rewritten: "data accuracy calculation errors report discrepancy numerical precision"
```

### 3. Vague/Underspecified Queries → Specific Queries

```
User: "PTO"
Rewritten: "paid time off policy vacation leave accrual request procedures"

User: "API limits"
Rewritten: "API rate limiting request quota throttling limits per minute"

User: "that error everyone's getting"
Rewritten: "common error messages frequent issues known bugs troubleshooting"
```

### 4. Multi-Turn Context Integration

In a conversation, the current query often lacks context:

```
User (turn 1): "How do I set up SSO?"
Assistant: [provides SSO setup guide]
User (turn 2): "what about for mobile?"

Standalone, "what about for mobile?" is useless for retrieval.
Rewritten with context: "SSO single sign-on configuration mobile app iOS Android"
```

---

## Implementation: Basic Query Rewriting

Here's a minimal implementation:

```python
from openai import OpenAI

client = OpenAI()


def rewrite_query(
    query: str,
    model: str = "gpt-4o-mini"
) -> str:
    """
    Rewrite a casual user query into retrieval-optimized language.
    """
    prompt = f"""You are a search query optimizer. 

Rewrite the following user query to improve document retrieval.
Transform casual language into formal, technical terms.
Transform symptom descriptions into root cause terminology.
Expand abbreviations into full forms.
Keep the rewritten query concise (under 20 words).

Do NOT answer the query. Only rewrite it for better search.

Original query: {query}

Rewritten query:"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,  # Low temperature for consistent rewrites
        max_tokens=50
    )
    
    return response.choices[0].message.content.strip()


# Examples
queries = [
    "my app keeps forgetting who I am",
    "how do I make things faster",
    "that thing where you can't log in",
    "PTO",
]

for q in queries:
    rewritten = rewrite_query(q)
    print(f"Original:  {q}")
    print(f"Rewritten: {rewritten}")
    print()
```

Output:

```
Original:  my app keeps forgetting who I am
Rewritten: session persistence authentication token expiration user session management

Original:  how do I make things faster
Rewritten: performance optimization speed improvement latency reduction

Original:  that thing where you can't log in
Rewritten: authentication failure login error troubleshooting access denied

Original:  PTO
Rewritten: paid time off policy vacation leave request accrual procedures
```

---

## Implementation: Context-Aware Rewriting

For multi-turn conversations, include conversation history:

```python
def rewrite_query_with_context(
    query: str,
    conversation_history: list[dict],  # [{"role": "user", "content": "..."}, ...]
    model: str = "gpt-4o-mini"
) -> str:
    """
    Rewrite query using conversation context.
    """
    # Build context summary from recent turns
    recent_context = ""
    for msg in conversation_history[-4:]:  # Last 4 messages
        role = msg["role"]
        content = msg["content"][:200]  # Truncate long messages
        recent_context += f"{role}: {content}\n"
    
    prompt = f"""You are a search query optimizer.

Given the conversation context and the latest user query, rewrite the query 
to be self-contained and optimized for document retrieval.

Include relevant context from the conversation that the query refers to.
Transform casual language into formal, technical terms.
Keep the rewritten query concise (under 25 words).

Conversation context:
{recent_context}

Latest query: {query}

Rewritten query (self-contained, search-optimized):"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=60
    )
    
    return response.choices[0].message.content.strip()


# Example: multi-turn conversation
history = [
    {"role": "user", "content": "How do I set up SSO for our app?"},
    {"role": "assistant", "content": "To set up SSO, you'll need to configure your identity provider..."},
    {"role": "user", "content": "Got it. What about mobile?"},
]

rewritten = rewrite_query_with_context(
    query="What about mobile?",
    conversation_history=history
)

print(f"Original: What about mobile?")
print(f"Rewritten: {rewritten}")
```

Output:

```
Original: What about mobile?
Rewritten: SSO single sign-on configuration mobile application iOS Android setup identity provider
```

---

## Implementation: Domain-Conditioned Rewriting

Generic rewriting might miss your domain's vocabulary. Condition on your domain:

```python
def rewrite_query_domain(
    query: str,
    domain_description: str,
    sample_terms: list[str] = None,
    model: str = "gpt-4o-mini"
) -> str:
    """
    Rewrite query using domain-specific vocabulary.
    """
    terms_hint = ""
    if sample_terms:
        terms_hint = f"\nCommon terms in this domain: {', '.join(sample_terms)}"
    
    prompt = f"""You are a search query optimizer for {domain_description}.

Rewrite the following user query using terminology common in this domain.
Transform casual descriptions into domain-specific technical terms.
{terms_hint}

Keep the rewritten query concise (under 20 words).
Do NOT answer the query. Only rewrite it.

Original query: {query}

Rewritten query:"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=50
    )
    
    return response.choices[0].message.content.strip()


# Example: HR domain
rewritten = rewrite_query_domain(
    query="can I take friday off",
    domain_description="an HR policy knowledge base for Acme Corp",
    sample_terms=["PTO", "vacation accrual", "leave request", "time-off policy", "manager approval"]
)

print(f"Original: can I take friday off")
print(f"Rewritten: {rewritten}")

# Example: DevOps domain
rewritten = rewrite_query_domain(
    query="my deploy keeps failing",
    domain_description="a DevOps and CI/CD documentation system",
    sample_terms=["pipeline", "deployment", "CI/CD", "build failure", "rollback", "artifact"]
)

print(f"\nOriginal: my deploy keeps failing")
print(f"Rewritten: {rewritten}")
```

---

## The Rewrite-Retrieve-Read Framework

A influential paper (Ma et al., 2023) formalized this as the **Rewrite-Retrieve-Read** pipeline, replacing the traditional Retrieve-then-Read:

```
Traditional:  Query → Retrieve → Read (Generate)
Rewrite:      Query → Rewrite → Retrieve → Read (Generate)
```

The paper showed that even a simple LLM-based rewriter improves retrieval quality, and training a small rewriter model with reinforcement learning (using answer quality as reward) improves it further.

```
┌──────────────────────────────────────────────────────────────────┐
│                   Rewrite-Retrieve-Read Pipeline                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐     ┌──────────┐     ┌───────────┐     ┌─────────┐ │
│  │  User   │ ──► │ Rewriter │ ──► │ Retriever │ ──► │ Reader  │ │
│  │  Query  │     │  (LLM)   │     │ (Search)  │     │  (LLM)  │ │
│  └─────────┘     └──────────┘     └───────────┘     └─────────┘ │
│                                                                  │
│  "my app forgets  "session timeout   [Retrieved    "To fix this │
│   who I am"        auth token         Documents]    issue, go   │
│                    expiration"                      to Settings  │
│                                                     > Session..."│
└──────────────────────────────────────────────────────────────────┘
```

---

## When Rewriting Can Hurt

Rewriting isn't always beneficial:

### 1. Already Well-Formed Queries

```
User: "How do I configure OIDC callback URLs in version 2.3.1"
```

This is already specific and technical. Rewriting might:

- Remove important specifics ("version 2.3.1")
- Introduce generic terms that dilute precision
- Add latency for no benefit

### 2. Proper Nouns and Specific Identifiers

```
User: "What is Project Tempest?"
Rewritten (bad): "project management storm planning initiative"
```

The rewriter doesn't know "Project Tempest" is a proper noun. It hallucinates generic terms.

### 3. When the LLM Lacks Domain Knowledge

If your domain uses specific terminology the LLM doesn't know, it might rewrite _away_ from the right terms:

```
User: "how does RBAC work in our system"
Rewritten (bad): "role-based system functionality"  
```

The user knew "RBAC." The rewriter expanded it but lost the exact match that would have hit your docs.

---

## Mitigation Strategies

### 1. Preserve Key Terms

Instruct the rewriter to keep certain terms unchanged:

```python
def rewrite_preserving_terms(
    query: str,
    preserve_patterns: list[str] = None,  # Regex patterns to preserve
    model: str = "gpt-4o-mini"
) -> str:
    """
    Rewrite query while preserving specific terms.
    """
    preserve_instruction = ""
    if preserve_patterns:
        preserve_instruction = f"""
IMPORTANT: Keep these exact terms/patterns unchanged in your rewrite:
- Version numbers (e.g., "v2.3.1", "version 4")
- Product names in quotes
- All-caps acronyms (e.g., "RBAC", "SSO", "API")
- Names that start with capital letters
"""
    
    prompt = f"""You are a search query optimizer.

Rewrite the user query to improve document retrieval.
Transform casual language into formal terms.
Keep the rewritten query concise.
{preserve_instruction}

Original query: {query}

Rewritten query:"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=50
    )
    
    return response.choices[0].message.content.strip()


# Test
query = "how does RBAC work in Project Tempest v2.3"
rewritten = rewrite_preserving_terms(query)
print(f"Original:  {query}")
print(f"Rewritten: {rewritten}")
```

### 2. Use Both Original and Rewritten

Don't throw away the original. Search with both:

```python
def retrieve_with_rewrite(
    query: str,
    retriever,
    top_k: int = 5
) -> list[dict]:
    """
    Retrieve using both original and rewritten queries.
    """
    # Get rewritten query
    rewritten = rewrite_query(query)
    
    # Retrieve for both
    original_results = retriever.retrieve(query, top_k=top_k)
    rewritten_results = retriever.retrieve(rewritten, top_k=top_k)
    
    # Combine with RRF or simple union
    combined = reciprocal_rank_fusion([original_results, rewritten_results])
    
    return combined[:top_k]
```

This way, if the rewrite is bad, the original query still contributes.

### 3. Confidence-Based Rewriting

Only rewrite when the query seems to need it:

```python
def should_rewrite(query: str) -> bool:
    """
    Heuristics for whether a query needs rewriting.
    """
    # Short queries often need expansion/rewriting
    if len(query.split()) < 4:
        return True
    
    # Casual language indicators
    casual_patterns = [
        "thing", "stuff", "thingy", "whatever",
        "how do i", "what's the deal", "help me",
        "doesn't work", "keeps", "always", "never",
        "my", "our",  # Possessives often indicate context needed
    ]
    query_lower = query.lower()
    if any(pattern in query_lower for pattern in casual_patterns):
        return True
    
    # Already technical/specific - skip rewriting
    technical_indicators = [
        "configure", "parameter", "endpoint", "api",
        "version", "v1", "v2", "error code",
    ]
    if any(ind in query_lower for ind in technical_indicators):
        return False
    
    return True  # Default to rewriting


def conditional_rewrite(query: str) -> str:
    """
    Only rewrite if the query seems to need it.
    """
    if should_rewrite(query):
        return rewrite_query(query)
    return query
```

---

## Rewriting for Hybrid Search

Query rewriting is particularly powerful in hybrid search (BM25 + dense retrieval):

- **BM25 benefits directly** from rewriting casual terms to formal terms that appear in documents
- **Dense retrieval** may benefit less (embeddings already capture semantics) but still gains from vocabulary alignment

```python
def hybrid_retrieve_with_rewrite(
    query: str,
    bm25_retriever,
    dense_retriever,
    top_k: int = 5,
    bm25_weight: float = 0.5
) -> list[dict]:
    """
    Hybrid retrieval with query rewriting.
    """
    # Rewrite for BM25 (benefits most from exact term matching)
    rewritten = rewrite_query(query)
    
    # BM25 with rewritten query
    bm25_results = bm25_retriever.retrieve(rewritten, top_k=top_k * 2)
    
    # Dense with original query (embeddings already semantic)
    # Could also use HyDE here instead
    dense_results = dense_retriever.retrieve(query, top_k=top_k * 2)
    
    # Fuse results
    combined = reciprocal_rank_fusion(
        [bm25_results, dense_results],
        weights=[bm25_weight, 1 - bm25_weight]
    )
    
    return combined[:top_k]
```

---

## Complete Query Rewriter Class

Here's a production-ready rewriter:

```python
from openai import OpenAI
from typing import Optional

client = OpenAI()


class QueryRewriter:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        domain_description: str = None,
        domain_terms: list[str] = None,
        preserve_patterns: bool = True,
        temperature: float = 0.3
    ):
        self.model = model
        self.domain_description = domain_description
        self.domain_terms = domain_terms or []
        self.preserve_patterns = preserve_patterns
        self.temperature = temperature
    
    def rewrite(
        self,
        query: str,
        conversation_history: list[dict] = None,
        skip_if_specific: bool = True
    ) -> str:
        """
        Rewrite a query for improved retrieval.
        
        Args:
            query: The user's original query
            conversation_history: Optional conversation context
            skip_if_specific: If True, skip rewriting for already-specific queries
        
        Returns:
            Rewritten query (or original if skipped)
        """
        # Optionally skip rewriting for specific queries
        if skip_if_specific and self._is_specific(query):
            return query
        
        # Build the prompt
        prompt = self._build_prompt(query, conversation_history)
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=60
            )
            
            rewritten = response.choices[0].message.content.strip()
            
            # Sanity check: if rewrite is empty or too short, return original
            if len(rewritten) < 3:
                return query
            
            return rewritten
        
        except Exception as e:
            print(f"Rewrite failed: {e}")
            return query  # Fallback to original
    
    def _is_specific(self, query: str) -> bool:
        """
        Check if query is already specific enough.
        """
        query_lower = query.lower()
        
        # Technical indicators suggest query is already specific
        technical_terms = [
            "configure", "configuration", "setting", "parameter",
            "endpoint", "api", "error", "exception", "version",
            "install", "deploy", "migrate", "integrate",
        ]
        
        tech_count = sum(1 for term in technical_terms if term in query_lower)
        
        # If query has multiple technical terms, it's probably specific
        if tech_count >= 2:
            return True
        
        # If query is long and has technical terms, skip
        if len(query.split()) > 8 and tech_count >= 1:
            return True
        
        return False
    
    def _build_prompt(
        self,
        query: str,
        conversation_history: list[dict] = None
    ) -> str:
        """
        Build the rewriting prompt.
        """
        parts = ["You are a search query optimizer."]
        
        # Domain context
        if self.domain_description:
            parts.append(f"You are optimizing queries for: {self.domain_description}")
        
        if self.domain_terms:
            parts.append(f"Common terms in this domain: {', '.join(self.domain_terms[:20])}")
        
        # Conversation context
        if conversation_history:
            recent = conversation_history[-4:]
            context_str = "\n".join(
                f"{m['role']}: {m['content'][:150]}" for m in recent
            )
            parts.append(f"Recent conversation:\n{context_str}")
        
        # Instructions
        parts.append("""
Rewrite the user query to improve document retrieval:
- Transform casual language into formal, technical terms
- Transform symptom descriptions into root cause terminology
- Include context from conversation if the query references it
- Keep the rewritten query concise (under 20 words)
""")
        
        # Preservation instructions
        if self.preserve_patterns:
            parts.append("""
PRESERVE these exactly (do not paraphrase):
- Version numbers (v1.2, version 3)
- ALL-CAPS acronyms (API, SSO, RBAC)  
- Quoted text
- Product/project names
""")
        
        parts.append(f"Original query: {query}")
        parts.append("Rewritten query:")
        
        return "\n\n".join(parts)


# Usage
rewriter = QueryRewriter(
    domain_description="enterprise IT support knowledge base",
    domain_terms=["SSO", "LDAP", "Active Directory", "VPN", "ticket", "incident"],
    preserve_patterns=True
)

# Simple query
result = rewriter.rewrite("can't get into my email")
print(f"'can't get into my email' → '{result}'")

# Query with conversation context
result = rewriter.rewrite(
    "what about on mobile?",
    conversation_history=[
        {"role": "user", "content": "How do I set up VPN?"},
        {"role": "assistant", "content": "To configure VPN, go to Settings..."},
    ]
)
print(f"'what about on mobile?' → '{result}'")

# Already specific query
result = rewriter.rewrite(
    "How do I configure LDAP authentication in Active Directory v2.1"
)
print(f"Specific query (should skip): '{result}'")
```

---

## Key Takeaways

1. **Query rewriting transforms casual user language into formal document language** — it's a translation step that bridges vocabulary gaps between how users ask and how docs are written.
    
2. **It differs from expansion (which adds terms) and HyDE (which generates hypothetical answers)** — rewriting produces a single, transformed query optimized for retrieval.
    
3. **Most effective for:** casual/conversational queries, symptom-to-mechanism translation, multi-turn context integration, and abbreviation expansion.
    
4. **Can hurt for:** already-specific queries, proper nouns the LLM doesn't recognize, and domain-specific terminology the LLM might dilute.
    
5. **Mitigate risks by:** preserving key terms (version numbers, acronyms), using both original and rewritten queries, and conditional rewriting based on query characteristics.
    
6. **Particularly powerful for BM25/keyword search** where exact term matching matters — rewriting directly puts the right vocabulary into the query.
    
7. **Adds ~200-300ms latency** for the LLM call. For latency-sensitive applications, consider skipping rewriting for queries that are already specific.