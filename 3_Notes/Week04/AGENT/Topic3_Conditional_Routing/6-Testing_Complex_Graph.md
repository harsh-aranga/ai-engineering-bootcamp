# Testing Complex Graphs

## Why Testing LangGraph is Different

LangGraph applications combine:

- **Non-deterministic LLM outputs** — Same input can produce different outputs
- **Stateful execution** — Results depend on accumulated state
- **Complex control flow** — Branches, loops, parallel execution
- **External dependencies** — APIs, databases, tools

You need a testing strategy that handles all of these.

## Testing Pyramid for LangGraph

```
         /\
        /  \     Integration Tests
       /    \    (Full graph, real/mocked LLM)
      /──────\
     /        \   Flow Tests
    /          \  (Routing logic, state transitions)
   /────────────\
  /              \ Unit Tests
 /                \(Individual nodes, pure functions)
/──────────────────\
```

**Strategy:**

- Many unit tests (fast, isolated)
- Moderate flow tests (routing correctness)
- Few integration tests (slow, expensive)

---

## Level 1: Unit Testing Individual Nodes

Nodes are just functions. Test them in isolation.

### Testing a Pure Node

```python
import pytest
from typing import TypedDict

class AgentState(TypedDict):
    query: str
    processed_query: str

def preprocess_query(state: AgentState) -> dict:
    """Clean and normalize user query."""
    cleaned = state["query"].strip().lower()
    return {"processed_query": cleaned}

# ─── Tests ───
def test_preprocess_query_strips_whitespace():
    state = {"query": "  Hello World  ", "processed_query": ""}
    result = preprocess_query(state)
    assert result["processed_query"] == "hello world"

def test_preprocess_query_lowercases():
    state = {"query": "UPPERCASE", "processed_query": ""}
    result = preprocess_query(state)
    assert result["processed_query"] == "uppercase"

def test_preprocess_query_handles_empty():
    state = {"query": "", "processed_query": ""}
    result = preprocess_query(state)
    assert result["processed_query"] == ""
```

### Testing Nodes with Dependencies (Mocking)

When nodes call LLMs or APIs, mock the dependencies:

```python
import pytest
from unittest.mock import Mock, patch
from typing import TypedDict

class State(TypedDict):
    query: str
    intent: str

def classify_intent(state: State, llm_client) -> dict:
    """Classify user intent using LLM."""
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": state["query"]}]
    )
    return {"intent": response.choices[0].message.content}

# ─── Tests with Mocking ───
def test_classify_intent_search():
    # Create mock LLM client
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="search"))]
    )
    
    state = {"query": "Find information about Python", "intent": ""}
    result = classify_intent(state, mock_client)
    
    assert result["intent"] == "search"
    mock_client.chat.completions.create.assert_called_once()

def test_classify_intent_calculation():
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="calculation"))]
    )
    
    state = {"query": "What is 5 + 3?", "intent": ""}
    result = classify_intent(state, mock_client)
    
    assert result["intent"] == "calculation"
```

### Dependency Injection Pattern

Design nodes to accept dependencies, making them testable:

```python
# ❌ Hard to test — dependency baked in
def bad_node(state):
    from openai import OpenAI
    client = OpenAI()  # Created inside
    return client.chat.completions.create(...)

# ✅ Easy to test — dependency injected
def good_node(state, *, llm_client):
    return llm_client.chat.completions.create(...)

# In production
from openai import OpenAI
result = good_node(state, llm_client=OpenAI())

# In tests
result = good_node(state, llm_client=mock_client)
```

---

## Level 2: Testing Routing Logic

Verify that conditional edges route correctly based on state.

### Testing Routing Functions Directly

```python
from typing import Literal

def route_by_intent(state: dict) -> Literal["search", "calculate", "general"]:
    """Route based on classified intent."""
    intent = state.get("intent", "")
    confidence = state.get("confidence", 0.0)
    
    if confidence < 0.5:
        return "general"  # Low confidence fallback
    
    if intent == "search":
        return "search"
    elif intent == "calculation":
        return "calculate"
    return "general"

# ─── Tests ───
def test_route_search_intent():
    state = {"intent": "search", "confidence": 0.9}
    assert route_by_intent(state) == "search"

def test_route_calculation_intent():
    state = {"intent": "calculation", "confidence": 0.8}
    assert route_by_intent(state) == "calculate"

def test_route_low_confidence_fallback():
    state = {"intent": "search", "confidence": 0.3}
    assert route_by_intent(state) == "general"

def test_route_unknown_intent():
    state = {"intent": "unknown", "confidence": 0.9}
    assert route_by_intent(state) == "general"

def test_route_missing_intent():
    state = {"confidence": 0.9}
    assert route_by_intent(state) == "general"
```

### Testing Full Routing Paths

Use partial graph execution to verify routing:

