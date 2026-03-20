# Note 3: Conditional Retrieval — When to Use RAG

## The Routing Problem

With RAG as a tool, the agent _can_ use it. But when _should_ it?

The naive approach: let the LLM decide every time. The problem: the LLM invokes tools through an inference call. If the LLM decides on every query, you're paying for that reasoning whether the decision was obvious or not.

```
User: "What's 2 + 2?"
        │
        ▼
┌──────────────────────────────────┐
│          LLM Reasoning           │  ← ~300ms, ~500 tokens
│                                  │
│  "Let me consider my tools...   │
│   calculator, knowledge_base,    │
│   web_search... This is math,    │
│   I should use calculator."      │
└──────────────────────────────────┘
        │
        ▼
    Calculator returns: 4
```

For obvious cases, this reasoning step is waste. For ambiguous cases, it's necessary. The goal is to route obvious cases cheaply and reserve LLM reasoning for the hard decisions.

---

## Query Classification Approaches

Three approaches, each with different cost/accuracy trade-offs:

### Approach 1: Rule-Based Classification

Fast, cheap, but brittle. Use keyword matching, regex, or simple heuristics.

```python
import re
from typing import Literal

QueryIntent = Literal["rag", "calculator", "web_search", "general"]

def classify_query_rules(query: str) -> QueryIntent:
    """
    Rule-based query classification.
    Fast but misses nuance and edge cases.
    """
    query_lower = query.lower()
    
    # Calculator patterns
    math_patterns = [
        r'\d+\s*[\+\-\*\/\%]\s*\d+',  # "15 + 20"
        r'calculate',
        r'what is \d+',
        r'compute',
        r'percentage of',
    ]
    for pattern in math_patterns:
        if re.search(pattern, query_lower):
            return "calculator"
    
    # RAG patterns (company/internal info)
    rag_keywords = [
        'our policy', 'our company', 'internal', 
        'procedure', 'employee handbook', 'benefits',
        'vacation', 'pto', 'expense', 'reimbursement',
        'onboarding', 'compliance', 'security policy',
    ]
    for keyword in rag_keywords:
        if keyword in query_lower:
            return "rag"
    
    # Web search patterns
    web_patterns = [
        r'latest news',
        r'current price',
        r'what happened',
        r'today\'s',
        r'recent',
    ]
    for pattern in web_patterns:
        if re.search(pattern, query_lower):
            return "web_search"
    
    # Default to general (LLM handles without tools)
    return "general"
```

**Pros:**

- Zero latency overhead
- No token cost
- Predictable behavior

**Cons:**

- Brittle: "What's the vacation policy?" works, "How much time off do I get?" doesn't
- Maintenance burden: keywords grow over time
- No semantic understanding

**When to use:**

- High-volume, latency-sensitive applications
- Queries follow predictable patterns
- You can enumerate the query space

### Approach 2: LLM-Based Classification

Accurate, flexible, but adds latency and cost. Use a small model or the main model with a classification prompt.

```python
# Doc reference: https://docs.langchain.com/oss/python/langchain/structured-output

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Literal

class QueryClassification(BaseModel):
    """Classification result for routing queries."""
    intent: Literal["rag", "calculator", "web_search", "general"] = Field(
        description="The type of query"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in this classification"
    )
    reasoning: str = Field(
        description="Brief explanation of why this classification"
    )

# Use a smaller, faster model for classification
classifier_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
classifier = classifier_llm.with_structured_output(QueryClassification)

CLASSIFICATION_PROMPT = """Classify this user query into one of these categories:

- rag: Questions about internal company information, policies, procedures, 
  documentation, or anything that would be in an internal knowledge base
- calculator: Mathematical calculations, percentages, conversions
- web_search: Current events, news, real-time information, external data
- general: General knowledge questions that don't need external tools

Query: {query}

Classify this query. Be precise about the intent."""

def classify_query_llm(query: str) -> QueryClassification:
    """
    LLM-based query classification.
    More accurate but adds ~200-500ms latency.
    """
    result = classifier.invoke(CLASSIFICATION_PROMPT.format(query=query))
    return result

# Example usage
result = classify_query_llm("How much PTO do I accrue per month?")
# QueryClassification(intent='rag', confidence=0.95, 
#                     reasoning='Asking about PTO accrual, which is company policy')
```

