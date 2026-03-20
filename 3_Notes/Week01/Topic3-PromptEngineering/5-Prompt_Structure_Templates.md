# Prompt Structure Patterns
Prompt Structure Patterns are reusable ways of organizing instructions so large language models (LLMs) behave predictably, consistently, and safely. They do not make models smarter; they reduce ambiguity, constrain behavior, and improve reliability—especially in production systems.

Below are the core patterns, each described with:
- What it is  
- What it does  
- An example  

---
## 1. Instruction → Context → Input → Output (ICIO)
### What it is
A foundational structure that separates **what to do**, **why/under what constraints**, **the data**, and **the expected output format**.
### What it does
Reduces ambiguity by forcing the model to build an execution plan before processing the input.
### Example

```text
Instruction:
Summarize the document.

Context:
The audience is senior engineers. Avoid simplifications.

Input:
<<<
<document text>
>>>

Output:
Bullet points, maximum 6 lines.
````

---
## 2. Role-Based Prompting
### What it is
Explicitly assigns the model a role or responsibility.
### What it does
Anchors tone, depth, and decision boundaries by narrowing the model’s behavioral space.
### Example

```text
You are a principal software architect.
Evaluate the design trade-offs and operational risks.
Do not explain basic concepts.
```

---
## 3. Delimited Input Pattern
### What it is
Uses clear markers to separate instructions from data.
### What it does
Prevents the model from interpreting input data as instructions and improves safety and correctness for long or mixed-content prompts.
### Example

```text
Analyze the following text:

<<<BEGIN INPUT>>>
User-generated content goes here.
<<<END INPUT>>>
```

---
## 4. Output Schema Pattern
### What it is
Defines the expected structure of the response explicitly.
### What it does
Makes outputs machine-readable, composable, and easier to validate or chain into downstream systems.
### Example

```text
Return the output in the following JSON format:
{
  "summary": string,
  "risks": [string],
  "recommendation": string
}
```

---
## 5. Step-Guided Execution Pattern
### What it is
Specifies the steps the model must follow without asking it to reveal internal reasoning.
### What it does
Controls execution order and reduces logical skips while keeping reasoning implicit.
### Example

```text
Follow this process:
1. Identify assumptions
2. Evaluate constraints
3. Produce the final answer only
```

---
## 6. Few-Shot Pattern (Example Anchoring)
### What it is
Provides one or more input–output examples before the actual task.
### What it does
Anchors tone, format, and interpretation when rules are difficult to describe precisely.
### Example

```text
Input:
Convert text to uppercase.
Output:
HELLO WORLD

Input:
Convert text to uppercase.
Output:
SYSTEM DESIGN

Now process:
Input:
Distributed systems
```

---
## 7. Constraint-First Pattern
### What it is
Places constraints and rules before the task description.
### What it does
Ensures limitations are applied globally and not overridden by later instructions.
### Example

```text
Constraints:
- Do not speculate
- Maximum 100 words
- No examples

Task:
Explain eventual consistency.
```

---
## 8. Single-Responsibility Prompt Pattern
### What it is
Designs a prompt to perform exactly one task.
### What it does
Improves reliability and composability, especially in multi-step or agent-based systems.
### Example

```text
Task:
Extract all dates mentioned in the text.
Return only the dates as a list.
```

---
# Closing Note
Prompt Structure Patterns are best understood as **interfaces**, not tricks.
They reduce entropy, improve debuggability, and make LLM behavior more predictable—especially when prompts are reused, chained, or embedded in software systems.

Structure does not increase intelligence.
It increases control.