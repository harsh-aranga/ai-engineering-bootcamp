# Graph Visualization

## Why Visualization Matters

You can't debug what you can't see. Graph visualization helps you:

1. **Verify structure** — Confirm edges connect the nodes you intended
2. **Spot missing paths** — Find orphaned nodes or missing END connections
3. **Debug conditional logic** — See which branches exist
4. **Communicate designs** — Share workflow diagrams with teammates
5. **Document systems** — Generate architecture docs automatically

---

## The Core Method: `get_graph()`

Every compiled graph exposes a `get_graph()` method that returns a graph object you can visualize:

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class State(TypedDict):
    query: str
    result: str

def process(state: State) -> dict:
    return {"result": "done"}

graph = StateGraph(State)
graph.add_node("process", process)
graph.add_edge(START, "process")
graph.add_edge("process", END)

# Compile first
app = graph.compile()

# Get the graph object
graph_obj = app.get_graph()
```

The `graph_obj` provides multiple visualization methods.

---

## Visualization Methods

### 1. ASCII Art (`draw_ascii()`)

Quick terminal visualization. No dependencies required.

```python
print(app.get_graph().draw_ascii())
```

Output:

```
+-----------+
| __start__ |
+-----------+
      *
      *
      *
 +---------+
 | process |
 +---------+
      *
      *
      *
 +---------+
 | __end__ |
 +---------+
```

**Pros**: Works everywhere, no external dependencies, fast **Cons**: Limited detail, doesn't show edge labels well, crude aesthetics

**Best for**: Quick sanity checks in terminal, CI/CD logs, environments without graphics

### 2. Mermaid Syntax (`draw_mermaid()`)

Returns Mermaid diagram syntax as a string.

```python
print(app.get_graph().draw_mermaid())
```

Output:

```
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;
    __start__([<p>__start__</p>]):::first
    process(process)
    __end__([<p>__end__</p>]):::last
    __start__ --> process;
    process --> __end__;
    classDef default fill:#f2f0ff,line-height:1.2
    classDef first fill-opacity:0
    classDef last fill:#bfb6fc
```

**Usage**: Copy this to [mermaid.live](https://mermaid.live/) to render interactively.

**Pros**: Editable, version-controllable, renders in Markdown (GitHub, Notion, etc.) **Cons**: Requires external tool to render visually

**Best for**: Documentation, README files, design discussions

### 3. PNG Image (`draw_mermaid_png()`)

Renders the graph as a PNG image.

```python
from IPython.display import Image, display

# In Jupyter notebook
display(Image(app.get_graph().draw_mermaid_png()))

# Or save to file
png_bytes = app.get_graph().draw_mermaid_png(output_file_path="graph.png")
```

**Draw Methods** (how PNG is generated):

```python
from langchain_core.runnables.graph import MermaidDrawMethod

# Method 1: API (default) - uses mermaid.ink service
png = app.get_graph().draw_mermaid_png(
    draw_method=MermaidDrawMethod.API
)

# Method 2: Pyppeteer - local rendering (requires pip install pyppeteer)
import nest_asyncio
nest_asyncio.apply()  # Required in Jupyter

png = app.get_graph().draw_mermaid_png(
    draw_method=MermaidDrawMethod.PYPPETEER
)
```

|Method|Pros|Cons|
|---|---|---|
|`API` (default)|No local deps, just works|Requires internet, can timeout|
|`PYPPETEER`|Works offline, no external service|Requires pyppeteer install, slower first run|

**Best for**: Jupyter notebooks, presentations, image exports

### 4. Graphviz PNG (`draw_png()`)

Alternative PNG rendering using Graphviz.

```python
# Requires: pip install graphviz
# And system graphviz: brew install graphviz (macOS) or apt install graphviz (Ubuntu)

display(Image(app.get_graph().draw_png()))
```

**Pros**: High quality, professional looking **Cons**: Requires system-level graphviz installation

---

## Customizing Visualizations

### Mermaid PNG Options

```python
from langchain_core.runnables.graph import (
    CurveStyle, 
    NodeColors,
    MermaidDrawMethod
)

png = app.get_graph().draw_mermaid_png(
    # Edge curve style
    curve_style=CurveStyle.LINEAR,  # or BASIS, BUMP, etc.
    
    # Custom node colors
    node_colors=NodeColors(
        start="#ffdfba",   # Start node color
        end="#baffc9",     # End node color  
        other="#fad7de"    # Other nodes
    ),
    
    # Wrap long labels
    wrap_label_n_words=9,
    
    # Save to file
    output_file_path="my_graph.png",
    
    # Rendering method
    draw_method=MermaidDrawMethod.API,
    
    # Background
    background_color="white",
    
    # Padding around diagram
    padding=10
)
```

### Mermaid Syntax Options

```python
mermaid_code = app.get_graph().draw_mermaid(
    with_styles=True,        # Include CSS styling
    curve_style=CurveStyle.LINEAR,
    node_colors=NodeColors(start="#green", end="#red", other="#blue"),
    wrap_label_n_words=9
)
```

---

## Visualizing Subgraphs

For graphs that contain subgraphs (graphs as nodes), use the `xray` parameter:

```python
# Show subgraph internals
display(Image(app.get_graph(xray=True).draw_mermaid_png()))