**Pros:**

- Semantic understanding: handles paraphrasing
- Handles edge cases better
- Returns confidence scores

**Cons:**

- Adds 200-500ms latency
- Costs tokens (~100-200 per classification)
- Still imperfect

**When to use:**

- Query patterns are diverse and unpredictable
- Accuracy matters more than latency
- Ambiguous queries are common

### Approach 3: Hybrid Classification

Rules for obvious cases, LLM for ambiguous ones. Best of both worlds.

```python
from typing import Optional

def classify_query_hybrid(query: str) -> tuple[QueryIntent, float]:
    """
    Hybrid classification: rules first, LLM for ambiguous cases.
    
    Returns (intent, confidence)
    """
    query_lower = query.lower()
    
    # High-confidence rule-based patterns (skip LLM entirely)
    
    # Math: very clear patterns
    if re.match(r'^\d+\s*[\+\-\*\/]\s*\d+$', query.strip()):
        return ("calculator", 1.0)
    
    if query_lower.startswith("calculate "):
        return ("calculator", 0.95)
    
    # Company-specific: clear internal references
    company_signals = ["our company", "my manager", "hr department", "employee id"]
    if any(signal in query_lower for signal in company_signals):
        return ("rag", 0.9)
    
    # Current events: clear temporal signals
    if any(word in query_lower for word in ["today's", "latest", "breaking"]):
        return ("web_search", 0.9)
    
    # Ambiguous: fall back to LLM
    # These queries could go multiple ways
    ambiguous_signals = [
        "policy",      # Company policy? General policy question?
        "how do i",    # Internal process? General knowledge?
        "what is the", # Could be anything
    ]
    
    needs_llm = any(signal in query_lower for signal in ambiguous_signals)
    
    if needs_llm or True:  # For safety, always use LLM for uncertain cases
        # But only for queries that aren't clearly matched above
        if not _has_strong_signal(query_lower):
            llm_result = classify_query_llm(query)
            return (llm_result.intent, llm_result.confidence)
    
    # Default fallback
    return ("general", 0.5)

def _has_strong_signal(query_lower: str) -> bool:
    """Check if query has strong signals for any category."""
    # Implementation: count keyword matches, return True if strong match
    return False
```

**Hybrid Strategy:**

```
Query arrives
     │
     ▼
┌────────────────────┐
│  Rule-based check  │  ← ~0ms
│                    │
│ Strong signal? ────┼──→ Yes: Return immediately
│                    │
│ No strong signal   │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  LLM classifier    │  ← ~300ms (only for ambiguous)
│                    │
└────────────────────┘
```

---

## Routing Decision Framework

When the classifier returns an intent, where should the query go?

|Query Type|Route To|Reasoning|
|---|---|---|
|Internal/company info|RAG tool|Private knowledge not in LLM training|
|Policies, procedures|RAG tool|Company-specific documentation|
|General knowledge|LLM directly|"What is photosynthesis?" — no tool needed|
|Math/calculations|Calculator tool|Deterministic, no hallucination risk|
|Current events|Web search tool|LLM knowledge is outdated|
|Code execution|Code interpreter|Need actual execution, not generation|
|External company info|Web search tool|"What's Apple's stock price?"|

### Multi-Signal Queries

Some queries need multiple tools:

```
"Compare our Q3 revenue to Apple's"
     │
     ▼
┌─────────────────────────────────────────────┐
│ This needs:                                  │
│ 1. RAG tool for "our Q3 revenue"            │
│ 2. Web search for "Apple Q3 revenue"         │
│ 3. LLM reasoning to compare                  │
└─────────────────────────────────────────────┘
```

