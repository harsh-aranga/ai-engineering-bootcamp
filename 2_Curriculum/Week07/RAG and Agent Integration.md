# Week 7: Combined Phase — RAG + Agent Integration & Observability

> **Track:** Combined (RAG + Agents merge) **Time:** 2 hours/day **Goal:** Integrate RAG and Agents into unified systems. Add production observability. Build Research Assistant v1.

---

## Overview

| Days | Topic                   | Output                              |
| ---- | ----------------------- | ----------------------------------- |
| 1-2  | RAG + Agent Integration | RAG as agent tool working           |
| 3-4  | Agentic RAG Patterns    | Iterative/self-correcting retrieval |
| 5-6  | Observability & Tracing | Full-stack tracing setup            |
| 7    | Mini Build              | Research Assistant v1               |

---

## Days 1-2: RAG + Agent Integration

### Why This Matters

You have two systems:

- **RAG**: Takes a question, retrieves context, generates answer
- **Agent**: Takes a task, reasons, uses tools, produces output

Separately, they're useful. Together, they're powerful:

- Agent decides _when_ to consult knowledge base (not every query needs RAG)
- Agent decides _what_ to ask RAG (rephrases user question for better retrieval)
- Agent decides _whether to trust_ RAG results (validates, asks follow-up)
- Agent can combine RAG with other tools (search web, calculate, then check internal docs)

The integration pattern: **RAG becomes a tool that the agent can call.**

### What to Learn

**Core Concepts:**

**Pattern 1: RAG as Simple Tool**

```
User: "What's our refund policy?"
     │
     ▼
┌─────────────┐
│    Agent    │
│             │
│ Thinks: This│──────────────┐
│ needs docs  │              │
└─────────────┘              ▼
                    ┌─────────────────┐
                    │   RAG Tool      │
                    │                 │
                    │ query_docs(     │
                    │   "refund       │
                    │    policy"      │
                    │ )               │
                    └────────┬────────┘
                             │
                             ▼
                    Returns context + answer
                             │
     ┌─────────────┐         │
     │    Agent    │◄────────┘
     │             │
     │ Formats     │
     │ response    │
     └─────────────┘
```

**Pattern 2: Conditional RAG (Agent decides when to retrieve)**

```python
def should_use_rag(query: str, agent_state: dict) -> bool:
    """
    Agent logic to decide if RAG is needed.
    
    Use RAG when:
    - Query asks about internal/company information
    - Query references documents, policies, procedures
    - Query requires factual accuracy from known sources
    
    Skip RAG when:
    - General knowledge question (use LLM knowledge)
    - Calculation or reasoning task (use other tools)
    - Clearly external info (use web search)
    """
    pass
```

**Pattern 3: Query Reformulation (Agent improves the RAG query)**

```
User: "What did we decide about the thing John mentioned?"
                    │
                    ▼
            ┌─────────────┐
            │    Agent    │
            │             │
            │ Thinks: Too │
            │ vague for   │
            │ RAG. Need   │
            │ to clarify. │
            └──────┬──────┘
                   │
                   ▼
        Agent reformulates:
        "meeting decisions John project X"
                   │
                   ▼
            ┌─────────────┐
            │  RAG Tool   │
            └─────────────┘
```

**Pattern 4: RAG + Other Tools Combined**

```
User: "Compare our pricing to competitors"
                    │
                    ▼
            ┌─────────────┐
            │    Agent    │
            │             │
            │ Plan:       │
            │ 1. Get our  │──> RAG Tool (internal docs)
            │    pricing  │
            │ 2. Search   │──> Web Search Tool (competitors)
            │    competitors
            │ 3. Compare  │──> Analysis (LLM reasoning)
            └─────────────┘
```

**Practical Skills:**

- Wrap your RAG system as an agent tool
- Design the tool interface (what params? what returns?)
- Implement conditional retrieval logic
- Handle RAG failures gracefully in agent flow

### Resources

**Primary:**

- LangChain Tools from Functions: https://python.langchain.com/docs/how_to/custom_tools/
- LangGraph Tool Integration: https://langchain-ai.github.io/langgraph/how-tos/tool-calling/

**Secondary:**

