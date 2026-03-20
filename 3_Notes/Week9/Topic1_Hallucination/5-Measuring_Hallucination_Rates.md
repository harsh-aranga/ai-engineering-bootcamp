# Note 5: Measuring and Monitoring Hallucination Rates

## Why Monitoring Matters

Building a hallucination detection pipeline (Note 4) is necessary but not sufficient. Without ongoing measurement, you can't answer critical questions:

- Is our system getting better or worse over time?
- Did that prompt change actually reduce hallucinations?
- Which query types have the highest hallucination rates?
- Are we abstaining too much (hurting helpfulness) or too little (letting hallucinations through)?

Monitoring closes the feedback loop between deployment and improvement.

---

## Hallucination Metrics

Four core metrics capture the hallucination landscape:

```
                                    ACTUAL STATE
                          ┌─────────────────┬─────────────────┐
                          │  Answerable     │  Unanswerable   │
          ┌───────────────┼─────────────────┼─────────────────┤
          │   Answered    │  ✓ True Positive│  ✗ Hallucination│
 SYSTEM   │   (faithful)  │    (correct)    │   (should have  │
 ACTION   │               │                 │    abstained)   │
          ├───────────────┼─────────────────┼─────────────────┤
          │   Abstained   │  ✗ False        │  ✓ True Negative│
          │               │    Abstention   │    (correct     │
          │               │   (should have  │     abstention) │
          │               │    answered)    │                 │
          └───────────────┴─────────────────┴─────────────────┘
```

### Metric 1: Faithfulness Rate

**Definition**: Percentage of generated answers that pass the faithfulness check.

```python
faithfulness_rate = (
    answers_passing_faithfulness_check / 
    total_answers_generated
) * 100
```

**What it tells you**: How often does your generation pipeline produce grounded answers (when it does generate)?

**Target**: 90%+ for production systems, higher for high-stakes domains.

### Metric 2: Abstention Rate

**Definition**: Percentage of queries where the system abstains instead of answering.

```python
abstention_rate = (
    queries_abstained / 
    total_queries
) * 100
```

**What it tells you**: How often does your system refuse to answer?

**Interpretation**:

- Too low (< 5%): Probably letting hallucinations through
- Too high (> 30%): Probably being overly cautious, hurting helpfulness
- Sweet spot: Depends on your domain and query distribution

### Metric 3: False Abstention Rate

**Definition**: Percentage of abstentions that were incorrect — the system could have answered.

```python
false_abstention_rate = (
    abstentions_where_answer_was_possible / 
    total_abstentions
) * 100
```

**What it tells you**: How much helpfulness are you sacrificing?

**How to measure**: Requires human review or gold-standard labels.

### Metric 4: Missed Hallucination Rate (Escape Rate)

**Definition**: Percentage of returned answers that are actually hallucinated.

```python
missed_hallucination_rate = (
    hallucinated_answers_returned_to_user / 
    total_answers_returned
) * 100
```

**What it tells you**: How often does a hallucination slip through all your defenses?

**This is the critical metric** — it measures actual harm reaching users.

**How to measure**: Requires human review sampling.

### Composite Metrics

```python
from dataclasses import dataclass

@dataclass
class HallucinationMetrics:
    """Complete hallucination metrics for a time period."""
    
    # Core counts
    total_queries: int
    total_answered: int
    total_abstained: int
    
    # Faithfulness
    answers_faithful: int
    answers_unfaithful: int
    
    # Human-validated (from sampling)
    false_abstentions: int  # Abstained when could answer
    missed_hallucinations: int  # Hallucinations that got through
    samples_reviewed: int
    
    @property
    def faithfulness_rate(self) -> float:
        if self.total_answered == 0:
            return 0.0
        return (self.answers_faithful / self.total_answered) * 100
    
    @property
    def abstention_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return (self.total_abstained / self.total_queries) * 100
    
    @property
    def false_abstention_rate(self) -> float:
        if self.total_abstained == 0:
            return 0.0
        return (self.false_abstentions / self.total_abstained) * 100
    
    @property
    def escape_rate(self) -> float:
        """Missed hallucination rate — the critical metric."""
        if self.total_answered == 0:
            return 0.0
        return (self.missed_hallucinations / self.total_answered) * 100
    
    @property
    def overall_accuracy(self) -> float:
        """Correct answers + correct abstentions."""
        correct_answers = self.answers_faithful - self.missed_hallucinations
        correct_abstentions = self.total_abstained - self.false_abstentions
        return ((correct_answers + correct_abstentions) / self.total_queries) * 100
```

---

## Building Evaluation Datasets

Offline evaluation requires curated datasets with known ground truth.

### Dataset Structure

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class QueryType(Enum):
    ANSWERABLE = "answerable"           # Context contains answer
    UNANSWERABLE = "unanswerable"       # Context doesn't contain answer
    PARTIAL = "partial"                 # Context contains partial answer
    TRAP = "trap"                       # Context contradicts common knowledge

@dataclass
class EvalExample:
    """A single evaluation example."""
    
    # Input
    query: str
    context: str
    
    # Ground truth
    query_type: QueryType
    expected_answer: Optional[str]      # None for unanswerable
    expected_abstain: bool
    
    # Trap details (if applicable)
    common_misconception: Optional[str] = None  # What the model might hallucinate
    
    # Metadata
    category: str = "general"           # For slicing analysis
    difficulty: str = "medium"
    
    # Notes
    notes: str = ""
