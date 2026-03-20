# What Is an Agent? (Agent vs. Chatbot vs. Chain)

## The Core Distinction

An **agent** is a system where the LLM decides the control flow of the application. Not just what to say—what to _do_.

|System|Who Controls Flow?|Behavior|
|---|---|---|
|**Chatbot**|Developer (hardcoded)|Responds to input with text output. One prompt in, one response out.|
|**Chain**|Developer (predefined sequence)|Executes a fixed sequence of steps. Step A → Step B → Step C. Predictable.|
|**Agent**|LLM (dynamic)|Decides what action to take next based on current state. Can loop, branch, use tools.|

The key insight: **Chains are state machines. Agents are reasoning engines.**

---

## Chatbot: The Baseline

A chatbot is a simple request-response system:

```
User Input → LLM → Text Response
```

The LLM has one job: generate a helpful response. No tools, no actions, no multi-step reasoning. The developer controls everything except the text generation.

**Example (Responses API — current standard):**

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4o",
    input="What's the capital of France?"
)
print(response.output_text)
# Output: "The capital of France is Paris."
```

> **Note:** The Responses API (March 2025) replaced Chat Completions as OpenAI's recommended interface. Chat Completions still works but new features land in Responses first. Responses is stateful by default, has better cache utilization, and native tool support.

**Limitations:**

- Can't access real-time information
- Can't perform calculations reliably
- Can't interact with external systems
- Knowledge limited to training data

---

## Chain: Developer-Controlled Sequence

A chain strings multiple LLM calls together in a **predefined order**. The developer decides the flow; the LLM just executes each step.

```
Input → [Step 1: Summarize] → [Step 2: Translate] → [Step 3: Format] → Output
```

**Example — Document Processing Chain:**

```python
from openai import OpenAI
client = OpenAI()

# Step 1: Extract key points
step1 = client.responses.create(
    model="gpt-4o",
    input=f"Summarize this document: {doc}"
)
summary = step1.output_text

# Step 2: Translate (always runs, regardless of content)
step2 = client.responses.create(
    model="gpt-4o",
    input=f"Translate to Spanish: {summary}"
)
translated = step2.output_text

# Step 3: Format as bullet points
step3 = client.responses.create(
    model="gpt-4o",
    input=f"Format as bullets: {translated}"
)
formatted = step3.output_text
```

**Characteristics:**

- Execution is **linear and predictable**
- Each step runs regardless of whether it's needed
- Developer pre-decides the sequence
- Good for well-defined, repeatable workflows
- **No runtime decision-making by the LLM**

**When Chains Work Well:**

- ETL-style transformations
- Fixed report generation
- Multi-step formatting pipelines
- Any workflow where the steps don't depend on content

---

## Agent: LLM-Controlled Flow

An agent gives the LLM **autonomy to decide what to do next**. The LLM reasons about the task, selects tools, executes actions, observes results, and decides whether to continue or stop.

```
User Task → [Agent Loop: Think → Act → Observe → Repeat] → Final Response
```

**The Agent Loop:**

```
┌─────────────────────────────────────┐
│  OBSERVE: What's the current state? │
│      ↓                              │
│  THINK: What should I do next?      │
│      ↓                              │
│  ACT: Execute a tool OR respond     │
│      ↓                              │
│  (Loop back if task incomplete)     │
└─────────────────────────────────────┘
```

**Example — Agent Handling "What's the weather in Tokyo?":**

```
Thought: User wants current weather. I don't have real-time data. 
         I should use the weather tool.
Action:  get_weather(location="Tokyo")
Observation: {"temp": 22, "condition": "Partly cloudy"}
Thought: I have the weather data. I can now respond.
Final Answer: It's 22°C and partly cloudy in Tokyo.
```

The LLM _decided_ to use a tool. It wasn't forced to. It _reasoned_ that it needed external data.

---

## The Critical Difference: Who Makes Decisions?

Consider this task: _"Send an email to my boss about the Q3 report if revenue dropped."_

**Chain Approach (Developer Decides):**

```python
from openai import OpenAI
client = OpenAI()

# Developer hardcodes the logic
revenue = get_q3_revenue()
if revenue < last_quarter:
    r1 = client.responses.create(model="gpt-4o", input="Summarize Q3 report...")
    r2 = client.responses.create(model="gpt-4o", input=f"Draft email about: {r1.output_text}")
    send_email(to="boss@company.com", body=r2.output_text)
```

The developer wrote the conditional logic. The LLM just fills in text.

**Agent Approach (LLM Decides):**

```
Task: "Send an email to my boss about the Q3 report if revenue dropped"

Thought: I need to check Q3 revenue first. Let me use the revenue tool.
Action: get_revenue(quarter="Q3")
Observation: {"q3": 1200000, "q2": 1500000}

