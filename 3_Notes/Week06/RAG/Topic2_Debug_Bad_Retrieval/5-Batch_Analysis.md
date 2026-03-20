# Batch Analysis and Pattern Detection

## The Core Insight

Fixing failures one at a time is whack-a-mole. You fix query A, query B breaks. You tune for error codes, date queries start failing. There's no end.

Batch analysis flips the approach: instead of "why did THIS query fail?", ask "what do all failing queries have in common?" Find the pattern, fix it once, solve dozens of failures simultaneously.

```
┌─────────────────────────────────────────────────────────────────────┐
│              One-by-One vs. Pattern-Based Fixing                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   One-by-one:                                                       │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                                                             │   │
│   │   Failure 1 → Debug → Fix → ✓                               │   │
│   │   Failure 2 → Debug → Fix → ✓                               │   │
│   │   Failure 3 → Debug → Fix → ✓                               │   │
│   │   ...                                                       │   │
│   │   Failure 47 → Debug → Fix → ✓                              │   │
│   │                                                             │   │
│   │   Time spent: 47 × 30 min = 23.5 hours                      │   │
│   │   Root causes found: Maybe 3-4 (but you didn't notice)      │   │
│   │                                                             │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Pattern-based:                                                    │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                                                             │   │
│   │   47 failures                                               │   │
│   │       │                                                     │   │
│   │       ▼                                                     │   │
│   │   Aggregate & cluster                                       │   │
│   │       │                                                     │   │
│   │       ▼                                                     │   │
│   │   Pattern A: 28 failures (error code queries)               │   │
│   │   Pattern B: 12 failures (multi-hop reasoning)              │   │
│   │   Pattern C: 7 failures (recent events)                     │   │
│   │       │                                                     │   │
│   │       ▼                                                     │   │
│   │   Fix Pattern A → 28 failures resolved                      │   │
│   │   Fix Pattern B → 12 failures resolved                      │   │
│   │   Fix Pattern C → 7 failures resolved                       │   │
│   │                                                             │   │
│   │   Time spent: 3 × 2 hours = 6 hours                         │   │
│   │   All 47 failures resolved systematically                   │   │
│   │                                                             │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The goal: **find the 3-5 patterns that explain 80% of failures, fix those.**

---

## Single Failures vs. Patterns

Understanding the difference:

|Single Failure|Pattern|
|---|---|
|"Query X failed"|"Queries with error codes fail"|
|Fix: tune this query|Fix: add BM25 hybrid search|
|Solves: 1 problem|Solves: entire category|
|Recurs: different query, same issue|Recurs: never (root cause fixed)|

### Signs You're Seeing a Pattern

- Multiple failures share a characteristic (query type, topic, format)
- Same failure type (retrieval, generation) appears repeatedly
- Fixes for individual queries don't generalize
- New queries fail in the same way old ones did

### Pattern Categories

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Pattern Categories                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   QUERY PATTERNS (what users ask)                                   │
│   • Contains numbers/codes: "error E-4012", "order #12345"          │
│   • Multi-part questions: "compare X and Y", "list all Z"          │
│   • Temporal queries: "current", "latest", "this year"             │
│   • Negations: "not X", "without Y", "except Z"                    │
│                                                                     │
│   CONTENT PATTERNS (what's in your corpus)                          │
│   • Document type: PDFs fail, markdown works                        │
│   • Content age: old docs outdated, new docs not indexed           │
│   • Domain: legal docs fail, technical docs work                   │
│                                                                     │
│   PIPELINE PATTERNS (where things break)                            │
│   • Retrieval: always the same failure type                        │
│   • Context: truncation at specific token counts                   │
│   • Generation: hallucination on specific topics                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Aggregating Failures

Before detecting patterns, aggregate failures into analyzable groups.

### Group by Failure Type

```python
from collections import defaultdict
from dataclasses import dataclass
from typing import List


@dataclass
class FailureRecord:
    """A single failure with diagnosis."""
    query: str
    expected: str
    actual: str
    failure_type: str      # indexing, retrieval, context, generation
    failure_subtype: str   # ranked_too_low, hallucination, etc.
    trace: dict            # Lightweight trace data
    timestamp: str
    metadata: dict = None  # Additional features


def aggregate_by_failure_type(
    failures: List[FailureRecord]
) -> dict[str, List[FailureRecord]]:
    """Group failures by type and subtype."""
    grouped = defaultdict(list)
    
    for failure in failures:
        key = f"{failure.failure_type}/{failure.failure_subtype}"
        grouped[key].append(failure)
    
    return dict(grouped)


# Usage
failures = load_failures_from_eval()
grouped = aggregate_by_failure_type(failures)

for failure_type, records in sorted(grouped.items(), key=lambda x: -len(x[1])):
    print(f"{failure_type}: {len(records)} failures")

# Output:
# retrieval/ranked_too_low: 28 failures
# generation/hallucination: 12 failures
# retrieval/not_retrieved: 7 failures
```

### Group by Query Characteristics

```python
import re
from typing import Callable