```

### Example Dataset Entries

```python
EVAL_DATASET = [
    # ═══════════════════════════════════════════════════════════
    # ANSWERABLE: Context clearly contains the answer
    # ═══════════════════════════════════════════════════════════
    EvalExample(
        query="What is the refund period?",
        context="Our refund policy allows returns within 30 days of purchase.",
        query_type=QueryType.ANSWERABLE,
        expected_answer="30 days",
        expected_abstain=False,
        category="policy"
    ),
    
    EvalExample(
        query="What programming languages does the API support?",
        context="The API provides official SDKs for Python, JavaScript, and Go.",
        query_type=QueryType.ANSWERABLE,
        expected_answer="Python, JavaScript, and Go",
        expected_abstain=False,
        category="technical"
    ),
    
    # ═══════════════════════════════════════════════════════════
    # UNANSWERABLE: Context doesn't contain the answer
    # ═══════════════════════════════════════════════════════════
    EvalExample(
        query="What is the shipping policy?",
        context="Our refund policy allows returns within 30 days of purchase.",
        query_type=QueryType.UNANSWERABLE,
        expected_answer=None,
        expected_abstain=True,
        category="policy"
    ),
    
    EvalExample(
        query="How much does the enterprise plan cost?",
        context="We offer three plans: Basic, Pro, and Enterprise. Contact sales for details.",
        query_type=QueryType.UNANSWERABLE,
        expected_answer=None,
        expected_abstain=True,
        notes="Price not specified — should abstain, not invent a number"
    ),
    
    # ═══════════════════════════════════════════════════════════
    # PARTIAL: Context contains some but not all information
    # ═══════════════════════════════════════════════════════════
    EvalExample(
        query="What is the refund period and processing time?",
        context="Our refund policy allows returns within 30 days of purchase.",
        query_type=QueryType.PARTIAL,
        expected_answer="Refund period is 30 days. Processing time not specified.",
        expected_abstain=False,
        notes="Should answer refund period, acknowledge missing processing time"
    ),
    
    # ═══════════════════════════════════════════════════════════
    # TRAP: Context contradicts common knowledge
    # ═══════════════════════════════════════════════════════════
    EvalExample(
        query="What is the capital of Australia?",
        context="Australia's capital is Canberra, not Sydney as commonly believed.",
        query_type=QueryType.TRAP,
        expected_answer="Canberra",
        expected_abstain=False,
        common_misconception="Sydney",
        notes="Model might ignore context and say Sydney"
    ),
    
    EvalExample(
        query="How many planets are in our solar system?",
        context="As of the 2006 IAU decision, our solar system has 8 planets. Pluto is classified as a dwarf planet.",
        query_type=QueryType.TRAP,
        expected_answer="8 planets",
        expected_abstain=False,
        common_misconception="9 planets",
        notes="Tests if model follows context vs. potentially outdated training"
    ),
    
    EvalExample(
        query="What is the company's revenue?",
        context="The company reported revenue of $50 million in 2023.",
        query_type=QueryType.TRAP,
        expected_answer="$50 million (2023)",
        expected_abstain=False,
        common_misconception="Model might add growth projections or comparisons",
        notes="Model should only state what's in context, not extrapolate"
    ),
]
```

### Dataset Design Principles

1. **Balance query types**: Include answerable, unanswerable, partial, and trap queries in realistic proportions.
    
2. **Cover your categories**: Include examples from all query categories your system handles (policy, technical, product, etc.).
    
3. **Include edge cases**: Ambiguous queries, multi-part questions, queries with subtle context requirements.
    
4. **Update regularly**: As your system evolves and you discover new failure modes, add them to the eval set.
    

```python
def create_eval_dataset(
    answerable_count: int = 50,
    unanswerable_count: int = 20,
    partial_count: int = 15,
    trap_count: int = 15
) -> list[EvalExample]:
    """
    Create a balanced evaluation dataset.
    
    Recommended distribution:
    - 50% answerable (baseline capability)
    - 20% unanswerable (abstention capability)
    - 15% partial (nuanced handling)
    - 15% trap (grounding vs. parametric knowledge)
    """
    dataset = []
    
    # Would typically load from curated sources
    # For illustration, showing structure
    
    return dataset
```

---

## Offline Evaluation

Run your pipeline on the evaluation dataset and calculate metrics.

```python
from dataclasses import dataclass, field
from typing import Optional
import json

@dataclass
class EvalResult:
    """Result of evaluating one example."""
    example: EvalExample
    
    # Pipeline output
    answer: str
    status: str  # "success" or "abstained"
    faithfulness_score: float
    
    # Evaluation
    is_correct: bool
    error_type: Optional[str] = None  # "false_abstention", "missed_hallucination", "wrong_answer"
    
    # Details
    notes: str = ""

@dataclass
class EvalReport:
    """Complete evaluation report."""
    results: list[EvalResult]
    
    # Aggregate metrics
    total: int = 0
    correct: int = 0
    false_abstentions: int = 0
    missed_hallucinations: int = 0
    wrong_answers: int = 0
    
    # By query type
    by_type: dict = field(default_factory=dict)
    
    # By category
    by_category: dict = field(default_factory=dict)