Thought: Revenue dropped from 1.5M to 1.2M. I should draft an email.
Action: draft_email(subject="Q3 Revenue Update", body="...")

Thought: Draft ready. Now I need to send it. But wait—should I confirm 
         with the user before sending to their boss?
Action: ask_user("Should I send this email to your boss?")
```

The agent _reasoned_ through the task. It checked conditions, made decisions, and even added a safeguard the developer didn't explicitly code.

---

## Tool Use: How Agents Interact with the World

Agents extend LLM capabilities through **tools** (also called functions). A tool is:

- A capability the agent can invoke
- Defined by a name, description, and parameters
- **Executed by your code, not the LLM**

**Tool Definition Example (Responses API — current):**

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
                    "location": {
                        "type": "string",
                        "description": "City name, e.g., 'Tokyo' or 'New York'"
                    }
                },
                "required": ["location"],
                "additionalProperties": False
            },
            "strict": True  # Enforces schema compliance
        }
    }
]

# Make request with tools
response = client.responses.create(
    model="gpt-4o",
    input="What's the weather in Tokyo?",
    tools=tools
)
```

**Critical Understanding:** The LLM doesn't execute tools. It outputs a structured request saying _"I want to call this tool with these arguments."_ Your code executes the tool and feeds results back.

```
LLM: "I want to call get_weather(location='Tokyo')"
       ↓
Your Code: actually_call_weather_api("Tokyo") → {"temp": 22}
       ↓
You: Feed result back to LLM (via previous_response_id or new input)
       ↓
LLM: "It's 22°C in Tokyo"
```

> **Responses API Advantage:** Stateful by default. Use `previous_response_id` to chain responses without resending full conversation history. The API preserves tool state and reasoning context automatically.

---

## Spectrum of Autonomy

Agents aren't binary. There's a spectrum:

|Level|Description|Example|
|---|---|---|
|**Level 0**|Chatbot|No tools, just text generation|
|**Level 1**|Single tool call|LLM calls one tool, you return result, done|
|**Level 2**|Multi-step agent|LLM loops: tool → observe → tool → observe → respond|
|**Level 3**|Planning agent|LLM creates a plan, then executes it step by step|
|**Level 4**|Multi-agent|Multiple LLMs coordinate, delegate subtasks|

Most "agent" discussions refer to Level 2-3. Level 4 is advanced territory (Week 6).

---

## When to Use What?

|Use Case|Best Fit|Why|
|---|---|---|
|Simple Q&A|Chatbot|No external data needed|
|Fixed report generation|Chain|Steps are predictable, same every time|
|Customer FAQ with search|Agent (Level 1-2)|May or may not need to search|
|Research assistant|Agent (Level 2-3)|Multiple searches, synthesis, dynamic flow|
|"Book a flight"|Agent (Level 2+)|Multi-step: search → select → book → confirm|
|Multi-step data analysis|Agent or Chain|Depends on whether steps vary by input|

**Rule of Thumb:**

- If the steps are **always the same** → Chain
- If the steps **depend on the content/context** → Agent
- If you're **unsure how many steps** → Agent

---

## The Cost of Agency

Agents are powerful but expensive:

|Factor|Chain|Agent|
|---|---|---|
|**LLM Calls**|Fixed (N steps)|Variable (could be 2 or 20)|
|**Latency**|Predictable|Unpredictable|
|**Cost**|Predictable|Can spiral|
|**Debuggability**|Easy (linear trace)|Hard (branching decisions)|
|**Reliability**|High (deterministic)|Lower (LLM may choose wrong path)|

**Production Reality:** Many teams start with agents, then "harden" critical paths into chains once patterns emerge. The agent discovers the workflow; the chain codifies it.

---

## Common Misconceptions

**"Agents are smarter than chains"** No. Agents give the LLM more control, which can be good or bad. A well-designed chain for a well-defined task will outperform an agent trying to figure out the same task.

**"I need an agent for any multi-step task"** No. If the steps are fixed, a chain is simpler and more reliable. Agents are for tasks where the steps _can't be predetermined_.

**"Tool calling = Agent"** No. A single tool call (retrieve weather → respond) isn't really an agent. An agent implies a _loop_ — the LLM decides whether to continue or stop.

**"Agents replace chains"** No. They complement each other. Many production systems use agents for orchestration and chains for deterministic subtasks.

---

## Key Takeaways

1. **Chatbot:** LLM generates text. That's it.
2. **Chain:** Developer controls the flow. LLM fills in the blanks.
3. **Agent:** LLM controls the flow. It decides what to do and when to stop.
4. **Tools** let agents interact with the world — but your code executes them.
5. **Agency has costs:** more LLM calls, less predictability, harder debugging.
6. **Choose based on task:** Fixed steps → Chain. Dynamic steps → Agent.

---
