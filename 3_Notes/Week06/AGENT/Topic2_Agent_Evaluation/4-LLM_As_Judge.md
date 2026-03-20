# Note 4: LLM-as-Judge for Agent Quality

## Why This Matters

Trajectory matching (Note 3) works when you have a known correct path. But agents are non-deterministic—the same query can have multiple valid trajectories.

Consider:

- Agent A: `search("SF weather")` → respond
- Agent B: `search("San Francisco weather forecast")` → respond
- Agent C: `search("weather")` → `search("SF")` → respond

All three might produce correct answers. A strict trajectory match would fail two of them. But a human reviewer would say: "These are all fine."

**LLM-as-judge** lets you evaluate agent behavior the way a human would—assessing whether trajectories are _reasonable_, not whether they're _identical_.

This approach:

- Handles non-deterministic outputs gracefully
- Evaluates nuanced qualities (efficiency, appropriateness, safety)
- Scales without requiring exhaustive reference trajectories
- Can assess aspects that have no "correct" answer

---

## What Is LLM-as-Judge?

LLM-as-judge uses a capable language model (the "judge") to evaluate another model's outputs. Instead of rule-based checks, you prompt the judge to assess quality based on criteria you define.

```
┌────────────────────────────────────────────────────────────────┐
│                       LLM-AS-JUDGE                              │
│                                                                │
│   ┌─────────────────┐    ┌─────────────────┐                   │
│   │  Agent Output   │───►│   Judge LLM     │───► Score + Reason│
│   │  (trajectory)   │    │  (GPT-4, etc.)  │                   │
│   └─────────────────┘    └─────────────────┘                   │
│           ▲                      │                              │
│           │                      │                              │
│   ┌───────┴───────┐      ┌──────▼──────┐                       │
│   │   Optional    │      │  Evaluation │                       │
│   │   Reference   │      │   Criteria  │                       │
│   └───────────────┘      └─────────────┘                       │
└────────────────────────────────────────────────────────────────┘
```

**Why it works:** LLMs trained with RLHF internalize human preferences. GPT-4 as judge achieves ~80% agreement with human evaluators—matching human-to-human consistency.

---

## Using `agentevals` for Trajectory Judging

The `agentevals` library provides `create_trajectory_llm_as_judge()` for trajectory evaluation:

```python
from agentevals.trajectory.llm import (
    create_trajectory_llm_as_judge,
    TRAJECTORY_ACCURACY_PROMPT,
    TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE
)
import json

# Create evaluator (no reference required)
evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini"  # Model string format: "provider:model_name"
)

# Example trajectory to evaluate
trajectory = [
    {"role": "user", "content": "What's the weather in Tokyo?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"city": "Tokyo"})
            }
        }]
    },
    {"role": "tool", "content": "72°F, partly cloudy"},
    {"role": "assistant", "content": "The weather in Tokyo is 72°F and partly cloudy."}
]

# Evaluate
result = evaluator(outputs=trajectory)

print(result)
# {
#     'key': 'trajectory_accuracy',
#     'score': True,
#     'comment': 'The trajectory accurately follows the user's request...'
# }
```