```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict

class State(TypedDict):
    intent: str
    result: str

def search_node(state): return {"result": "search_executed"}
def calculate_node(state): return {"result": "calculate_executed"}
def general_node(state): return {"result": "general_executed"}

def route_by_intent(state) -> str:
    return state.get("intent", "general")

@pytest.fixture
def routing_graph():
    builder = StateGraph(State)
    builder.add_node("search", search_node)
    builder.add_node("calculate", calculate_node)
    builder.add_node("general", general_node)
    
    builder.add_conditional_edges(START, route_by_intent, {
        "search": "search",
        "calculate": "calculate",
        "general": "general"
    })
    builder.add_edge("search", END)
    builder.add_edge("calculate", END)
    builder.add_edge("general", END)
    
    return builder.compile()

def test_routes_to_search(routing_graph):
    result = routing_graph.invoke({"intent": "search", "result": ""})
    assert result["result"] == "search_executed"

def test_routes_to_calculate(routing_graph):
    result = routing_graph.invoke({"intent": "calculate", "result": ""})
    assert result["result"] == "calculate_executed"

def test_routes_to_general_by_default(routing_graph):
    result = routing_graph.invoke({"intent": "unknown", "result": ""})
    assert result["result"] == "general_executed"
```

---

## Level 3: Testing Interrupt/Resume Flows

HITL patterns require testing the pause and resume cycle.

```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from typing import TypedDict

class ApprovalState(TypedDict):
    action: str
    approved: bool
    result: str

def propose_action(state):
    return {"action": "delete_files"}

def get_approval(state):
    response = interrupt(f"Approve: {state['action']}?")
    return {"approved": response == "yes"}

def execute_action(state):
    if state["approved"]:
        return {"result": "executed"}
    return {"result": "cancelled"}

@pytest.fixture
def approval_graph():
    builder = StateGraph(ApprovalState)
    builder.add_node("propose", propose_action)
    builder.add_node("approve", get_approval)
    builder.add_node("execute", execute_action)
    
    builder.add_edge(START, "propose")
    builder.add_edge("propose", "approve")
    builder.add_edge("approve", "execute")
    builder.add_edge("execute", END)
    
    return builder.compile(checkpointer=MemorySaver())

def test_interrupt_pauses_execution(approval_graph):
    config = {"configurable": {"thread_id": "test-1"}}
    result = approval_graph.invoke(
        {"action": "", "approved": False, "result": ""},
        config
    )
    
    # Should be interrupted
    assert "__interrupt__" in result
    assert "Approve: delete_files?" in str(result["__interrupt__"])

def test_resume_with_approval(approval_graph):
    config = {"configurable": {"thread_id": "test-2"}}
    
    # First invoke — hits interrupt
    approval_graph.invoke({"action": "", "approved": False, "result": ""}, config)
    
    # Resume with approval
    result = approval_graph.invoke(Command(resume="yes"), config)
    
    assert result["approved"] == True
    assert result["result"] == "executed"

def test_resume_with_rejection(approval_graph):
    config = {"configurable": {"thread_id": "test-3"}}
    
    # First invoke — hits interrupt
    approval_graph.invoke({"action": "", "approved": False, "result": ""}, config)
    
    # Resume with rejection
    result = approval_graph.invoke(Command(resume="no"), config)
    
    assert result["approved"] == False
    assert result["result"] == "cancelled"
```

---

## Level 4: Testing Parallel Execution

Verify parallel branches execute correctly and results merge properly.

```python
import pytest
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import operator

class ParallelState(TypedDict):
    input: str
    results: Annotated[list, operator.add]

def worker_a(state):
    return {"results": [f"A processed: {state['input']}"]}

def worker_b(state):
    return {"results": [f"B processed: {state['input']}"]}

def worker_c(state):
    return {"results": [f"C processed: {state['input']}"]}

def aggregate(state):
    return {}  # Results already merged via reducer

@pytest.fixture
def parallel_graph():
    builder = StateGraph(ParallelState)
    builder.add_node("worker_a", worker_a)
    builder.add_node("worker_b", worker_b)
    builder.add_node("worker_c", worker_c)
    builder.add_node("aggregate", aggregate)
    
    # Fan out
    builder.add_edge(START, "worker_a")
    builder.add_edge(START, "worker_b")
    builder.add_edge(START, "worker_c")
    
    # Fan in
    builder.add_edge("worker_a", "aggregate")
    builder.add_edge("worker_b", "aggregate")
    builder.add_edge("worker_c", "aggregate")
    builder.add_edge("aggregate", END)
    
    return builder.compile()

def test_parallel_execution_collects_all_results(parallel_graph):
    result = parallel_graph.invoke({"input": "test", "results": []})
    
    # All three workers should have contributed
    assert len(result["results"]) == 3
    assert any("A processed" in r for r in result["results"])
    assert any("B processed" in r for r in result["results"])
    assert any("C processed" in r for r in result["results"])
```

---

## Mocking LLM Calls for Deterministic Tests

### Using unittest.mock

```python
from unittest.mock import patch, Mock

def test_with_mocked_openai():
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="mocked response"))]
    
    with patch("openai.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = mock_response
        
        # Your test code here
        result = my_function_that_calls_openai()
        assert "mocked response" in result
```

### Using pytest-mock

