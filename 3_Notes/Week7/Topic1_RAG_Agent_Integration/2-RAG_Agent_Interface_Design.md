# Note 2: RAG as an Agent Tool — Interface Design

## The Goal: Make RAG Callable by an Agent

Your RAG system exists. Now you need to expose it as a tool the agent can invoke. This means:

1. Wrapping RAG in a function with a clear signature
2. Decorating it so LangChain/LangGraph recognizes it as a tool
3. Designing the interface (what goes in, what comes out)
4. Writing a description that helps the agent decide when to use it

---

## Creating Tools with `@tool` Decorator

**Doc source**: [LangChain Tools Documentation](https://docs.langchain.com/oss/python/langchain/tools) (current as of March 2025)

The `@tool` decorator transforms a Python function into a tool the agent can call. The function's docstring becomes the tool description, and type hints define the input schema.

```python
# Doc reference: https://docs.langchain.com/oss/python/langchain/tools
# Section: "Basic tool definition"

from langchain.tools import tool

@tool
def query_knowledge_base(query: str) -> str:
    """Search the company knowledge base for information.
    
    Use this for questions about internal policies, procedures,
    product documentation, and company-specific information.
    
    Args:
        query: The search query to find relevant documents
    """
    # Your RAG implementation here
    result = rag.query(query)
    return f"Answer: {result.answer}\n\nSources: {result.sources}"
```

Key requirements from the docs:

- **Type hints are required** — they define the tool's input schema
- **Docstring becomes the description** — the agent uses this to decide when to invoke the tool
- **Function name becomes tool name** — prefer `snake_case` for compatibility across providers

---

## Interface Design: Simple vs Rich

The most important design decision: how much control do you expose to the agent?

### Option 1: Simple Interface

```python
@tool
def query_knowledge_base(query: str) -> str:
    """Search internal company documents for information.
    
    Use for questions about policies, procedures, documentation,
    or any company-specific information.
    
    Args:
        query: Natural language search query
    """
    result = rag.query(query)
    return format_result(result)
```

**Characteristics:**

- Single input: the query string
- Single output: formatted text response
- RAG controls all retrieval parameters internally

**When to use:**

- Agent doesn't need fine-grained retrieval control
- You want predictable, consistent RAG behavior
- Simpler tool schema = fewer tokens, less confusion

### Option 2: Rich Interface

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class KnowledgeBaseQuery(BaseModel):
    """Input schema for knowledge base queries."""
    query: str = Field(description="Natural language search query")
    department: Optional[str] = Field(
        default=None,
        description="Filter by department: 'engineering', 'hr', 'legal', 'sales'"
    )
    doc_type: Optional[Literal["policy", "procedure", "technical", "all"]] = Field(
        default="all",
        description="Type of document to search"
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results to retrieve"
    )

@tool(args_schema=KnowledgeBaseQuery)
def query_knowledge_base(
    query: str,
    department: Optional[str] = None,
    doc_type: str = "all",
    max_results: int = 5
) -> dict:
    """Search internal company documents with filtering options.
    
    Use for questions about policies, procedures, documentation,
    or any company-specific information. Use filters to narrow
    results when you know the relevant department or document type.
    
    Returns structured results with answer, sources, and confidence.
    """
    result = rag.query(
        query,
        filters={"department": department, "doc_type": doc_type},
        k=max_results
    )
    return {
        "answer": result.answer,
        "sources": result.sources,
        "confidence": result.confidence,
        "chunk_ids": result.chunk_ids
    }
```

**Characteristics:**

- Multiple inputs with constraints (Pydantic validation)
- Structured output (dict instead of string)
- Agent can control retrieval behavior

**When to use:**

- Agent needs to filter by metadata (department, date, type)
- You want the agent to adjust retrieval aggressiveness
- Downstream logic needs structured fields (confidence scores, chunk IDs)

### The Trade-off

|Aspect|Simple|Rich|
|---|---|---|
|Token cost|Lower (smaller schema)|Higher (larger schema)|
|Agent confusion risk|Lower|Higher (more params to get wrong)|
|Flexibility|Lower|Higher|
|Error surface|Smaller|Larger (more params to validate)|
|Debugging|Easier|Harder|

**Recommendation**: Start with simple. Add parameters only when you observe the agent needing them. Over-parameterization creates more problems than it solves.

---

## What Metadata to Return to the Agent

The agent receives your tool's return value and decides what to do next. What you return shapes those decisions.

### Minimal Return (String)

```python
@tool
def query_knowledge_base(query: str) -> str:
    """Search internal documents."""
    result = rag.query(query)
    return result.answer
```

The agent sees only the answer. No sources, no confidence, no ability to verify or follow up.

### Informative Return (Structured)

```python
@tool  
def query_knowledge_base(query: str) -> str:
    """Search internal documents. Returns answer with sources."""
    result = rag.query(query)
    
    response = f"Answer: {result.answer}\n\n"
    response += "Sources:\n"
    for source in result.sources:
        response += f"- {source['title']} (relevance: {source['score']:.2f})\n"
    response += f"\nConfidence: {result.confidence:.2f}"
    
    return response
```

Now the agent can:

- Cite sources in its response to the user
- Judge whether to trust the answer (low confidence → maybe search again)
- Identify which documents to drill into

### Fully Structured Return (Dict)

```python
@tool
def query_knowledge_base(query: str) -> dict:
    """Search internal documents. Returns structured results."""
    result = rag.query(query)
    
    return {
        "answer": result.answer,
        "confidence": result.confidence,
        "sources": [
            {
                "title": s["title"],
                "chunk_id": s["chunk_id"],
                "relevance_score": s["score"],
                "snippet": s["snippet"][:200]
            }
            for s in result.sources
        ],
        "query_used": result.query,  # After any query transformation
        "retrieval_time_ms": result.latency
    }
```

**When structured dict is valuable:**

- `chunk_ids`: Agent can request specific chunks for follow-up
- `confidence`: Agent can decide to re-query or acknowledge uncertainty
- `query_used`: Agent can see how RAG interpreted its query
- `relevance_scores`: Agent can filter low-relevance results

**Caution**: Structured returns cost more tokens. The entire dict gets serialized into the conversation. Only include fields the agent will actually use.

---

## Tool Description Design: How the Agent Decides

The tool description is not documentation for humans. It's the instruction the LLM uses to decide whether to call this tool.

### Bad Description

```python
@tool
def query_knowledge_base(query: str) -> str:
    """Search documents."""
    ...
```

Problems:

- What documents? The agent doesn't know this is for internal/company docs
- When should it use this vs web search?
- What kind of queries work well?

### Good Description

```python
@tool
def query_knowledge_base(query: str) -> str:
    """Search the company's internal knowledge base for information.
    
    Use this tool for:
    - Company policies (HR, legal, security, compliance)
    - Internal procedures and processes
    - Product documentation and specifications
    - Historical decisions and meeting notes
    - Employee handbook and benefits information
    
    Do NOT use for:
    - General knowledge questions (use your training data)
    - Current events or news (use web search)
    - Information about external companies (use web search)
    
    Args:
        query: Natural language search query. Be specific and include
               relevant context (department, date range, project name)
               for better results.
    """
    ...
```

### Description Design Principles

1. **State the domain explicitly**: "company's internal knowledge base"
2. **List positive examples**: When TO use this tool
3. **List negative examples**: When NOT to use this tool
4. **Guide query construction**: What makes a good query

### Description Length Trade-off

Longer descriptions = more tokens per inference = higher cost.

But under-specified descriptions = wrong tool selection = wasted tool calls = even higher cost.

**Find the minimum description that achieves correct routing.** Test with diverse queries and observe when the agent makes wrong choices.

---

## Error Handling in the Tool Wrapper

Tools fail. RAG returns nothing. Vectors stores timeout. What does the agent see?

### Don't: Throw Exceptions

```python
@tool
def query_knowledge_base(query: str) -> str:
    """Search internal documents."""
    result = rag.query(query)  # Might throw!
    return result.answer
```

If `rag.query()` throws, the agent sees an error message it can't act on. Depending on your error handling configuration, the agent might retry indefinitely or give up entirely.

### Do: Return Informative "No Results" Response

```python
@tool
def query_knowledge_base(query: str) -> str:
    """Search internal documents."""
    try:
        result = rag.query(query)
        
        if not result.sources:
            return (
                "No relevant documents found for this query. "
                "Try rephrasing with different keywords, or this "
                "information may not exist in the knowledge base."
            )
        
        if result.confidence < 0.3:
            return (
                f"Found some documents but confidence is low ({result.confidence:.0%}). "
                f"Best match: {result.answer}\n"
                "Consider rephrasing or this may not be the right source."
            )
        
        return format_successful_result(result)
        
    except TimeoutError:
        return (
            "Knowledge base search timed out. "
            "Try a simpler query or try again later."
        )
    except Exception as e:
        return (
            f"Knowledge base search encountered an error: {type(e).__name__}. "
            "Try rephrasing your query or use alternative sources."
        )
```

Now the agent receives actionable information:

- "No documents found" → Agent can try different query or acknowledge to user
- "Low confidence" → Agent can caveat its response
- "Timed out" → Agent can retry or inform user of delay

### Error Response Principles

1. **Never return empty string** — agent needs information to proceed
2. **Explain what happened** — not technical details, but the situation
3. **Suggest alternatives** — what could the agent try next?
4. **Keep it concise** — don't waste tokens on error explanations

---

## LangGraph Integration: Adding RAG Tool to Your Agent

**Doc source**: [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents), [LangGraph ToolNode](https://docs.langchain.com/oss/python/langgraph/overview)

### Using `create_agent` (Recommended for Standard Cases)

```python
# Doc reference: https://docs.langchain.com/oss/python/langchain/agents
# Section: "Static tools"

from langchain.agents import create_agent
from langchain.tools import tool

# Define your RAG tool
@tool
def query_knowledge_base(query: str) -> str:
    """Search internal company documents for policies, procedures, 
    and company-specific information.
    
    Args:
        query: Natural language search query
    """
    result = rag.query(query)
    return format_result(result)

# Define other tools
@tool
def calculator(expression: str) -> str:
    """Evaluate mathematical expressions."""
    return str(eval(expression))

@tool  
def get_current_date() -> str:
    """Get today's date."""
    from datetime import date
    return date.today().isoformat()

# Create agent with all tools
agent = create_agent(
    model="gpt-4o",  # or ChatOpenAI instance
    tools=[query_knowledge_base, calculator, get_current_date],
    system_prompt="""You are a helpful assistant with access to the company 
    knowledge base, a calculator, and date information. Use the appropriate 
    tool for each query."""
)

# Invoke the agent
result = agent.invoke({
    "messages": [{"role": "user", "content": "What's our vacation policy?"}]
})
```

### Using `ToolNode` Directly (For Custom Graphs)

When you need more control over the agent graph structure:

```python
# Doc reference: https://docs.langchain.com/oss/python/langchain/tools
# Section: "ToolNode"

from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_openai import ChatOpenAI

# Define tools
tools = [query_knowledge_base, calculator, get_current_date]

# Create model with tools bound
model = ChatOpenAI(model="gpt-4o")
model_with_tools = model.bind_tools(tools)

# Define the agent node
def call_model(state: MessagesState):
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}