class OfflineEvaluator:
    """
    Run offline evaluation on a test dataset.
    """
    
    def __init__(self, guard):
        self.guard = guard
    
    def evaluate(
        self,
        dataset: list[EvalExample]
    ) -> EvalReport:
        """
        Evaluate the pipeline on a dataset.
        """
        results = []
        
        for example in dataset:
            result = self._evaluate_example(example)
            results.append(result)
        
        return self._aggregate_results(results)
    
    def _evaluate_example(self, example: EvalExample) -> EvalResult:
        """Evaluate a single example."""
        
        # Simulate retrieval (in real system, would use actual retriever)
        chunks = [{"text": example.context, "score": 0.9, "metadata": {}}]
        
        # Run pipeline
        guard_result = self.guard.process(example.query, chunks)
        
        # Evaluate correctness
        is_correct, error_type = self._check_correctness(
            example=example,
            answer=guard_result.answer,
            status=guard_result.status
        )
        
        return EvalResult(
            example=example,
            answer=guard_result.answer,
            status=guard_result.status,
            faithfulness_score=guard_result.faithfulness_score,
            is_correct=is_correct,
            error_type=error_type
        )
    
    def _check_correctness(
        self,
        example: EvalExample,
        answer: str,
        status: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if the system's response is correct.
        
        Returns (is_correct, error_type)
        """
        abstained = status == "abstained"
        
        # Case 1: Should abstain, did abstain → Correct
        if example.expected_abstain and abstained:
            return True, None
        
        # Case 2: Should abstain, didn't abstain → Missed hallucination
        if example.expected_abstain and not abstained:
            return False, "missed_hallucination"
        
        # Case 3: Shouldn't abstain, did abstain → False abstention
        if not example.expected_abstain and abstained:
            return False, "false_abstention"
        
        # Case 4: Shouldn't abstain, didn't abstain → Check answer quality
        if example.expected_answer:
            # Simple containment check (production would use semantic similarity)
            key_terms = example.expected_answer.lower().split()
            answer_lower = answer.lower()
            
            # Check if key information is present
            matches = sum(1 for term in key_terms if term in answer_lower)
            if matches / len(key_terms) >= 0.5:
                return True, None
            else:
                return False, "wrong_answer"
        
        return True, None
    
    def _aggregate_results(self, results: list[EvalResult]) -> EvalReport:
        """Aggregate individual results into a report."""
        report = EvalReport(results=results)
        report.total = len(results)
        
        # Count outcomes
        for r in results:
            if r.is_correct:
                report.correct += 1
            elif r.error_type == "false_abstention":
                report.false_abstentions += 1
            elif r.error_type == "missed_hallucination":
                report.missed_hallucinations += 1
            elif r.error_type == "wrong_answer":
                report.wrong_answers += 1
        
        # Group by query type
        for qtype in QueryType:
            type_results = [r for r in results if r.example.query_type == qtype]
            if type_results:
                correct = sum(1 for r in type_results if r.is_correct)
                report.by_type[qtype.value] = {
                    "total": len(type_results),
                    "correct": correct,
                    "accuracy": correct / len(type_results) * 100
                }
        
        # Group by category
        categories = set(r.example.category for r in results)
        for category in categories:
            cat_results = [r for r in results if r.example.category == category]
            correct = sum(1 for r in cat_results if r.is_correct)
            report.by_category[category] = {
                "total": len(cat_results),
                "correct": correct,
                "accuracy": correct / len(cat_results) * 100
            }
        
        return report
    
    def print_report(self, report: EvalReport):
        """Print a formatted evaluation report."""
        print("=" * 60)
        print("HALLUCINATION GUARD EVALUATION REPORT")
        print("=" * 60)
        
        # Overall metrics
        print(f"\nOVERALL METRICS:")
        print(f"  Total examples: {report.total}")
        print(f"  Correct: {report.correct} ({report.correct/report.total*100:.1f}%)")
        print(f"  False abstentions: {report.false_abstentions}")
        print(f"  Missed hallucinations: {report.missed_hallucinations}")
        print(f"  Wrong answers: {report.wrong_answers}")
        
        # By query type
        print(f"\nBY QUERY TYPE:")
        for qtype, stats in report.by_type.items():
            print(f"  {qtype}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.1f}%)")
        
        # By category
        print(f"\nBY CATEGORY:")
        for category, stats in report.by_category.items():
            print(f"  {category}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.1f}%)")
        
        # Failures
        failures = [r for r in report.results if not r.is_correct]
        if failures:
            print(f"\nFAILURES ({len(failures)}):")
            for f in failures[:5]:  # Show first 5
                print(f"  [{f.error_type}] Q: {f.example.query[:50]}...")
                print(f"    Expected: {f.example.expected_answer or 'abstain'}")
                print(f"    Got: {f.answer[:100]}...")
        
        print("=" * 60)


# Usage
evaluator = OfflineEvaluator(guard)
report = evaluator.evaluate(EVAL_DATASET)
evaluator.print_report(report)
```

### Comparing Configurations

```python
def compare_configurations(
    configs: list[tuple[str, GuardConfig]],
    dataset: list[EvalExample]
) -> dict:
    """
    Compare multiple configurations on the same dataset.
    
    Args:
        configs: List of (name, config) tuples
        dataset: Evaluation dataset
    
    Returns:
        Comparison results
    """
    results = {}
    
    for name, config in configs:
        guard = HallucinationGuard(config)
        evaluator = OfflineEvaluator(guard)
        report = evaluator.evaluate(dataset)
        
        results[name] = {
            "accuracy": report.correct / report.total * 100,
            "false_abstention_rate": report.false_abstentions / report.total * 100,
            "escape_rate": report.missed_hallucinations / report.total * 100,
            "config": config
        }
    
    # Print comparison
    print("\nCONFIGURATION COMPARISON:")
    print("-" * 70)
    print(f"{'Config':<20} {'Accuracy':<12} {'False Abstain':<15} {'Escape Rate':<12}")
    print("-" * 70)
    
    for name, r in results.items():
        print(f"{name:<20} {r['accuracy']:.1f}%{'':<6} {r['false_abstention_rate']:.1f}%{'':<10} {r['escape_rate']:.1f}%")
    
    return results


# Example: Compare threshold settings
configs = [
    ("strict", GuardConfig(faithfulness_threshold=0.9, relevance_threshold=0.8)),
    ("balanced", GuardConfig(faithfulness_threshold=0.75, relevance_threshold=0.6)),
    ("lenient", GuardConfig(faithfulness_threshold=0.6, relevance_threshold=0.5)),
]

comparison = compare_configurations(configs, EVAL_DATASET)
```

---

## Online Monitoring

Production monitoring requires logging, aggregation, and alerting.

### Logging Infrastructure

```python
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
import json
import logging

@dataclass
class QueryLog:
    """Log entry for a single query."""
    
    # Identifiers
    query_id: str
    timestamp: datetime
    
    # Input
    query: str
    chunk_count: int
    
    # Pipeline results
    status: str
    relevance_score: float
    faithfulness_score: float
    attempts: int
    
    # Timing
    latency_ms: float
    
    # Flags
    abstained: bool
    abstention_reason: Optional[str]
    
    # For debugging (optional, can be large)
    answer_preview: Optional[str] = None
    issues: Optional[list[str]] = None
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

class HallucinationLogger:
    """
    Log hallucination guard results for monitoring.
    """
    
    def __init__(
        self,
        log_file: str = "hallucination_guard.jsonl",
        also_log_to_stdout: bool = False
    ):
        self.log_file = log_file
        self.also_log_to_stdout = also_log_to_stdout
        self.logger = logging.getLogger("HallucinationMonitor")
    
    def log(self, query_log: QueryLog):
        """Log a query result."""
        log_dict = query_log.to_dict()
        
        # Write to JSONL file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_dict) + "\n")
        
        if self.also_log_to_stdout:
            self.logger.info(json.dumps(log_dict))
    
    def from_guard_result(
        self,
        query_id: str,
        query: str,
        chunk_count: int,
        result  # GuardResult
    ) -> QueryLog:
        """Create log entry from GuardResult."""
        return QueryLog(
            query_id=query_id,
            timestamp=datetime.now(),
            query=query,
            chunk_count=chunk_count,
            status=result.status,
            relevance_score=result.relevance_score,
            faithfulness_score=result.faithfulness_score,
            attempts=result.attempts,
            latency_ms=result.total_time_ms,
            abstained=result.status == "abstained",
            abstention_reason=result.abstention_reason,
            answer_preview=result.answer[:200] if result.answer else None,
            issues=result.issues_found if result.issues_found else None
        )
```

### Metrics Aggregation

```python
from collections import defaultdict
from datetime import datetime, timedelta
import statistics

@dataclass
class TimeWindowMetrics:
    """Metrics for a time window."""
    
    window_start: datetime
    window_end: datetime
    
    # Counts
    total_queries: int
    total_answered: int
    total_abstained: int
    
    # Score distributions
    avg_faithfulness: float
    p50_faithfulness: float
    p90_faithfulness: float
    min_faithfulness: float
    
    avg_relevance: float
    
    # Rates
    abstention_rate: float
    low_faithfulness_rate: float  # Below threshold but still answered
    
    # Latency
    avg_latency_ms: float
    p99_latency_ms: float

class MetricsAggregator:
    """
    Aggregate query logs into time-windowed metrics.
    """
    
    def __init__(self, faithfulness_threshold: float = 0.75):
        self.threshold = faithfulness_threshold
    
    def aggregate_window(
        self,
        logs: list[QueryLog],
        window_start: datetime,
        window_end: datetime
    ) -> TimeWindowMetrics:
        """Aggregate logs for a time window."""
        
        if not logs:
            return self._empty_metrics(window_start, window_end)
        
        # Filter to window
        window_logs = [
            log for log in logs
            if window_start <= log.timestamp < window_end
        ]
        
        if not window_logs:
            return self._empty_metrics(window_start, window_end)
        
        # Calculate metrics
        faithfulness_scores = [log.faithfulness_score for log in window_logs]
        relevance_scores = [log.relevance_score for log in window_logs]
        latencies = [log.latency_ms for log in window_logs]
        
        answered = [log for log in window_logs if not log.abstained]
        abstained = [log for log in window_logs if log.abstained]
        
        low_faithfulness = [
            log for log in answered
            if log.faithfulness_score < self.threshold
        ]
        
        return TimeWindowMetrics(
            window_start=window_start,
            window_end=window_end,
            total_queries=len(window_logs),
            total_answered=len(answered),
            total_abstained=len(abstained),
            avg_faithfulness=statistics.mean(faithfulness_scores),
            p50_faithfulness=statistics.median(faithfulness_scores),
            p90_faithfulness=self._percentile(faithfulness_scores, 90),
            min_faithfulness=min(faithfulness_scores),
            avg_relevance=statistics.mean(relevance_scores),
            abstention_rate=len(abstained) / len(window_logs) * 100,
            low_faithfulness_rate=len(low_faithfulness) / len(window_logs) * 100 if answered else 0,
            avg_latency_ms=statistics.mean(latencies),
            p99_latency_ms=self._percentile(latencies, 99)
        )
    
    def _percentile(self, data: list[float], p: int) -> float:
        """Calculate percentile."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * p / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _empty_metrics(
        self,
        start: datetime,
        end: datetime
    ) -> TimeWindowMetrics:
        """Return empty metrics for a window with no data."""
        return TimeWindowMetrics(
            window_start=start,
            window_end=end,
            total_queries=0,
            total_answered=0,
            total_abstained=0,
            avg_faithfulness=0.0,
            p50_faithfulness=0.0,
            p90_faithfulness=0.0,
            min_faithfulness=0.0,
            avg_relevance=0.0,
            abstention_rate=0.0,
            low_faithfulness_rate=0.0,
            avg_latency_ms=0.0,
            p99_latency_ms=0.0
        )