The classifier should recognize this and route to a planning node, not directly to a single tool. This is covered more in Note 5.

---

## Implementing Routing in LangGraph

**Doc reference:** [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) — Conditional Edges section

### Architecture: Classification Node + Conditional Routing

```
┌─────────┐     ┌────────────┐     ┌─────────────────────┐
│  START  │────▶│ Classifier │────▶│ Conditional Routing │
└─────────┘     └────────────┘     └─────────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
              ┌─────────┐            ┌─────────────┐         ┌──────────┐
              │   RAG   │            │ Web Search  │         │ LLM Only │
              │  Tool   │            │    Tool     │         │ (no tool)│
              └─────────┘            └─────────────┘         └──────────┘
                    │                       │                       │
                    └───────────────────────┼───────────────────────┘
                                            │
                                            ▼
                                       ┌─────────┐
                                       │ Response│
                                       │ Builder │
                                       └─────────┘
```

### Implementation

```python
# Doc reference: https://docs.langchain.com/oss/python/langgraph/graph-api
# Sections: "Conditional edges", "StateGraph"

from typing import TypedDict, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# State schema
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query_intent: str  # "rag", "calculator", "web_search", "general"
    intent_confidence: float
    rag_result: str | None
    web_result: str | None

# Classification node
def classify_node(state: AgentState) -> dict:
    """Classify the incoming query to determine routing."""
    last_message = state["messages"][-1]
    query = last_message.content
    
    # Use hybrid classification
    intent, confidence = classify_query_hybrid(query)
    
    return {
        "query_intent": intent,
        "intent_confidence": confidence
    }

# Routing function for conditional edges
def route_by_intent(state: AgentState) -> Literal["rag_node", "web_node", "calculator_node", "direct_response"]:
    """Route to appropriate tool based on classification."""
    intent = state["query_intent"]
    
    routing_map = {
        "rag": "rag_node",
        "web_search": "web_node",
        "calculator": "calculator_node",
        "general": "direct_response",
    }
    
    return routing_map.get(intent, "direct_response")

# Tool nodes
def rag_node(state: AgentState) -> dict:
    """Execute RAG retrieval."""
    query = state["messages"][-1].content
    result = query_knowledge_base.invoke({"query": query})
    return {"rag_result": result}

def web_node(state: AgentState) -> dict:
    """Execute web search."""
    query = state["messages"][-1].content
    result = web_search.invoke({"query": query})
    return {"web_result": result}

def calculator_node(state: AgentState) -> dict:
    """Execute calculation."""
    query = state["messages"][-1].content
    result = calculator.invoke({"expression": query})
    return {"messages": [AIMessage(content=f"Result: {result}")]}

def direct_response(state: AgentState) -> dict:
    """Generate response directly from LLM without tools."""
    query = state["messages"][-1].content
    response = llm.invoke(f"Answer this question: {query}")
    return {"messages": [AIMessage(content=response.content)]}

def response_builder(state: AgentState) -> dict:
    """Build final response from tool results."""
    # Combine results and format response
    context = ""
    if state.get("rag_result"):
        context += f"From knowledge base:\n{state['rag_result']}\n\n"
    if state.get("web_result"):
        context += f"From web search:\n{state['web_result']}\n\n"
    
    query = state["messages"][-1].content
    prompt = f"Based on this context:\n{context}\nAnswer: {query}"
    response = llm.invoke(prompt)
    
    return {"messages": [AIMessage(content=response.content)]}

# Build the graph
builder = StateGraph(AgentState)

# Add nodes
builder.add_node("classifier", classify_node)
builder.add_node("rag_node", rag_node)
builder.add_node("web_node", web_node)
builder.add_node("calculator_node", calculator_node)
builder.add_node("direct_response", direct_response)
builder.add_node("response_builder", response_builder)

# Add edges
builder.add_edge(START, "classifier")

# Conditional routing after classification
builder.add_conditional_edges(
    "classifier",
    route_by_intent,
    {
        "rag_node": "rag_node",
        "web_node": "web_node",
        "calculator_node": "calculator_node",
        "direct_response": "direct_response",
    }
)

# Tool nodes go to response builder
builder.add_edge("rag_node", "response_builder")
builder.add_edge("web_node", "response_builder")
builder.add_edge("calculator_node", END)  # Calculator returns directly
builder.add_edge("direct_response", END)
builder.add_edge("response_builder", END)

# Compile
graph = builder.compile()
```

