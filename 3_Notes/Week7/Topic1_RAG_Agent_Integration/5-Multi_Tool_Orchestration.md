# Note 5: Multi-Tool Orchestration with RAG

## The Multi-Tool Reality

Real questions rarely map to a single tool:

|User Question|Tools Needed|
|---|---|
|"Compare our pricing to competitors"|RAG (internal pricing) + Web Search (competitors)|
|"Calculate the ROI if we adopt the new policy"|RAG (policy details) + Calculator (ROI math)|
|"Summarize our Q3 report and find industry benchmarks"|RAG (Q3 report) + Web Search (benchmarks)|
|"What's the deadline for the project, and how many days until then?"|RAG (project deadline) + Calculator (days remaining)|

The agent must:

1. **Decompose** the question into sub-tasks
2. **Map** sub-tasks to tools
3. **Execute** tools (sequentially or in parallel)
4. **Aggregate** results into a coherent response

---

## Example Walkthrough: "Compare Our Pricing to Competitors"

Let's trace how an agent handles this multi-tool query:

```
User: "Compare our pricing to competitors"
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│                    AGENT                             │
│                                                      │
│  Step 1: Decompose                                   │
│  ├── Sub-task A: Get our pricing                    │
│  └── Sub-task B: Get competitor pricing             │
│                                                      │
│  Step 2: Map to tools                               │
│  ├── Sub-task A → RAG (internal docs)               │
│  └── Sub-task B → Web Search (external data)        │
│                                                      │
│  Step 3: Execute                                    │
│  ├── RAG: "company pricing tiers plans"             │
│  │   → "Basic: $29/mo, Pro: $99/mo, Enterprise..."  │
│  │                                                   │
│  └── Web Search: "SaaS pricing CompetitorA B C"     │
│      → "CompetitorA: $25/mo, CompetitorB: $89/mo..."│
│                                                      │
│  Step 4: Synthesize                                 │
│  └── LLM combines both results into comparison      │
└─────────────────────────────────────────────────────┘
                    │
                    ▼
    "Here's how our pricing compares:
     - Our Basic ($29) vs CompetitorA ($25): +16%
     - Our Pro ($99) vs CompetitorB ($89): +11%
     ..."
```

---

## Agent Planning for Multi-Part Questions

### Implicit Planning (Let the LLM Decide)

The simplest approach: give the agent all tools and let it figure out what to call.

```python
# The agent sees all available tools and decides
tools = [
    query_knowledge_base,  # RAG tool
    web_search,            # Web search tool
    calculator,            # Math tool
]

# System prompt guides tool selection
system_prompt = """You are a helpful assistant with access to:
- query_knowledge_base: Search internal company documents
- web_search: Search the web for current information
- calculator: Perform mathematical calculations

When answering questions, use multiple tools if needed:
1. First, identify what information you need
2. Use the appropriate tool(s) to gather information
3. Combine the results to answer the question

For comparison questions, you typically need both internal and external data.
For calculations involving company data, retrieve the data first, then calculate.
"""
```

**Pros**: Simple, flexible, no custom planning logic **Cons**: LLM might miss steps, inefficient tool ordering, unpredictable

### Explicit Planning Node

Add a planning step that decomposes the query before execution:

```python
from pydantic import BaseModel, Field
from typing import Literal

class SubTask(BaseModel):
    """A single sub-task to accomplish."""
    description: str = Field(description="What needs to be done")
    tool: Literal["rag", "web_search", "calculator", "none"] = Field(
        description="Which tool to use"
    )
    query: str = Field(description="The query/input for the tool")
    depends_on: list[int] = Field(
        default_factory=list,
        description="Indices of sub-tasks this depends on (for ordering)"
    )

class ExecutionPlan(BaseModel):
    """Plan for answering a complex question."""
    original_question: str
    sub_tasks: list[SubTask]
    synthesis_needed: bool = Field(
        description="Whether results need to be combined/compared"
    )

# Planner LLM
planner_llm = ChatOpenAI(model="gpt-4o", temperature=0)
planner = planner_llm.with_structured_output(ExecutionPlan)

PLANNING_PROMPT = """Analyze this question and create an execution plan.

Question: {question}

Break the question into sub-tasks. For each sub-task, specify:
- What information is needed
- Which tool to use (rag for internal docs, web_search for external, calculator for math)
- The query to send to that tool
- Dependencies (which sub-tasks must complete first)

If a sub-task needs results from another, mark the dependency."""

def create_plan(question: str) -> ExecutionPlan:
    """Create execution plan for a complex question."""
    prompt = PLANNING_PROMPT.format(question=question)
    return planner.invoke(prompt)
```