```

### Alerting

```python
from dataclasses import dataclass
from enum import Enum
from typing import Callable

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Alert:
    """An alert for quality degradation."""
    severity: AlertSeverity
    metric: str
    message: str
    current_value: float
    threshold: float
    timestamp: datetime

class AlertManager:
    """
    Monitor metrics and trigger alerts on degradation.
    """
    
    def __init__(
        self,
        # Thresholds
        min_avg_faithfulness: float = 0.7,
        max_abstention_rate: float = 30.0,
        max_escape_rate: float = 5.0,
        max_p99_latency_ms: float = 10000,
        
        # Alert handler
        alert_handler: Callable[[Alert], None] = None
    ):
        self.thresholds = {
            "avg_faithfulness": ("min", min_avg_faithfulness),
            "abstention_rate": ("max", max_abstention_rate),
            "low_faithfulness_rate": ("max", max_escape_rate),
            "p99_latency_ms": ("max", max_p99_latency_ms)
        }
        
        self.alert_handler = alert_handler or self._default_handler
        self.alert_history: list[Alert] = []
    
    def check_metrics(self, metrics: TimeWindowMetrics) -> list[Alert]:
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        
        for metric_name, (direction, threshold) in self.thresholds.items():
            value = getattr(metrics, metric_name, None)
            
            if value is None:
                continue
            
            triggered = False
            if direction == "min" and value < threshold:
                triggered = True
                severity = AlertSeverity.CRITICAL if value < threshold * 0.8 else AlertSeverity.WARNING
            elif direction == "max" and value > threshold:
                triggered = True
                severity = AlertSeverity.CRITICAL if value > threshold * 1.2 else AlertSeverity.WARNING
            
            if triggered:
                alert = Alert(
                    severity=severity,
                    metric=metric_name,
                    message=f"{metric_name} is {'below' if direction == 'min' else 'above'} threshold",
                    current_value=value,
                    threshold=threshold,
                    timestamp=datetime.now()
                )
                alerts.append(alert)
                self.alert_handler(alert)
        
        self.alert_history.extend(alerts)
        return alerts
    
    def _default_handler(self, alert: Alert):
        """Default alert handler — log to console."""
        severity_emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨"
        }
        
        print(
            f"{severity_emoji[alert.severity]} [{alert.severity.value.upper()}] "
            f"{alert.message}: {alert.current_value:.2f} "
            f"(threshold: {alert.threshold:.2f})"
        )