- Search: "RAG as agent tool pattern"
- Search: "conditional retrieval agent"

### Day 1 Tasks (2 hours)

**Hour 1 — Learn + Design:**

1. Review the integration patterns above (15 min)
2. Think through: How should your RAG expose itself as a tool? What's the interface? (15 min)
    
    ```python
    # Option A: Simpledef query_knowledge_base(query: str) -> str:    """Search internal documents and return relevant information."""    pass# Option B: Richdef query_knowledge_base(    query: str,    filters: dict = None,  # {"department": "engineering"}    num_results: int = 5,    include_sources: bool = True) -> dict:    """Search internal documents with filtering and source tracking."""    pass
    ```
    
3. Decide on your tool interface — write the schema (15 min)
4. Consider: What metadata should RAG return to the agent? (sources, confidence, relevance scores?) (15 min)

**Hour 2 — Implement:**

1. Wrap your Week 6 RAG as a tool:
    
    ```python
    from langchain_core.tools import toolfrom your_rag import RAGrag = RAG.from_config("config/default.yaml")@tooldef query_knowledge_base(query: str) -> str:    """    Search the company knowledge base for information.    Use this for questions about policies, procedures,     internal documentation, or company-specific information.        Args:        query: The search query            Returns:        Relevant information from internal documents with sources    """    result = rag.query(query)    # Format for agent consumption    response = f"Answer: {result.answer}\n\nSources:\n"    for source in result.sources:        response += f"- {source['title']}: {source['snippet']}\n"    return response
    ```
    
2. Create a simple agent with this tool + one other tool (e.g., calculator)
3. Test: "What's our vacation policy?" → Should use RAG
4. Test: "What's 15% of 230?" → Should use calculator, not RAG
5. Test: "How many vacation days do I get if I work 230 days at 15% PTO rate?" → Should use both

### Day 2 Tasks (2 hours)

**Hour 1 — Conditional Retrieval:**

1. Implement logic for when to use RAG:
    
    ```python
    class SmartAgent:    def __init__(self, rag_tool, other_tools):        self.rag_tool = rag_tool        self.other_tools = other_tools        def classify_query(self, query: str) -> str:        """        Classify query intent to decide tool routing.        Returns: "internal_docs" | "web_search" | "calculation" | "general"        """        # Could be rule-based or LLM-based        pass        def run(self, query: str):        intent = self.classify_query(query)        if intent == "internal_docs":            # Use RAG            pass        elif intent == "web_search":            # Use web search tool            pass        # etc.
    ```
    
2. Test classification on 10 different queries
3. Measure: How often does it correctly route?

**Hour 2 — Query Reformulation:**

1. Add query reformulation before RAG:
    
    ```python
    def reformulate_for_rag(user_query: str, conversation_history: list) -> str:    """    Improve query for better RAG retrieval.    - Resolve pronouns ("it", "that", "the thing")    - Add context from conversation    - Remove conversational fluff    """    prompt = f"""    Conversation history: {conversation_history}    User query: {user_query}        Rewrite this query to be optimal for searching a document database.    - Be specific and include relevant context    - Use keywords likely to appear in documents    - Remove conversational elements        Rewritten query:    """    # Call LLM    pass
    ```
    
2. Test on vague queries:
    - "What about that policy?" → Should become specific
    - "Tell me more" → Should incorporate previous context
3. Compare retrieval quality: original query vs. reformulated

### 5 Things to Ponder

