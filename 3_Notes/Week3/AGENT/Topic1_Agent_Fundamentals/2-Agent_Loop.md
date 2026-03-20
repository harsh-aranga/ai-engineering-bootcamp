# The Agent Loop: Observe → Think → Act

> **Doc References:** OpenAI Responses API (March 2025), OpenAI Function Calling Guide, LangGraph 1.0, ReAct Paper (Yao et al. 2022), IBM ReAct Agent Guide, Hugging Face Agents Course

---

## The Core Loop

Every agent—regardless of framework—follows the same fundamental pattern:

```
┌────────────────────────────────────────────────┐
│                   AGENT LOOP                   │
├────────────────────────────────────────────────┤
│                                                │
│   ┌─────────┐                                  │
│   │ OBSERVE │ ← Current state, tool results,  │
│   └────┬────┘   user input, context            │
│        │                                       │
│        ▼                                       │
│   ┌─────────┐                                  │
│   │  THINK  │ ← Reason about what to do next  │
│   └────┬────┘   (the LLM's job)               │
│        │                                       │
│        ▼                                       │
│   ┌─────────┐                                  │
│   │   ACT   │ ← Call a tool OR respond        │
│   └────┬────┘                                  │
│        │                                       │
│        ▼                                       │
│   ┌─────────────┐                              │
│   │ LOOP or END │ ← Is the task complete?     │
│   └─────────────┘                              │
│                                                │
└────────────────────────────────────────────────┘
```

This loop continues until:

- The agent decides the task is complete
- A maximum iteration limit is hit
- An error occurs that can't be recovered

---

## The Three Phases in Detail

### 1. OBSERVE — What Does the Agent See?

The agent's "observation" is everything in its current context:

|Source|Example|
|---|---|
|**User input**|"What's the weather in Tokyo?"|
|**Tool results**|`{"temp": 22, "condition": "Cloudy"}`|
|**Previous thoughts**|"I called get_weather and got results"|
|**System instructions**|"You are a helpful assistant with access to weather data"|
|**Conversation history**|Prior turns in the chat|

**Key insight:** Each loop iteration, the observation grows. The agent sees everything that happened before, allowing it to build on prior steps.

```
Iteration 1: [User query]
Iteration 2: [User query] + [Thought 1] + [Action 1] + [Tool result 1]
Iteration 3: [All above] + [Thought 2] + [Action 2] + [Tool result 2]
...
```

This accumulating context is why agents can handle multi-step tasks—each step informs the next.

---

### 2. THINK — The LLM Reasons

The LLM analyzes the current observation and decides what to do next. This is **chain-of-thought reasoning** applied to action selection.

**What happens in the "Think" phase:**

- Understand what the user wants
- Assess what's already been done
- Identify what information is missing
- Select the appropriate next action
- Determine when to stop

**Example thought process:**

```
Observation: User asked "What's the population of the capital of France?"

Thought: The user wants population data. I need to:
  1. First identify the capital of France (Paris)
  2. Then look up Paris's population
  
  I already know Paris is the capital. Now I need population data.
  I should use the search tool to find current population figures.
```

**Not all models expose reasoning:** OpenAI's reasoning models (o3, o4-mini, GPT-5) generate internal chain-of-thought but don't always expose it via API. The Responses API preserves this reasoning state server-side using `previous_response_id`.

---

### 3. ACT — Execute or Respond

Based on reasoning, the agent takes one of two actions:

|Action Type|When|What Happens|
|---|---|---|
|**Tool Call**|More information needed|Agent outputs a structured tool request|
|**Final Response**|Task is complete|Agent outputs answer to user|

**Tool Call Output (Responses API format):**

```json
{
  "type": "function_call",
  "name": "get_weather",
  "call_id": "call_abc123",
  "arguments": "{\"location\": \"Tokyo\"}"
}
```

**Final Response Output:**

```json
{
  "type": "message",
  "content": "It's currently 22°C and cloudy in Tokyo."
}
```

**Critical:** The LLM doesn't execute tools. It outputs a _request_ to call a tool. Your code:

1. Parses the tool call
2. Executes the actual function
3. Feeds the result back as a new observation
4. Loops again

---

## The ReAct Pattern

**ReAct = Reasoning + Acting**

The dominant pattern for implementing agent loops. From the 2022 paper by Yao et al., now standard in production.

**ReAct structures output as:**

```
Thought: [Reasoning about current state and next step]
Action: [Tool name and arguments]
Observation: [Result from tool execution]
... (repeat) ...
Thought: [Final reasoning]
Final Answer: [Response to user]
```

**Example Trace:**

```
User: What's the elevation of the city where the 2024 Olympics were held?

Thought: I need to find where the 2024 Olympics were held, then look up 
         that city's elevation. Let me search for 2024 Olympics location.
Action: search("2024 Summer Olympics host city")
Observation: The 2024 Summer Olympics were held in Paris, France.

Thought: The Olympics were in Paris. Now I need Paris's elevation.
Action: search("Paris France elevation meters")
Observation: Paris has an average elevation of 35 meters (115 feet) 
             above sea level.

Thought: I have all the information needed to answer.
Final Answer: The 2024 Summer Olympics were held in Paris, France, 
              which has an elevation of approximately 35 meters 
              (115 feet) above sea level.
```

**Why ReAct works:**

1. **Grounded:** Actions fetch real data, reducing hallucination
2. **Transparent:** Each step is traceable and debuggable
3. **Adaptive:** Agent adjusts based on what it learns