# Usage
alert_manager = AlertManager(
    min_avg_faithfulness=0.7,
    max_abstention_rate=25.0,
    alert_handler=lambda a: send_to_slack(a)  # Custom handler
)

# Check hourly metrics
alerts = alert_manager.check_metrics(hourly_metrics)
```

---

## Sampling Strategies

Full verification is expensive. Use sampling strategically.

```python
import random
from enum import Enum

class SamplingStrategy(Enum):
    ALL = "all"                    # Check everything
    RANDOM = "random"              # Random sample
    RISK_BASED = "risk_based"      # More checks for risky queries
    ADAPTIVE = "adaptive"          # Adjust based on recent quality

class SamplingController:
    """
    Control which queries get full verification.
    """
    
    def __init__(
        self,
        strategy: SamplingStrategy = SamplingStrategy.RISK_BASED,
        base_sample_rate: float = 0.1,  # 10% default
        high_risk_categories: list[str] = None
    ):
        self.strategy = strategy
        self.base_rate = base_sample_rate
        self.high_risk_categories = high_risk_categories or ["medical", "legal", "financial"]
        
        # For adaptive strategy
        self.recent_scores: list[float] = []
        self.window_size = 100
    
    def should_verify(
        self,
        query: str,
        category: str = "general",
        initial_score: float = None
    ) -> bool:
        """
        Decide whether to run full verification on this query.
        """
        if self.strategy == SamplingStrategy.ALL:
            return True
        
        if self.strategy == SamplingStrategy.RANDOM:
            return random.random() < self.base_rate
        
        if self.strategy == SamplingStrategy.RISK_BASED:
            # Always verify high-risk categories
            if category in self.high_risk_categories:
                return True
            
            # Verify if initial score is borderline
            if initial_score and 0.5 < initial_score < 0.85:
                return True
            
            # Sample the rest
            return random.random() < self.base_rate
        
        if self.strategy == SamplingStrategy.ADAPTIVE:
            # Increase sampling if recent quality is dropping
            sample_rate = self._adaptive_rate()
            return random.random() < sample_rate
        
        return random.random() < self.base_rate
    
    def _adaptive_rate(self) -> float:
        """Adjust sample rate based on recent quality."""
        if len(self.recent_scores) < 10:
            return self.base_rate
        
        avg_score = sum(self.recent_scores[-50:]) / min(50, len(self.recent_scores))
        
        # Increase sampling if quality is dropping
        if avg_score < 0.7:
            return min(1.0, self.base_rate * 3)  # 3x sampling
        elif avg_score < 0.8:
            return min(1.0, self.base_rate * 2)  # 2x sampling
        else:
            return self.base_rate
    
    def record_score(self, score: float):
        """Record a faithfulness score for adaptive strategy."""
        self.recent_scores.append(score)
        if len(self.recent_scores) > self.window_size:
            self.recent_scores = self.recent_scores[-self.window_size:]


