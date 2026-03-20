# Week 6: Parallel Tracks — RAG Evaluation & Multi-Agent Systems

> **Track:** Parallel (RAG + Agents) — FINAL WEEK OF PARALLEL PHASE **Time:** 2 hours/day (1 hour RAG + 1 hour Agents) **Goal:** Complete both tracks with evaluation capabilities and portfolio-ready final builds.

---

## Overview

### RAG Track (1 hour/day)

|Days|Topic|Output|
|---|---|---|
|1-2|RAG Evaluation Fundamentals|Eval metrics implemented|
|3-4|Debugging Bad Retrieval|Diagnostic framework|
|5-7|Final Build|Production RAG with Eval Pipeline|

### Agent Track (1 hour/day)

|Days|Topic|Output|
|---|---|---|
|1-2|Multi-Agent Patterns|Pattern implementations|
|3-4|Agent Evaluation|Eval framework|
|5-7|Final Build|Multi-Agent System with Eval|

---

# RAG TRACK

---

## Days 1-2 (RAG): RAG Evaluation Fundamentals

### Why This Matters

You've built RAG v1, improved it to v2 with hybrid search, reranking, and query transformation. But how do you _know_ v2 is better? "It feels better" doesn't cut it in production or interviews.

Evaluation gives you:

- Proof that your system works (for stakeholders, for yourself)
- Signal for where to improve (which component is failing?)
- Regression detection (did that change break something?)

Without eval, you're flying blind.

### What to Learn

**Core Concepts:**

**Retrieval Metrics (Is the right context being retrieved?):**

- **Recall@K**: Of all relevant documents, what fraction did you retrieve in top-K?
- **Precision@K**: Of the K documents retrieved, what fraction are relevant?
- **MRR (Mean Reciprocal Rank)**: How high is the first relevant document ranked?
- **NDCG (Normalized Discounted Cumulative Gain)**: Are relevant documents ranked higher than irrelevant ones?
- **Hit Rate**: Did you retrieve _any_ relevant document?

**Generation Metrics (Is the answer good?):**

- **Faithfulness**: Is the answer supported by the retrieved context? (No hallucination)
- **Answer Relevance**: Does the answer address the question?
- **Context Relevance**: Is the retrieved context relevant to the question?
- **Correctness**: Is the answer factually correct? (Requires ground truth)

**Evaluation Components:**

```
[Question] ──> [Retriever] ──> [Retrieved Docs] ──> [Generator] ──> [Answer]
                   │                   │                              │
                   ▼                   ▼                              ▼
            Retrieval Metrics    Context Metrics              Answer Metrics
            (recall, precision)  (context relevance)     (faithfulness, relevance)
```

**Practical Skills:**

- Build an evaluation dataset (questions + ground truth)
- Compute retrieval metrics
- Use LLM-as-judge for generation quality
- Interpret results and identify weak points

### Resources

**Primary:**

- RAGAS (RAG Assessment): https://docs.ragas.io/en/latest/
- LlamaIndex Evaluation: https://docs.llamaindex.ai/en/stable/module_guides/evaluating/
- LangChain Evaluation: https://python.langchain.com/docs/concepts/evaluation/

**Secondary:**

- Search: "RAG evaluation metrics explained"
- Search: "RAGAS tutorial"
- Search: "LLM as judge evaluation"

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Understand retrieval metrics: Recall@K, Precision@K, MRR (15 min)
2. Understand generation metrics: Faithfulness, relevance (10 min)
3. Read RAGAS overview — understand the framework (5 min)

**Next 30 min — Experiment:**

1. Create a small eval dataset: 10 questions with known answers and source documents
    
    ```python
    eval_data = [    {        "question": "What is our refund policy?",        "ground_truth": "30-day money-back guarantee",        "relevant_doc_ids": ["policy_doc_3", "faq_doc_7"]    },    # ... 9 more]
    ```
    
2. Run your RAG v2 on these questions
3. Manually check: Did it retrieve the right docs? Did it answer correctly?
4. This manual check is what we'll automate

### Day 2 Tasks (1 hour)

**First 30 min — Learn:**

1. Read about LLM-as-judge pattern (10 min)
2. Read RAGAS metrics in detail: faithfulness, answer_relevancy, context_precision (15 min)
3. Understand: When do you need ground truth vs. when can you evaluate without it? (5 min)

**Next 30 min — Experiment:**