# Create the ToolNode
tool_node = ToolNode(tools)

# Build the graph
builder = StateGraph(MessagesState)
builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)  # Routes to "tools" or END
builder.add_edge("tools", "agent")

graph = builder.compile()

# Run the agent
result = graph.invoke({
    "messages": [{"role": "user", "content": "What's our vacation policy?"}]
})
```

### `tools_condition` Routing

The `tools_condition` function checks if the last message contains tool calls:

- If yes → routes to `"tools"` node
- If no → routes to `END`

This creates the standard agent loop: LLM → (tool calls?) → execute tools → LLM → ... → END

---

## Complete Example: RAG Tool Wrapper

Putting it all together:

```python
# Doc reference: https://docs.langchain.com/oss/python/langchain/tools
# Sections: "Basic tool definition", "Customize tool properties"

from langchain.tools import tool
from langchain.agents import create_agent
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RAGToolWrapper:
    """Wrapper to expose RAG system as an agent tool."""
    
    def __init__(self, rag_system, include_confidence: bool = True):
        self.rag = rag_system
        self.include_confidence = include_confidence
    
    def create_tool(self):
        """Create the tool with closure over RAG instance."""
        rag = self.rag
        include_confidence = self.include_confidence
        
        @tool
        def query_knowledge_base(query: str) -> str:
            """Search the company's internal knowledge base.
            
            Use for questions about:
            - Company policies (HR, legal, security, compliance)
            - Internal procedures and processes  
            - Product documentation and specifications
            - Historical decisions and meeting notes
            
            Do NOT use for general knowledge or external information.
            
            Args:
                query: Natural language search query. Be specific.
            """
            try:
                result = rag.query(query)
                
                # Handle no results
                if not result.sources:
                    return (
                        "No relevant documents found in the knowledge base. "
                        "Try different keywords or this information may not exist internally."
                    )
                
                # Format response
                response = f"Answer: {result.answer}\n\n"
                response += "Sources:\n"
                for i, source in enumerate(result.sources[:3], 1):
                    response += f"{i}. {source['title']}"
                    if 'relevance' in source:
                        response += f" (relevance: {source['relevance']:.0%})"
                    response += "\n"
                
                if include_confidence:
                    confidence_level = (
                        "high" if result.confidence > 0.7 
                        else "medium" if result.confidence > 0.4 
                        else "low"
                    )
                    response += f"\nConfidence: {confidence_level}"
                
                return response
                
            except TimeoutError:
                logger.warning(f"RAG timeout for query: {query[:50]}...")
                return "Knowledge base search timed out. Try a simpler query."
                
            except Exception as e:
                logger.error(f"RAG error for query: {query[:50]}...", exc_info=True)
                return f"Knowledge base search failed. Try rephrasing your query."
        
        return query_knowledge_base


# Usage
from your_rag_system import RAG

rag = RAG.from_config("config/default.yaml")
wrapper = RAGToolWrapper(rag)
rag_tool = wrapper.create_tool()

# Create agent with RAG tool
agent = create_agent(
    model="gpt-4o",
    tools=[rag_tool],
    system_prompt="You are a helpful assistant with access to the company knowledge base."
)
```

---

## Summary

|Decision|Recommendation|
|---|---|
|Interface complexity|Start simple, add params only when needed|
|Return type|String with structured content for most cases; dict only if agent needs to parse fields|
|What to return|Answer + sources + confidence level|
|Description|Explicit domain + positive examples + negative examples + query guidance|
|Error handling|Never throw; return informative "no results" with suggestions|
|Integration|`create_agent` for standard cases; `ToolNode` for custom graphs|

**What's Next:**

- **Note 3**: When to route to RAG (conditional retrieval logic)
- **Note 4**: Query reformulation before RAG
- **Note 5**: Combining RAG with other tools