# Usage in pipeline
sampler = SamplingController(
    strategy=SamplingStrategy.RISK_BASED,
    base_sample_rate=0.1,
    high_risk_categories=["medical", "compliance"]
)

# In the pipeline
if sampler.should_verify(query, category="medical"):
    # Run full faithfulness check
    faith_result = faithfulness_checker.check(query, context, answer)
else:
    # Skip verification, log for later batch analysis
    faith_result = None
```

---

## Human-in-the-Loop Validation

Automated checks have blind spots. Human review calibrates and improves the system.

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class HumanVerdict(Enum):
    CORRECT = "correct"           # Answer is accurate and well-grounded
    HALLUCINATION = "hallucination"  # Answer contains fabricated information
    PARTIAL = "partial"           # Partially correct
    WRONG_ABSTENTION = "wrong_abstention"  # Should have answered
    CORRECT_ABSTENTION = "correct_abstention"  # Right to abstain

@dataclass
class HumanReview:
    """Human review of a query result."""
    
    query_id: str
    reviewer: str
    verdict: HumanVerdict
    
    # Automated assessment
    automated_faithfulness: float
    automated_abstained: bool
    
    # Human notes
    issues_found: list[str]
    notes: str
    
    # Calibration
    agrees_with_automated: bool

class HumanReviewQueue:
    """
    Manage human review workflow.
    """
    
    def __init__(
        self,
        sample_rate: float = 0.05,  # 5% for human review
        prioritize_borderline: bool = True
    ):
        self.sample_rate = sample_rate
        self.prioritize_borderline = prioritize_borderline
        self.queue: list[QueryLog] = []
        self.reviews: list[HumanReview] = []
    
    def maybe_queue(self, log: QueryLog) -> bool:
        """Decide whether to queue for human review."""
        # Always queue borderline cases
        if self.prioritize_borderline:
            if 0.6 < log.faithfulness_score < 0.85:
                self.queue.append(log)
                return True
        
        # Random sample
        if random.random() < self.sample_rate:
            self.queue.append(log)
            return True
        
        return False
    
    def submit_review(self, review: HumanReview):
        """Submit a completed human review."""
        self.reviews.append(review)
    
    def calibration_report(self) -> dict:
        """
        Compare human reviews against automated checks.
        
        Identifies where automated checks are wrong.
        """
        if not self.reviews:
            return {"error": "No reviews yet"}
        
        # Agreement rate
        agreements = sum(1 for r in self.reviews if r.agrees_with_automated)
        agreement_rate = agreements / len(self.reviews)
        
        # False positive rate (automated said bad, human said good)
        auto_flagged = [r for r in self.reviews if r.automated_faithfulness < 0.75]
        false_positives = [r for r in auto_flagged if r.verdict == HumanVerdict.CORRECT]
        fp_rate = len(false_positives) / len(auto_flagged) if auto_flagged else 0
        
        # False negative rate (automated said good, human said bad)
        auto_passed = [r for r in self.reviews if r.automated_faithfulness >= 0.75]
        false_negatives = [r for r in auto_passed if r.verdict == HumanVerdict.HALLUCINATION]
        fn_rate = len(false_negatives) / len(auto_passed) if auto_passed else 0
        
        return {
            "total_reviews": len(self.reviews),
            "agreement_rate": agreement_rate,
            "false_positive_rate": fp_rate,
            "false_negative_rate": fn_rate,
            "recommendations": self._generate_recommendations(fp_rate, fn_rate)
        }
    
    def _generate_recommendations(
        self,
        fp_rate: float,
        fn_rate: float
    ) -> list[str]:
        """Generate tuning recommendations based on calibration."""
        recommendations = []
        
        if fp_rate > 0.2:
            recommendations.append(
                f"High false positive rate ({fp_rate:.1%}): Consider lowering "
                "faithfulness threshold to reduce unnecessary abstentions"
            )
        
        if fn_rate > 0.1:
            recommendations.append(
                f"High false negative rate ({fn_rate:.1%}): Consider raising "
                "faithfulness threshold or improving detection prompts"
            )
        
        if fp_rate < 0.05 and fn_rate < 0.05:
            recommendations.append(
                "Calibration looks good! Continue monitoring."
            )
        
        return recommendations
```

