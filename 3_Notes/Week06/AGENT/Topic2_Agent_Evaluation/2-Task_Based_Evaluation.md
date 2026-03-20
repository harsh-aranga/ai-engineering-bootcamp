# Note 2: Task-Based Evaluation — Defining Success Criteria

## Why This Matters

Before you can evaluate an agent, you need to define what "success" looks like. This sounds obvious, but it's where most evaluation efforts fail.

Without well-designed test cases:

- You'll test easy cases and miss edge cases
- You'll use vague success criteria that different people interpret differently
- You'll have no way to know if your changes helped or hurt
- Your evaluation won't catch the failures that matter in production

This note covers the foundation: how to design test cases, build datasets, and define success criteria that actually measure what you care about.

---

## What Is Task-Based Evaluation?

Task-based evaluation is the simplest form of agent evaluation. It treats the agent as a black box:

```
┌────────────────────────────────────────────────────────────┐
│                    TASK-BASED EVALUATION                   │
│                                                            │
│  1. Define task input                                      │
│  2. Define expected outcome                                │
│  3. Run agent                                              │
│  4. Compare actual outcome to expected                     │
│  5. Score: pass/fail or partial credit                     │
└────────────────────────────────────────────────────────────┘
```

This is the evaluation equivalent of a unit test: given this input, I expect this output.

**When to use task-based evaluation:**

- Regression testing (did my changes break existing behavior?)
- Benchmarking (how does this agent compare to another?)
- Monitoring production quality (are we still succeeding on known tasks?)

**Limitations:**

- Doesn't tell you _why_ failures occur
- Can miss trajectory problems (agent got lucky but reasoned poorly)
- Requires you to know what "correct" looks like

---

## Anatomy of a Good Test Case

A well-designed test case has five components:

### 1. Input (The Task/Prompt)

What the user asks the agent to do. This should be:

- Realistic (similar to actual user queries)
- Unambiguous enough to have a verifiable outcome
- Representative of a category of queries you care about

```python
# Good: Specific, verifiable
input = "What is the current weather in Tokyo?"

# Bad: Too vague to evaluate
input = "Tell me about Tokyo"

# Good: Realistic agent task
input = "Book a meeting with John Smith for tomorrow at 2pm"

# Bad: Unrealistic for your agent
input = "Write a novel"
```

### 2. Expected Outcome (What Should Happen)

The ground truth against which you'll compare the agent's output. This can be:

- **Exact match**: "The answer should be 'Tokyo, Japan'"
- **Contains**: "The answer should mention 'Tokyo Tower'"
- **Semantic**: "The answer should convey that it will rain tomorrow"
- **State change**: "A calendar event should exist with these properties"

```python
expected_outcome = {
    "type": "contains",
    "value": "weather in Tokyo",
    "notes": "Should mention current temperature or conditions"
}
```

### 3. Success Criteria (Checkboxes for Partial Credit)

For complex tasks, binary pass/fail is too coarse. Define multiple criteria:

```python
success_criteria = [
    {"criterion": "Used weather tool", "required": True},
    {"criterion": "Mentioned temperature", "required": True},
    {"criterion": "Mentioned precipitation", "required": False},
    {"criterion": "Response in English", "required": True},
    {"criterion": "Response under 100 words", "required": False}
]
```

The `required` flag distinguishes hard requirements from nice-to-haves.

### 4. Expected Tools (Which Tools Should Be Used)

For agents, _how_ they solve the task matters:

```python
expected_tools = {
    "must_use": ["weather_api"],  # Required tools
    "may_use": ["geocoding"],      # Optional but acceptable
    "must_not_use": ["web_search"] # Forbidden for this task
}
```

This catches cases where the agent gets the right answer using the wrong approach (e.g., web scraping instead of the official API).

### 5. Metadata (Context for Analysis)

Information that helps you analyze results later:

```python
metadata = {
    "category": "weather_queries",
    "difficulty": "easy",
    "source": "production_logs",
    "created_at": "2025-03-15",
    "edge_case": False
}
```

---

## Complete Test Case Example

Here's a complete test case for an agent with search and note-taking capabilities:

