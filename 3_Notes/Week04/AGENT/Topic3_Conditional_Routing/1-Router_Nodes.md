# Router Nodes: LLM-Based Intent Classification

## What is a Router Node?

A **router node** is a decision node that **classifies incoming input and returns a routing signal**, but does not perform the actual work. It answers: "What kind of request is this?" so the graph can branch accordingly.

Unlike action nodes (which execute tools, call APIs, or generate responses), a router node's only job is to **produce a value that conditional edges can consume**.

```
User Query → [Router Node] → "search" | "calculation" | "general" | "escalate"
                                  ↓
                    Conditional edges route to appropriate path
```

## Why LLM-Based Classification?

Simple keyword matching fails in practice:

- "What's 5 times 7?" → calculation (obvious)
- "How much would 5 items cost at $7 each?" → calculation (less obvious)
- "Can you help me figure out the math on this?" → calculation (no numbers mentioned)

An LLM can understand **semantic intent**, not just surface patterns.

## The Pattern: Structured Output for Classification

The router node calls the LLM with a classification prompt and uses **structured output** to get a clean, typed response.

### OpenAI Example

```python
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Literal
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

client = OpenAI()

# 1. Define the classification schema
class IntentClassification(BaseModel):
    """Classification of user intent."""
    intent: Literal["search", "calculation", "general", "escalate"] = Field(
        description="The classified intent category"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score between 0 and 1"
    )
    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )

# 2. Define graph state
class AgentState(TypedDict):
    user_query: str
    intent: str
    confidence: float
    messages: list

# 3. Router node using structured output
def classify_intent(state: AgentState) -> dict:
    """Router node: classifies intent, returns routing signal."""
    
    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": """Classify the user's intent into one of these categories:
                - search: User wants to find information, look something up, or research a topic
                - calculation: User wants math, numbers, computations, or quantitative analysis
                - general: Casual conversation, greetings, simple questions answerable from knowledge
                - escalate: User is frustrated, request is unclear, or requires human help
                
                Be precise. When uncertain, prefer 'general' over wrong classification."""
            },
            {"role": "user", "content": state["user_query"]}
        ],
        text_format=IntentClassification
    )
    
    classification = response.output_parsed
    
    return {
        "intent": classification.intent,
        "confidence": classification.confidence
    }
```

### Anthropic Example

```python
import anthropic
from pydantic import BaseModel, Field
from typing import Literal

client = anthropic.Anthropic()

class IntentClassification(BaseModel):
    intent: Literal["search", "calculation", "general", "escalate"]
    confidence: float
    reasoning: str

def classify_intent_anthropic(state: AgentState) -> dict:
    """Router node using Anthropic's tool use for structured output."""
    
    # Define as a tool for structured extraction
    tools = [{
        "name": "classify_intent",
        "description": "Classify the user's intent into a category",
        "input_schema": IntentClassification.model_json_schema()
    }]
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        system="""You are an intent classifier. Analyze the user message and call 
        the classify_intent tool with the appropriate category:
        - search: Information lookup, research queries
        - calculation: Math, numbers, quantitative analysis  
        - general: Casual conversation, simple knowledge questions
        - escalate: Frustrated user, unclear request, needs human""",
        messages=[{"role": "user", "content": state["user_query"]}],
        tools=tools,
        tool_choice={"type": "tool", "name": "classify_intent"}
    )
    
    # Extract from tool use block
    tool_use = next(block for block in response.content if block.type == "tool_use")
    classification = IntentClassification(**tool_use.input)
    
    return {
        "intent": classification.intent,
        "confidence": classification.confidence
    }
```

## Connecting Router to Conditional Edges

The router node **produces a value**. Conditional edges **consume that value** to decide the next node.