### Using `Command` for Combined Updates

When you need to both update state and route in one step, use `Command`:

```python
# Doc reference: https://docs.langchain.com/oss/python/langgraph/graph-api
# Section: "Command"

from langgraph.types import Command
from typing import Literal

def classify_and_route(state: AgentState) -> Command[Literal["rag_node", "web_node", "direct_response"]]:
    """Classify query and route in a single step using Command."""
    last_message = state["messages"][-1]
    query = last_message.content
    
    intent, confidence = classify_query_hybrid(query)
    
    # Map intent to node
    routing_map = {
        "rag": "rag_node",
        "web_search": "web_node",
        "general": "direct_response",
    }
    next_node = routing_map.get(intent, "direct_response")
    
    return Command(
        update={
            "query_intent": intent,
            "intent_confidence": confidence,
        },
        goto=next_node
    )
```

---

## Handling Low-Confidence Retrieval

RAG doesn't always find relevant documents. When retrieval confidence is low, what should the agent do?

### The Problem

```
Query: "What's our policy on bringing pets to work?"

RAG returns:
- No exact match found
- Best result: "Office dress code policy" (relevance: 0.31)
- Confidence: 0.25
```

### Decision Options

|Option|When to Use|Implementation|
|---|---|---|
|**Use anyway**|Information is better than nothing|Return with caveat: "I found related info but not an exact match..."|
|**Tell user not found**|User should know limits|"I couldn't find information about pets in the office in our knowledge base."|
|**Reformulate and retry**|Query might be poorly phrased|Try: "pet policy", "animals in office", "pet-friendly workplace"|
|**Fall back to web search**|External info might help|Search web for "corporate pet policy best practices"|
|**Escalate to human**|Critical query, can't answer confidently|"I'm not sure about this. Let me connect you with HR."|

### Implementation: Post-RAG Decision Logic

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class RAGResult:
    answer: str
    sources: list[dict]
    confidence: float
    query_used: str

@dataclass  
class RAGDecision:
    action: Literal["use", "not_found", "retry", "fallback", "escalate"]
    response: str | None = None
    retry_query: str | None = None

def decide_on_rag_result(
    result: RAGResult,
    original_query: str,
    retry_count: int = 0
) -> RAGDecision:
    """
    Decide what to do with RAG results based on confidence.
    """
    # High confidence: use the result
    if result.confidence >= 0.7:
        return RAGDecision(action="use")
    
    # Medium confidence: use with caveat
    if result.confidence >= 0.4:
        response = (
            f"Based on what I found (though not a perfect match):\n\n"
            f"{result.answer}\n\n"
            f"Note: This answer is based on related documents. "
            f"If you need more specific information, please rephrase your question."
        )
        return RAGDecision(action="use", response=response)
    
    # Low confidence: try strategies
    if retry_count < 2:
        # Generate reformulated query
        retry_query = reformulate_query(original_query, result.query_used)
        if retry_query != original_query:
            return RAGDecision(action="retry", retry_query=retry_query)
    
    # Very low confidence after retries: acknowledge not found
    if result.confidence < 0.2:
        response = (
            f"I couldn't find information about '{original_query}' "
            f"in our knowledge base. This topic may not be covered in our "
            f"documentation, or you might try rephrasing your question."
        )
        return RAGDecision(action="not_found", response=response)
    
    # Fallback to web search for general context
    return RAGDecision(action="fallback")