**Example output:**

```python
plan = create_plan("Compare our pricing to competitors")

# ExecutionPlan(
#     original_question="Compare our pricing to competitors",
#     sub_tasks=[
#         SubTask(
#             description="Get our company pricing information",
#             tool="rag",
#             query="pricing tiers plans costs",
#             depends_on=[]
#         ),
#         SubTask(
#             description="Get competitor pricing information", 
#             tool="web_search",
#             query="SaaS competitor pricing 2024",
#             depends_on=[]
#         ),
#     ],
#     synthesis_needed=True
# )
```

### Sequential vs Parallel Execution

Sub-tasks without dependencies can run in parallel:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def execute_plan(plan: ExecutionPlan, tools: dict) -> dict[int, str]:
    """
    Execute plan, respecting dependencies.
    Returns {task_index: result}
    """
    results = {}
    pending = list(range(len(plan.sub_tasks)))
    
    while pending:
        # Find tasks with satisfied dependencies
        ready = [
            i for i in pending
            if all(dep in results for dep in plan.sub_tasks[i].depends_on)
        ]
        
        if not ready:
            raise ValueError("Circular dependency or unsatisfiable plan")
        
        # Execute ready tasks (parallel if multiple)
        if len(ready) > 1:
            # Parallel execution for independent tasks
            with ThreadPoolExecutor(max_workers=len(ready)) as executor:
                futures = {
                    executor.submit(
                        execute_single_task,
                        plan.sub_tasks[i],
                        tools,
                        {dep: results[dep] for dep in plan.sub_tasks[i].depends_on}
                    ): i
                    for i in ready
                }
                for future in as_completed(futures):
                    task_idx = futures[future]
                    results[task_idx] = future.result()
        else:
            # Sequential for single task
            i = ready[0]
            task = plan.sub_tasks[i]
            dep_results = {dep: results[dep] for dep in task.depends_on}
            results[i] = execute_single_task(task, tools, dep_results)
        
        # Remove completed tasks from pending
        for i in ready:
            pending.remove(i)
    
    return results

def execute_single_task(
    task: SubTask,
    tools: dict,
    dependency_results: dict[int, str]
) -> str:
    """Execute a single sub-task."""
    # Incorporate dependency results into query if needed
    query = task.query
    if dependency_results:
        # Could enhance query with prior results
        context = "\n".join(f"Prior result: {r}" for r in dependency_results.values())
        query = f"{query}\n\nContext from previous steps:\n{context}"
    
    tool = tools.get(task.tool)
    if tool is None:
        return f"No tool available for: {task.tool}"
    
    return tool.invoke({"query": query})
```

---

## Tool Result Aggregation

Each tool returns data in different formats:

|Tool|Return Format|
|---|---|
|RAG|Answer + sources + confidence|
|Web Search|Snippets + URLs + timestamps|
|Calculator|Numeric result|

The agent must synthesize these into a coherent response.

### Aggregation Node

```python
def aggregate_results(
    plan: ExecutionPlan,
    results: dict[int, str],
    llm: ChatOpenAI
) -> str:
    """
    Synthesize multiple tool results into a coherent response.
    """
    # Format results for the LLM
    results_text = ""
    for i, task in enumerate(plan.sub_tasks):
        results_text += f"\n## Sub-task {i+1}: {task.description}\n"
        results_text += f"Tool used: {task.tool}\n"
        results_text += f"Result:\n{results[i]}\n"
    
    synthesis_prompt = f"""You have gathered information to answer this question:

Original question: {plan.original_question}

Information gathered:
{results_text}

Now synthesize these results into a clear, coherent answer.
- Combine information from all sources
- Highlight comparisons or contrasts if relevant
- Cite which source each piece of information came from
- If there are conflicts, note them
- Be concise but complete"""

    response = llm.invoke(synthesis_prompt)
    return response.content