def extract_query_features(query: str) -> dict:
    """Extract features from a query for pattern detection."""
    return {
        "has_numbers": bool(re.search(r'\d+', query)),
        "has_error_code": bool(re.search(r'[A-Z]+-?\d+|error\s+\d+', query, re.I)),
        "is_comparison": any(w in query.lower() for w in ["compare", "vs", "versus", "difference"]),
        "is_list_request": any(w in query.lower() for w in ["list", "all", "every", "each"]),
        "is_temporal": any(w in query.lower() for w in ["current", "latest", "now", "today", "recent"]),
        "has_negation": any(w in query.lower() for w in ["not", "without", "except", "exclude"]),
        "question_type": classify_question_type(query),
        "word_count": len(query.split()),
        "query_length": len(query),
    }


def classify_question_type(query: str) -> str:
    """Classify question type."""
    query_lower = query.lower()
    
    if query_lower.startswith(("what is", "what's", "what are")):
        return "definition"
    elif query_lower.startswith(("how do", "how to", "how can")):
        return "procedural"
    elif query_lower.startswith(("why")):
        return "explanatory"
    elif query_lower.startswith(("when", "what time", "what date")):
        return "temporal"
    elif query_lower.startswith(("where")):
        return "location"
    elif query_lower.startswith(("who")):
        return "person"
    elif "compare" in query_lower or "vs" in query_lower:
        return "comparison"
    else:
        return "other"


def aggregate_by_features(
    failures: List[FailureRecord]
) -> dict[str, List[FailureRecord]]:
    """Group failures by query features."""
    
    # Extract features for each failure
    for failure in failures:
        failure.metadata = failure.metadata or {}
        failure.metadata["features"] = extract_query_features(failure.query)
    
    # Group by significant features
    feature_groups = defaultdict(list)
    
    for failure in failures:
        features = failure.metadata["features"]
        
        # Create feature signature
        significant_features = []
        if features["has_error_code"]:
            significant_features.append("error_code")
        if features["is_comparison"]:
            significant_features.append("comparison")
        if features["is_temporal"]:
            significant_features.append("temporal")
        if features["has_negation"]:
            significant_features.append("negation")
        if features["is_list_request"]:
            significant_features.append("list_request")
        
        # Default to question type if no special features
        if not significant_features:
            significant_features.append(f"type:{features['question_type']}")
        
        for feature in significant_features:
            feature_groups[feature].append(failure)
    
    return dict(feature_groups)
```

### Group by Time Window

```python
from datetime import datetime, timedelta