# Control depth of xray
display(Image(app.get_graph(xray=2).draw_mermaid_png()))  # 2 levels deep
```

### xray Parameter

|Value|Behavior|
|---|---|
|`False` (default)|Subgraphs shown as single nodes|
|`True` or `1`|Expand one level of subgraphs|
|`2`, `3`, etc.|Expand N levels deep|

### Limitation

If subgraphs are invoked inside node functions (not passed directly to `add_node`), they won't appear in visualization:

```python
# This WON'T show subgraph internals in visualization
def my_node(state):
    result = subgraph.invoke(state)  # Called inside function
    return result

graph.add_node("my_node", my_node)

# This WILL show subgraph internals
graph.add_node("my_node", compiled_subgraph)  # Passed directly
```

---

## Reading the Visual Output

### Node Types

|Visual|Meaning|
|---|---|
|`__start__`|Entry point (START constant)|
|`__end__`|Terminal point (END constant)|
|Regular box|Your custom nodes|

### Edge Types

In Mermaid output:

- **Solid arrow** (`-->`) = Normal edge
- **Dotted arrow** (`-.->`) = Conditional edge
- **Labels on edges** = Condition values

Example conditional edge output:

```
agent -.tool.-> tools;
agent -.end.-> __end__;
```

---

## Practical Workflow

### During Development

```python
# Quick check after adding nodes/edges
print(app.get_graph().draw_ascii())
```

### In Jupyter Notebooks

```python
from IPython.display import Image, display

# Rich visualization
display(Image(app.get_graph().draw_mermaid_png()))
```

### For Documentation

```python
# Get Mermaid code for README
mermaid = app.get_graph().draw_mermaid()
print(mermaid)

# Copy to your docs, renders on GitHub
```

### For Reports/Presentations

```python
# Save high-quality PNG
app.get_graph().draw_mermaid_png(
    output_file_path="architecture.png",
    background_color="white"
)
```

---

## Handling Common Issues

### Issue 1: Mermaid API Timeout

The default `MermaidDrawMethod.API` calls mermaid.ink, which can timeout.

**Fix**: Use local rendering:

```python
import nest_asyncio
nest_asyncio.apply()

from langchain_core.runnables.graph import MermaidDrawMethod

png = app.get_graph().draw_mermaid_png(
    draw_method=MermaidDrawMethod.PYPPETEER
)
```

### Issue 2: Graphviz Not Found

```
ExecutableNotFound: failed to execute 'dot'
```

**Fix**: Install graphviz system package:

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz graphviz-dev

# Windows
choco install graphviz
```

### Issue 3: Pyppeteer Issues in Jupyter

```
RuntimeError: This event loop is already running
```

**Fix**: Apply nest_asyncio:

```python
import nest_asyncio
nest_asyncio.apply()
```

### Issue 4: Visualization Doesn't Match Expected Graph

Recent versions (v0.3.32+) may show additional edges to `__end__` in conditional edge scenarios. This is a visualization artifact, not an execution issue.

**Workaround**: Check actual execution behavior separately from visualization.

---

## Complete Example

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from operator import add
from IPython.display import Image, display

class State(TypedDict):
    messages: Annotated[list, add]
    next_action: str

def agent(state: State) -> dict:
    # Decide next action
    return {"messages": ["thinking..."], "next_action": "tool"}

def tool(state: State) -> dict:
    return {"messages": ["tool result"]}

def respond(state: State) -> dict:
    return {"messages": ["final response"]}

def router(state: State) -> str:
    if state["next_action"] == "tool":
        return "tool"
    return "respond"

# Build graph
graph = StateGraph(State)
graph.add_node("agent", agent)
graph.add_node("tool", tool)
graph.add_node("respond", respond)

graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", router, {"tool": "tool", "respond": "respond"})
graph.add_edge("tool", "agent")  # Loop back
graph.add_edge("respond", END)

app = graph.compile()

# Visualize
print("=== ASCII ===")
print(app.get_graph().draw_ascii())

print("\n=== Mermaid ===")
print(app.get_graph().draw_mermaid())

# In Jupyter:
# display(Image(app.get_graph().draw_mermaid_png()))
```

---

## Method Reference

|Method|Returns|Dependencies|
|---|---|---|
|`get_graph()`|Graph object|None|
|`get_graph(xray=True)`|Graph with expanded subgraphs|None|
|`.draw_ascii()`|String (ASCII art)|None|
|`.draw_mermaid()`|String (Mermaid syntax)|None|
|`.draw_mermaid_png()`|Bytes (PNG image)|Internet (API) or pyppeteer|
|`.draw_png()`|Bytes (PNG image)|graphviz (system)|

---

## Key Takeaways

1. **Always visualize after building** — Catch edge mistakes early
2. **Use ASCII for quick checks** — No dependencies, works in any terminal
3. **Use Mermaid for docs** — Version-controllable, renders in Markdown
4. **Use PNG for presentations** — High quality, exportable
5. **Use xray for subgraphs** — See inside nested graphs
6. **Have fallbacks ready** — API can timeout, Pyppeteer is reliable offline
7. **Visualization ≠ Execution** — Some rendering bugs exist; verify behavior separately

---

## Tools Ecosystem

|Tool|URL|Use|
|---|---|---|
|Mermaid Live Editor|mermaid.live|Interactive editing/rendering|
|GitHub Markdown|Native support|Renders Mermaid in READMEs|
|VS Code Mermaid Preview|Extension|Local preview|
|LangSmith|smith.langchain.com|Production tracing with visualization|

---

_Sources: LangGraph visualization docs, langchain_core.runnables.graph reference, community examples, GitHub issues on rendering_