```

### Handling Conflicting Information

When tools return conflicting data:

```python
def synthesize_with_conflict_handling(
    results: dict[int, str],
    sources: list[str]
) -> str:
    """Handle cases where tools return conflicting information."""
    
    synthesis_prompt = f"""Synthesize these results, paying attention to conflicts:

{format_results(results, sources)}

If you find conflicting information:
1. Note the conflict explicitly
2. Indicate which source is likely more reliable (internal docs vs web, recent vs old)
3. Present both viewpoints if the conflict can't be resolved
4. Suggest how the user could verify the correct information

Do NOT silently choose one source over another for disputed facts."""
```

---

## Context Window Management

Multi-tool queries fill context quickly:

```
Query: "Compare our pricing to competitors and calculate market share"
                    │
                    ▼
RAG result: 2,000 tokens (pricing docs, 3 chunks with sources)
Web search: 1,500 tokens (5 competitor pages with snippets)
Previous messages: 3,000 tokens (conversation history)
System prompt: 500 tokens
                    │
                    ▼
Total: 7,000+ tokens before the LLM even starts generating
```

### Strategy 1: Summarize Tool Outputs

```python
def summarize_tool_result(
    result: str,
    task_description: str,
    max_tokens: int = 500,
    llm: ChatOpenAI = None
) -> str:
    """
    Summarize verbose tool output to fit context window.
    """
    if llm is None:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Estimate token count (rough: 4 chars per token)
    estimated_tokens = len(result) // 4
    
    if estimated_tokens <= max_tokens:
        return result
    
    summary_prompt = f"""Summarize this tool output to extract only the information 
relevant to: {task_description}

Tool output:
{result}

Provide a concise summary (max {max_tokens} tokens) that preserves:
- Key facts and figures
- Source references if present
- Any caveats or confidence indicators

Summary:"""

    summary = llm.invoke(summary_prompt)
    return summary.content
```

### Strategy 2: Select Relevant Portions

```python
def select_relevant_content(
    result: str,
    original_question: str,
    max_chunks: int = 3
) -> str:
    """
    From verbose RAG output, select only the most relevant chunks.
    """
    # Parse the RAG result to extract chunks
    chunks = parse_rag_chunks(result)
    
    if len(chunks) <= max_chunks:
        return result
    
    # Score chunks by relevance to original question
    scored_chunks = []
    for chunk in chunks:
        score = compute_relevance(chunk, original_question)
        scored_chunks.append((score, chunk))
    
    # Keep top N
    scored_chunks.sort(reverse=True)
    top_chunks = [chunk for _, chunk in scored_chunks[:max_chunks]]
    
    return format_chunks(top_chunks)
```

### Strategy 3: Hierarchical Summarization

For very long results, summarize in stages:

```
Raw web search results (10,000 tokens)
            │
            ▼
    First pass summary (2,000 tokens)
            │
            ▼
    Final summary (500 tokens)
```

### Strategy 4: Streaming Aggregation

Process results as they arrive, don't wait for all:

```python
async def stream_aggregate(
    plan: ExecutionPlan,
    tools: dict
):
    """
    Stream partial answers as tool results arrive.
    """
    partial_results = {}
    
    async for task_idx, result in execute_tasks_async(plan, tools):
        partial_results[task_idx] = result
        
        # Generate partial answer with available results
        if len(partial_results) >= 1:
            partial_answer = generate_partial_answer(
                plan.original_question,
                partial_results,
                plan.sub_tasks
            )
            yield partial_answer
    
    # Final synthesis with all results
    final_answer = aggregate_results(plan, partial_results, llm)
    yield final_answer
```

---

## LangGraph Implementation

Putting it all together in a LangGraph agent:

```python
# Doc reference: https://docs.langchain.com/oss/python/langgraph/graph-api
# Also uses patterns from https://docs.langchain.com/oss/python/langchain/tools

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

