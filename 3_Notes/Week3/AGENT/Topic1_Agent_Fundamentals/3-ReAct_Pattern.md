# ReAct Pattern: Reasoning + Acting

> **Doc References:** ReAct Paper (Yao et al., ICLR 2023), Google Research Blog, Prompt Engineering Guide, OpenAI Responses API docs

---

## What Is ReAct?

**ReAct = Reasoning + Acting**

A framework where an LLM generates **interleaved** reasoning traces and actions. Not "think then act" but "think, act, observe, think, act, observe..."

```
┌─────────────────────────────────────────────────────┐
│                   ReAct CYCLE                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Thought  →  Action  →  Observation  →  Thought   │
│      │                        │                     │
│      └────────────────────────┘                     │
│              (repeat until done)                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**The key insight:** Reasoning helps the model plan and track progress. Actions ground the model in reality. Neither alone is sufficient.

---

## The Three Components

### 1. Thought (Reasoning Trace)

The model's internal reasoning, verbalized. Used to:

- Analyze the current situation
- Plan the next step
- Track what's been done
- Handle unexpected results

```
Thought: The user wants to know the population of France's capital.
         I know Paris is the capital, but I should verify the 
         current population. Let me search for it.
```

**Thoughts don't affect the external world**—they're internal deliberation.

### 2. Action (Tool Invocation)

The model requests an external operation:

- Search queries
- API calls
- Database lookups
- Code execution
- Any tool interaction

```
Action: search("Paris population 2024")
```

**Actions interface with the world**—they produce side effects or retrieve information.

### 3. Observation (Environment Feedback)

The result returned from the action:

```
Observation: Paris has a population of approximately 2.1 million 
             in the city proper, and 12 million in the metro area.
```

**Observations update the model's context**—they become input for the next thought.

---

## Full ReAct Trace Example

**Task:** "What's the elevation of the city that hosted the 2024 Olympics?"

```
Thought 1: I need to find which city hosted the 2024 Olympics,
           then look up that city's elevation. Let me start by
           finding the host city.

Action 1:  search("2024 Summer Olympics host city")

Observation 1: The 2024 Summer Olympics were held in Paris, France,
               from July 26 to August 11, 2024.

Thought 2: The 2024 Olympics were in Paris. Now I need to find
           Paris's elevation above sea level.

Action 2:  search("Paris France elevation meters")

Observation 2: Paris has an average elevation of 35 meters (115 ft)
               above sea level, with a range from 28m to 131m.

Thought 3: I have all the information needed. Paris hosted the
           2024 Olympics and has an elevation of ~35 meters.

Final Answer: The 2024 Summer Olympics were held in Paris, France,
              which has an average elevation of 35 meters (115 feet)
              above sea level.
```

**What makes this ReAct:**

- Reasoning and acting are _interleaved_, not sequential
- Each observation informs the next thought
- The model adapts based on what it learns

---

## ReAct vs. Chain-of-Thought (CoT)

|Aspect|Chain-of-Thought|ReAct|
|---|---|---|
|**Structure**|Think → Think → Think → Answer|Think → Act → Observe → Think → ...|
|**External access**|None (internal only)|Yes (tools, APIs, search)|
|**Grounding**|Uses only training knowledge|Grounds in real-world data|
|**Hallucination risk**|Higher (no fact-checking)|Lower (can verify facts)|
|**Error recovery**|Cannot self-correct|Can retry with new info|
|**Best for**|Math, logic, self-contained problems|Knowledge tasks, dynamic environments|

**The paper's finding:** CoT alone hallucinates. Acting alone lacks strategy. ReAct combines both advantages.

### Side-by-Side Comparison

**Question:** "Who is Olivia Wilde's boyfriend and what is his age raised to the 0.23 power?"

**CoT Approach:**

```
Let me think step by step.
Olivia Wilde's boyfriend is Harry Styles.  ← Could be outdated/wrong
Harry Styles was born in 1994, so he's about 29.  ← Reasoning from memory
29^0.23 = 2.17
Final Answer: 2.17
```

_Problem: If the relationship changed or age is wrong, no way to verify._

**ReAct Approach:**

```
Thought: I need to find Olivia Wilde's current boyfriend, then his age.
Action: search("Olivia Wilde boyfriend 2024")
Observation: [Current, verified information]

Thought: Now I need his exact age.
Action: search("Harry Styles age")
Observation: 29 years old

Thought: Now I calculate 29^0.23
Action: calculator(29^0.23)
Observation: 2.169

Final Answer: Harry Styles, 29 years old. 29^0.23 = 2.169
```

_Advantage: Facts are retrieved, not assumed. Calculation is verified._

---

## ReAct vs. Act-Only

What if we skip the reasoning traces entirely?

**Act-Only Approach:**

```
Action: search("2024 Olympics host city")
Observation: Paris, France

Action: search("Paris elevation")
Observation: 35 meters

Action: search("Paris population")  ← Why? Not relevant
Observation: 2.1 million

Final Answer: Paris has 2.1 million people  ← Wrong answer
```

**Without reasoning:**

- No clear goal tracking
- Random or unfocused tool use
- Can't synthesize results coherently
- Often gets lost or gives wrong answers

**The paper showed:** Act-only fails because it can't plan or track progress.

---

## The ReAct Prompt Template

ReAct works through **prompt engineering**—you teach the model the format:

```
You are a helpful assistant that reasons step-by-step.

For each question, follow this format:

Thought: Analyze the situation and plan your next step
Action: Choose from [search, lookup, calculator, finish]
Observation: (Result will be provided)
... (repeat as needed)
Final Answer: Your complete answer