**Source:** agentevals GitHub repository (https://github.com/langchain-ai/agentevals)

---

## Built-in Prompts

The library provides two main prompt templates:

### `TRAJECTORY_ACCURACY_PROMPT` (No Reference)

Use when you don't have a reference trajectory. The judge evaluates whether the trajectory is _reasonable_ based on general principles.

```python
evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini"
)

result = evaluator(outputs=trajectory)
```

**What it evaluates:**

- Is the trajectory logically coherent?
- Do the steps make progress toward the goal?
- Is the final response aligned with the user's request?
- Are the tool calls reasonable for the task?

### `TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE` (With Reference)

Use when you have a reference trajectory to compare against. The judge evaluates whether the actual trajectory is _semantically equivalent_ to the reference.

```python
evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE,
    model="openai:o3-mini"
)

result = evaluator(
    outputs=actual_trajectory,
    reference_outputs=reference_trajectory
)
```

**What it evaluates:**

- Does the trajectory achieve the same goal as the reference?
- Are the differences between trajectories acceptable?
- Did the agent use equivalent (not necessarily identical) approaches?

---

## Key Parameters

The `create_trajectory_llm_as_judge()` function accepts several parameters for customization:

### `model`

Which LLM to use as the judge. Format: `"provider:model_name"`.

```python
# OpenAI
model = "openai:gpt-4o"
model = "openai:o3-mini"  # Reasoning model, good for complex judgments

# Anthropic
model = "anthropic:claude-3-opus-20240229"
model = "anthropic:claude-3-sonnet-20240229"
```

**Choosing a judge model:**

- Use capable models (GPT-4-class) for higher agreement with humans
- Reasoning models (o3-mini, o1) often perform better on nuanced evaluations
- Smaller models are cheaper but less reliable

### `continuous`

Whether to return a continuous float score (0.0-1.0) instead of binary (True/False).

```python
# Binary scoring (default)
evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini",
    continuous=False  # Default: returns True/False
)

# Continuous scoring
evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini",
    continuous=True  # Returns 0.0-1.0
)
```

**When to use continuous:**

- When you want granular quality scores
- When you're tracking improvement over time
- When you're comparing multiple agents

### `choices`

Restrict the score to specific values (for non-binary, non-continuous scoring).

```python
# 5-point scale
evaluator = create_trajectory_llm_as_judge(
    prompt=custom_prompt,
    model="openai:o3-mini",
    choices=[0.0, 0.25, 0.5, 0.75, 1.0]
)
```

### `system`

Prepend a system message to the judge prompt.

```python
evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini",
    system="You are an expert evaluator for customer service agents. Be strict about politeness."
)
```

### `few_shot_examples`

Provide calibration examples showing the judge how to score.

```python
few_shot_examples = [
    {
        "inputs": "Book a flight to NYC",
        "outputs": "[trajectory with correct tools]",
        "reasoning": "The agent correctly searched for flights and made a booking.",
        "score": 1.0
    },
    {
        "inputs": "Book a flight to NYC",
        "outputs": "[trajectory with wrong tools]",
        "reasoning": "The agent searched for hotels instead of flights.",
        "score": 0.0
    }
]

evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini",
    few_shot_examples=few_shot_examples
)
```

**Source:** openevals and agentevals documentation (https://github.com/langchain-ai/openevals)

---

## Designing Custom Judge Prompts

The built-in prompts are good starting points, but you'll often want custom evaluation criteria.

### Prompt Structure

A good judge prompt has:

1. **Role definition**: Who the judge is
2. **Criteria/Rubric**: What to evaluate
3. **Instructions**: How to score
4. **Output format**: What to return

```python
CUSTOM_TRAJECTORY_PROMPT = """You are an expert evaluator for AI customer service agents.

<Criteria>
Evaluate the agent's trajectory based on:
1. EFFICIENCY: Did the agent complete the task with minimal steps? 
2. CORRECTNESS: Did the agent use the right tools with correct arguments?
3. SAFETY: Did the agent avoid dangerous or unauthorized actions?
4. POLITENESS: Was the agent's communication professional?
</Criteria>

<Rubric>
- Score 1.0: All criteria met excellently
- Score 0.75: Minor issues in one area
- Score 0.5: Significant issues in one area OR minor issues in multiple
- Score 0.25: Significant issues in multiple areas
- Score 0.0: Failed to complete task OR safety violation
</Rubric>

<Instructions>
1. Review the trajectory carefully
2. Assess each criterion
3. Explain your reasoning step-by-step
4. Provide a final score based on the rubric
</Instructions>

<Trajectory>
{outputs}
</Trajectory>

Provide your evaluation:"""

evaluator = create_trajectory_llm_as_judge(
    prompt=CUSTOM_TRAJECTORY_PROMPT,
    model="openai:o3-mini",
    choices=[0.0, 0.25, 0.5, 0.75, 1.0]
)
```

### Criteria to Consider

|Dimension|What to Evaluate|
|---|---|
|**Efficiency**|Minimal steps, no redundant tool calls, fast completion|
|**Correctness**|Right tools, correct arguments, accurate final answer|
|**Safety**|No dangerous actions, respected guardrails, proper authorization|
|**Completeness**|All sub-tasks addressed, no partial completion|
|**Error Handling**|Recovered from tool failures, handled edge cases|
|**Coherence**|Logical progression, consistent reasoning|

### Chain-of-Thought in Judge Output

Requiring the judge to explain its reasoning improves score quality:

```python
PROMPT_WITH_COT = """...

Before scoring, explain your reasoning step by step:
1. What was the user's goal?
2. What tools did the agent use?
3. Were the tool calls appropriate?
4. Was the final response correct?
5. Were there any issues?

Then provide your final score.
"""
```

**Why this helps:**

- Forces the judge to consider all aspects
- Makes scores more consistent
- Provides interpretable feedback for debugging
- Reduces bias from snap judgments

---

## Multi-Level Judging

For comprehensive agent evaluation, use different judges at different levels:

### Level 1: Final Response Quality

Does the final answer satisfy the user?

```python
from openevals.prompts import CORRECTNESS_PROMPT
from openevals.llm import create_llm_as_judge

response_judge = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    model="openai:o3-mini"
)

# Evaluate just the final response
final_message = trajectory[-1]["content"]
result = response_judge(
    outputs=final_message,
    reference_outputs=expected_answer
)
```

### Level 2: Trajectory Reasonableness

Was the path to the answer sensible?

```python
from agentevals.trajectory.llm import create_trajectory_llm_as_judge

trajectory_judge = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini"
)

result = trajectory_judge(outputs=trajectory)
```

### Level 3: Individual Step Quality

Was each decision correct?

```python
STEP_EVALUATION_PROMPT = """Given the context so far, evaluate whether this step was appropriate.

Context:
{context}

Step being evaluated:
{step}

Was this step appropriate? Consider:
- Given the user's goal, was this action logical?
- Were the tool arguments correct?
- Was this the most efficient choice?
"""

step_judge = create_llm_as_judge(
    prompt=STEP_EVALUATION_PROMPT,
    model="openai:o3-mini"
)

# Evaluate each step in context
for i, step in enumerate(trajectory):
    context = trajectory[:i]
    result = step_judge(
        context=str(context),
        step=str(step)
    )
```

### Combining Multiple Judges

```python
def comprehensive_evaluation(trajectory: list[dict], reference: dict) -> dict:
    """Run multi-level evaluation on a trajectory."""
    
    # Level 1: Final response
    response_score = response_judge(
        outputs=trajectory[-1]["content"],
        reference_outputs=reference.get("expected_answer")
    )
    
    # Level 2: Trajectory
    trajectory_score = trajectory_judge(
        outputs=trajectory,
        reference_outputs=reference.get("expected_trajectory")
    )
    
    # Level 3: Critical steps only (for efficiency)
    step_scores = []
    for step in get_tool_call_steps(trajectory):
        step_score = step_judge(...)
        step_scores.append(step_score)
    
    return {
        "response_quality": response_score,
        "trajectory_quality": trajectory_score,
        "step_quality": step_scores,
        "overall": compute_weighted_average(...)
    }
```

---

## Calibrating LLM Judges

LLM judges are not perfect. They have biases and can be inconsistent. Calibration helps.

### Known Biases

|Bias|Description|Mitigation|
|---|---|---|
|**Position bias**|Prefers outputs based on order in prompt|Evaluate (A,B) and (B,A), average results|
|**Verbosity bias**|Prefers longer outputs|Explicitly instruct to reward conciseness|
|**Self-enhancement**|Prefers outputs from same model family|Use different model families|
|**Authority bias**|Over-trusts confident-sounding outputs|Instruct to verify claims|
|**Recency bias**|Favors more recent items in context|Randomize order|

### Human-in-the-Loop Calibration

The gold standard for judge calibration:

1. **Collect human annotations** on a sample of trajectories
2. **Run your judge** on the same samples
3. **Measure agreement** (Cohen's Kappa, percent agreement)
4. **Identify disagreements** — where does the judge fail?
5. **Refine judge prompt** based on failure patterns
6. **Repeat** until agreement is acceptable

```python
# Pseudocode for calibration workflow
calibration_set = [
    {"trajectory": t1, "human_score": 0.8, "human_reasoning": "..."},
    {"trajectory": t2, "human_score": 0.3, "human_reasoning": "..."},
    # ...
]

judge_scores = []
for example in calibration_set:
    result = evaluator(outputs=example["trajectory"])
    judge_scores.append(result["score"])

# Calculate agreement
agreement = calculate_agreement(
    human_scores=[e["human_score"] for e in calibration_set],
    judge_scores=judge_scores
)

# Find disagreements for analysis
disagreements = [
    e for e, j in zip(calibration_set, judge_scores)
    if abs(e["human_score"] - j) > 0.3
]
```

### LangSmith Annotation Queues

LangSmith provides infrastructure for human review:

1. **Flag runs for review**: Mark specific traces that need human evaluation
2. **Assign to reviewers**: Route to subject-matter experts
3. **Collect feedback**: Reviewers score and annotate
4. **Compare to judge**: Identify where automated evaluation disagrees
5. **Iterate**: Use disagreements to improve judge prompts

```python
from langsmith import Client

client = Client()

# Flag runs for human review
for run in uncertain_runs:
    client.create_feedback(
        run_id=run.id,
        key="needs_human_review",
        value=True
    )

# Later, use human feedback to calibrate
human_feedback = client.list_feedback(
    run_ids=[r.id for r in calibration_runs]
)
```

### Few-Shot Calibration

Use your calibration examples as few-shot examples for the judge:

```python
# Convert calibration set to few-shot examples
few_shot_examples = [
    {
        "inputs": e["trajectory"][0]["content"],  # User query
        "outputs": str(e["trajectory"]),
        "reasoning": e["human_reasoning"],
        "score": e["human_score"]
    }
    for e in calibration_set[:5]  # Use 5 examples
]

# Create calibrated evaluator
calibrated_evaluator = create_trajectory_llm_as_judge(
    prompt=TRAJECTORY_ACCURACY_PROMPT,
    model="openai:o3-mini",
    few_shot_examples=few_shot_examples
)
```

---

## Limitations of LLM-as-Judge

### 1. Cost

Every evaluation requires an LLM call.

|Scenario|Evals/Day|Cost @ $0.03/eval|
|---|---|---|
|Dev testing|100|$3/day|
|CI/CD|1,000|$30/day|
|Production sampling|10,000|$300/day|

**Mitigations:**

- Sample production traffic (1-5%)
- Use cheaper models for screening, expensive models for critical decisions
- Cache evaluation results
- Use deterministic checks where possible, LLM-as-judge only where necessary

### 2. Non-Determinism

Same trajectory, different scores on different runs.

```python
# Run 5 times, get different scores
scores = []
for _ in range(5):
    result = evaluator(outputs=trajectory)
    scores.append(result["score"])

# scores might be: [0.8, 0.75, 0.85, 0.8, 0.7]
```

**Mitigations:**

- Run multiple evaluations, average or vote
- Use lower temperature for judge (if configurable)
- Use reasoning models (o3-mini, o1) which tend to be more consistent
- Accept that some variance is inherent

### 3. Bias

Judges have systematic preferences that may not align with yours.

**Mitigations:**

- Calibrate against human judgments
- Use multiple judge models and ensemble
- Explicitly address biases in the prompt
- Monitor for drift over time

### 4. Evaluation of the Evaluator

How do you know your judge is good? You need meta-evaluation.

```python
# Meta-evaluation workflow
def evaluate_judge(judge, calibration_set):
    """Evaluate how well the judge agrees with human annotations."""
    
    judge_scores = [judge(outputs=e["trajectory"])["score"] for e in calibration_set]
    human_scores = [e["human_score"] for e in calibration_set]
    
    return {
        "correlation": pearsonr(judge_scores, human_scores),
        "agreement_rate": sum(1 for j, h in zip(judge_scores, human_scores) if abs(j-h) < 0.2) / len(calibration_set),
        "bias": mean(judge_scores) - mean(human_scores)
    }
```

---

## Practical Recommendations

### When to Use LLM-as-Judge

✅ **Use for:**

- Evaluating non-deterministic agent behavior
- Assessing subjective qualities (helpfulness, politeness)
- Scaling evaluation beyond what humans can review
- Quick iteration during development

❌ **Avoid for:**

- Tasks with deterministic correct answers (use exact match)
- Format validation (use schema checks)
- Real-time evaluation (<50ms required)
- When you have no calibration data

### Evaluation Strategy by Stage

|Stage|Primary Method|LLM-as-Judge Role|
|---|---|---|
|**Development**|Manual inspection|Quick feedback on changes|
|**Pre-deployment**|Offline eval on dataset|Comprehensive trajectory assessment|
|**Production**|Online sampling|Quality monitoring, drift detection|
|**Post-incident**|Root cause analysis|Understand what went wrong|

### Cost-Effective Judge Usage

1. **Layer your evaluation:**
    
    - First: Fast, cheap checks (format, schema, keywords)
    - Second: Deterministic trajectory matching where applicable
    - Third: LLM-as-judge only for what passes earlier filters
2. **Sample strategically:**
    
    - Sample 1-5% of production traffic for evaluation
    - Oversample from tails (very short, very long, error cases)
    - Use stratified sampling by query type
3. **Cache results:**
    
    - Same trajectory → same evaluation
    - Store evaluation results for debugging

---

## Key Takeaways

1. **LLM-as-judge evaluates like a human would**—assessing reasonableness, not exact matches. Use it for non-deterministic agent outputs.
    
2. **Use `create_trajectory_llm_as_judge()`** from `agentevals` with `TRAJECTORY_ACCURACY_PROMPT` (no reference) or `TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE` (with reference).
    
3. **Key parameters:** `model` (judge LLM), `continuous` (float vs binary scores), `few_shot_examples` (calibration).
    
4. **Design custom prompts** with clear criteria, rubrics, and chain-of-thought instructions.
    
5. **Use multi-level judging:** Final response quality + trajectory reasonableness + individual step quality.
    
6. **Calibrate against humans:** Collect human annotations, measure agreement, refine prompts based on disagreements.
    
7. **Know the limitations:** Cost, non-determinism, bias. Mitigate with sampling, ensembling, and explicit prompt instructions.
    
8. **Layer evaluation:** Use LLM-as-judge strategically alongside deterministic checks, not as a replacement.
    

---

## References

- agentevals Library: https://github.com/langchain-ai/agentevals
- openevals Library: https://github.com/langchain-ai/openevals
- LangSmith Trajectory Evaluation: https://docs.langchain.com/langsmith/trajectory-evals
- Langfuse Agent Evaluation Guide: https://langfuse.com/guides/cookbook/example_pydantic_ai_mcp_agent_evaluation
- "Judging LLM-as-a-Judge" Paper: https://arxiv.org/abs/2306.05685
- "Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge": https://openreview.net/forum?id=3GTtZFiajM
- LLM-as-Judge Calibration (Cameron Wolfe): https://cameronrwolfe.substack.com/p/llm-as-a-judge