---

## Dashboard Metrics

Key visualizations for monitoring hallucination rates.

### Dashboard Components

```python
from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta

@dataclass
class DashboardData:
    """Data for hallucination monitoring dashboard."""
    
    # Time range
    start_time: datetime
    end_time: datetime
    
    # Overall metrics (current period)
    current_metrics: TimeWindowMetrics
    
    # Trend data (historical)
    faithfulness_trend: list[tuple[datetime, float]]  # (timestamp, avg_score)
    abstention_trend: list[tuple[datetime, float]]
    escape_rate_trend: list[tuple[datetime, float]]
    
    # Distribution data
    faithfulness_histogram: dict[str, int]  # {"0.0-0.1": 5, "0.1-0.2": 10, ...}
    
    # Top issues
    top_hallucination_patterns: list[tuple[str, int]]  # (pattern, count)
    high_hallucination_categories: list[tuple[str, float]]  # (category, rate)
    
    # Alerts
    active_alerts: list[Alert]

class DashboardGenerator:
    """
    Generate dashboard data from logs.
    """
    
    def __init__(self, logs: list[QueryLog]):
        self.logs = logs
        self.aggregator = MetricsAggregator()
    
    def generate(
        self,
        period_hours: int = 24,
        trend_windows: int = 7  # 7 data points
    ) -> DashboardData:
        """Generate dashboard data."""
        
        now = datetime.now()
        start = now - timedelta(hours=period_hours)
        
        # Current metrics
        current = self.aggregator.aggregate_window(self.logs, start, now)
        
        # Trend data
        window_size = timedelta(hours=period_hours / trend_windows)
        faith_trend = []
        abstain_trend = []
        
        for i in range(trend_windows):
            w_start = start + (window_size * i)
            w_end = w_start + window_size
            w_metrics = self.aggregator.aggregate_window(self.logs, w_start, w_end)
            
            faith_trend.append((w_start, w_metrics.avg_faithfulness))
            abstain_trend.append((w_start, w_metrics.abstention_rate))
        
        # Histogram
        histogram = self._build_histogram([log.faithfulness_score for log in self.logs])
        
        # Top patterns
        patterns = self._extract_patterns()
        categories = self._category_analysis()
        
        return DashboardData(
            start_time=start,
            end_time=now,
            current_metrics=current,
            faithfulness_trend=faith_trend,
            abstention_trend=abstain_trend,
            escape_rate_trend=[],  # Would need human review data
            faithfulness_histogram=histogram,
            top_hallucination_patterns=patterns,
            high_hallucination_categories=categories,
            active_alerts=[]
        )
    
    def _build_histogram(self, scores: list[float]) -> dict[str, int]:
        """Build histogram of faithfulness scores."""
        buckets = {f"{i/10:.1f}-{(i+1)/10:.1f}": 0 for i in range(10)}
        
        for score in scores:
            bucket_idx = min(int(score * 10), 9)
            bucket_key = f"{bucket_idx/10:.1f}-{(bucket_idx+1)/10:.1f}"
            buckets[bucket_key] += 1
        
        return buckets
    
    def _extract_patterns(self) -> list[tuple[str, int]]:
        """Extract common hallucination patterns from issues."""
        pattern_counts = {}
        
        for log in self.logs:
            if log.issues:
                for issue in log.issues:
                    # Normalize issue to pattern
                    pattern = issue.lower()[:50]  # Truncate for grouping
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        return sorted(pattern_counts.items(), key=lambda x: -x[1])[:10]
    
    def _category_analysis(self) -> list[tuple[str, float]]:
        """Analyze hallucination rates by category."""
        # Would need category metadata in logs
        return []
    
    def print_dashboard(self, data: DashboardData):
        """Print a text-based dashboard."""
        print("\n" + "=" * 70)
        print("HALLUCINATION MONITORING DASHBOARD")
        print(f"Period: {data.start_time.strftime('%Y-%m-%d %H:%M')} to {data.end_time.strftime('%Y-%m-%d %H:%M')}")
        print("=" * 70)
        
        m = data.current_metrics
        print(f"\n📊 CURRENT METRICS")
        print(f"   Total Queries: {m.total_queries}")
        print(f"   Faithfulness:  {m.avg_faithfulness:.1%} avg | {m.p50_faithfulness:.1%} p50 | {m.p90_faithfulness:.1%} p90")
        print(f"   Abstention:    {m.abstention_rate:.1f}%")
        print(f"   Latency:       {m.avg_latency_ms:.0f}ms avg | {m.p99_latency_ms:.0f}ms p99")
        
        print(f"\n📈 FAITHFULNESS TREND")
        for ts, score in data.faithfulness_trend:
            bar = "█" * int(score * 20)
            print(f"   {ts.strftime('%H:%M')}: {bar} {score:.1%}")
        
        print(f"\n📉 ABSTENTION TREND")
        for ts, rate in data.abstention_trend:
            bar = "█" * int(rate / 5)  # Scale for readability
            print(f"   {ts.strftime('%H:%M')}: {bar} {rate:.1f}%")
        
        if data.top_hallucination_patterns:
            print(f"\n⚠️ TOP HALLUCINATION PATTERNS")
            for pattern, count in data.top_hallucination_patterns[:5]:
                print(f"   [{count}] {pattern}")
        
        if data.active_alerts:
            print(f"\n🚨 ACTIVE ALERTS")
            for alert in data.active_alerts:
                print(f"   {alert.severity.value}: {alert.message}")
        
        print("\n" + "=" * 70)
```