Available actions:
- search[query]: Search for information
- lookup[term]: Look up a specific term
- calculator[expression]: Evaluate math
- finish[answer]: Provide final answer

Question: {user_question}
```

**Few-shot examples** dramatically improve performance. Include 1-2 worked examples showing the Thought → Action → Observation pattern.

---

## Implementing ReAct with Responses API

Modern APIs have native support for the ReAct pattern via tool calling:

```python
from openai import OpenAI

client = OpenAI()

tools = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
                "additionalProperties": False
            },
            "strict": True
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression"}
                },
                "required": ["expression"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
]

def execute_tool(name: str, args: dict) -> str:
    if name == "search":
        # Call actual search API
        return search_web(args["query"])
    elif name == "calculator":
        return str(eval(args["expression"]))  # Simplified; use safe eval
    
def react_agent(question: str) -> str:
    """ReAct agent using Responses API"""
    
    instructions = """You are a ReAct agent. For each step:
    1. Think about what you need to do next
    2. Use a tool if needed
    3. Based on the result, think again
    Continue until you have the final answer."""
    
    response = client.responses.create(
        model="gpt-4o",
        instructions=instructions,
        input=question,
        tools=tools
    )
    
    # ReAct loop
    while response.output:
        tool_calls = [item for item in response.output if item.type == "function_call"]
        
        if not tool_calls:
            # No more tool calls = final answer
            return response.output_text
        
        # Execute tools and collect results
        tool_results = []
        for call in tool_calls:
            result = execute_tool(call.name, call.arguments)
            tool_results.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": result
            })
        
        # Continue conversation with tool results
        response = client.responses.create(
            model="gpt-4o",
            previous_response_id=response.id,
            input=tool_results,
            tools=tools
        )
    
    return response.output_text
```

**Note:** The Responses API is explicitly designed as an "agentic loop" that naturally supports ReAct-style reasoning with `previous_response_id` maintaining state.

---

## When ReAct Works Best

|Task Type|ReAct Fit|Why|
|---|---|---|
|Multi-hop QA (HotPotQA)|✅ Excellent|Requires chaining facts from multiple sources|
|Fact verification (FEVER)|✅ Excellent|Must retrieve and verify claims|
|Text games (ALFWorld)|✅ Excellent|Dynamic environment requires adaptive planning|
|Web navigation (WebShop)|✅ Excellent|Actions produce new states to reason about|
|Pure math|⚠️ CoT may suffice|If no external data needed|
|Simple factual|⚠️ Overkill|Single lookup, no reasoning chain needed|

**Paper benchmarks:**

- HotPotQA: ReAct outperforms Act-only, competitive with CoT
- FEVER: ReAct outperforms both Act-only and CoT
- ALFWorld: ReAct +34% over imitation learning
- WebShop: ReAct +10% over RL methods

---

## ReAct Failure Modes

|Failure|Cause|Mitigation|
|---|---|---|
|**Bad search results**|Query too vague or wrong|Model struggles to recover; add query reformulation|
|**Infinite loops**|Model doesn't recognize completion|Max iterations + explicit stop criteria|
|**Thought-action mismatch**|Model says one thing, does another|Few-shot examples showing correct alignment|
|**Over-searching**|Model calls search for known facts|Prompt to use internal knowledge when confident|
|**Observation ignored**|Model doesn't update based on results|Emphasize observation incorporation in prompt|

**From the paper:** "Non-informative search results derail model reasoning and lead to difficulty in recovering and reformulating thoughts."

---

## ReAct + CoT Hybrid

The paper found **combining ReAct with CoT** works best:

```
Strategy:
1. Start with ReAct
2. If ReAct fails after N steps → fall back to CoT
3. If CoT lacks confidence → switch to ReAct for verification
```

**Why it works:**

- CoT is better when internal knowledge suffices
- ReAct is better when external grounding is needed
- Hybrid gets benefits of both

**Implementation heuristic:**

```python
def hybrid_agent(question):
    # Try ReAct first
    react_result = react_agent(question, max_steps=5)
    
    if react_result.confidence < 0.7 or react_result.failed:
        # Fall back to CoT
        cot_result = cot_agent(question)
        
        if cot_result.needs_verification:
            # Use ReAct to verify CoT claims
            return react_agent(f"Verify: {cot_result.answer}")
        
        return cot_result
    
    return react_result
```

---

## Key Takeaways

1. **ReAct = Thought + Action + Observation in a loop**
    
    - Reasoning guides action selection
    - Actions ground reasoning in reality
2. **Interleaving is critical**
    
    - Not "think then act" but "think, act, observe, think..."
    - Each observation updates the next thought
3. **ReAct beats alternatives**
    
    - CoT alone hallucinates (no fact-checking)
    - Act alone lacks strategy (no planning)
    - ReAct combines both strengths
4. **It's just prompting + parsing**
    
    - No magic—few-shot examples + structured format
    - Modern APIs (Responses API) make this native
5. **Hybrid approaches win**
    
    - ReAct + CoT with fallback > either alone
    - Use internal knowledge when confident, tools when uncertain
6. **Failure modes exist**
    
    - Bad search results derail reasoning
    - Need max iterations and recovery strategies

---

## Connection to Previous Topics

- **Agent Loop (Observe → Think → Act):** ReAct is the dominant implementation of this pattern
- **What Is an Agent:** ReAct is what makes an agent "agentic"—the LLM controls flow via reasoning

## Up Next

Now that we understand the ReAct pattern conceptually, the next topic covers the mechanics: **Tool Calling** — how tools are defined, invoked, and how results flow back into the agent.