# State schema
class MultiToolState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    # Planning
    execution_plan: ExecutionPlan | None
    # Tool results (keyed by sub-task index)
    tool_results: dict[int, str]
    # Final synthesis
    final_answer: str | None
    # Metadata
    tools_called: list[str]
    total_tool_tokens: int

# Define tools
@tool
def query_knowledge_base(query: str) -> str:
    """Search internal company documents for policies, procedures, pricing, etc."""
    result = rag.query(query)
    return format_rag_result(result)

@tool
def web_search(query: str) -> str:
    """Search the web for current information about competitors, market data, news."""
    result = search_api.search(query)
    return format_search_result(result)

@tool
def calculator(expression: str) -> str:
    """Evaluate mathematical expressions. Use for calculations, percentages, comparisons."""
    try:
        result = eval(expression)  # In production, use a safe math parser
        return str(result)
    except Exception as e:
        return f"Error: {e}"

tools = [query_knowledge_base, web_search, calculator]

# LLM with tools bound
llm = ChatOpenAI(model="gpt-4o", temperature=0)
llm_with_tools = llm.bind_tools(tools)

# Node: Agent decides next action
def agent_node(state: MultiToolState) -> dict:
    """Agent reasons about what to do next."""
    messages = state["messages"]
    
    # Include context about what's been done
    if state.get("tool_results"):
        context = "\n\nResults gathered so far:\n"
        for idx, result in state["tool_results"].items():
            context += f"- Tool call {idx}: {result[:200]}...\n"
        
        # Add context as system message
        messages = messages + [AIMessage(content=context)]
    
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}

# Node: Execute tools
tool_node = ToolNode(tools)

# Node: Synthesize final answer
def synthesis_node(state: MultiToolState) -> dict:
    """Combine all tool results into final answer."""
    messages = state["messages"]
    tool_results = state.get("tool_results", {})
    
    # Extract all tool results from message history
    all_results = []
    for msg in messages:
        if hasattr(msg, 'content') and isinstance(msg.content, str):
            if "Result:" in msg.content or "Found:" in msg.content:
                all_results.append(msg.content)
    
    synthesis_prompt = f"""Based on the information gathered, provide a comprehensive answer.

Original question: {messages[0].content}

Information from tools:
{chr(10).join(all_results)}

Provide a clear, synthesized answer that:
1. Directly addresses the question
2. Combines information from all sources
3. Notes any conflicts or uncertainties
4. Cites sources where appropriate"""

    response = llm.invoke(synthesis_prompt)
    
    return {
        "messages": [AIMessage(content=response.content)],
        "final_answer": response.content
    }