```python
def test_with_mocker(mocker):
    mock_create = mocker.patch("mymodule.client.chat.completions.create")
    mock_create.return_value = Mock(
        choices=[Mock(message=Mock(content="test response"))]
    )
    
    result = my_node({"query": "test"})
    assert result["response"] == "test response"
```

### Creating a Fake LLM for Testing

```python
class FakeLLM:
    """Deterministic fake LLM for testing."""
    
    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.calls = []
    
    def create(self, messages, **kwargs):
        user_message = messages[-1]["content"]
        self.calls.append(user_message)
        
        # Return predetermined response based on input
        for pattern, response in self.responses.items():
            if pattern in user_message:
                return Mock(choices=[Mock(message=Mock(content=response))])
        
        return Mock(choices=[Mock(message=Mock(content="default response"))])

# Usage in tests
def test_with_fake_llm():
    fake_llm = FakeLLM({
        "weather": "search",
        "calculate": "calculation",
        "hello": "general"
    })
    
    result = classify_intent({"query": "weather forecast"}, fake_llm)
    assert result["intent"] == "search"
    assert "weather" in fake_llm.calls[0]
```

---

## Snapshot Testing for Graph Structure

Verify graph structure doesn't accidentally change:

```python
import pytest
from langgraph.graph import StateGraph, START, END

def test_graph_structure_snapshot(snapshot):
    builder = StateGraph(State)
    # ... build graph ...
    graph = builder.compile()
    
    # Get Mermaid representation
    mermaid = graph.get_graph().draw_mermaid()
    
    # Compare against stored snapshot
    assert mermaid == snapshot

# Or save as file for visual inspection
def test_graph_visualization():
    graph = build_my_graph()
    
    # Save Mermaid diagram
    mermaid = graph.get_graph().draw_mermaid()
    with open("tests/snapshots/my_graph.mmd", "w") as f:
        f.write(mermaid)
    
    # Optionally save as PNG
    png_bytes = graph.get_graph().draw_mermaid_png()
    with open("tests/snapshots/my_graph.png", "wb") as f:
        f.write(png_bytes)
```

---

## Testing Best Practices

### 1. Fresh Graph Per Test

State can leak between tests. Create new graphs in fixtures:

```python
@pytest.fixture
def graph():
    """Create fresh graph for each test."""
    builder = StateGraph(State)
    # ... build ...
    return builder.compile(checkpointer=MemorySaver())

def test_one(graph):
    # Fresh graph
    pass

def test_two(graph):
    # Another fresh graph
    pass
```

### 2. Unique Thread IDs

When using checkpointers, use unique thread IDs per test:

```python
import uuid

def test_with_unique_thread(graph):
    config = {"configurable": {"thread_id": f"test-{uuid.uuid4()}"}}
    result = graph.invoke(input, config)
```

### 3. Test Edge Cases

```python
# Empty state
def test_handles_empty_state(graph):
    result = graph.invoke({"query": "", "results": []})
    assert result is not None

# Missing keys
def test_handles_missing_keys(graph):
    result = graph.invoke({})  # May raise or handle gracefully

# Very long input
def test_handles_long_input(graph):
    long_query = "test " * 10000
    result = graph.invoke({"query": long_query})
```

### 4. Test Error Paths

```python
def test_handles_tool_failure(graph, mocker):
    mocker.patch("mymodule.call_api", side_effect=Exception("API down"))
    
    result = graph.invoke({"query": "test"})
    assert result["error"] == "API down"
    # Or verify error handling path was taken
```

### 5. Async Testing

For async graphs, use `pytest-asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_async_graph():
    graph = build_async_graph()
    result = await graph.ainvoke({"query": "test"})
    assert result["response"] is not None
```

---

## Test Organization

```
tests/
├── conftest.py           # Shared fixtures
├── unit/
│   ├── test_nodes.py     # Individual node tests
│   └── test_routing.py   # Routing function tests
├── integration/
│   ├── test_flows.py     # Full graph execution
│   └── test_hitl.py      # Interrupt/resume flows
└── snapshots/
    └── graph_structure.mmd  # Mermaid snapshots
```

### conftest.py Example

```python
import pytest
from langgraph.checkpoint.memory import MemorySaver
from unittest.mock import Mock

@pytest.fixture
def mock_llm():
    """Shared mock LLM client."""
    mock = Mock()
    mock.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="mocked"))]
    )
    return mock

@pytest.fixture
def checkpointer():
    """Fresh checkpointer per test."""
    return MemorySaver()
```

---

## Key Takeaways

1. **Unit test nodes in isolation** — They're just functions
2. **Mock LLM calls** — Makes tests fast and deterministic
3. **Test routing functions directly** — Before testing full graph
4. **Use unique thread IDs** — Prevents state leakage between tests
5. **Fresh graph per test** — Use fixtures to avoid shared state
6. **Test interrupt/resume cycles** — Verify HITL flows work correctly
7. **Snapshot graph structure** — Catch accidental structural changes
8. **Dependency injection** — Design nodes to accept mockable dependencies

---

_Sources: LangGraph docs (docs.langchain.com/oss/python/langgraph/test), pytest documentation, LangGraph testing patterns_