1. Your agent can call RAG or web search. User asks: "What are the best practices for code review?" This could be answered by internal docs (your company's practices) or web (general practices). How does the agent decide? Should it do both and synthesize?
    
2. RAG returns results with low confidence (relevance scores are all below 0.5). Should the agent: (a) use them anyway, (b) tell user "I couldn't find relevant info," (c) try reformulating and searching again, (d) fall back to web search? How do you encode this decision logic?
    
3. User asks a multi-part question: "What's our refund policy and how does it compare to Amazon's?" This needs RAG (internal) + web search (Amazon). How does the agent decompose this? Does it matter which it does first?
    
4. Your RAG tool returns a 2000-token response. Agent's context is filling up. After 5 RAG calls, you're hitting limits. How do you manage context when RAG responses are verbose? Summarize? Truncate? Select?
    
5. The agent reformulates "that thing John mentioned" into "John project requirements." But John mentioned multiple things — budget, timeline, and requirements. The agent guessed wrong. How do you handle ambiguity? Ask user? Try multiple reformulations?
    

---

## Days 3-4: Agentic RAG Patterns

### Why This Matters

Basic RAG: Query → Retrieve → Generate. One shot. Done.

But complex questions need more:

- "Summarize all customer complaints from Q3" → Need multiple retrievals, synthesis
- "What changed between policy v1 and v2?" → Need to retrieve both, compare
- "Find evidence for and against this proposal" → Need targeted multi-perspective retrieval

Agentic RAG adds reasoning loops around retrieval. The agent:

- Evaluates retrieval quality
- Decides if more retrieval is needed
- Decomposes complex queries
- Self-corrects when retrieval fails

### What to Learn

**Core Concepts:**

**Pattern 1: Iterative Retrieval**

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Query ──> Retrieve ──> Evaluate ──> Enough? ──No──> Refine│
│                              │                      Query   │
│                              │                        │     │
│                             Yes                       │     │
│                              │                        │     │
│                              ▼                        │     │
│                          Generate                     │     │
│                              │                        │     │
│                              ▼                        │     │
│                           Answer ◄────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Agent retrieves, checks if results are sufficient, retrieves more if needed.

**Pattern 2: Query Decomposition**

```
Complex Query: "Compare our 2023 and 2024 product roadmaps"
                              │
                              ▼
                    ┌─────────────────┐
                    │ Decompose into  │
                    │ sub-queries     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        "2023 product   "2024 product   "roadmap
         roadmap"        roadmap"        changes"
              │              │              │
              ▼              ▼              ▼
           Retrieve       Retrieve       Retrieve
              │              │              │
              └──────────────┼──────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Synthesize    │
                    │   comparison    │
                    └─────────────────┘
```

**Pattern 3: Self-Correcting RAG**

```
Query ──> Retrieve ──> Generate Answer
                              │
                              ▼
                    ┌─────────────────┐
                    │ Verify Answer   │
                    │ against Context │
                    └────────┬────────┘
                             │
               ┌─────────────┴─────────────┐
               │                           │
           Supported                  Not Supported
               │                           │
               ▼                           ▼
           Return                   ┌─────────────┐
           Answer                   │ Re-retrieve │
                                    │ or Refine   │
                                    └─────────────┘
```

**Pattern 4: Adaptive Retrieval Strategy**

```python
class AdaptiveRAG:
    def query(self, question: str) -> str:
        # Analyze question complexity
        complexity = self.analyze_complexity(question)
        
        if complexity == "simple":
            # Single retrieval
            return self.simple_rag(question)
        
        elif complexity == "multi_part":
            # Decompose and retrieve separately
            sub_questions = self.decompose(question)
            results = [self.simple_rag(sq) for sq in sub_questions]
            return self.synthesize(results)
        
        elif complexity == "comparative":
            # Retrieve multiple perspectives
            aspects = self.identify_aspects(question)
            results = {aspect: self.retrieve_for_aspect(aspect) for aspect in aspects}
            return self.compare(results)
        
        elif complexity == "exploratory":
            # Iterative retrieval until satisfied
            return self.iterative_rag(question)
```

**Practical Skills:**

- Implement iterative retrieval with stopping criteria
- Decompose complex queries into sub-queries
- Verify answers against retrieved context
- Build adaptive strategies based on query type

### Resources

**Primary:**

- LlamaIndex Agentic RAG: https://docs.llamaindex.ai/en/stable/understanding/putting_it_all_together/agents/
- LangChain Self-Query: https://python.langchain.com/docs/how_to/self_query/
- Corrective RAG Paper: https://arxiv.org/abs/2401.15884

**Secondary:**

- Search: "agentic RAG patterns"
- Search: "iterative retrieval LLM"
- Search: "CRAG corrective RAG"

### Day 3 Tasks (2 hours)

**Hour 1 — Learn + Design:**

1. Read about CRAG (Corrective RAG) — understand the evaluate-then-act pattern (20 min)
2. Think through query decomposition: How would you break down these?
    - "What are all the ways we've addressed customer complaints about shipping?"
    - "Compare engineering team's approach to the sales team's approach on remote work"
    - "Summarize everything we know about competitor X"
3. Design an iterative retrieval loop:
    
    ```python
    def iterative_retrieve(query: str, max_iterations: int = 3) -> list:    """    Retrieve iteratively until we have enough relevant information.    """    all_results = []    current_query = query        for i in range(max_iterations):        results = retrieve(current_query)        all_results.extend(results)                # Evaluate: Do we have enough?        if self.has_sufficient_context(query, all_results):            break                # Refine query for next iteration        current_query = self.refine_query(query, all_results)        return all_results
    ```
    
4. What does `has_sufficient_context` look like? What does `refine_query` do? (20 min)

**Hour 2 — Implement Iterative RAG:**

1. Implement basic iterative retrieval:
    
    ```python
    class IterativeRAG:    def __init__(self, rag_system, llm):        self.rag = rag_system        self.llm = llm        def has_sufficient_context(        self,         query: str,         retrieved_docs: list    ) -> bool:        """Use LLM to judge if we have enough context."""        prompt = f"""        Question: {query}                Retrieved information:        {self._format_docs(retrieved_docs)}                Can this question be fully answered with the retrieved information?        Respond with YES or NO, then explain what's missing if NO.        """        response = self.llm.invoke(prompt)        return response.startswith("YES")        def refine_query(        self,         original_query: str,         retrieved_docs: list    ) -> str:        """Generate a refined query to fill gaps."""        prompt = f"""        Original question: {original_query}                We retrieved this information:        {self._format_docs(retrieved_docs)}                What additional information do we need?         Write a search query to find the missing information.        """        return self.llm.invoke(prompt)
    ```
    
2. Test on a query that needs multiple retrievals
3. Test on a query where one retrieval is enough — verify it stops early
4. Track: How many iterations does it typically need?

### Day 4 Tasks (2 hours)

**Hour 1 — Query Decomposition:**

1. Implement query decomposition:
    
    ```python
    class QueryDecomposer:    def __init__(self, llm):        self.llm = llm        def decompose(self, complex_query: str) -> list[str]:        """Break complex query into sub-queries."""        prompt = f"""        Complex question: {complex_query}                Break this into simpler sub-questions that can each be         answered independently. Each sub-question should be         searchable in a document database.                Return as a numbered list:        1. [first sub-question]        2. [second sub-question]        ...        """        response = self.llm.invoke(prompt)        return self._parse_list(response)        def synthesize(        self,         original_query: str,         sub_results: dict[str, str]    ) -> str:        """Synthesize sub-answers into final answer."""        prompt = f"""        Original question: {original_query}                Sub-questions and answers:        {self._format_sub_results(sub_results)}                Synthesize these into a complete answer to the original question.        """        return self.llm.invoke(prompt)
    ```
    
2. Test decomposition on complex queries
3. Test synthesis — does it produce coherent combined answers?

**Hour 2 — Mini Challenge: Agentic RAG System**

Build an `AgenticRAG` class that combines patterns:

```python
class AgenticRAG:
    def __init__(
        self,
        rag_system,
        llm,
        max_iterations: int = 3,
        enable_decomposition: bool = True,
        enable_self_correction: bool = True
    ):
        pass
    
    def query(self, question: str) -> dict:
        """
        Intelligently answer using agentic RAG patterns.
        
        Returns:
            {
                "answer": str,
                "sources": list,
                "strategy_used": "simple|iterative|decomposed",
                "iterations": int,
                "sub_queries": list (if decomposed),
                "corrections": list (if self-corrected),
                "trace": list  # Full reasoning trace
            }
        """
        pass
    
    def _classify_query_complexity(self, query: str) -> str:
        """Classify as simple, multi_part, comparative, exploratory."""
        pass
    
    def _simple_query(self, query: str) -> dict:
        """Standard RAG for simple queries."""
        pass
    
    def _iterative_query(self, query: str) -> dict:
        """Iterative retrieval until sufficient."""
        pass
    
    def _decomposed_query(self, query: str) -> dict:
        """Decompose, retrieve separately, synthesize."""
        pass
    
    def _verify_answer(self, query: str, answer: str, context: str) -> bool:
        """Check if answer is supported by context."""
        pass
```

**Success Criteria:**

- [ ] Correctly classifies query complexity
- [ ] Simple queries use single retrieval (efficient)
- [ ] Complex queries use decomposition or iteration
- [ ] Self-correction catches unsupported answers
- [ ] Full trace available for debugging
- [ ] Tested on at least 10 queries of varying complexity
- [ ] At least 3 queries show benefit of agentic patterns vs. simple RAG

### 5 Things to Ponder

1. Iterative retrieval keeps going until "sufficient context." But what's sufficient? If you're too strict, you loop forever. Too lenient, you stop with incomplete info. How do you calibrate this threshold? Should it be query-dependent?
    
2. You decompose "Compare A and B" into two sub-queries. You retrieve for A, retrieve for B, then synthesize. But what if the comparison requires information that neither sub-query surfaces (like shared context)? Is decomposition always the right move?
    
3. Self-correction: You generate an answer, verify it's supported, find it's not, re-retrieve. But you're using an LLM to check itself. LLMs can confidently verify their own hallucinations. How do you make verification reliable?
    
4. Your agentic RAG does 5 retrievals and 3 LLM calls per query. Basic RAG does 1 of each. Cost is 5x. Latency is 3x. When is this justified? How do you decide per-query whether to go agentic or simple?
    
5. Agentic RAG increases complexity significantly. More code, more failure modes, harder debugging. Your Week 6 RAG had clear eval metrics. How do you evaluate agentic RAG? What new metrics do you need? How do you measure "reasoning quality"?
    

---

## Days 5-6: Observability & Tracing

### Why This Matters

You've built complex systems:

- Multi-step agent flows
- RAG with hybrid search + reranking + query transformation
- Agentic RAG with iterative retrieval

When something goes wrong in production, you need to know:

- Which step failed?
- What did the LLM see? What did it output?
- How long did each step take?
- How much did this request cost?
- Is this a one-off error or a pattern?

Observability gives you visibility. Without it, debugging production issues is nearly impossible.

### What to Learn

**Core Concepts:**

**What to Trace:**

```
REQUEST LIFECYCLE
┌─────────────────────────────────────────────────────────────────┐
│ User Query                                                      │
│     │                                                           │
│     ▼                                                           │
│ ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │
│ │ Agent   │→ │ Query   │→ │Retrieval│→ │ Rerank  │→ │Generate│ │
│ │ Route   │  │Transform│  │ (RAG)   │  │         │  │        │ │
│ └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └───┬────┘ │
│      │            │            │            │           │      │
│   trace_id    trace_id     trace_id     trace_id    trace_id   │
│   span_id     span_id      span_id      span_id     span_id    │
│   latency     latency      latency      latency     latency    │
│   tokens      tokens       results      results     tokens     │
│   cost        cost                                  cost       │
└─────────────────────────────────────────────────────────────────┘
```

**Tracing Hierarchy:**

```
Trace (full request lifecycle)
  └── Span: agent_decision (50ms)
        └── Span: llm_call (45ms)
              - input: "Classify query intent..."
              - output: "internal_docs"
              - tokens: 150
  └── Span: rag_retrieval (200ms)
        └── Span: query_transform (80ms)
        └── Span: hybrid_search (100ms)
        └── Span: rerank (20ms)
  └── Span: generation (500ms)
        └── Span: llm_call (495ms)
              - input: context + query
              - output: answer
              - tokens: 2000
```

**Key Metrics:**

- **Latency**: Total and per-span
- **Token usage**: Input/output per LLM call
- **Cost**: Per request, per model
- **Error rate**: Which spans fail most often
- **Retrieval quality**: Hit rate, relevance scores (from your eval)

**Tools:**

- **LangSmith**: Built for LangChain/LangGraph, full tracing, evals
- **LangFuse**: Open source alternative, similar features
- **OpenTelemetry**: Generic tracing standard, requires more setup
- **Custom logging**: JSON logs, structured for analysis

**Practical Skills:**

- Instrument your code with traces
- Use LangSmith or LangFuse for visualization
- Track costs per request
- Identify bottlenecks and failures
- Set up alerts for anomalies

### Resources

**Primary:**

- LangSmith Docs: https://docs.smith.langchain.com/
- LangSmith Tracing Guide: https://docs.smith.langchain.com/observability
- LangFuse (open source): https://langfuse.com/docs

**Secondary:**

- Search: "LangSmith tutorial"
- Search: "LLM observability best practices"
- Search: "langfuse setup guide"

### Day 5 Tasks (2 hours)

**Hour 1 — Learn + Setup:**

1. Read LangSmith tracing concepts (20 min)
2. Choose your tool:
    - **LangSmith**: Easier if using LangChain/LangGraph, cloud-hosted
    - **LangFuse**: Open source, can self-host, works with any stack
3. Set up account and get API keys (15 min)
4. Configure in your project:
    
    ```python
    # LangSmith setupimport osos.environ["LANGCHAIN_TRACING_V2"] = "true"os.environ["LANGCHAIN_API_KEY"] = "your-key"os.environ["LANGCHAIN_PROJECT"] = "research-assistant-v1"# Or LangFuse setupfrom langfuse import Langfuselangfuse = Langfuse(    public_key="your-public-key",    secret_key="your-secret-key")
    ```
    
5. Run a simple query, verify it appears in dashboard (15 min)

**Hour 2 — Instrument Your Code:**

1. Add tracing to your RAG system:
    
    ```python
    from langsmith import traceableclass RAG:    @traceable(name="rag_query")    def query(self, question: str) -> dict:        transformed = self._transform_query(question)        retrieved = self._retrieve(transformed)        reranked = self._rerank(retrieved)        answer = self._generate(question, reranked)        return answer        @traceable(name="query_transform")    def _transform_query(self, query: str) -> str:        # HyDE or other transformation        pass        @traceable(name="retrieve")    def _retrieve(self, query: str) -> list:        # Hybrid search        pass        @traceable(name="rerank")    def _rerank(self, docs: list) -> list:        # Cross-encoder reranking        pass        @traceable(name="generate")    def _generate(self, query: str, context: list) -> str:        # LLM generation        pass
    ```
    
2. Add tracing to your agent system
3. Run 10 queries, explore them in the dashboard
4. Identify: Which step is slowest? Which uses most tokens?

### Day 6 Tasks (2 hours)

**Hour 1 — Cost Tracking + Alerts:**

1. Add cost tracking:
    
    ```python
    # Token counting for cost estimationimport tiktokendef estimate_cost(    model: str,    input_tokens: int,    output_tokens: int) -> float:    """Estimate cost in USD."""    # Prices as of knowledge cutoff - verify current rates    prices = {        "gpt-4o-mini": {"input": 0.15/1e6, "output": 0.60/1e6},        "gpt-4o": {"input": 2.50/1e6, "output": 10.00/1e6},    }    if model not in prices:        return 0.0    return (        input_tokens * prices[model]["input"] +        output_tokens * prices[model]["output"]    )class CostTracker:    def __init__(self):        self.total_cost = 0.0        self.costs_by_model = {}        def log_call(self, model: str, input_tokens: int, output_tokens: int):        cost = estimate_cost(model, input_tokens, output_tokens)        self.total_cost += cost        self.costs_by_model[model] = self.costs_by_model.get(model, 0) + cost        return cost
    ```
    
2. Add cost logging to your traces
3. After 10 queries: What's the average cost per query?

**Hour 2 — Mini Challenge: Observability Dashboard**

Create an `ObservabilityWrapper` that instruments any RAG/Agent system:

```python
class ObservabilityWrapper:
    def __init__(
        self,
        system,  # RAG or Agent
        project_name: str,
        enable_tracing: bool = True,
        enable_cost_tracking: bool = True
    ):
        pass
    
    def query(self, *args, **kwargs) -> dict:
        """
        Wrap the underlying system's query method.
        
        Adds:
        - Trace with span hierarchy
        - Latency per span
        - Token/cost tracking
        - Error capture
        
        Returns:
            Original response + observability metadata:
            {
                **original_response,
                "_observability": {
                    "trace_id": "...",
                    "total_latency_ms": 750,
                    "spans": [
                        {"name": "retrieve", "latency_ms": 200},
                        {"name": "generate", "latency_ms": 500}
                    ],
                    "total_tokens": 3500,
                    "estimated_cost_usd": 0.0045
                }
            }
        """
        pass
    
    def get_stats(self, last_n_hours: int = 24) -> dict:
        """
        Get aggregate statistics.
        
        Returns:
            {
                "total_queries": 150,
                "avg_latency_ms": 650,
                "p95_latency_ms": 1200,
                "total_cost_usd": 1.25,
                "error_rate": 0.02,
                "slowest_span": "generate",
                "most_expensive_model": "gpt-4o"
            }
        """
        pass
    
    def get_errors(self, last_n_hours: int = 24) -> list:
        """Get recent errors with traces for debugging."""
        pass
```

**Success Criteria:**

- [ ] Full trace visible in LangSmith/LangFuse dashboard
- [ ] Each span shows latency
- [ ] LLM calls show input/output tokens
- [ ] Cost per query calculated
- [ ] Aggregate stats accessible
- [ ] Errors captured with full trace
- [ ] Can identify the slowest span across 10 queries
- [ ] Can identify total cost over 10 queries

### 5 Things to Ponder

1. You add tracing to everything. Every span is logged. Storage costs grow. After a month, you have millions of traces. How do you manage this? Sampling? TTL? When is 100% tracing necessary vs. wasteful?
    
2. Your observability shows Generation span is slowest (500ms). But you can't speed up the LLM. What optimizations are actually actionable based on trace data? Where does observability help vs. just inform?
    
3. A query fails. The trace shows the retrieval span succeeded but generate span threw an error. The error is "context too long." Observability told you _where_, but not _why_ context got too long. What additional context do you log?
    
4. You're tracking costs. Average query is $0.005. Seems fine. But one user sent 1000 queries in an hour — $5 and counting. How do you set up alerts for anomalies? What thresholds do you use?
    
5. Your traces contain user queries and LLM outputs. This is sensitive data. How do you handle PII in traces? Do you redact? Encrypt? What's the tradeoff between debuggability and privacy?
    

---

## Day 7: Mini Build — Research Assistant v1

### What to Build

Combine everything from Weeks 1-7 into a working Research Assistant:

- Multi-agent architecture (from Week 6)
- RAG as a tool (from this week)
- Agentic RAG patterns (iterative, decomposition)
- Full observability

This is the foundation you'll harden in Weeks 8-9.

### Specifications

**Architecture:**

```
User Query
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    RESEARCH ORCHESTRATOR                     │
│                                                              │
│  - Understands research request                              │
│  - Plans research strategy                                   │
│  - Delegates to specialized agents                           │
│  - Synthesizes final response                                │
│                                                              │
│  Tools available:                                            │
│  - query_knowledge_base (your RAG)                          │
│  - web_search                                                │
│  - calculate                                                 │
│  - save_notes                                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   INTERNAL  │    │  EXTERNAL   │    │   WRITER    │
│  RESEARCHER │    │  RESEARCHER │    │             │
│             │    │             │    │ Produces    │
│ Uses: RAG   │    │ Uses: web   │    │ final       │
│ (your docs) │    │ search      │    │ output      │
└─────────────┘    └─────────────┘    └─────────────┘
```

**Core Interface:**

```python
from research_assistant import ResearchAssistant

# Initialize
assistant = ResearchAssistant(
    rag_config="config/rag.yaml",  # Your Week 6 RAG
    llm_model="gpt-4o-mini",
    enable_web_search=True,
    enable_observability=True
)

# Index your knowledge base
assistant.index_documents("./company_docs/")

# Simple research query
result = assistant.research("What's our current refund policy?")
print(result.answer)
print(result.sources)

# Complex research query
result = assistant.research(
    "Compare our pricing strategy to competitor X and recommend adjustments"
)
# Uses: RAG (our pricing), web search (competitor), analysis, synthesis
print(result.answer)
print(result.research_plan)  # Shows what agents did
print(result.sources)  # Internal + external sources

# Trace available
print(result.trace_url)  # Link to LangSmith/LangFuse trace

# With conversation memory
session = assistant.create_session()
result1 = session.research("What are our top 3 products by revenue?")
result2 = session.research("How do their profit margins compare?")  # Remembers context

# Export research
session.export_to_markdown("research_output.md")
```

**Example Workflow:**

```
User: "Research how our customer satisfaction compares to industry 
       benchmarks and identify areas for improvement"

Orchestrator thinks:
  1. Need internal data → Internal Researcher → RAG
  2. Need industry benchmarks → External Researcher → Web Search
  3. Need comparison and recommendations → Analysis + Writer

Execution:
  [Internal Researcher]
  - Queries RAG: "customer satisfaction scores"
  - Queries RAG: "customer feedback themes"
  - Queries RAG: "NPS scores by product"
  
  [External Researcher]
  - Web search: "industry customer satisfaction benchmarks 2024"
  - Web search: "SaaS NPS benchmarks"
  
  [Writer]
  - Synthesizes: comparison table, gap analysis, recommendations

Output:
  - Structured report with internal data, benchmarks, analysis
  - Sources cited (internal docs + web URLs)
  - Trace showing full research path
```

### Success Criteria

**Core Functionality:**

- [ ] Single query → Appropriate tool/agent selection
- [ ] RAG integration working (internal docs searchable)
- [ ] Web search integration working
- [ ] Multi-step research for complex queries
- [ ] Synthesized output from multiple sources

**Agentic Patterns:**

- [ ] Iterative retrieval when initial results insufficient
- [ ] Query decomposition for complex questions
- [ ] Self-verification of answers

**Observability:**

- [ ] Full traces visible in LangSmith/LangFuse
- [ ] Cost per query tracked
- [ ] Latency per step visible
- [ ] Errors captured with context

**Memory & Persistence:**

- [ ] Conversation context maintained within session
- [ ] Can resume research sessions

**Output Quality:**

- [ ] Sources properly cited
- [ ] Internal vs. external sources distinguished
- [ ] Research plan/strategy visible

### Things to Ponder (Post-Build)

1. Your Research Assistant worked great in testing. You deploy it. Users ask questions you never anticipated. Some queries fail, some produce mediocre results. How do you use observability data to systematically improve?
    
2. The assistant uses RAG for internal docs, web search for external. But sometimes internal docs reference external standards ("per ISO 27001..."). Should the assistant automatically fetch external references mentioned in internal docs?
    
3. Research quality varies. Sometimes brilliant, sometimes mediocre. How would you add a quality feedback loop? User ratings? Automated quality checks? How does feedback inform improvement?
    
4. The assistant is slow for complex queries (10+ seconds). Users get impatient. How would you add streaming? Show partial results? Indicate progress? What's the UX for long-running research?
    
5. Looking ahead to Weeks 8-9: This assistant works but isn't "production hardened." What would break under load? What security vulnerabilities exist? What happens when RAG or web search fail? What needs hardening?
    

---

# WEEK 7 CHECKLIST

## Completion Criteria

- [ ] **RAG + Agent Integration:** RAG is a callable tool within agent framework
- [ ] **Conditional Retrieval:** Agent decides when to use RAG vs. other tools
- [ ] **Query Reformulation:** Agent improves queries before RAG retrieval
- [ ] **Agentic RAG:** Iterative retrieval and query decomposition working
- [ ] **Self-Correction:** Agent verifies answers against retrieved context
- [ ] **Observability Setup:** LangSmith or LangFuse configured and receiving traces
- [ ] **Cost Tracking:** Can see cost per query and aggregate costs
- [ ] **Mini Build:** Research Assistant v1 with RAG + agents + observability

## What's Next

**Week 8: LLMOps & Cost Engineering**

- Production logging and monitoring
- Cost optimization strategies
- Caching for performance and cost
- Rate limiting and quotas

**Week 9: Production Hardening**

- Hallucination detection and mitigation
- Error handling and fallbacks
- Security (prompt injection, data leakage)
- Final Build: Production-Ready Research Assistant

---

# NOTES SECTION

### Days 1-2 Notes (RAG + Agent Integration)

### Days 3-4 Notes (Agentic RAG Patterns)

### Days 5-6 Notes (Observability & Tracing)

### Day 7 Notes (Research Assistant v1 Mini Build)