---

## Continuous Improvement Loop

Use monitoring data to systematically improve the system.

```python
class ContinuousImprover:
    """
    Analyze monitoring data and suggest improvements.
    """
    
    def analyze_failures(
        self,
        failed_logs: list[QueryLog]
    ) -> dict:
        """
        Analyze failure patterns and suggest improvements.
        """
        analysis = {
            "total_failures": len(failed_logs),
            "patterns": {},
            "recommendations": []
        }
        
        # Group by abstention reason
        by_reason = {}
        for log in failed_logs:
            reason = log.abstention_reason or "low_faithfulness"
            by_reason.setdefault(reason, []).append(log)
        
        analysis["patterns"]["by_reason"] = {
            k: len(v) for k, v in by_reason.items()
        }
        
        # Generate recommendations
        if by_reason.get("low_relevance", []):
            count = len(by_reason["low_relevance"])
            if count / len(failed_logs) > 0.5:
                analysis["recommendations"].append({
                    "area": "retrieval",
                    "suggestion": "High proportion of low-relevance failures. "
                                "Consider improving chunking, embeddings, or adding query expansion.",
                    "priority": "high"
                })
        
        if by_reason.get("max_retries_exceeded", []):
            count = len(by_reason["max_retries_exceeded"])
            if count > 10:
                analysis["recommendations"].append({
                    "area": "generation",
                    "suggestion": "Many queries failing after retries. "
                                "Review strict prompt effectiveness or adjust thresholds.",
                    "priority": "medium"
                })
        
        # Analyze common issues in failed queries
        common_issues = {}
        for log in failed_logs:
            if log.issues:
                for issue in log.issues:
                    common_issues[issue] = common_issues.get(issue, 0) + 1
        
        if common_issues:
            top_issue = max(common_issues.items(), key=lambda x: x[1])
            analysis["recommendations"].append({
                "area": "detection",
                "suggestion": f"Common issue: '{top_issue[0]}' ({top_issue[1]} occurrences). "
                            "Consider adding specific handling for this case.",
                "priority": "medium"
            })
        
        return analysis
    
    def suggest_threshold_adjustment(
        self,
        calibration: dict
    ) -> dict:
        """
        Suggest threshold adjustments based on calibration data.
        """
        suggestions = {}
        
        fp_rate = calibration.get("false_positive_rate", 0)
        fn_rate = calibration.get("false_negative_rate", 0)
        
        if fp_rate > 0.15:
            suggestions["faithfulness_threshold"] = {
                "current": 0.75,
                "suggested": 0.70,
                "reason": f"High false positive rate ({fp_rate:.1%}) indicates threshold is too strict"
            }
        
        if fn_rate > 0.10:
            suggestions["faithfulness_threshold"] = {
                "current": 0.75,
                "suggested": 0.80,
                "reason": f"High false negative rate ({fn_rate:.1%}) indicates threshold is too lenient"
            }
        
        return suggestions
```

---

## Key Takeaways

1. **Four core metrics**: Faithfulness rate, abstention rate, false abstention rate, and escape rate. The escape rate (missed hallucinations) is the most critical — it measures harm reaching users.
    
2. **Build evaluation datasets thoughtfully**: Include answerable, unanswerable, partial, and trap queries. Update as you discover new failure modes.
    
3. **Offline evaluation for experiments**: Compare configurations, prompt versions, and thresholds before deploying.
    
4. **Online monitoring for reality**: Log everything, aggregate into time windows, alert on degradation.
    
5. **Sample strategically**: 100% verification in dev, risk-based sampling in prod. Always verify high-stakes categories.
    
6. **Human review calibrates automation**: Periodic human review identifies blind spots in automated detection and provides data for tuning thresholds.
    
7. **Close the improvement loop**: Analyze failure patterns → adjust prompts/thresholds/retrieval → measure impact → repeat.
    

---

## Summary: Days 1-2 Complete

You now have a complete framework for hallucination detection and mitigation:

|Note|Focus|Key Deliverable|
|---|---|---|
|Note 1|Understanding|Why hallucinations happen, types in RAG|
|Note 2|Detection|LLM-as-Judge, claim verification, self-consistency|
|Note 3|Mitigation|Prompt constraints, retrieval anchoring, abstention|
|Note 4|Implementation|Complete HallucinationGuard pipeline|
|Note 5|Operations|Metrics, monitoring, continuous improvement|

Next in Week 9: Error handling, circuit breakers, and production hardening patterns.