1. Implement basic retrieval metrics:
    
    ```python
    def recall_at_k(retrieved_ids: list, relevant_ids: list, k: int) -> float:    """What fraction of relevant docs appear in top-k retrieved?"""    retrieved_k = set(retrieved_ids[:k])    relevant = set(relevant_ids)    if not relevant:        return 0.0    return len(retrieved_k & relevant) / len(relevant)def precision_at_k(retrieved_ids: list, relevant_ids: list, k: int) -> float:    """What fraction of top-k retrieved are relevant?"""    retrieved_k = set(retrieved_ids[:k])    relevant = set(relevant_ids)    if not retrieved_k:        return 0.0    return len(retrieved_k & relevant) / len(retrieved_k)
    ```
    
2. Implement simple LLM-as-judge for faithfulness:
    
    ```python
    def judge_faithfulness(question: str, context: str, answer: str) -> float:    """Use LLM to judge if answer is faithful to context."""    prompt = f"""    Question: {question}    Context: {context}    Answer: {answer}        Is the answer fully supported by the context?     Respond with a score from 0 to 1.    """    # Call LLM, parse score
    ```
    
3. Run on your 10-question eval set — compute metrics

### 5 Things to Ponder (RAG Evaluation)

1. You compute Recall@5 = 0.8 (80% of relevant docs retrieved). Sounds good. But the 20% missed includes the _most_ important document. Recall treats all relevant docs equally. How would you weight by importance?
    
2. LLM-as-judge: You ask GPT-4 to judge if an answer is faithful. But GPT-4 might have different standards than humans. It might be too lenient or too strict. How do you calibrate LLM judges? How do you know if the judge is reliable?
    
3. Your eval dataset has 50 questions. You built the dataset from documents you know well. But real users ask questions you never anticipated. How representative is your eval set? How do you handle the long tail of unexpected queries?
    