---

## Implementing the Loop with OpenAI Responses API

The Responses API (March 2025) is explicitly designed as an "agentic loop":

```python
from openai import OpenAI

client = OpenAI()

# Define tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
]

# Your tool implementations
def execute_tool(name: str, arguments: dict) -> str:
    if name == "get_weather":
        # Call actual weather API
        return '{"temp": 22, "condition": "Cloudy"}'
    raise ValueError(f"Unknown tool: {name}")

# The agent loop
def run_agent(user_input: str) -> str:
    response = client.responses.create(
        model="gpt-4o",
        instructions="You are a helpful assistant with weather data access.",
        input=user_input,
        tools=tools
    )
    
    # Loop while there are tool calls to process
    while response.output and any(
        item.type == "function_call" for item in response.output
    ):
        # Process each tool call
        tool_outputs = []
        for item in response.output:
            if item.type == "function_call":
                result = execute_tool(item.name, item.arguments)
                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": result
                })
        
        # Continue the loop with tool results
        response = client.responses.create(
            model="gpt-4o",
            previous_response_id=response.id,  # Stateful chaining
            input=tool_outputs,
            tools=tools
        )
    
    return response.output_text
```

**Key Responses API features for agent loops:**

- `previous_response_id`: Chains responses without resending history
- `store: true` (default): Preserves reasoning context server-side
- Built-in tools: `web_search`, `code_interpreter`, `file_search`
- Native multi-tool execution in single response

---

## Loop Termination Strategies

The loop must end. Without termination logic, agents can spiral infinitely.

|Strategy|How It Works|Trade-off|
|---|---|---|
|**Max iterations**|Hard limit (e.g., 10 loops)|Simple but may cut off valid long tasks|
|**Model decides**|LLM outputs "Final Answer"|Flexible but model may not stop|
|**Confidence threshold**|Stop when model is "sure"|Requires confidence scoring|
|**Task completion check**|Verify output meets criteria|Most robust, most complex|

**Production pattern: Combine strategies**

```python
MAX_ITERATIONS = 10

for i in range(MAX_ITERATIONS):
    response = get_next_response()
    
    if no_tool_calls(response):
        return response.output_text  # Model decided to stop
    
    if i == MAX_ITERATIONS - 1:
        # Force conclusion on last iteration
        response = client.responses.create(
            model="gpt-4o",
            previous_response_id=response.id,
            input="You must provide a final answer now based on what you know.",
            tools=[]  # No tools = force text response
        )
        return response.output_text
```

---

## What Can Go Wrong?

|Failure Mode|Cause|Mitigation|
|---|---|---|
|**Infinite loop**|Agent keeps calling same tool|Max iterations + loop detection|
|**Wrong tool selection**|Poor tool descriptions|Better descriptions + examples|
|**Tool call with bad args**|Schema mismatch|`strict: true` + validation|
|**Lost context**|Context window overflow|Summarization + truncation|
|**Hallucinated tool**|Model invents non-existent tool|Validate tool name before execution|
|**Never stops**|Model doesn't recognize completion|Explicit stop criteria in prompt|

**Debugging tip:** Log every iteration. When an agent misbehaves, trace through:

1. What was the observation?
2. What did the model think?
3. What action did it take?
4. What was the result?

Most bugs are in step 1 (bad context) or step 3 (wrong tool call).

---

## Framework Implementations

Different frameworks implement the same loop with different abstractions:

### LangGraph (v1.0)

```python
from langgraph.graph import StateGraph

# State accumulates across loop iterations
class AgentState(TypedDict):
    messages: list
    
# Nodes = steps in the loop
def reasoning_node(state):
    # THINK: Call LLM to decide action
    ...

def action_node(state):
    # ACT: Execute tool
    ...

# Build graph with conditional edges
graph = StateGraph(AgentState)
graph.add_node("reason", reasoning_node)
graph.add_node("act", action_node)
graph.add_conditional_edges("reason", should_continue)
graph.add_edge("act", "reason")  # Loop back
```

### Raw Python (No Framework)

```python
while True:
    thought = llm.generate(context)
    
    if thought.is_final_answer:
        return thought.content
    
    tool_result = execute(thought.tool_call)
    context.append(thought)
    context.append(tool_result)
```

The pattern is identical. Frameworks add:

- State management
- Persistence/checkpointing
- Streaming
- Observability
- Error recovery

---

## Key Takeaways

1. **The loop is universal:** Observe → Think → Act → (Repeat or Stop)
    
2. **Context accumulates:** Each iteration sees all prior thoughts, actions, and results
    
3. **LLM thinks, code acts:** The model outputs tool _requests_; your code _executes_ them
    
4. **ReAct is the standard:** Thought-Action-Observation structure dominates production systems
    
5. **Termination is critical:** Always have a max iteration limit + explicit stop conditions
    
6. **Responses API is agent-native:** Built specifically for this loop pattern with `previous_response_id` and stateful context
    
7. **Debug by tracing:** Log every observation, thought, and action to find where things break
    

---

## Connection to Previous Topic

In "What Is an Agent?" we established that agents let the LLM control flow. This topic showed _how_ that control works: a loop where the model reasons and acts iteratively until the task is complete.

## Up Next

The next topic covers **tool calling mechanics**—how tools are defined, how the LLM "calls" them, and how results flow back into the loop.