# Routing function
def should_continue(state: MultiToolState) -> Literal["tools", "synthesize", END]:
    """Decide whether to continue with tools, synthesize, or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If there are tool calls, execute them
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    # If we've gathered results, synthesize
    if state.get("tool_results") and not state.get("final_answer"):
        return "synthesize"
    
    # Otherwise, end
    return END

# Build the graph
builder = StateGraph(MultiToolState)

# Add nodes
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)
builder.add_node("synthesize", synthesis_node)

# Add edges
builder.add_edge(START, "agent")
builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "synthesize": "synthesize",
        END: END
    }
)
builder.add_edge("tools", "agent")  # After tools, agent decides next
builder.add_edge("synthesize", END)

# Compile
graph = builder.compile()
```

### Using the Agent

```python
# Simple query (single tool)
result = graph.invoke({
    "messages": [HumanMessage(content="What's our vacation policy?")],
    "tool_results": {},
    "tools_called": [],
    "total_tool_tokens": 0
})

# Multi-tool query
result = graph.invoke({
    "messages": [HumanMessage(content="Compare our pricing to competitors")],
    "tool_results": {},
    "tools_called": [],
    "total_tool_tokens": 0
})

# The agent will:
# 1. Call RAG for internal pricing
# 2. Call web_search for competitor pricing
# 3. Synthesize comparison
```

---

## Execution Patterns

### Pattern 1: Tool Calls in Parallel

When sub-tasks are independent, execute simultaneously:

```
┌─────────────────────────────────────┐
│              Agent                   │
│                                      │
│  Plan: Get our pricing + Get        │
│  competitor pricing (independent)    │
└──────────────────┬──────────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
    ┌─────────┐        ┌───────────┐
    │   RAG   │        │ Web Search│
    └────┬────┘        └─────┬─────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
           ┌─────────────┐
           │  Synthesize │
           └─────────────┘
```

This is implicit in LangGraph when the LLM returns multiple tool calls in one response.

### Pattern 2: Sequential with Dependencies

When later tools need earlier results:

```
User: "Calculate ROI if we adopt the new policy"
                   │
                   ▼
              ┌─────────┐
              │   RAG   │  ← Get policy details (cost, benefits)
              └────┬────┘
                   │
                   ▼
           ┌─────────────┐
           │ Calculator  │  ← Calculate ROI using retrieved numbers
           └─────────────┘
```

The agent naturally handles this by calling RAG first, then using the result in the calculator call.

### Pattern 3: Iterative Refinement

First result informs next query:

```
User: "Find our top 3 products by revenue and compare to industry"
                   │
                   ▼
              ┌─────────┐
              │   RAG   │  → "ProductA, ProductB, ProductC"
              └────┬────┘
                   │
                   ▼
           ┌─────────────┐
           │ Web Search  │  → Search for each product's industry benchmark
           │ (3 calls)   │
           └─────────────┘
```

---

## Cost and Latency Considerations

### Token Budget

```python
def estimate_multi_tool_cost(plan: ExecutionPlan) -> dict:
    """Estimate token usage for a multi-tool query."""
    estimates = {
        "rag": 1500,        # Average RAG response
        "web_search": 1000, # Average web snippets
        "calculator": 50,   # Just a number
    }
    
    total_input = 500  # Base prompt
    total_output = 0
    
    for task in plan.sub_tasks:
        total_output += estimates.get(task.tool, 500)
    
    # Synthesis step
    total_input += total_output  # Results become input
    total_output += 500  # Final answer
    
    return {
        "estimated_input_tokens": total_input,
        "estimated_output_tokens": total_output,
        "estimated_cost_gpt4o": (total_input * 0.005 + total_output * 0.015) / 1000
    }
```

### Latency Budget

```
Single-tool query:
  Agent reasoning: 300ms
  Tool execution: 500ms
  Response generation: 400ms
  Total: ~1.2s

Multi-tool query (2 parallel tools):
  Agent reasoning: 300ms
  Tools (parallel): max(500ms, 600ms) = 600ms
  Synthesis: 500ms
  Total: ~1.4s

Multi-tool query (3 sequential tools):
  Agent reasoning × 3: 900ms
  Tool executions: 1500ms
  Synthesis: 500ms
  Total: ~2.9s
```

### Optimization Strategies

1. **Parallelize independent tools**: Use async execution
2. **Summarize before synthesis**: Reduce context tokens
3. **Cache common queries**: RAG results, web searches
4. **Early termination**: If first tool gives complete answer, skip others

---

## Summary

|Aspect|Single Tool|Multi-Tool|
|---|---|---|
|Query complexity|Simple, focused|Compound, multi-part|
|Tool calls|1|2+ (sequential or parallel)|
|Context management|Straightforward|Requires summarization/selection|
|Synthesis|Minimal|Required aggregation step|
|Latency|Lower|Higher (but parallelizable)|
|Error handling|Simple|Must handle partial failures|

**Multi-tool orchestration patterns:**

1. **Implicit planning**: Let LLM decide tools (simple, less predictable)
2. **Explicit planning**: Decompose → Map → Execute → Synthesize (more control)
3. **Parallel execution**: Independent sub-tasks run simultaneously
4. **Sequential with dependencies**: Later tools use earlier results

**Context window management:**

1. Summarize verbose tool outputs
2. Select only relevant portions
3. Use hierarchical summarization for very long results
4. Stream partial results for responsiveness

**LangGraph implementation:**

- Multiple tools in ToolNode
- Agent node decides which tools to call
- Conditional routing: tools → agent (loop) or synthesize → end
- State accumulates results across tool calls

**What's Next (Days 3-4):**

- Agentic RAG patterns (iterative retrieval, self-correction)
- Query decomposition for complex research
- Grading and filtering retrieved documents