```python
test_case = {
    # Input
    "input": {
        "task": "Find the current CEO of OpenAI and save a note about them"
    },
    
    # Expected outcome
    "expected_outcome": {
        "note_saved": True,
        "note_contains": ["Sam Altman", "CEO", "OpenAI"],
        "factually_correct": True
    },
    
    # Success criteria (partial credit)
    "success_criteria": [
        {"criterion": "Agent completed without errors", "required": True, "weight": 1.0},
        {"criterion": "Note was saved", "required": True, "weight": 1.0},
        {"criterion": "Note contains CEO name", "required": True, "weight": 1.0},
        {"criterion": "Information is current/correct", "required": True, "weight": 1.0},
        {"criterion": "Used search tool (not hallucinated)", "required": True, "weight": 0.5},
        {"criterion": "Completed in under 5 tool calls", "required": False, "weight": 0.25}
    ],
    
    # Expected tools
    "expected_tools": {
        "must_use": ["search", "save_note"],
        "may_use": [],
        "must_not_use": []
    },
    
    # Metadata
    "metadata": {
        "category": "search_and_save",
        "difficulty": "medium",
        "source": "manual_curation",
        "tests": ["tool_selection", "information_retrieval", "note_creation"]
    }
}
```

---

## Building a Test Case Dataset

### Start Small, Grow Intentionally

You don't need hundreds of test cases to start. Follow this progression:

|Phase|Size|Focus|
|---|---|---|
|**Bootstrap**|10-20 cases|Cover main happy paths|
|**Expand**|50-100 cases|Add edge cases, failure modes|
|**Production**|100-500+ cases|Add real user failures, comprehensive coverage|

### Three Sources of Test Cases

#### 1. Manual Curation (Bootstrap)

Start by hand-crafting test cases that cover:

- **Happy paths**: Normal, expected usage
- **Edge cases**: Boundary conditions, unusual inputs
- **Known failure modes**: Cases that have broken before

```python
manually_curated = [
    # Happy path
    {"input": "What's the weather in New York?", "category": "weather", "difficulty": "easy"},
    
    # Edge case: ambiguous location
    {"input": "What's the weather in Springfield?", "category": "weather", "difficulty": "hard"},
    
    # Edge case: no result expected
    {"input": "What's the weather on Mars?", "category": "weather", "difficulty": "edge"},
    
    # Known failure mode
    {"input": "Weather New York tomorrow", "category": "weather", "difficulty": "medium",
     "notes": "Previously failed due to missing 'in' preposition"}
]
```

#### 2. Production Failures (High Value)

When your agent fails in production, capture that trace as a test case:

```python
# Pseudocode for capturing production failures
def on_user_feedback(trace, feedback):
    if feedback.rating == "negative":
        # Convert this trace to a test case
        test_case = {
            "input": trace.input,
            "expected_outcome": get_expected_from_human(trace),
            "source": "production_failure",
            "original_trace_id": trace.id
        }
        add_to_dataset(test_case)
```

This is the highest-value source because:

- It represents real user queries
- It captures failure modes you didn't anticipate
- It ensures you don't regress on fixed bugs

#### 3. Synthetic Generation (Scale)

Use an LLM to generate variations of existing test cases:

```python
def generate_synthetic_cases(seed_case: dict, n_variations: int = 5) -> list[dict]:
    """Generate variations of a seed test case using an LLM."""
    
    prompt = f"""Given this test case for an AI agent:
    Task: {seed_case['input']['task']}
    Category: {seed_case['metadata']['category']}
    
    Generate {n_variations} similar but different test cases that:
    1. Test the same capability
    2. Have different phrasing/parameters
    3. Include some edge cases
    
    Return as JSON array with 'task' and 'difficulty' fields."""
    
    # Call LLM and parse response
    variations = call_llm(prompt)
    
    # Tag as synthetic for tracking
    for v in variations:
        v["metadata"] = {"source": "synthetic", "seed_case": seed_case["id"]}
    
    return variations
```

**Important:** Always tag synthetic cases and review them manually before trusting them in your evaluation suite.

---

## Success Criteria Design

### Binary vs. Partial Credit

**Binary (pass/fail)** is simpler but loses information:

```python
def binary_evaluate(actual, expected) -> bool:
    return actual == expected  # True or False
```

**Partial credit** preserves more signal:

```python
def partial_evaluate(actual, criteria: list[dict]) -> float:
    """
    Returns score between 0.0 and 1.0
    """
    total_weight = sum(c.get("weight", 1.0) for c in criteria)
    earned_weight = 0.0
    
    for criterion in criteria:
        if check_criterion(actual, criterion):
            earned_weight += criterion.get("weight", 1.0)
    
    return earned_weight / total_weight
```

**Use partial credit when:**

- Tasks have multiple sub-goals
- You want to track improvement on individual aspects
- You need to prioritize which failures to fix first

### Required vs. Optional Criteria

Distinguish between:

- **Hard requirements**: Must pass for the test to pass
- **Soft requirements**: Nice to have, contribute to score

```python
def evaluate_with_requirements(actual, criteria: list[dict]) -> dict:
    results = {
        "passed": True,
        "score": 0.0,
        "failed_required": [],
        "failed_optional": []
    }
    
    total_weight = 0.0
    earned_weight = 0.0
    
    for criterion in criteria:
        met = check_criterion(actual, criterion)
        weight = criterion.get("weight", 1.0)
        total_weight += weight
        
        if met:
            earned_weight += weight
        else:
            if criterion.get("required", False):
                results["passed"] = False
                results["failed_required"].append(criterion["criterion"])
            else:
                results["failed_optional"].append(criterion["criterion"])
    
    results["score"] = earned_weight / total_weight if total_weight > 0 else 0.0
    return results
```

### Criteria Categories

Design criteria that cover different aspects of agent behavior:

|Category|Example Criteria|
|---|---|
|**Correctness**|Answer matches expected, No factual errors|
|**Completeness**|All sub-tasks completed, All required info included|
|**Tool Use**|Used correct tools, Correct tool arguments|
|**Safety**|No dangerous actions, Respected rate limits|
|**Efficiency**|Completed in N steps, Under token budget|
|**Format**|Response in correct format, Proper structure|

---

## LangSmith Datasets

LangSmith provides infrastructure for managing evaluation datasets. Here's how to use it:

### Creating a Dataset (Python SDK)

```python
from langsmith import Client

client = Client()

# Create a new dataset
dataset = client.create_dataset(
    dataset_name="Agent Weather Evaluation",
    description="Test cases for weather-related agent tasks"
)

# Add examples to the dataset
examples = [
    {
        "inputs": {"task": "What's the weather in Tokyo?"},
        "outputs": {"expected_answer": "Should include current temperature and conditions"},
        "metadata": {"category": "weather", "difficulty": "easy"}
    },
    {
        "inputs": {"task": "Will it rain in London tomorrow?"},
        "outputs": {"expected_answer": "Should include precipitation forecast"},
        "metadata": {"category": "weather", "difficulty": "medium"}
    }
]

for example in examples:
    client.create_example(
        inputs=example["inputs"],
        outputs=example["outputs"],
        metadata=example["metadata"],
        dataset_id=dataset.id
    )
```

### Adding Production Traces to Dataset

When you find interesting or problematic runs in production:

```python
# Get runs from a project
runs = client.list_runs(
    project_name="my-agent-production",
    filter='eq(feedback_key, "thumbs_down")'  # Only negative feedback
)

# Add them to evaluation dataset
for run in runs:
    client.create_example(
        inputs=run.inputs,
        outputs={"expected": "TBD - needs human annotation"},
        metadata={"source": "production", "trace_id": str(run.id)},
        dataset_id=dataset.id
    )
```

### Dataset Versioning

LangSmith automatically versions datasets:

```python
# Datasets are versioned automatically on every edit
# You can tag specific versions for reference

# Use a specific dataset version in evaluation
results = client.evaluate(
    target=my_agent,
    data="Agent Weather Evaluation",  # Uses latest version by default
    # Or specify a version tag
)
```

**Best practice:** Tag versions before major deployments so you can compare apples-to-apples.

---

## Offline vs. Online Evaluation

These are two complementary evaluation modes:

### Offline Evaluation (Pre-Deployment)

**What:** Run your agent against a curated dataset during development.

**When:** Before deploying changes. Acts like unit tests for your agent.

**How:**