```python
from langgraph.graph import StateGraph, START, END

def route_by_intent(state: AgentState) -> str:
    """Routing function: reads state, returns node name."""
    intent = state["intent"]
    confidence = state["confidence"]
    
    # Low confidence → escalate regardless of classified intent
    if confidence < 0.6:
        return "escalate_node"
    
    # Route based on intent
    routing_map = {
        "search": "search_node",
        "calculation": "calculator_node",
        "general": "general_response_node",
        "escalate": "escalate_node"
    }
    return routing_map.get(intent, "general_response_node")

# Build graph
builder = StateGraph(AgentState)

# Add nodes
builder.add_node("classifier", classify_intent)  # Router node
builder.add_node("search_node", handle_search)
builder.add_node("calculator_node", handle_calculation)
builder.add_node("general_response_node", handle_general)
builder.add_node("escalate_node", handle_escalation)

# Wire it up
builder.add_edge(START, "classifier")

# Conditional edges from classifier
builder.add_conditional_edges(
    "classifier",                    # Source node
    route_by_intent,                 # Routing function
    {                                # Mapping: return value → node name
        "search_node": "search_node",
        "calculator_node": "calculator_node",
        "general_response_node": "general_response_node",
        "escalate_node": "escalate_node"
    }
)

# All paths end
builder.add_edge("search_node", END)
builder.add_edge("calculator_node", END)
builder.add_edge("general_response_node", END)
builder.add_edge("escalate_node", END)

graph = builder.compile()
```

## Prompt Design for Intent Classification

### Principle 1: Exhaustive Categories

Every possible input must map to exactly one category. Add a catch-all.

```python
# Bad: What happens to "Tell me a joke"?
categories = ["search", "calculation"]

# Good: Explicit fallback
categories = ["search", "calculation", "general"]  # general catches everything else
```

### Principle 2: Clear Boundaries

Ambiguous boundaries cause inconsistent routing.

```python
# Bad: Overlapping definitions
"""
- information: User wants information
- question: User asks a question
"""

# Good: Mutually exclusive
"""
- search: User wants to find EXTERNAL information (web, documents, databases)
- knowledge: User wants to use YOUR EXISTING knowledge (no lookup needed)
"""
```

### Principle 3: Examples in Prompt

Few-shot examples dramatically improve classification accuracy.

```python
system_prompt = """Classify user intent:

Categories:
- search: External lookup needed
- calculation: Math/numbers required
- general: Conversational, use existing knowledge

Examples:
- "What's the weather in Tokyo?" → search (external API needed)
- "What is 15% of 230?" → calculation
- "What is photosynthesis?" → general (basic knowledge)
- "Find recent news about AI" → search
- "How many days until Christmas?" → calculation
"""
```

## Confidence-Based Routing

Don't just route on intent—use confidence to add safety nets.

```python
def route_with_confidence(state: AgentState) -> str:
    intent = state["intent"]
    confidence = state["confidence"]
    
    if confidence < 0.5:
        # Very uncertain → ask for clarification
        return "clarification_node"
    elif confidence < 0.7:
        # Somewhat uncertain → use safe default
        return "general_response_node"
    else:
        # Confident → route to specialized handler
        return f"{intent}_node"
```

## Multi-Level Classification

For complex domains, use hierarchical classification:

```python
class PrimaryIntent(BaseModel):
    category: Literal["support", "sales", "technical", "other"]

class SupportIntent(BaseModel):
    subcategory: Literal["billing", "account", "complaint", "question"]

def two_stage_classifier(state: AgentState) -> dict:
    # Stage 1: Primary classification
    primary = classify_primary(state["user_query"])
    
    # Stage 2: If support, classify subcategory
    if primary.category == "support":
        secondary = classify_support(state["user_query"])
        return {"intent": f"support_{secondary.subcategory}"}
    
    return {"intent": primary.category}
```

## Key Takeaways

1. **Router nodes classify, they don't act** — Keep them focused on producing routing signals
2. **Use structured output** — Pydantic models ensure clean, typed classification results
3. **Confidence matters** — Route uncertain classifications to safe fallbacks
4. **Prompt design is critical** — Exhaustive categories, clear boundaries, and examples
5. **The routing function reads state** — It doesn't call the LLM; it just maps state values to node names

---

**Next:** Note 2 covers `Command` — how to combine state updates with routing in a single return.

_Sources: LangGraph docs (docs.langchain.com/oss/python/langgraph), OpenAI Responses API docs, Anthropic Messages API docs_