def aggregate_by_time(
    failures: List[FailureRecord],
    window_hours: int = 24
) -> dict[str, List[FailureRecord]]:
    """Group failures by time window to detect temporal patterns."""
    
    time_groups = defaultdict(list)
    
    for failure in failures:
        ts = datetime.fromisoformat(failure.timestamp)
        window_start = ts.replace(
            hour=(ts.hour // window_hours) * window_hours,
            minute=0, second=0, microsecond=0
        )
        window_key = window_start.isoformat()
        time_groups[window_key].append(failure)
    
    return dict(time_groups)


# Detect spikes
def detect_failure_spikes(
    failures: List[FailureRecord],
    window_hours: int = 1,
    spike_threshold: float = 2.0
) -> List[dict]:
    """Detect time periods with abnormally high failure rates."""
    
    time_groups = aggregate_by_time(failures, window_hours)
    
    counts = [len(v) for v in time_groups.values()]
    if not counts:
        return []
    
    avg_count = sum(counts) / len(counts)
    
    spikes = []
    for window, records in time_groups.items():
        if len(records) > avg_count * spike_threshold:
            spikes.append({
                "window": window,
                "count": len(records),
                "average": avg_count,
                "multiplier": len(records) / avg_count,
                "failures": records
            })
    
    return sorted(spikes, key=lambda x: -x["multiplier"])
```

---

## Pattern Detection Methods

### Method 1: Feature Correlation

Find which query features correlate with failures:

```python
from typing import List, Tuple
import statistics


def correlate_features_with_failures(
    all_queries: List[dict],  # [{"query": ..., "failed": bool}]
) -> List[Tuple[str, float]]:
    """
    Find which features correlate most strongly with failures.
    
    Returns list of (feature, correlation) sorted by correlation.
    """
    # Extract features for all queries
    for item in all_queries:
        item["features"] = extract_query_features(item["query"])
    
    # Calculate failure rate per feature
    feature_stats = defaultdict(lambda: {"with": 0, "with_failed": 0, "without": 0, "without_failed": 0})
    
    for item in all_queries:
        for feature, present in item["features"].items():
            if isinstance(present, bool):
                if present:
                    feature_stats[feature]["with"] += 1
                    if item["failed"]:
                        feature_stats[feature]["with_failed"] += 1
                else:
                    feature_stats[feature]["without"] += 1
                    if item["failed"]:
                        feature_stats[feature]["without_failed"] += 1
    
    # Calculate correlation (difference in failure rates)
    correlations = []
    
    for feature, stats in feature_stats.items():
        if stats["with"] > 0 and stats["without"] > 0:
            rate_with = stats["with_failed"] / stats["with"]
            rate_without = stats["without_failed"] / stats["without"]
            correlation = rate_with - rate_without
            
            # Only include if statistically meaningful
            if stats["with"] >= 5:  # Minimum sample size
                correlations.append((feature, correlation, stats))
    
    return sorted(correlations, key=lambda x: -abs(x[1]))


# Usage
results = correlate_features_with_failures(all_queries)

print("Features most correlated with failure:")
for feature, corr, stats in results[:5]:
    print(f"  {feature}: {corr:+.2%} "
          f"({stats['with_failed']}/{stats['with']} vs "
          f"{stats['without_failed']}/{stats['without']})")

# Output:
# Features most correlated with failure:
#   has_error_code: +45.2% (28/35 vs 19/165)
#   is_temporal: +23.1% (12/30 vs 35/170)
#   has_negation: +18.7% (8/20 vs 39/180)
```

### Method 2: Failure Clustering

Cluster similar failing queries to find natural groupings:

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from collections import Counter


def cluster_failing_queries(
    failures: List[FailureRecord],
    n_clusters: int = 5
) -> List[dict]:
    """
    Cluster failing queries to find natural groupings.
    
    Returns cluster summaries with representative queries.
    """
    queries = [f.query for f in failures]
    
    # Vectorize queries
    vectorizer = TfidfVectorizer(
        max_features=500,
        stop_words='english',
        ngram_range=(1, 2)
    )
    X = vectorizer.fit_transform(queries)
    
    # Cluster
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(X)
    
    # Analyze clusters
    clusters = []
    feature_names = vectorizer.get_feature_names_out()
    
    for cluster_id in range(n_clusters):
        cluster_indices = [i for i, l in enumerate(labels) if l == cluster_id]
        cluster_failures = [failures[i] for i in cluster_indices]
        
        # Get top terms for this cluster
        cluster_center = kmeans.cluster_centers_[cluster_id]
        top_term_indices = cluster_center.argsort()[-10:][::-1]
        top_terms = [feature_names[i] for i in top_term_indices]
        
        # Get failure type distribution
        failure_types = Counter(
            f"{f.failure_type}/{f.failure_subtype}" 
            for f in cluster_failures
        )
        
        clusters.append({
            "cluster_id": cluster_id,
            "size": len(cluster_failures),
            "top_terms": top_terms[:5],
            "failure_types": dict(failure_types),
            "example_queries": [f.query for f in cluster_failures[:3]],
            "failures": cluster_failures
        })
    
    return sorted(clusters, key=lambda x: -x["size"])


# Usage
clusters = cluster_failing_queries(failures, n_clusters=5)

for cluster in clusters:
    print(f"\nCluster {cluster['cluster_id']} ({cluster['size']} failures)")
    print(f"  Top terms: {', '.join(cluster['top_terms'])}")
    print(f"  Failure types: {cluster['failure_types']}")
    print(f"  Examples:")
    for q in cluster['example_queries']:
        print(f"    - {q[:60]}...")
```

### Method 3: Retrieval Score Analysis

Find patterns in retrieval scores:

```python
import statistics


def analyze_retrieval_patterns(
    failures: List[FailureRecord]
) -> dict:
    """
    Analyze retrieval-stage patterns in failures.
    """
    retrieval_failures = [
        f for f in failures 
        if f.failure_type == "retrieval"
    ]
    
    if not retrieval_failures:
        return {"retrieval_failures": 0}
    
    patterns = {
        "retrieval_failures": len(retrieval_failures),
        "subtypes": Counter(f.failure_subtype for f in retrieval_failures),
    }
    
    # Analyze score distributions
    top_scores = []
    relevant_positions = []
    
    for f in retrieval_failures:
        if "trace" in f.__dict__ and f.trace:
            # Get top retrieved score
            if f.trace.get("fused_results"):
                top_score = f.trace["fused_results"][0].get("score", 0)
                top_scores.append(top_score)
            
            # Get position of relevant doc if known
            if f.trace.get("relevant_doc_position"):
                relevant_positions.append(f.trace["relevant_doc_position"])
    
    if top_scores:
        patterns["top_score_stats"] = {
            "mean": statistics.mean(top_scores),
            "median": statistics.median(top_scores),
            "min": min(top_scores),
            "max": max(top_scores)
        }
    
    if relevant_positions:
        patterns["relevant_position_stats"] = {
            "mean": statistics.mean(relevant_positions),
            "median": statistics.median(relevant_positions),
            "min": min(relevant_positions),
            "max": max(relevant_positions),
            "beyond_top_20": sum(1 for p in relevant_positions if p > 20)
        }
    
    return patterns
```

---

## Common RAG Failure Patterns

A catalog of patterns with signatures and fixes:

### Pattern 1: Error Code / ID Queries

**Signature:**

- Query contains alphanumeric codes: `E-4012`, `SKU-12345`, `order #789`
- Failure type: retrieval/ranked_too_low or retrieval/not_retrieved
- Dense retrieval scores low, BM25 would match exactly

**Detection:**

```python
def detect_error_code_pattern(failures: List[FailureRecord]) -> dict:
    code_pattern = re.compile(r'[A-Z]+-?\d+|\b\d{4,}\b|#\d+', re.I)
    
    code_failures = [
        f for f in failures
        if code_pattern.search(f.query) and f.failure_type == "retrieval"
    ]
    
    return {
        "pattern": "error_code_queries",
        "count": len(code_failures),
        "percentage": len(code_failures) / len(failures) * 100 if failures else 0,
        "examples": [f.query for f in code_failures[:5]],
        "fix": "Add BM25 hybrid search for exact matching"
    }
```

**Fix:** Add BM25 hybrid search with weight 0.3-0.5

---

### Pattern 2: Multi-Hop Reasoning

**Signature:**

- Query requires connecting multiple facts: "Compare X and Y", "What's the relationship between A and B"
- Failure type: generation/incomplete or retrieval (each piece retrieved but not connected)
- Individual chunks correct, synthesis wrong

**Detection:**

```python
def detect_multihop_pattern(failures: List[FailureRecord]) -> dict:
    multihop_signals = ["compare", "relationship", "between", "connect", "both", "and", "vs"]
    
    multihop_failures = [
        f for f in failures
        if any(s in f.query.lower() for s in multihop_signals)
        and f.failure_type in ("generation", "retrieval")
    ]
    
    return {
        "pattern": "multi_hop_reasoning",
        "count": len(multihop_failures),
        "percentage": len(multihop_failures) / len(failures) * 100 if failures else 0,
        "examples": [f.query for f in multihop_failures[:5]],
        "fix": "Add query decomposition or multi-turn retrieval"
    }
```

**Fix:** Query decomposition (split into sub-queries), or iterative retrieval

---

### Pattern 3: Temporal / Recency Queries

**Signature:**

- Query asks about "current", "latest", "now", "today"
- Failure type: retrieval (old docs ranked higher) or generation (outdated info)
- Recent documents exist but not surfaced

**Detection:**

```python
def detect_temporal_pattern(failures: List[FailureRecord]) -> dict:
    temporal_signals = ["current", "latest", "now", "today", "recent", "this year", "2024", "2025"]
    
    temporal_failures = [
        f for f in failures
        if any(s in f.query.lower() for s in temporal_signals)
    ]
    
    return {
        "pattern": "temporal_queries",
        "count": len(temporal_failures),
        "percentage": len(temporal_failures) / len(failures) * 100 if failures else 0,
        "examples": [f.query for f in temporal_failures[:5]],
        "fix": "Add date metadata boosting or recency filter"
    }
```

**Fix:** Metadata filtering by date, recency boosting in retrieval

---

### Pattern 4: Negation Queries

**Signature:**

- Query contains "not", "without", "except", "exclude"
- Failure type: retrieval (embeddings don't handle negation well)
- Returns results matching the positive part, ignoring negation

**Detection:**

```python
def detect_negation_pattern(failures: List[FailureRecord]) -> dict:
    negation_signals = ["not", "without", "except", "exclude", "don't", "doesn't", "isn't", "aren't"]
    
    negation_failures = [
        f for f in failures
        if any(f" {s} " in f" {f.query.lower()} " for s in negation_signals)
        and f.failure_type == "retrieval"
    ]
    
    return {
        "pattern": "negation_queries",
        "count": len(negation_failures),
        "percentage": len(negation_failures) / len(failures) * 100 if failures else 0,
        "examples": [f.query for f in negation_failures[:5]],
        "fix": "Post-retrieval filtering or query rewriting"
    }
```

**Fix:** Post-retrieval filtering, or rewrite query to positive form with filter

---

### Pattern 5: Lost in the Middle

**Signature:**

- Failure type: generation/ignored_context
- Relevant info is in retrieved chunks but at positions 4-8 of 10
- Answer would be correct if relevant chunk was first or last

**Detection:**

```python
def detect_lost_in_middle_pattern(failures: List[FailureRecord]) -> dict:
    middle_failures = []
    
    for f in failures:
        if f.failure_type == "generation" and f.trace:
            selected_chunks = f.trace.get("selected_chunks", [])
            if len(selected_chunks) >= 5:
                # Check if relevant content is in middle positions
                relevant_positions = f.trace.get("relevant_chunk_positions", [])
                if relevant_positions:
                    middle_positions = [p for p in relevant_positions if 2 < p < len(selected_chunks) - 1]
                    if middle_positions:
                        middle_failures.append(f)
    
    return {
        "pattern": "lost_in_middle",
        "count": len(middle_failures),
        "percentage": len(middle_failures) / len(failures) * 100 if failures else 0,
        "examples": [f.query for f in middle_failures[:5]],
        "fix": "Reorder chunks (relevant at start/end) or reduce context size"
    }
```

**Fix:** Reorder chunks to put highest-relevance at start and end, or reduce total chunks

---

### Pattern Catalog Summary

|Pattern|Signature|Typical %|Fix|
|---|---|---|---|
|Error codes|Contains codes, retrieval failure|15-30%|BM25 hybrid search|
|Multi-hop|Comparison/relationship, synthesis failure|10-20%|Query decomposition|
|Temporal|"current/latest", outdated results|10-15%|Date metadata boosting|
|Negation|"not/without", wrong results|5-10%|Post-retrieval filtering|
|Lost in middle|Generation failure, info at position 4-8|5-15%|Context reordering|
|Document type|Specific format fails (PDF/table)|5-10%|Fix parser for that type|
|Vocabulary|Domain terms not in embeddings|5-15%|Domain-specific embeddings|

---

## Prioritization Framework

Not all patterns are equal. Prioritize by impact and effort.

### Impact × Frequency Matrix

```
                    HIGH FREQUENCY
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         │   FIX FIRST    │   FIX FIRST    │
         │   (Quick wins) │   (Critical)   │
         │                │                │
    LOW  ├────────────────┼────────────────┤ HIGH
  IMPACT │                │                │ IMPACT
         │   IGNORE /     │   FIX LATER    │
         │   BACKLOG      │   (Important)  │
         │                │                │
         └────────────────┼────────────────┘
                          │
                    LOW FREQUENCY
```

### Scoring Function

```python
@dataclass
class PatternPriority:
    """Priority score for a failure pattern."""
    pattern_name: str
    failure_count: int
    failure_percentage: float
    estimated_effort: str  # "low", "medium", "high"
    fix_description: str
    priority_score: float
    
    def __repr__(self):
        return f"{self.pattern_name}: {self.failure_count} failures, priority={self.priority_score:.1f}"


def prioritize_patterns(
    patterns: List[dict],
    total_failures: int
) -> List[PatternPriority]:
    """
    Score and prioritize patterns for fixing.
    
    Priority = (impact × frequency) / effort
    """
    effort_multiplier = {"low": 1.0, "medium": 0.5, "high": 0.25}
    
    priorities = []
    
    for pattern in patterns:
        count = pattern["count"]
        percentage = count / total_failures * 100 if total_failures else 0
        effort = estimate_effort(pattern["pattern"])
        
        # Impact: how bad is this failure type?
        impact = get_impact_score(pattern.get("failure_types", {}))
        
        # Frequency component
        frequency = count / total_failures if total_failures else 0
        
        # Combined score
        score = (impact * frequency) * effort_multiplier.get(effort, 0.5) * 100
        
        priorities.append(PatternPriority(
            pattern_name=pattern["pattern"],
            failure_count=count,
            failure_percentage=percentage,
            estimated_effort=effort,
            fix_description=pattern["fix"],
            priority_score=score
        ))
    
    return sorted(priorities, key=lambda x: -x.priority_score)


def estimate_effort(pattern_name: str) -> str:
    """Estimate effort to fix a pattern."""
    effort_map = {
        "error_code_queries": "low",      # Add BM25, config change
        "temporal_queries": "low",         # Add date filter
        "negation_queries": "medium",      # Query rewriting logic
        "multi_hop_reasoning": "high",     # Query decomposition
        "lost_in_middle": "medium",        # Context reordering
    }
    return effort_map.get(pattern_name, "medium")


def get_impact_score(failure_types: dict) -> float:
    """Score impact based on failure types."""
    # Retrieval failures are more fundamental
    impact_weights = {
        "indexing": 1.0,    # Critical - content not available
        "retrieval": 0.9,   # Serious - can't find content
        "context": 0.7,     # Moderate - losing good content
        "generation": 0.5   # Lower - can often fix with prompts
    }
    
    if not failure_types:
        return 0.5
    
    total = sum(failure_types.values())
    weighted_sum = sum(
        count * impact_weights.get(ftype.split("/")[0], 0.5)
        for ftype, count in failure_types.items()
    )
    
    return weighted_sum / total if total else 0.5
```

### Usage

```python
# Detect all patterns
patterns = [
    detect_error_code_pattern(failures),
    detect_multihop_pattern(failures),
    detect_temporal_pattern(failures),
    detect_negation_pattern(failures),
    detect_lost_in_middle_pattern(failures),
]

# Filter patterns with > 3 failures
significant_patterns = [p for p in patterns if p["count"] >= 3]

# Prioritize
priorities = prioritize_patterns(significant_patterns, len(failures))

print("Fix priority order:")
for i, p in enumerate(priorities, 1):
    print(f"{i}. {p.pattern_name}")
    print(f"   {p.failure_count} failures ({p.failure_percentage:.1f}%)")
    print(f"   Effort: {p.estimated_effort}")
    print(f"   Fix: {p.fix_description}")
    print()
```

Output:

```
Fix priority order:
1. error_code_queries
   28 failures (35.0%)
   Effort: low
   Fix: Add BM25 hybrid search for exact matching

2. temporal_queries
   12 failures (15.0%)
   Effort: low
   Fix: Add date metadata boosting or recency filter

3. lost_in_middle
   8 failures (10.0%)
   Effort: medium
   Fix: Reorder chunks (relevant at start/end) or reduce context size
```

---

## Implementation

Complete batch analyzer:

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import Counter, defaultdict
import re


@dataclass
class BatchAnalysisResult:
    """Complete result of batch failure analysis."""
    total_failures: int
    total_successes: int
    failure_rate: float
    
    # Aggregations
    by_failure_type: Dict[str, int]
    by_query_feature: Dict[str, int]
    
    # Detected patterns
    patterns: List[dict]
    
    # Prioritized fixes
    priorities: List[PatternPriority]
    
    # Time analysis
    time_spikes: List[dict]
    
    # Recommendations
    top_recommendations: List[str]


class BatchAnalyzer:
    """
    Analyze failures in batch to detect patterns and prioritize fixes.
    """
    
    def __init__(self):
        self.pattern_detectors = [
            self._detect_error_code_pattern,
            self._detect_multihop_pattern,
            self._detect_temporal_pattern,
            self._detect_negation_pattern,
            self._detect_lost_in_middle_pattern,
            self._detect_vocabulary_pattern,
        ]
    
    def analyze(
        self,
        failures: List[FailureRecord],
        successes: List[dict] = None
    ) -> BatchAnalysisResult:
        """
        Run full batch analysis on failures.
        
        Args:
            failures: List of failure records with diagnosis
            successes: Optional list of successful queries for comparison
        
        Returns:
            BatchAnalysisResult with patterns and recommendations
        """
        successes = successes or []
        
        # Basic stats
        total_failures = len(failures)
        total_successes = len(successes)
        total = total_failures + total_successes
        failure_rate = total_failures / total if total else 0
        
        # Aggregate by failure type
        by_failure_type = Counter(
            f"{f.failure_type}/{f.failure_subtype}" 
            for f in failures
        )
        
        # Aggregate by query features
        by_query_feature = self._aggregate_by_features(failures)
        
        # Detect patterns
        patterns = []
        for detector in self.pattern_detectors:
            pattern = detector(failures)
            if pattern["count"] >= 3:  # Minimum threshold
                patterns.append(pattern)
        
        # Prioritize
        priorities = prioritize_patterns(patterns, total_failures)
        
        # Time analysis
        time_spikes = detect_failure_spikes(failures)
        
        # Generate recommendations
        top_recommendations = self._generate_recommendations(priorities[:3])
        
        return BatchAnalysisResult(
            total_failures=total_failures,
            total_successes=total_successes,
            failure_rate=failure_rate,
            by_failure_type=dict(by_failure_type),
            by_query_feature=by_query_feature,
            patterns=patterns,
            priorities=priorities,
            time_spikes=time_spikes,
            top_recommendations=top_recommendations
        )
    
    def _aggregate_by_features(
        self, 
        failures: List[FailureRecord]
    ) -> Dict[str, int]:
        """Count failures by query feature."""
        feature_counts = Counter()
        
        for f in failures:
            features = extract_query_features(f.query)
            for feature, present in features.items():
                if isinstance(present, bool) and present:
                    feature_counts[feature] += 1
        
        return dict(feature_counts)
    
    def _detect_error_code_pattern(
        self, 
        failures: List[FailureRecord]
    ) -> dict:
        code_pattern = re.compile(r'[A-Z]+-?\d+|\b\d{4,}\b|#\d+', re.I)
        
        matches = [
            f for f in failures
            if code_pattern.search(f.query) and f.failure_type == "retrieval"
        ]
        
        return {
            "pattern": "error_code_queries",
            "count": len(matches),
            "failure_types": Counter(f"{f.failure_type}/{f.failure_subtype}" for f in matches),
            "examples": [f.query for f in matches[:5]],
            "fix": "Add BM25 hybrid search for exact matching"
        }
    
    def _detect_multihop_pattern(
        self, 
        failures: List[FailureRecord]
    ) -> dict:
        signals = ["compare", "relationship", "between", "both", "and", "vs", "versus"]
        
        matches = [
            f for f in failures
            if any(s in f.query.lower() for s in signals)
        ]
        
        return {
            "pattern": "multi_hop_reasoning",
            "count": len(matches),
            "failure_types": Counter(f"{f.failure_type}/{f.failure_subtype}" for f in matches),
            "examples": [f.query for f in matches[:5]],
            "fix": "Add query decomposition or iterative retrieval"
        }
    
    def _detect_temporal_pattern(
        self, 
        failures: List[FailureRecord]
    ) -> dict:
        signals = ["current", "latest", "now", "today", "recent", "this year"]
        
        matches = [
            f for f in failures
            if any(s in f.query.lower() for s in signals)
        ]
        
        return {
            "pattern": "temporal_queries",
            "count": len(matches),
            "failure_types": Counter(f"{f.failure_type}/{f.failure_subtype}" for f in matches),
            "examples": [f.query for f in matches[:5]],
            "fix": "Add date metadata boosting or recency filter"
        }
    
    def _detect_negation_pattern(
        self, 
        failures: List[FailureRecord]
    ) -> dict:
        signals = [" not ", " without ", " except ", " exclude "]
        
        matches = [
            f for f in failures
            if any(s in f" {f.query.lower()} " for s in signals)
            and f.failure_type == "retrieval"
        ]
        
        return {
            "pattern": "negation_queries",
            "count": len(matches),
            "failure_types": Counter(f"{f.failure_type}/{f.failure_subtype}" for f in matches),
            "examples": [f.query for f in matches[:5]],
            "fix": "Post-retrieval filtering or query rewriting"
        }
    
    def _detect_lost_in_middle_pattern(
        self, 
        failures: List[FailureRecord]
    ) -> dict:
        matches = [
            f for f in failures
            if f.failure_type == "generation" 
            and f.failure_subtype in ("ignored_context", "hallucination")
        ]
        
        return {
            "pattern": "lost_in_middle",
            "count": len(matches),
            "failure_types": Counter(f"{f.failure_type}/{f.failure_subtype}" for f in matches),
            "examples": [f.query for f in matches[:5]],
            "fix": "Reorder chunks or reduce context size"
        }
    
    def _detect_vocabulary_pattern(
        self, 
        failures: List[FailureRecord]
    ) -> dict:
        # Queries where BM25 found nothing but query has domain terms
        matches = [
            f for f in failures
            if f.failure_type == "retrieval"
            and f.trace 
            and len(f.trace.get("bm25_results", [])) == 0
        ]
        
        return {
            "pattern": "vocabulary_mismatch",
            "count": len(matches),
            "failure_types": Counter(f"{f.failure_type}/{f.failure_subtype}" for f in matches),
            "examples": [f.query for f in matches[:5]],
            "fix": "Query expansion with synonyms or domain-specific embeddings"
        }
    
    def _generate_recommendations(
        self, 
        top_priorities: List[PatternPriority]
    ) -> List[str]:
        """Generate actionable recommendations from top priorities."""
        recommendations = []
        
        for p in top_priorities:
            rec = f"[{p.estimated_effort.upper()} EFFORT] Fix '{p.pattern_name}' "
            rec += f"({p.failure_count} failures, {p.failure_percentage:.1f}%): "
            rec += p.fix_description
            recommendations.append(rec)
        
        return recommendations


# Usage
analyzer = BatchAnalyzer()
result = analyzer.analyze(failures)

print(f"Total: {result.total_failures} failures, {result.failure_rate:.1%} failure rate")
print(f"\nBy failure type:")
for ftype, count in sorted(result.by_failure_type.items(), key=lambda x: -x[1]):
    print(f"  {ftype}: {count}")

print(f"\nDetected patterns: {len(result.patterns)}")
for pattern in result.patterns:
    print(f"  {pattern['pattern']}: {pattern['count']} failures")

print(f"\nTop recommendations:")
for rec in result.top_recommendations:
    print(f"  • {rec}")
```

---

## From Pattern to Systematic Fix

Translating detected patterns into pipeline changes:

### Fix Implementation Checklist

For each prioritized pattern:

```
□ Pattern identified and validated
□ Root cause understood (not just symptoms)
□ Fix designed with specific changes
□ Fix implemented in code
□ Unit tests for the fix
□ Regression test on original failures
□ Side effect check on working queries
□ Deploy and monitor
```

### Example: Error Code Pattern → BM25 Hybrid

```python
# Before: Dense-only retrieval
class Retriever:
    def retrieve(self, query: str, top_k: int = 20):
        embedding = self.embed(query)
        return self.vector_store.search(embedding, top_k=top_k)


# After: Hybrid retrieval (systematic fix)
class HybridRetriever:
    def __init__(self, vector_store, bm25_index, dense_weight: float = 0.7):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.dense_weight = dense_weight
        self.bm25_weight = 1 - dense_weight
    
    def retrieve(self, query: str, top_k: int = 20):
        # Dense retrieval
        embedding = self.embed(query)
        dense_results = self.vector_store.search(embedding, top_k=top_k * 2)
        
        # BM25 retrieval
        bm25_results = self.bm25_index.search(query, top_k=top_k * 2)
        
        # RRF fusion
        fused = self.rrf_fusion(dense_results, bm25_results, top_k)
        
        return fused
```

### Validation After Fix

```python
def validate_pattern_fix(
    analyzer: BatchAnalyzer,
    pattern_name: str,
    original_failures: List[FailureRecord],
    rag_system,
    debugger: RAGDebugger
) -> dict:
    """
    Validate that a fix resolved the pattern.
    """
    # Get queries that were in this pattern
    pattern_queries = [
        f for f in original_failures
        if pattern_matches(f, pattern_name)  # Your matching logic
    ]
    
    # Re-run them
    still_failing = []
    now_passing = []
    
    for f in pattern_queries:
        result = debugger.diagnose_failure(
            question=f.query,
            expected_answer=f.expected
        )
        
        if result.is_correct:
            now_passing.append(f.query)
        else:
            still_failing.append({
                "query": f.query,
                "new_failure_type": f"{result.failure_type}/{result.failure_subtype}"
            })
    
    return {
        "pattern": pattern_name,
        "original_failures": len(pattern_queries),
        "now_passing": len(now_passing),
        "still_failing": len(still_failing),
        "fix_rate": len(now_passing) / len(pattern_queries) if pattern_queries else 0,
        "remaining_issues": still_failing[:5]  # Sample
    }
```

---

## Measuring Fix Effectiveness

Track impact over time:

### Before/After Comparison

```python
@dataclass
class FixEffectiveness:
    """Measure effectiveness of a fix."""
    fix_name: str
    fix_date: str
    
    # Before metrics
    before_failure_rate: float
    before_pattern_count: int
    
    # After metrics (measured N days later)
    after_failure_rate: float
    after_pattern_count: int
    
    # Calculated
    failure_rate_change: float
    pattern_reduction: float
    
    # Regressions
    new_failure_patterns: List[str]


def measure_fix_effectiveness(
    before_analysis: BatchAnalysisResult,
    after_analysis: BatchAnalysisResult,
    fix_name: str,
    target_pattern: str
) -> FixEffectiveness:
    """
    Compare before/after analysis to measure fix effectiveness.
    """
    # Find target pattern counts
    before_pattern = next(
        (p for p in before_analysis.patterns if p["pattern"] == target_pattern),
        {"count": 0}
    )
    after_pattern = next(
        (p for p in after_analysis.patterns if p["pattern"] == target_pattern),
        {"count": 0}
    )
    
    # Check for new patterns that weren't significant before
    before_patterns = {p["pattern"] for p in before_analysis.patterns}
    after_patterns = {p["pattern"] for p in after_analysis.patterns}
    new_patterns = list(after_patterns - before_patterns)
    
    return FixEffectiveness(
        fix_name=fix_name,
        fix_date=datetime.now().isoformat(),
        before_failure_rate=before_analysis.failure_rate,
        before_pattern_count=before_pattern["count"],
        after_failure_rate=after_analysis.failure_rate,
        after_pattern_count=after_pattern["count"],
        failure_rate_change=after_analysis.failure_rate - before_analysis.failure_rate,
        pattern_reduction=(
            (before_pattern["count"] - after_pattern["count"]) / before_pattern["count"]
            if before_pattern["count"] > 0 else 0
        ),
        new_failure_patterns=new_patterns
    )
```

### Tracking Dashboard Metrics

```python
# Metrics to track per fix
fix_metrics = {
    "hybrid_search_added": {
        "target_pattern": "error_code_queries",
        "before_count": 28,
        "after_count": 3,
        "reduction": "89%",
        "regressions": None,
        "deploy_date": "2025-03-01"
    },
    "date_boosting_added": {
        "target_pattern": "temporal_queries",
        "before_count": 12,
        "after_count": 2,
        "reduction": "83%",
        "regressions": None,
        "deploy_date": "2025-03-05"
    }
}
```

---

## Key Takeaways

1. **Patterns > individual failures** — Don't fix one query at a time. Find what failing queries have in common, fix the root cause, solve dozens at once.
    
2. **Aggregate first, then detect** — Group failures by type, query features, time. Patterns emerge from aggregation.
    
3. **Common patterns have known fixes** — Error codes → BM25. Temporal → date boosting. Multi-hop → query decomposition. Lost-in-middle → context reordering. Learn the catalog.
    
4. **Prioritize by impact × frequency / effort** — Fix high-frequency, high-impact, low-effort patterns first. That's your 80/20.
    
5. **Feature correlation finds hidden patterns** — "Queries with numbers fail 45% more often" reveals patterns you wouldn't see manually.
    
6. **Clustering finds natural groupings** — Let the data tell you what patterns exist, beyond your predefined detectors.
    
7. **Validate fixes on the original failures** — Re-run the pattern's queries after the fix. Measure the fix rate. Check for regressions.
    
8. **Track effectiveness over time** — Before/after analysis proves the fix worked. New patterns appearing signals regressions.
    
9. **3-5 patterns explain most failures** — You don't need to detect 50 patterns. Find the big ones, fix them, move on.