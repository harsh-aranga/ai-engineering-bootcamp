# Note 2: LangSmith Setup and Instrumentation

## Documentation Reference

All code in this note is based on:

- LangSmith PyPI package docs (https://pypi.org/project/langsmith/)
- LangSmith official docs (https://docs.langchain.com/langsmith/)
- LangSmith wrappers reference (https://reference.langchain.com/python/langsmith/observability/sdk/wrappers/)

Last verified: March 2026. Note that environment variable naming has evolved — current best practice uses `LANGSMITH_*` prefix, though `LANGCHAIN_*` still works for backwards compatibility.

---

## LangSmith Core Concepts

Before diving into setup, understand the terminology LangSmith uses:

### Project

A **project** is a workspace for organizing traces. Think of it as a folder that groups related traces together.

```
Projects in LangSmith:
├── research-assistant-dev      ← Development traces
├── research-assistant-staging  ← Staging environment
├── research-assistant-prod     ← Production traces
└── experiment-hyde-variations  ← A/B testing experiments
```

You'll typically have separate projects for different environments and experiments. This keeps production traces clean while allowing messy experimentation elsewhere.

### Trace

A **trace** represents the complete lifecycle of a single user request — from when a query arrives to when a response is returned.

```
Trace: "abc-123-def-456"
├── User Input: "What's our refund policy for enterprise?"
├── Final Output: "Enterprise customers have a 60-day..."
├── Total Duration: 2.5 seconds
├── Total Tokens: 4,500
├── Total Cost: $0.0054
└── Status: SUCCESS
```

One user request = one trace. If the same user asks a follow-up question, that's a new trace (though you can link them via metadata).

### Run

A **run** is LangSmith's term for what distributed tracing calls a "span" — an individual operation within a trace. Every step in your pipeline creates a run.

```
Trace: "abc-123"
│
├── Run: "query_analysis" (50ms)
│   └── Run: "llm_call" (45ms)
│
├── Run: "retrieval" (300ms)
│   ├── Run: "embed_query" (50ms)
│   └── Run: "vector_search" (250ms)
│
└── Run: "generation" (1500ms)
    └── Run: "llm_call" (1450ms)
```

Runs can be nested. A `retrieval` run might contain child runs for `embed_query` and `vector_search`. This hierarchy is how you drill down from "retrieval took 300ms" to "vector search specifically took 250ms."

---

## Environment Variables Setup

LangSmith tracing activates through environment variables. When configured correctly, LangChain and LangGraph automatically send trace data — no code changes required for basic tracing.

### Required Variables

```python
import os

# Enable tracing
os.environ["LANGSMITH_TRACING"] = "true"

# API endpoint (default is US region)
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
# For EU region: "https://eu.api.smith.langchain.com"

# Your API key from https://smith.langchain.com
os.environ["LANGSMITH_API_KEY"] = "<YOUR-LANGSMITH-API-KEY>"

# Project name (optional, defaults to "default")
os.environ["LANGSMITH_PROJECT"] = "research-assistant-dev"

# Required for organization-scoped API keys (optional for personal keys)
# os.environ["LANGSMITH_WORKSPACE_ID"] = "<YOUR-WORKSPACE-ID>"
```

**Doc reference:** LangSmith PyPI docs (https://pypi.org/project/langsmith/)

### Environment Variable Evolution

You may see older code using `LANGCHAIN_*` prefixed variables. Both work:

|Current (Preferred)|Legacy (Still Works)|
|---|---|
|`LANGSMITH_TRACING`|`LANGCHAIN_TRACING_V2`|
|`LANGSMITH_API_KEY`|`LANGCHAIN_API_KEY`|
|`LANGSMITH_PROJECT`|`LANGCHAIN_PROJECT`|

Use `LANGSMITH_*` for new code. The `LANGCHAIN_*` versions exist for backwards compatibility.

### Common Setup Pattern

For local development, use a `.env` file:

```bash
# .env file
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=my-project-dev
OPENAI_API_KEY=sk-...
```

Load it in your code:

```python
from dotenv import load_dotenv
load_dotenv()

# Now LangChain/LangGraph will automatically trace
```

---

## The `@traceable` Decorator

The `@traceable` decorator is the primary way to instrument arbitrary functions for tracing. When you decorate a function, LangSmith automatically:

1. Creates a run when the function is called
2. Captures inputs (function arguments)
3. Captures outputs (return value)
4. Records timing (start and end)
5. Captures errors (if the function raises an exception)

### Basic Usage

```python
from langsmith import traceable

@traceable
def process_query(query: str) -> dict:
    """Process a user query."""
    # Your logic here
    return {"result": "processed"}
```

**Doc reference:** LangSmith PyPI docs, @traceable decorator section

### Naming Runs

By default, the run name is the function name. Override it for clarity:

```python
@traceable(name="Query Analysis")
def analyze(query: str) -> dict:
    # ...
    pass

@traceable(name="RAG Retrieval")  
def retrieve(query: str) -> list:
    # ...
    pass
```

This makes traces more readable in the dashboard.

### Run Types

LangSmith categorizes runs by type for filtering and visualization. The main types are:

|Run Type|Use For|
|---|---|
|`chain`|Multi-step pipelines (default for `@traceable`)|
|`llm`|Direct LLM calls|
|`tool`|Tool/function executions|
|`retriever`|RAG retrieval operations|
|`embedding`|Embedding generation|

Specify run type explicitly when it matters for filtering:

```python
@traceable(run_type="retriever")
def retrieve_documents(query: str) -> list:
    """Retrieve relevant documents."""
    # Hybrid search logic
    return documents

@traceable(run_type="llm")
def call_llm(messages: list) -> str:
    """Direct LLM call."""
    # LLM invocation
    return response
```

### Automatic Nesting

When a `@traceable` function calls another `@traceable` function, LangSmith automatically creates a parent-child relationship:

```python
from langsmith import traceable

@traceable(name="embed_query")
def embed_query(query: str) -> list:
    # Generate embedding
    return embedding

@traceable(name="vector_search")
def vector_search(embedding: list) -> list:
    # Search vector store
    return results

@traceable(name="retrieval")
def retrieve(query: str) -> list:
    embedding = embed_query(query)      # Child run
    results = vector_search(embedding)   # Child run
    return results
```

This creates:

```
retrieval (parent)
├── embed_query (child)
└── vector_search (child)
```

No explicit linking required — LangSmith handles the hierarchy automatically through context propagation.

---

## Wrapping LLM Clients

For LLM calls, LangSmith provides client wrappers that automatically capture:

- Input messages
- Output completion
- Token counts (input, output, total)
- Model name
- Latency

### OpenAI Wrapper

```python
import openai
from langsmith.wrappers import wrap_openai

# Wrap the OpenAI client
client = wrap_openai(openai.OpenAI())

# Use normally — all calls are automatically traced
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello, world!"}]
)
```

**Doc reference:** LangSmith wrappers reference (https://reference.langchain.com/python/langsmith/observability/sdk/wrappers/)

### Anthropic Wrapper

```python
import anthropic
from langsmith.wrappers import wrap_anthropic

# Wrap the Anthropic client
client = wrap_anthropic(anthropic.Anthropic())

# Use normally — all calls are automatically traced
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Hello, world!"}]
)
```

**Doc reference:** LangSmith wrappers reference

### Combining Wrappers with `@traceable`

The power comes from combining wrapped clients with `@traceable` functions:

```python
import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai

client = wrap_openai(openai.OpenAI())

@traceable(name="generate_answer")
def generate_answer(query: str, context: list[str]) -> str:
    """Generate answer from context."""
    context_text = "\n".join(context)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Context:\n{context_text}"},
            {"role": "user", "content": query}
        ]
    )
    
    return response.choices[0].message.content

@traceable(name="rag_pipeline")
def rag_pipeline(query: str) -> str:
    """Full RAG pipeline."""
    docs = retrieve(query)          # Traced via @traceable
    answer = generate_answer(query, docs)  # Traced, with nested LLM call
    return answer
```

This creates:

```
rag_pipeline
├── retrieve
│   ├── embed_query
│   │   └── ChatOpenAI (auto-traced by wrapper)
│   └── vector_search
└── generate_answer
    └── ChatOpenAI (auto-traced by wrapper)
```

The wrapper ensures the LLM call appears as a child of `generate_answer`, not floating at the top level.

---

## Instrumenting RAG Systems

Here's a complete span hierarchy for a RAG system:

```
rag_query (trace root)
├── query_transform (span)
│   └── llm_call (sub-span) — HyDE generation
├── retrieve (span)
│   ├── embed_query (sub-span)
│   ├── bm25_search (sub-span)
│   ├── dense_search (sub-span)
│   └── merge_results (sub-span)
├── rerank (span)
│   └── cross_encoder (sub-span)
└── generate (span)
    └── llm_call (sub-span)
```

### Implementation

```python
import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai

client = wrap_openai(openai.OpenAI())


@traceable(name="query_transform", run_type="chain")
def transform_query(query: str) -> str:
    """HyDE: Generate hypothetical document."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Generate a hypothetical document that would answer this query."},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message.content


@traceable(name="embed_query", run_type="embedding")
def embed_query(text: str) -> list[float]:
    """Generate embedding for query."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


@traceable(name="bm25_search", run_type="retriever")
def bm25_search(query: str, top_k: int = 20) -> list[dict]:
    """Sparse retrieval with BM25."""
    # BM25 search logic
    return results


@traceable(name="dense_search", run_type="retriever")
def dense_search(embedding: list[float], top_k: int = 20) -> list[dict]:
    """Dense retrieval with vector search."""
    # Vector store query
    return results


@traceable(name="merge_results", run_type="chain")
def merge_results(bm25_results: list, dense_results: list) -> list[dict]:
    """Merge and deduplicate results."""
    # RRF or other fusion
    return merged


@traceable(name="retrieve", run_type="retriever")
def retrieve(query: str, top_k: int = 10) -> list[dict]:
    """Hybrid retrieval: BM25 + dense."""
    # Transform query
    transformed = transform_query(query)
    
    # Get embedding
    embedding = embed_query(transformed)
    
    # Parallel search
    bm25_results = bm25_search(query)
    dense_results = dense_search(embedding)
    
    # Merge
    merged = merge_results(bm25_results, dense_results)
    
    return merged[:top_k]


@traceable(name="rerank", run_type="chain")
def rerank(query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank with cross-encoder."""
    # Cross-encoder scoring
    return reranked[:top_k]


@traceable(name="generate", run_type="chain")
def generate(query: str, context: list[dict]) -> str:
    """Generate answer from context."""
    context_text = "\n\n".join([doc["text"] for doc in context])
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Answer based on this context:\n{context_text}"},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message.content


@traceable(name="rag_query")
def rag_query(query: str) -> dict:
    """Complete RAG pipeline."""
    # Retrieve
    documents = retrieve(query)
    
    # Rerank
    reranked = rerank(query, documents)
    
    # Generate
    answer = generate(query, reranked)
    
    return {
        "query": query,
        "answer": answer,
        "sources": reranked
    }
```

---

## Instrumenting Agent Systems

Agent systems have a different trace structure — they include decision points, tool calls, and potentially multiple iterations:

```
agent_run (trace root)
├── agent_decision (span)
│   └── llm_call — "Should I use RAG or web search?"
├── tool_call: rag_search (span)
│   └── [Full RAG hierarchy nested here]
├── agent_decision (span)
│   └── llm_call — "Do I have enough info?"
├── tool_call: web_search (span)
│   └── search_api_call
└── final_generation (span)
    └── llm_call
```

### With LangGraph

When using LangGraph with LangSmith tracing enabled, graph nodes automatically create runs:

```python
# Environment variables handle tracing
# LANGSMITH_TRACING=true

from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o-mini")

def agent_node(state: MessagesState):
    """This node automatically creates a run."""
    # LangChain model calls are auto-traced
    response = model.invoke(state["messages"])
    return {"messages": [response]}

def tool_node(state: MessagesState):
    """This node also automatically creates a run."""
    # Tool execution logic
    pass

# Build graph
graph = StateGraph(MessagesState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
# ... edges

app = graph.compile()

# Invoking the graph creates a trace with runs for each node
result = app.invoke({"messages": [("user", "What's the weather in SF?")]})
```

**Doc reference:** LangSmith docs for LangGraph tracing (https://docs.langchain.com/langsmith/trace-with-langgraph)

The key point: **LangGraph + LangChain components auto-trace when environment variables are set**. You only need `@traceable` for custom functions that aren't using LangChain primitives.

### Custom Functions in LangGraph

If you call non-LangChain code within a LangGraph node, wrap it with `@traceable`:

```python
from langsmith import traceable
from langsmith.wrappers import wrap_openai
import openai

client = wrap_openai(openai.OpenAI())

@traceable(name="custom_processing")
def custom_processing(data: str) -> str:
    """Custom logic that should appear in traces."""
    # Your business logic
    return processed

def agent_node(state: MessagesState):
    """LangGraph node."""
    # This will appear in traces
    processed = custom_processing(state["messages"][-1].content)
    
    # This is auto-traced via wrapped client
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": processed}]
    )
    
    return {"messages": [response.choices[0].message.content]}
```

---

## What to Log in Each Span

Beyond automatic input/output capture, you can add metadata and tags for filtering:

### Metadata

Metadata is key-value pairs for contextual information:

```python
@traceable(
    name="generate_answer",
    metadata={
        "model_version": "v2.1",
        "prompt_version": "hyde-v3"
    }
)
def generate_answer(query: str, context: list) -> str:
    # ...
    pass
```

Useful metadata:

- `model_version`: Which model version is running
- `prompt_version`: Which prompt template version
- `user_id`: For per-user analysis (be mindful of PII)
- `experiment_id`: For A/B testing

### Tags

Tags are string labels for filtering:

```python
@traceable(
    name="rag_query",
    tags=["production", "rag-v2", "hybrid-search"]
)
def rag_query(query: str) -> dict:
    # ...
    pass
```

Use tags to:

- Filter traces by environment (`dev`, `staging`, `prod`)
- Filter by feature (`rag-v2`, `agent-v3`)
- Group experiments (`experiment-hyde`, `experiment-no-hyde`)

---

## Viewing Traces in Dashboard

Once traces are flowing, the LangSmith dashboard provides several views:

### Trace List

Shows all traces for a project with:

- Timestamp
- Total latency
- Total tokens
- Status (success/error)
- Tags

Filter by time range, tags, or metadata.

### Trace Detail: Hierarchy View

Click a trace to see the run hierarchy:

```
[===== rag_query (2500ms) ================================]
  [== query_transform (150ms) ==]
    [= ChatOpenAI (140ms) =]
  [======== retrieve (300ms) ========]
    [= embed_query (50ms) =]
    [bm25 (100ms)]
    [dense (120ms)]
    [merge (30ms)]
  [==== rerank (200ms) ====]
  [=============== generate (1500ms) ===============]
    [============= ChatOpenAI (1450ms) =============]
```

Expand any run to see:

- Input (what the function received)
- Output (what the function returned)
- Timing (start, end, duration)
- Tokens (for LLM calls)
- Errors (if any)

### Timing Waterfall

Visual representation showing:

- Sequential vs. parallel execution
- Where latency is concentrated
- Unexpected gaps or delays

### Input/Output Inspection

For each run, view:

- **Inputs**: Function arguments, serialized to JSON
- **Outputs**: Return value, serialized to JSON
- **For LLM calls**: Full prompt, full completion

This is where you answer "what did the LLM see?" — you can inspect the exact prompt that was sent.

---

## Error Capture

Errors are automatically captured with full context:

```python
@traceable(name="risky_operation")
def risky_operation(data: str) -> str:
    if not data:
        raise ValueError("Data cannot be empty")
    return process(data)
```

When this raises an exception:

- The run is marked as failed
- The exception type and message are captured
- The stack trace is captured
- The inputs that caused the failure are preserved

In the dashboard:

- Failed runs are highlighted (typically red)
- You can filter to show only errors
- Click to see full error details with inputs

This is crucial for debugging: you see not just "ValueError" but the exact input that caused it.

---

## Practical Setup Checklist

1. **Create LangSmith account** at https://smith.langchain.com
2. **Get API key** from Settings → API Keys
3. **Set environment variables**:
    
    ```bash
    LANGSMITH_TRACING=trueLANGSMITH_API_KEY=ls-...LANGSMITH_PROJECT=my-project
    ```
    
4. **Install packages**:
    
    ```bash
    pip install langsmith langchain-openai
    ```
    
5. **Wrap LLM clients**:
    
    ```python
    from langsmith.wrappers import wrap_openaiclient = wrap_openai(openai.OpenAI())
    ```
    
6. **Add `@traceable` to key functions**:
    
    ```python
    @traceable(name="my_pipeline")def my_pipeline(...):    ...
    ```
    
7. **Run a query and verify** in dashboard

---

## What's Next

With tracing set up, you can see every step of your pipeline. But you're still missing cost visibility — knowing how much each query costs and where the expense comes from. The next note covers token counting, cost calculation, and budget tracking.