4. Faithfulness score is high (answer matches context). But context relevance is low (retrieved context doesn't answer the question). The RAG "correctly" generated from wrong context. Which metric caught the real problem?
    
5. You evaluate RAG v2 vs v1. V2 wins on retrieval metrics but loses on generation metrics. Which is better? How do you make a single decision from multiple metrics?
    

---

## Days 3-4 (RAG): Debugging Bad Retrieval

### Why This Matters

Your RAG returns a wrong answer. Why? The failure could be anywhere:

- Bad chunking (split relevant info across chunks)
- Bad embedding (semantically similar but wrong content retrieved)
- Bad retrieval (right docs exist but not retrieved)
- Bad context assembly (too much noise, relevant info buried)
- Bad generation (right context, wrong answer)

Systematic debugging pinpoints the problem.

### What to Learn

**Core Concepts:**

**The RAG Failure Taxonomy:**

```
1. INDEXING FAILURES (problems before retrieval)
   - Chunking split key information
   - Metadata not extracted/used
   - Document not indexed at all
   
2. RETRIEVAL FAILURES (wrong documents retrieved)
   - Query-document vocabulary mismatch
   - Embedding doesn't capture query intent
   - Relevant doc exists but ranked too low
   
3. CONTEXT FAILURES (right docs, wrong context)
   - Too many chunks → relevant info diluted
   - Chunks lack sufficient context
   - Reranking made wrong choices
   
4. GENERATION FAILURES (right context, wrong answer)
   - LLM hallucinated despite good context
   - LLM ignored relevant context
   - LLM misunderstood question
```

**Debugging Workflow:**

```
Bad Answer
    │
    ▼
Was relevant content in retrieved chunks? ──No──> RETRIEVAL FAILURE
    │                                              (check: embedding, query, index)
    Yes
    │
    ▼
Was relevant content in final context to LLM? ──No──> CONTEXT ASSEMBLY FAILURE
    │                                                  (check: reranking, k value)
    Yes
    │
    ▼
Did LLM use the relevant content? ──No──> GENERATION FAILURE
    │                                       (check: prompt, position, LLM limits)
    Yes
    │
    ▼
Something else is wrong (check ground truth, question ambiguity)
```

**Practical Skills:**

- Trace a failure through the pipeline
- Build diagnostic tools that expose each stage
- Identify patterns in failures (systematic vs. random)
- Prioritize fixes based on failure frequency

### Resources

**Primary:**

- Your own RAG v2 code (best resource — you'll debug it)
- LangSmith Tracing: https://docs.smith.langchain.com/ (for observability)

**Secondary:**

- Search: "RAG debugging techniques"
- Search: "retrieval failure analysis"

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Internalize the failure taxonomy above (10 min)
2. Think through: For each failure type, what would you check? (10 min)
3. Review your RAG v2 code: Where would you add logging/tracing? (10 min)

**Next 30 min — Build Diagnostic Tools:**

1. Add a `debug=True` mode to your RAG that returns full trace:
    
    ```python
    result = rag.query("question", debug=True)# result.debug contains:# - original_query# - transformed_query (if any)# - bm25_results (with scores)# - dense_results (with scores)# - fused_results# - reranked_results# - final_context (what LLM saw)# - answer
    ```
    
2. Test on a few queries — see the full pipeline

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `RAGDebugger` class:

```python
class RAGDebugger:
    def __init__(self, rag_system):
        """Wraps a RAG system with debugging capabilities."""
        self.rag = rag_system
    
    def diagnose_failure(
        self,
        question: str,
        expected_answer: str,
        relevant_doc_ids: list[str]
    ) -> dict:
        """
        Diagnose why RAG failed for a specific question.
        
        Returns:
            {
                "failure_type": "retrieval|context|generation|none",
                "failure_details": "...",
                "recommendations": ["..."],
                "trace": {...}  # Full pipeline trace
            }
        """
        pass
    
    def batch_diagnose(
        self,
        eval_set: list[dict]  # [{"question": ..., "expected": ..., "relevant_ids": ...}]
    ) -> dict:
        """
        Diagnose failures across an eval set.
        
        Returns:
            {
                "total": 50,
                "correct": 35,
                "failures": {
                    "retrieval": 8,
                    "context": 4,
                    "generation": 3
                },
                "patterns": ["query transformation not helping technical queries", ...],
                "priority_fixes": ["improve BM25 for error codes", ...]
            }
        """
        pass
    
    def compare_configs(
        self,
        question: str,
        configs: list[dict]  # Different RAG configurations
    ) -> dict:
        """
        Compare different RAG configurations on the same question.
        Shows which config retrieves better, generates better.
        """
        pass
```

**Success Criteria:**

- [ ] Single-question diagnosis identifies failure type accurately
- [ ] Provides actionable recommendations (not just "retrieval failed")
- [ ] Batch diagnosis aggregates patterns (not just individual failures)
- [ ] Can compare configurations (v1 vs v2, different settings)
- [ ] Tested on at least 10 failure cases
- [ ] Correctly identifies at least 3 different failure types
- [ ] Recommendations are specific ("add BM25 for keyword queries" not "improve retrieval")

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Debugging Bad Retrieval)

1. You diagnose: "Retrieval failure — relevant doc ranked #47, below top-20 cutoff." Easy fix: increase top-k. But that adds noise. How do you balance recall (getting relevant docs) vs. precision (not overwhelming with irrelevant)?
    
2. You find a pattern: Technical queries with error codes fail. Query transformation (HyDE) actually hurts — it generates hypothetical answers without the exact error code. How do you detect when a technique is hurting and bypass it?
    
3. Your batch diagnosis shows 60% retrieval failures, 25% generation failures, 15% context failures. You have limited time. Fixing retrieval helps most users. Fixing generation might be easier. How do you prioritize?
    
4. A failure: "The 2024 annual report shows..." but the doc is from 2023. The retrieval got a relevant doc, the answer is plausible, but wrong. This isn't retrieval, context, or generation failure in the classic sense. What category is this? How do you catch it?
    
5. You add extensive debugging. Now your RAG is 3x slower because of all the logging. In production, you can't afford this. How do you have visibility without killing performance? (Hint: sampling, async logging, separate debug path)
    

---

## Days 5-7 (RAG): Final Build — Production RAG with Eval Pipeline

### What to Build

This is the capstone of your RAG track. A complete, production-ready RAG system with:

- All retrieval improvements from Weeks 4-5
- Comprehensive evaluation pipeline
- Debugging capabilities
- Configuration management for A/B testing

This should be portfolio-worthy and GitHub-ready.

### Specifications

**Directory Structure:**

```
production_rag/
├── README.md
├── requirements.txt
├── config/
│   ├── default.yaml
│   └── experiments/
│       ├── v1_baseline.yaml
│       └── v2_hybrid.yaml
├── src/
│   ├── __init__.py
│   ├── indexer.py          # Document processing + indexing
│   ├── retriever.py        # Hybrid search, reranking
│   ├── generator.py        # LLM answer generation
│   ├── rag.py              # Main RAG orchestrator
│   ├── query_transform.py  # HyDE, expansion, rewriting
│   └── utils.py
├── eval/
│   ├── __init__.py
│   ├── metrics.py          # Retrieval + generation metrics
│   ├── evaluator.py        # Run evaluation
│   ├── debugger.py         # Diagnose failures
│   └── datasets/
│       └── sample_eval.json
├── scripts/
│   ├── index_documents.py
│   ├── run_eval.py
│   └── compare_configs.py
└── tests/
    └── test_rag.py
```

**Core Interface:**

```python
from production_rag import RAG, Evaluator, Debugger

# Initialize with config
rag = RAG.from_config("config/default.yaml")

# Or programmatically
rag = RAG(
    embedding_model="text-embedding-3-small",
    llm_model="gpt-4o-mini",
    retrieval_mode="hybrid",
    use_reranker=True,
    reranker_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    query_transform="hyde",
    top_k_retrieve=50,
    top_k_rerank=5
)

# Index documents
rag.index_directory("./documents/", chunk_size=512, chunk_overlap=50)

# Query
result = rag.query("What is the refund policy?")
print(result.answer)
print(result.sources)
print(result.metadata)  # Timing, tokens, config used

# Evaluate
evaluator = Evaluator(rag)
results = evaluator.evaluate("eval/datasets/sample_eval.json")
print(results.summary())
# {
#     "retrieval": {"recall@5": 0.82, "precision@5": 0.65, "mrr": 0.71},
#     "generation": {"faithfulness": 0.89, "relevance": 0.85},
#     "overall_score": 0.78
# }

# Debug failures
debugger = Debugger(rag)
diagnosis = debugger.diagnose_failure(
    question="What's error code X123?",
    expected_answer="Memory allocation failure",
    relevant_doc_ids=["errors_doc_5"]
)
print(diagnosis.failure_type)  # "retrieval"
print(diagnosis.recommendations)  # ["BM25 would help with exact code match"]

# Compare configurations
from production_rag import compare_configs

comparison = compare_configs(
    eval_set="eval/datasets/sample_eval.json",
    configs=["config/experiments/v1_baseline.yaml", "config/experiments/v2_hybrid.yaml"]
)
print(comparison.winner)  # "v2_hybrid"
print(comparison.details)  # Per-metric comparison
```

**Evaluation Dataset Format:**

```json
{
  "dataset_name": "Company Docs QA",
  "created": "2024-01-15",
  "questions": [
    {
      "id": "q1",
      "question": "What is the refund policy?",
      "ground_truth_answer": "30-day money-back guarantee for all products",
      "relevant_doc_ids": ["policy_3", "faq_12"],
      "difficulty": "easy",
      "category": "policy"
    }
  ]
}
```

### Success Criteria

**Core RAG:**

- [ ] Hybrid retrieval (BM25 + dense) working
- [ ] Reranking integrated
- [ ] Query transformation (at least HyDE) implemented
- [ ] Configurable via YAML files
- [ ] Clean separation of indexer, retriever, generator

**Evaluation Pipeline:**

- [ ] Retrieval metrics: Recall@K, Precision@K, MRR
- [ ] Generation metrics: Faithfulness (LLM-as-judge), Relevance
- [ ] Batch evaluation from JSON dataset
- [ ] Summary report generation
- [ ] Config comparison (A/B testing different RAG configs)

**Debugging:**

- [ ] Single-question diagnosis with failure type
- [ ] Batch diagnosis with pattern detection
- [ ] Actionable recommendations

**Production Readiness:**

- [ ] README with setup instructions
- [ ] Requirements.txt with pinned versions
- [ ] At least 5 unit tests
- [ ] Sample eval dataset (10+ questions)
- [ ] Example scripts that work out of the box

**Portfolio Quality:**

- [ ] Code is clean, documented, typed
- [ ] Someone could clone and run in 5 minutes
- [ ] Demonstrates understanding of RAG architecture
- [ ] Shows measurable improvement (v2 > v1 with numbers)

### Things to Ponder (Post-Build)

1. You've built evaluation. But who evaluates the evaluator? Your LLM-as-judge might have biases. Your eval dataset might have errors. How do you gain confidence in your evaluation system itself?
    
2. Your eval shows 82% recall, 89% faithfulness. Is that good? What's "good enough" for production? How do you set thresholds? How does it depend on the use case?
    
3. You want to improve from 82% to 90% recall. You could: (a) better embeddings, (b) better chunking, (c) better query transformation, (d) more data in eval set to understand failures. How do you decide where to invest?
    
4. Your RAG works great on your eval set. You deploy. Real users have questions you never anticipated. Performance drops. This is distribution shift. How do you detect it? How do you update your eval set?
    
5. Looking ahead to Week 7: Your RAG is standalone. But you'll combine it with agents. The agent decides _when_ to retrieve, _what_ to retrieve, _whether_ to trust the results. How does this change your RAG design? What interfaces does the agent need?
    

---

# AGENT TRACK

---

## Days 1-2 (Agents): Multi-Agent Patterns

### Why This Matters

Single agents hit limits:

- Context window fills up with tool results
- Too many tools = confused agent
- Complex tasks need different expertise
- No oversight of agent decisions

Multi-agent systems address this by distributing work:

- Specialized agents for specific subtasks
- Coordinator agents for orchestration
- Supervisor agents for quality control

### What to Learn

**Core Concepts:**

**Pattern 1: Orchestrator (One boss, many workers)**

```
                    ┌─────────────┐
                    │ Orchestrator│
                    │   Agent     │
                    └──────┬──────┘
                           │ delegates
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  Research   │ │   Writing   │ │   Review    │
    │   Agent     │ │    Agent    │ │    Agent    │
    └─────────────┘ └─────────────┘ └─────────────┘
```

- Orchestrator understands the task, breaks it down
- Workers are specialists with narrow tool sets
- Works well for: Complex multi-step tasks with clear subtasks

**Pattern 2: Supervisor (Monitor and correct)**

```
    ┌─────────────┐
    │  Supervisor │ ◄── Reviews all outputs
    │    Agent    │     Can reject/request redo
    └──────┬──────┘
           │ monitors
           ▼
    ┌─────────────┐
    │   Worker    │ ◄── Does the actual work
    │   Agent     │
    └─────────────┘
```

- Worker proposes, supervisor approves
- Adds quality control without human-in-loop
- Works well for: High-stakes tasks, quality assurance

**Pattern 3: Peer/Swarm (Collaborative)**

```
    ┌─────────────┐     ┌─────────────┐
    │   Agent A   │◄───►│   Agent B   │
    └──────┬──────┘     └──────┬──────┘
           │                   │
           └───────┬───────────┘
                   ▼
            ┌─────────────┐
            │   Agent C   │
            └─────────────┘
```

- Agents communicate directly
- No central coordinator
- Works well for: Brainstorming, debate, consensus

**When to Use Which:**

|Pattern|Use When|Avoid When|
|---|---|---|
|Orchestrator|Clear subtasks, diverse tools|Simple tasks, overhead not worth it|
|Supervisor|Quality critical, need oversight|Speed critical, trust is high|
|Peer/Swarm|Creative tasks, multiple perspectives|Need single authoritative answer|

**Practical Skills:**

- Implement orchestrator pattern in LangGraph
- Design agent boundaries (what tools does each agent have?)
- Handle inter-agent communication
- Manage shared state across agents

### Resources

**Primary:**

- LangGraph Multi-Agent: https://langchain-ai.github.io/langgraph/concepts/multi_agent/
- LangGraph Supervisor Pattern: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
- LangGraph Swarm: https://langchain-ai.github.io/langgraph/concepts/multi_agent/#primitives

**Secondary:**

- Search: "multi-agent LLM patterns"
- Search: "langgraph multi agent tutorial"

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph multi-agent concepts (15 min)
2. Understand the three patterns: orchestrator, supervisor, peer (10 min)
3. Think: For a "research and write report" task, which pattern fits? (5 min)

**Next 30 min — Experiment:**

1. Design a simple orchestrator system on paper:
    - Orchestrator agent: Breaks down "Write a report on X" into subtasks
    - Research agent: Has search tool, finds information
    - Writer agent: Has no tools, just writes
    - Task: Research agent gathers info, Writer agent produces report
2. Implement the skeleton in LangGraph (doesn't need to fully work yet)
3. Focus on: How do agents pass information to each other?

### Day 2 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph supervisor tutorial (15 min)
2. Understand: How does supervisor decide if work is acceptable? (10 min)
3. Read about agent handoffs and message passing (5 min)

**Next 30 min — Experiment:**

1. Extend your Day 1 orchestrator:
    - Add a simple supervisor that reviews the Writer's output
    - Supervisor can: approve, or request revision with feedback
    - Writer receives feedback, revises
2. Test: Does the supervisor catch obvious problems? Does revision improve quality?
3. Edge case: What if supervisor and writer loop forever? (Add max iterations)

### 5 Things to Ponder (Multi-Agent Patterns)

1. Your orchestrator delegates to 3 worker agents. Each worker has its own LLM calls. Total cost: 4x a single agent. When is this cost justified? When should you stick with one capable agent?
    
2. Agent A passes information to Agent B. But A's context is lost — B only sees what A explicitly sent. A knew something relevant but didn't think to pass it. How do you handle context loss at agent boundaries?
    
3. Your supervisor rejects the worker's output. Worker revises. Supervisor rejects again. After 5 iterations, output is worse than iteration 1. How do you prevent over-revision? When should supervisor accept "good enough"?
    
4. Peer agents debate a topic. Agent A says X, Agent B says not-X. They're both LLMs with similar training. They might just reflect training biases back at each other. How do you get genuine diversity of thought?
    
5. You have Research Agent, Writing Agent, Review Agent. The task is "answer this customer question." Do you really need 3 agents? What's the minimum viable multi-agent system? When does adding agents help vs. hurt?
    

---

## Days 3-4 (Agents): Agent Evaluation

### Why This Matters

Agents are harder to evaluate than RAG:

- Non-deterministic (same input, different paths)
- Multi-step (failure could be at any step)
- Tool interactions (tool errors vs. agent errors)
- Subjective success (is the output "good enough"?)

Without evaluation, you can't know if your agent works reliably.

### What to Learn

**Core Concepts:**

**What to Measure:**

```
1. TASK COMPLETION
   - Did the agent complete the task?
   - Did it complete it correctly?
   - Partial completion scoring

2. EFFICIENCY
   - How many steps/tool calls?
   - How much token usage?
   - Wall clock time?

3. TOOL USE
   - Did it use the right tools?
   - Did it use tools correctly (right arguments)?
   - Did it handle tool errors?

4. SAFETY
   - Did it attempt dangerous actions?
   - Did it respect guardrails?
   - Did it escalate appropriately?

5. TRAJECTORY QUALITY
   - Was the path reasonable?
   - Unnecessary loops or backtracking?
   - Would a human take this path?
```

**Evaluation Approaches:**

```
1. TASK-BASED EVALUATION
   - Define tasks with known correct outcomes
   - Run agent, check if outcome matches
   - Example: "Book a meeting with John" → Check if meeting exists

2. TRAJECTORY EVALUATION
   - Record the sequence of actions
   - Compare to reference trajectories
   - Or: LLM-as-judge on trajectory reasonableness

3. COMPONENT EVALUATION
   - Test tool selection in isolation
   - Test argument generation in isolation
   - Unit test components, integration test agent

4. ADVERSARIAL EVALUATION
   - Try to break the agent
   - Edge cases, malformed inputs, conflicting instructions
   - Security testing (prompt injection resistance)
```

**Practical Skills:**

- Design agent test cases
- Implement task completion scoring
- Build trajectory logging and analysis
- Use LLM-as-judge for subjective quality

### Resources

**Primary:**

- LangSmith Agent Evaluation: https://docs.smith.langchain.com/evaluation
- Inspect AI (agent eval framework): https://inspect.ai-safety-institute.org.uk/
- AgentBench Paper: https://arxiv.org/abs/2308.03688

**Secondary:**

- Search: "LLM agent evaluation"
- Search: "agent benchmark evaluation"

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Understand the dimensions of agent evaluation (task, efficiency, safety) (15 min)
2. Read about trajectory evaluation — recording and analyzing agent paths (10 min)
3. Think: How would you evaluate your Week 5 agent? What would "success" mean? (5 min)

**Next 30 min — Experiment:**

1. Create 5 test cases for your Week 5 agent:
    
    ```python
    test_cases = [    {        "task": "Find the weather in Tokyo and save a note about it",        "expected_tools": ["search", "save_note"],        "success_criteria": "Note saved with Tokyo weather info"    },    # ... more]
    ```
    
2. Run agent on each test case
3. Manually evaluate: Did it succeed? Was the trajectory reasonable?
4. Record observations — what would you automate?

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build an `AgentEvaluator` class:

```python
class AgentEvaluator:
    def __init__(self, agent, llm_judge_model: str = "gpt-4o-mini"):
        self.agent = agent
        self.judge_model = llm_judge_model
    
    def evaluate_task(
        self,
        task: str,
        expected_outcome: str,
        success_criteria: list[str],
        max_steps: int = 20
    ) -> dict:
        """
        Run agent on task and evaluate.
        
        Returns:
            {
                "completed": bool,
                "outcome_correct": bool,
                "criteria_met": {"criterion1": True, "criterion2": False},
                "steps_taken": 5,
                "tools_used": ["search", "save_note"],
                "trajectory": [...],
                "efficiency_score": 0.8,  # Fewer steps = higher
                "trajectory_quality": 0.9  # LLM judge
            }
        """
        pass
    
    def evaluate_trajectory(self, trajectory: list[dict]) -> dict:
        """
        Evaluate a recorded trajectory using LLM-as-judge.
        
        Returns:
            {
                "reasonableness": 0.85,
                "issues": ["Unnecessary retry on step 3"],
                "suggestions": ["Could have used tool X instead"]
            }
        """
        pass
    
    def batch_evaluate(self, test_cases: list[dict]) -> dict:
        """
        Run evaluation on multiple test cases.
        
        Returns:
            {
                "success_rate": 0.8,
                "avg_steps": 6.2,
                "common_failures": ["Doesn't handle ambiguous queries"],
                "tool_accuracy": {"search": 0.95, "save_note": 0.90}
            }
        """
        pass
```

**Success Criteria:**

- [ ] Single task evaluation returns completion status + metrics
- [ ] Trajectory logged with all actions and tool calls
- [ ] LLM-as-judge rates trajectory quality
- [ ] Batch evaluation aggregates across test cases
- [ ] Identifies common failure patterns
- [ ] Per-tool accuracy tracking
- [ ] Tested on at least 5 different tasks
- [ ] At least one deliberately failing test case (to verify detection)

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Agent Evaluation)

1. Your agent completes a task in 15 steps. Reference trajectory does it in 5. Agent took longer but explored alternatives and found a better solution. Is longer always worse? How do you evaluate exploration vs. exploitation?
    
2. Task: "Send email to John about the meeting." Agent sends email. But the email content is bad (rude, incorrect info). Task "completed" but outcome poor. How do you evaluate output quality, not just completion?
    
3. You test 100 tasks. Agent succeeds 80%. You want to improve. But which 20% failed? One failure is "tool down," another is "agent confused," another is "ambiguous task." How do you categorize failures for actionable insights?
    
4. Agent uses tools. Tool returns error. Agent handles gracefully and retries. Is this a failure (tool errored) or success (agent recovered)? How do you score resilience?
    
5. Your test cases are deterministic tasks with clear success criteria. But real usage is "help me write a report" — subjective, open-ended. How do you evaluate open-ended tasks? Can you?
    

---

## Days 5-7 (Agents): Final Build — Multi-Agent System with Eval

### What to Build

This is the capstone of your Agent track. A complete multi-agent system with:

- Multiple specialized agents
- Orchestration pattern
- Comprehensive evaluation
- Memory and persistence (from Week 5)

This should be portfolio-worthy and GitHub-ready.

### Specifications

**System Design: Research Assistant Team**

```
User Query
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│  - Understands user request                              │
│  - Breaks into subtasks                                  │
│  - Delegates to specialists                              │
│  - Assembles final response                              │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  RESEARCHER │   │   ANALYST   │   │   WRITER    │
│             │   │             │   │             │
│ Tools:      │   │ Tools:      │   │ Tools:      │
│ - web_search│   │ - calculate │   │ - save_doc  │
│ - fetch_url │   │ - compare   │   │ - format    │
│             │   │ - summarize │   │             │
└─────────────┘   └─────────────┘   └─────────────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  REVIEWER   │
                  │             │
                  │ Can: approve│
                  │ reject, ask │
                  │ for revision│
                  └─────────────┘
```

**Directory Structure:**

```
multi_agent_system/
├── README.md
├── requirements.txt
├── config/
│   └── agents.yaml
├── src/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── researcher.py
│   │   ├── analyst.py
│   │   ├── writer.py
│   │   └── reviewer.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── search.py
│   │   ├── calculate.py
│   │   └── document.py
│   ├── memory.py
│   ├── state.py
│   └── graph.py
├── eval/
│   ├── __init__.py
│   ├── evaluator.py
│   ├── metrics.py
│   └── test_cases/
│       └── research_tasks.json
├── scripts/
│   ├── run_agent.py
│   └── run_eval.py
└── tests/
    └── test_agents.py
```

**Core Interface:**

```python
from multi_agent_system import ResearchTeam, AgentEvaluator

# Initialize team
team = ResearchTeam(
    llm_model="gpt-4o-mini",
    persistence="sqlite",  # Checkpointing
    memory_enabled=True
)

# Simple query
result = team.run(
    "Research the top 3 electric vehicles of 2024 and compare their ranges",
    thread_id="research_001"
)

print(result.answer)
print(result.sources)
print(result.agent_trace)  # Which agent did what

# With HITL for dangerous actions (if any)
result = team.run(
    "Research and email me a summary",
    thread_id="research_002",
    require_approval=["send_email"]
)

# Resume interrupted session
result = team.resume(thread_id="research_002")

# Evaluate
evaluator = AgentEvaluator(team)

results = evaluator.evaluate("eval/test_cases/research_tasks.json")
print(results.summary())
# {
#     "success_rate": 0.85,
#     "avg_steps": 8.3,
#     "avg_time": "45s",
#     "agent_utilization": {
#         "researcher": 0.9,  # Used in 90% of tasks
#         "analyst": 0.6,
#         "writer": 0.95,
#         "reviewer": 0.8
#     },
#     "failure_analysis": {...}
# }

# Single task detailed eval
eval_result = evaluator.evaluate_task(
    task="Find the GDP of Japan in 2023",
    expected_outcome="Approximately $4.2 trillion",
    success_criteria=["Uses search tool", "Provides source", "Correct value"]
)
```

**Test Cases Format:**

```json
{
  "test_suite": "Research Tasks",
  "cases": [
    {
      "id": "simple_lookup",
      "task": "What is the capital of France?",
      "expected_outcome": "Paris",
      "expected_agents": ["researcher"],
      "max_steps": 5,
      "success_criteria": ["Correct answer", "Uses search if needed"]
    },
    {
      "id": "comparison",
      "task": "Compare the populations of Tokyo and New York",
      "expected_outcome": "Tokyo larger (~14M vs ~8M)",
      "expected_agents": ["researcher", "analyst"],
      "max_steps": 10,
      "success_criteria": ["Both populations found", "Comparison made", "Sources cited"]
    }
  ]
}
```

### Success Criteria

**Multi-Agent Architecture:**

- [ ] At least 3 specialized agents with distinct tools
- [ ] Orchestrator that delegates appropriately
- [ ] Reviewer/supervisor for quality control
- [ ] Clean agent boundaries (no tool overlap unless intentional)
- [ ] Inter-agent communication working

**Persistence & Memory (from Week 5):**

- [ ] Checkpointing works (can resume after crash)
- [ ] Memory persists across sessions
- [ ] Multiple threads isolated

**Evaluation:**

- [ ] Task completion evaluation
- [ ] Trajectory logging and analysis
- [ ] Per-agent performance metrics
- [ ] Batch evaluation with summary
- [ ] At least 10 test cases

**Production Readiness:**

- [ ] README with architecture diagram
- [ ] Requirements.txt with pinned versions
- [ ] At least 5 unit tests
- [ ] Example scripts that work out of the box
- [ ] Configurable via YAML

**Portfolio Quality:**

- [ ] Code is clean, documented, typed
- [ ] Architecture diagram in README
- [ ] Demonstrates multi-agent patterns clearly
- [ ] Shows evaluation results (metrics in README)
- [ ] Someone could understand the system in 5 minutes of reading

### Things to Ponder (Post-Build)

1. You have 4 agents. Each has its own system prompt, tools, personality. Maintaining consistency across them is hard. One change requires updating 4 places. How would you manage agent configurations at scale?
    
2. Your orchestrator decides which agent to call. Sometimes it chooses wrong (sends to Analyst when Researcher is needed). How do you improve orchestrator decisions? Training? Better prompts? Feedback loops?
    
3. The Reviewer agent approves/rejects work. But Reviewer is also an LLM — it might have the same blind spots as the Writer. Two LLMs agreeing doesn't mean they're right. How do you add genuine quality assurance?
    
4. Your multi-agent system works. But it's complex. Debugging is hard. Something goes wrong in a 6-agent, 20-step trace. How do you build observability for multi-agent systems? (Preview: Week 8)
    
5. Looking ahead to Week 7: You have production RAG (Week 6 RAG track) and production multi-agent (Week 6 Agent track). How do they combine? Which agent calls RAG? When? How does RAG output flow through agents? Sketch the architecture.
    

---

# WEEK 6 CHECKLIST

## RAG Track Completion Criteria

- [ ] **Evaluation Fundamentals:** Can compute retrieval metrics (Recall, Precision, MRR)
- [ ] **Evaluation Fundamentals:** Can evaluate generation quality (faithfulness, relevance)
- [ ] **Debugging:** Can diagnose RAG failures by type (retrieval, context, generation)
- [ ] **Debugging:** Can identify patterns in failures and prioritize fixes
- [ ] **Final Build:** Production RAG with full eval pipeline, GitHub-ready

## Agent Track Completion Criteria

- [ ] **Multi-Agent Patterns:** Can implement orchestrator pattern
- [ ] **Multi-Agent Patterns:** Can implement supervisor/reviewer pattern
- [ ] **Agent Evaluation:** Can evaluate task completion and trajectory quality
- [ ] **Agent Evaluation:** Can identify failure patterns and per-agent metrics
- [ ] **Final Build:** Multi-agent system with eval, GitHub-ready

## End of Parallel Phase

**Congratulations!** You've completed the parallel RAG and Agent tracks.

You now have:

- Production RAG system with hybrid search, reranking, query transformation, and evaluation
- Multi-agent system with orchestration, memory, HITL, and evaluation
- Two portfolio-ready projects on GitHub

## What's Next

**Week 7: Combined Phase Begins**

The tracks merge. You'll build systems that combine RAG + Agents:

- Agentic RAG (agent decides when/how to retrieve)
- Research Assistant that uses your RAG as a tool
- Observability and tracing across the full stack

---

# NOTES SECTION

## RAG Track Notes

### Days 1-2 Notes (RAG Evaluation Fundamentals)

### Days 3-4 Notes (Debugging Bad Retrieval)

### Days 5-7 Notes (Production RAG Final Build)

---

## Agent Track Notes

### Days 1-2 Notes (Multi-Agent Patterns)

### Days 3-4 Notes (Agent Evaluation)

### Days 5-7 Notes (Multi-Agent Final Build)