```python
from langsmith import evaluate

# Run evaluation on dataset
results = evaluate(
    target=my_agent,
    data="Agent Weather Evaluation",
    evaluators=[correctness_evaluator, tool_use_evaluator],
    experiment_prefix="v2.0-candidate"
)

# Check results before deploying
if results.aggregate_score < 0.95:
    raise Exception("Evaluation failed - do not deploy")
```

**Benefits:**

- Catches regressions before users see them
- Reproducible (same dataset, same tests)
- Can integrate with CI/CD

### Online Evaluation (Post-Deployment)

**What:** Score production traces in real-time as users interact with your agent.

**When:** Continuously, after deployment. Monitors quality drift.

**How:**

```python
# In LangSmith, configure online evaluators to run on production traces
# These score incoming traces against criteria you define

# Example: Set up an online evaluator that checks response safety
# This runs automatically on every production trace
```

**Benefits:**

- Catches issues on real user traffic
- Detects edge cases your test suite missed
- Monitors for quality degradation over time

### The Evaluation Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                      EVALUATION LIFECYCLE                           │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   DEVELOP    │───►│   OFFLINE    │───►│   DEPLOY     │          │
│  │              │    │   EVAL       │    │              │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         ▲                                       │                   │
│         │                                       ▼                   │
│         │            ┌──────────────┐    ┌──────────────┐          │
│         └────────────│   ANALYZE    │◄───│   ONLINE     │          │
│                      │   FAILURES   │    │   EVAL       │          │
│                      └──────────────┘    └──────────────┘          │
│                             │                                       │
│                             ▼                                       │
│                      ┌──────────────┐                              │
│                      │   ADD TO     │                              │
│                      │   DATASET    │                              │
│                      └──────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

1. **Develop**: Make changes to agent
2. **Offline Eval**: Run against curated dataset, catch regressions
3. **Deploy**: If offline eval passes, ship to production
4. **Online Eval**: Monitor production traces for quality
5. **Analyze Failures**: When online eval catches issues, investigate
6. **Add to Dataset**: Convert failures to test cases, preventing regression

---

## Practical Tips

### 1. Start with What You Know

Don't wait for a perfect dataset. Start with 10-20 cases covering your most important use cases. You can always add more.

### 2. Make Criteria Measurable

Bad: "Response should be good" Good: "Response contains the booking confirmation number"

Bad: "Agent should be efficient" Good: "Agent completes in 5 or fewer tool calls"

### 3. Include Deliberately Failing Cases

Your evaluation should catch failures. Include test cases you know should fail (with current implementation) to verify your evaluator is working:

```python
negative_test_case = {
    "input": "This query will timeout the agent",
    "expected_outcome": "FAIL",
    "purpose": "Verify we detect timeout failures"
}
```

### 4. Version Your Datasets

When you change your dataset, you invalidate historical comparisons. Version explicitly:

- v1.0: Initial 50 cases
- v1.1: Added 10 edge cases from production
- v2.0: Major restructure, added tool use criteria

### 5. Separate Functional from Non-Functional Criteria

**Functional:** Does it work correctly?

- Correct answer
- Correct tool selection
- Task completed

**Non-Functional:** How well does it work?

- Response time
- Token usage
- User-friendliness

Test both, but prioritize functional correctness first.

---

## Key Takeaways

1. **A test case has five components:** Input, expected outcome, success criteria, expected tools, and metadata.
    
2. **Build datasets from three sources:** Manual curation (start here), production failures (highest value), synthetic generation (scale).
    
3. **Use partial credit scoring** for complex tasks—binary pass/fail loses too much signal.
    
4. **Distinguish required vs. optional criteria** to separate "must work" from "nice to have."
    
5. **Offline evaluation catches regressions before deployment.** Online evaluation catches issues in production traffic.
    
6. **The evaluation lifecycle is continuous:** develop → offline eval → deploy → online eval → analyze failures → add to dataset → repeat.
    

---

## References

- LangSmith Evaluation Quickstart: https://docs.langchain.com/langsmith/evaluation-quickstart
- LangSmith Dataset Management: https://docs.smith.langchain.com/evaluation/how_to_guides/manage_datasets
- LangSmith Cookbook - Evaluating Agents: https://github.com/langchain-ai/langsmith-cookbook/blob/main/testing-examples/agent_steps/evaluating_agents.ipynb
- LangSmith Python SDK: https://pypi.org/project/langsmith/