def reformulate_query(original: str, tried: str) -> str:
    """Generate alternative query phrasing."""
    # Simple heuristic: use LLM to rephrase
    prompt = f"""
    The query "{tried}" didn't find good results in a document database.
    Generate an alternative query that might find relevant documents.
    
    Original user question: {original}
    
    Alternative query (just the query, nothing else):
    """
    return llm.invoke(prompt).content.strip()
```

### Integrating Decision Logic into the Graph

```python
def rag_node_with_decision(state: AgentState) -> Command[Literal["response_builder", "retry_rag", "web_fallback", "not_found_response"]]:
    """
    RAG node that makes decisions based on retrieval quality.
    """
    query = state["messages"][-1].content
    retry_count = state.get("rag_retry_count", 0)
    
    # Execute RAG
    result = execute_rag(query)
    
    # Decide what to do
    decision = decide_on_rag_result(result, query, retry_count)
    
    if decision.action == "use":
        return Command(
            update={
                "rag_result": decision.response or result.answer,
                "rag_confidence": result.confidence,
            },
            goto="response_builder"
        )
    
    elif decision.action == "retry":
        return Command(
            update={
                "rag_retry_count": retry_count + 1,
                "rag_query": decision.retry_query,
            },
            goto="retry_rag"
        )
    
    elif decision.action == "fallback":
        return Command(
            update={"fallback_reason": "low_rag_confidence"},
            goto="web_fallback"
        )
    
    else:  # not_found
        return Command(
            update={"rag_result": decision.response},
            goto="not_found_response"
        )
```

---

## Confidence Thresholds: Production Considerations

Confidence thresholds should be tuned based on your data and use case.

### Tuning Guidelines

|Scenario|Recommended Threshold|Reasoning|
|---|---|---|
|High-stakes (legal, medical)|0.8+|Better to say "I don't know" than be wrong|
|Customer support|0.5-0.7|Some answer is often better than none|
|Internal productivity|0.4-0.6|Users can verify and provide feedback|
|Research/exploration|0.3-0.5|Low threshold + show sources for user judgment|

### Measuring and Improving

Track these metrics:

1. **Routing accuracy**: % of queries routed to correct tool
2. **False negatives**: Queries that should have used RAG but didn't
3. **False positives**: Queries that used RAG unnecessarily
4. **Confidence calibration**: Does 80% confidence mean 80% accuracy?

```python
# Logging for analysis
import logging

logger = logging.getLogger(__name__)

def log_routing_decision(
    query: str,
    intent: str,
    confidence: float,
    rag_used: bool,
    rag_confidence: float | None,
    user_feedback: str | None = None
):
    """Log routing decisions for later analysis."""
    logger.info({
        "event": "routing_decision",
        "query": query[:100],
        "intent": intent,
        "intent_confidence": confidence,
        "rag_used": rag_used,
        "rag_confidence": rag_confidence,
        "user_feedback": user_feedback,
    })
```

---

## Summary

|Aspect|Rule-Based|LLM-Based|Hybrid|
|---|---|---|---|
|Latency|~0ms|200-500ms|0-500ms|
|Cost|None|~200 tokens|Variable|
|Accuracy|Low-Medium|High|High|
|Maintenance|High|Low|Medium|
|Best for|Predictable queries|Diverse queries|Production systems|

**Decision flow for RAG routing:**

1. **Classify** the query (rule-based, LLM, or hybrid)
2. **Route** to appropriate tool(s) via conditional edges
3. **Execute** the tool (RAG, web search, calculator, etc.)
4. **Evaluate** result confidence
5. **Decide** next action (use, retry, fallback, or acknowledge failure)
6. **Respond** to user with appropriate caveats if needed

**What's Next:**

- **Note 4**: Query reformulation (improving what we send to RAG)
- **Note 5**: Multi-tool orchestration (combining RAG with other tools)