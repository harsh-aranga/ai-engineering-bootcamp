# Dead Letter Queues and Async Error Recovery

## The Problem with Sync-Only Error Handling

Everything we've covered so far—retries, circuit breakers, fallbacks—happens synchronously while the user waits. This works for most failures, but some scenarios break the model:

**User Experience Problem:**

```
User sends query
→ Retry 1 (2s wait)
→ Retry 2 (4s wait)
→ Retry 3 (8s wait)
→ Fallback to degraded response
Total: 14+ seconds of user staring at spinner
```

Even with fallbacks, those 14 seconds feel like an eternity. And if the degraded response isn't acceptable, you've wasted everyone's time.

**Investigation Problem:**

Some failures need human investigation:

- Why did retrieval return irrelevant results?
- Why did the LLM refuse to answer?
- Why did the same query fail 50 times today?

Dropping these failures means losing the evidence. You can't debug what you can't see.

**Timing Problem:**

Some failures are recoverable—just not _right now_:

- Rate limit will reset in 60 seconds
- API is down but will be back in 10 minutes
- Embedding model is being updated, try in 5 minutes

Making the user wait isn't viable. Dropping the request wastes their effort.

---

## The Dead Letter Queue Pattern

A Dead Letter Queue (DLQ) is a holding area for failed requests that can't be processed immediately but shouldn't be dropped.

```
Normal Flow:
Request → Process → Success → Response

With DLQ:
Request → Process → Failure → DLQ → Later Processing → Success/Abandon
                         ↓
                   Immediate Fallback Response to User
```

The key insight: **decouple the user response from the full processing**.

1. User gets an immediate response (fallback or "we'll get back to you")
2. Failed request goes to DLQ for later handling
3. Background process retries or escalates for investigation

### When DLQ Makes Sense

|Scenario|Use DLQ?|Why|
|---|---|---|
|User needs answer now|No|Fallback immediately|
|Background batch job|Yes|No user waiting|
|High-value query worth retrying|Yes|Don't lose the request|
|Repeated failure pattern|Yes|Needs investigation|
|Rate limit hit|Yes|Will succeed later|
|Auth failure|No|Won't succeed without intervention|

---

## What to Capture in DLQ

A DLQ entry must contain everything needed to:

1. Reproduce the failure
2. Debug the cause
3. Reprocess successfully

### DLQ Entry Structure

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import traceback
import json


@dataclass
class DLQEntry:
    """A failed request stored for later processing."""
    
    # Identity
    id: str                          # Unique identifier
    created_at: datetime             # When failure occurred
    
    # Original request
    query: str                       # User's original query
    user_id: Optional[str]           # Who made the request
    session_id: Optional[str]        # Session context
    request_metadata: Dict[str, Any] # Headers, source, etc.
    
    # Error details
    error_type: str                  # Exception class name
    error_message: str               # Exception message
    stack_trace: str                 # Full traceback
    
    # Pipeline state
    pipeline_stage: str              # Where it failed
    completed_stages: List[str]      # What succeeded before failure
    partial_results: Dict[str, Any]  # Any intermediate results
    
    # Retry tracking
    attempt_count: int = 1           # How many times we've tried
    last_attempt_at: datetime = None # When we last tried
    next_retry_at: datetime = None   # Scheduled retry time
    
    # Status
    status: str = "pending"          # pending, processing, succeeded, abandoned
    resolution: Optional[str] = None # How it was resolved
    resolved_at: datetime = None     # When resolved
    
    # Context for debugging
    environment: Dict[str, Any] = field(default_factory=dict)  # Versions, config
    
    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "query": self.query,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "request_metadata": self.request_metadata,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "pipeline_stage": self.pipeline_stage,
            "completed_stages": self.completed_stages,
            "partial_results": self.partial_results,
            "attempt_count": self.attempt_count,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "status": self.status,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "environment": self.environment
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DLQEntry":
        """Deserialize from storage."""
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            query=data["query"],
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            request_metadata=data.get("request_metadata", {}),
            error_type=data["error_type"],
            error_message=data["error_message"],
            stack_trace=data["stack_trace"],
            pipeline_stage=data["pipeline_stage"],
            completed_stages=data.get("completed_stages", []),
            partial_results=data.get("partial_results", {}),
            attempt_count=data.get("attempt_count", 1),
            last_attempt_at=datetime.fromisoformat(data["last_attempt_at"]) if data.get("last_attempt_at") else None,
            next_retry_at=datetime.fromisoformat(data["next_retry_at"]) if data.get("next_retry_at") else None,
            status=data.get("status", "pending"),
            resolution=data.get("resolution"),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            environment=data.get("environment", {})
        )


def create_dlq_entry(
    query: str,
    error: Exception,
    pipeline_stage: str,
    completed_stages: List[str] = None,
    partial_results: Dict[str, Any] = None,
    user_id: str = None,
    session_id: str = None,
    request_metadata: Dict[str, Any] = None
) -> DLQEntry:
    """Create a DLQ entry from a failed request."""
    import uuid
    
    return DLQEntry(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        query=query,
        user_id=user_id,
        session_id=session_id,
        request_metadata=request_metadata or {},
        error_type=type(error).__name__,
        error_message=str(error),
        stack_trace=traceback.format_exc(),
        pipeline_stage=pipeline_stage,
        completed_stages=completed_stages or [],
        partial_results=partial_results or {},
        environment={
            "python_version": "3.11",  # Capture actual versions
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

### Capturing Pipeline State

When a failure occurs mid-pipeline, capture what succeeded:

```python
class PipelineContext:
    """Tracks pipeline execution for DLQ capture."""
    
    def __init__(self):
        self.completed_stages: List[str] = []
        self.partial_results: Dict[str, Any] = {}
        self.current_stage: Optional[str] = None
    
    def enter_stage(self, stage_name: str):
        """Mark entering a pipeline stage."""
        self.current_stage = stage_name
    
    def complete_stage(self, stage_name: str, result: Any = None):
        """Mark stage as completed with optional result."""
        self.completed_stages.append(stage_name)
        if result is not None:
            # Store serializable summary, not full objects
            self.partial_results[stage_name] = self._summarize(result)
        self.current_stage = None
    
    def _summarize(self, result: Any) -> Any:
        """Create serializable summary of result."""
        if hasattr(result, '__len__'):
            return {"type": type(result).__name__, "length": len(result)}
        return {"type": type(result).__name__}
    
    def get_failure_context(self) -> dict:
        """Get context when failure occurs."""
        return {
            "current_stage": self.current_stage,
            "completed_stages": self.completed_stages.copy(),
            "partial_results": self.partial_results.copy()
        }


def execute_pipeline_with_dlq(query: str, dlq: "DeadLetterQueue") -> dict:
    """Execute pipeline with DLQ capture on failure."""
    context = PipelineContext()
    
    try:
        # Embedding stage
        context.enter_stage("embedding")
        embedding = embed_query(query)
        context.complete_stage("embedding", embedding)
        
        # Retrieval stage
        context.enter_stage("retrieval")
        documents = retrieve(embedding)
        context.complete_stage("retrieval", documents)
        
        # Generation stage
        context.enter_stage("generation")
        response = generate(query, documents)
        context.complete_stage("generation")
        
        return {"success": True, "response": response}
        
    except Exception as e:
        # Capture to DLQ
        failure_context = context.get_failure_context()
        entry = create_dlq_entry(
            query=query,
            error=e,
            pipeline_stage=failure_context["current_stage"],
            completed_stages=failure_context["completed_stages"],
            partial_results=failure_context["partial_results"]
        )
        dlq.enqueue(entry)
        
        # Return fallback
        return {
            "success": False,
            "dlq_id": entry.id,
            "response": "We're processing your request. You'll be notified when ready."
        }
```

---

## DLQ Processing Strategies

Once items are in the DLQ, how do you handle them?

### Strategy 1: Manual Review

Human investigates, diagnoses, and decides what to do.

**When to use:**

- Novel error types
- Potential bugs in your system
- Security-related failures
- High-value requests worth individual attention

```python
class ManualReviewProcessor:
    """Presents DLQ items for human review."""
    
    def __init__(self, dlq: "DeadLetterQueue", notification_service):
        self.dlq = dlq
        self.notifications = notification_service
    
    def flag_for_review(self, entry: DLQEntry, reason: str):
        """Flag entry for manual review."""
        entry.status = "needs_review"
        entry.resolution = f"Flagged: {reason}"
        self.dlq.update(entry)
        
        # Notify on-call engineer
        self.notifications.send_alert(
            channel="dlq-review",
            message=f"DLQ item needs review: {entry.id}",
            details={
                "error_type": entry.error_type,
                "pipeline_stage": entry.pipeline_stage,
                "query_preview": entry.query[:100],
                "reason": reason
            }
        )
    
    def resolve_manually(
        self, 
        entry_id: str, 
        resolution: str,
        reprocess: bool = False
    ):
        """Resolve an entry after manual review."""
        entry = self.dlq.get(entry_id)
        
        if reprocess:
            # Attempt to process again
            result = self._reprocess(entry)
            if result["success"]:
                entry.status = "succeeded"
                entry.resolution = f"Manual reprocess: {resolution}"
            else:
                entry.status = "abandoned"
                entry.resolution = f"Reprocess failed: {resolution}"
        else:
            entry.status = "abandoned"
            entry.resolution = resolution
        
        entry.resolved_at = datetime.utcnow()
        self.dlq.update(entry)
        
        # Notify user if they're waiting
        if entry.user_id:
            self._notify_user(entry)
```

### Strategy 2: Scheduled Retry

Automatically retry all DLQ items after a cooldown period.

**When to use:**

- Transient failures (rate limits, temporary outages)
- Batch processing where timing isn't critical
- Known recovery patterns

```python
import time
from datetime import datetime, timedelta


class ScheduledRetryProcessor:
    """Automatically retries DLQ items on a schedule."""
    
    def __init__(
        self,
        dlq: "DeadLetterQueue",
        pipeline,
        max_retries: int = 3,
        base_delay_minutes: int = 5,
        max_delay_minutes: int = 60
    ):
        self.dlq = dlq
        self.pipeline = pipeline
        self.max_retries = max_retries
        self.base_delay = base_delay_minutes
        self.max_delay = max_delay_minutes
    
    def calculate_next_retry(self, entry: DLQEntry) -> datetime:
        """Calculate next retry time with exponential backoff."""
        delay_minutes = min(
            self.base_delay * (2 ** entry.attempt_count),
            self.max_delay
        )
        return datetime.utcnow() + timedelta(minutes=delay_minutes)
    
    def process_due_items(self):
        """Process all items due for retry."""
        due_items = self.dlq.get_due_for_retry()
        
        for entry in due_items:
            self._process_item(entry)
    
    def _process_item(self, entry: DLQEntry):
        """Attempt to reprocess a single item."""
        if entry.attempt_count >= self.max_retries:
            self._abandon(entry, "Max retries exceeded")
            return
        
        entry.status = "processing"
        entry.attempt_count += 1
        entry.last_attempt_at = datetime.utcnow()
        self.dlq.update(entry)
        
        try:
            result = self.pipeline.execute(entry.query)
            
            if result["success"]:
                entry.status = "succeeded"
                entry.resolution = f"Succeeded on attempt {entry.attempt_count}"
                entry.resolved_at = datetime.utcnow()
                
                # Deliver result to user if applicable
                self._deliver_result(entry, result)
            else:
                # Still failing, schedule next retry
                entry.status = "pending"
                entry.next_retry_at = self.calculate_next_retry(entry)
            
            self.dlq.update(entry)
            
        except Exception as e:
            # Update with new error info
            entry.status = "pending"
            entry.error_message = str(e)
            entry.next_retry_at = self.calculate_next_retry(entry)
            self.dlq.update(entry)
    
    def _abandon(self, entry: DLQEntry, reason: str):
        """Abandon item after max retries."""
        entry.status = "abandoned"
        entry.resolution = reason
        entry.resolved_at = datetime.utcnow()
        self.dlq.update(entry)
        
        # Notify user
        self._notify_user_abandoned(entry)
    
    def _deliver_result(self, entry: DLQEntry, result: dict):
        """Deliver successful result to user."""
        # Implementation depends on your notification system
        pass
    
    def _notify_user_abandoned(self, entry: DLQEntry):
        """Notify user their request couldn't be processed."""
        # Implementation depends on your notification system
        pass
```

### Strategy 3: Conditional Retry

Retry only when specific conditions are met.

**When to use:**

- Failures tied to specific services (wait for circuit to close)
- Rate limits (wait for reset)
- Scheduled maintenance windows

```python
class ConditionalRetryProcessor:
    """Retries DLQ items based on conditions."""
    
    def __init__(
        self,
        dlq: "DeadLetterQueue",
        pipeline,
        circuit_breakers: Dict[str, "CircuitBreaker"]
    ):
        self.dlq = dlq
        self.pipeline = pipeline
        self.circuits = circuit_breakers
    
    def process_if_conditions_met(self):
        """Process items whose retry conditions are satisfied."""
        pending_items = self.dlq.get_pending()
        
        for entry in pending_items:
            if self._check_conditions(entry):
                self._process_item(entry)
    
    def _check_conditions(self, entry: DLQEntry) -> bool:
        """Check if conditions for retry are met."""
        
        # Check 1: Has enough time passed?
        if entry.next_retry_at and datetime.utcnow() < entry.next_retry_at:
            return False
        
        # Check 2: Is the relevant circuit breaker closed?
        stage = entry.pipeline_stage
        if stage in self.circuits:
            circuit = self.circuits[stage]
            if circuit.state != CircuitState.CLOSED:
                return False
        
        # Check 3: Error-specific conditions
        if entry.error_type == "RateLimitError":
            # Check if rate limit window has passed
            if not self._rate_limit_reset(entry):
                return False
        
        return True
    
    def _rate_limit_reset(self, entry: DLQEntry) -> bool:
        """Check if rate limit has likely reset."""
        # Most rate limits reset within 60 seconds
        time_since_error = datetime.utcnow() - entry.last_attempt_at
        return time_since_error.total_seconds() > 60
    
    def _process_item(self, entry: DLQEntry):
        """Process item (same as scheduled retry)."""
        # ... same implementation as ScheduledRetryProcessor
        pass
```

### Strategy 4: Abandon with Notification

Some items can't or shouldn't be retried. Notify and move on.

**When to use:**

- Non-retryable errors (auth failures, invalid input)
- Items too old to be relevant
- User has since gotten their answer another way

```python
class AbandonmentProcessor:
    """Handles items that should be abandoned."""
    
    def __init__(
        self,
        dlq: "DeadLetterQueue",
        notification_service,
        max_age_hours: int = 24
    ):
        self.dlq = dlq
        self.notifications = notification_service
        self.max_age_hours = max_age_hours
    
    def process_abandonments(self):
        """Identify and abandon items that can't/shouldn't be retried."""
        pending_items = self.dlq.get_pending()
        
        for entry in pending_items:
            abandon_reason = self._should_abandon(entry)
            if abandon_reason:
                self._abandon(entry, abandon_reason)
    
    def _should_abandon(self, entry: DLQEntry) -> Optional[str]:
        """Check if item should be abandoned. Returns reason or None."""
        
        # Too old
        age = datetime.utcnow() - entry.created_at
        if age.total_seconds() > self.max_age_hours * 3600:
            return f"Exceeded max age ({self.max_age_hours} hours)"
        
        # Non-retryable error types
        non_retryable_errors = {
            "AuthenticationError": "Authentication failure - requires user action",
            "InvalidRequestError": "Invalid request - cannot retry without changes",
            "ContentFilterError": "Content policy violation",
            "ContextLengthExceeded": "Request too large for processing"
        }
        
        if entry.error_type in non_retryable_errors:
            return non_retryable_errors[entry.error_type]
        
        # Max retries exceeded
        if entry.attempt_count >= 5:
            return "Maximum retry attempts exceeded"
        
        return None
    
    def _abandon(self, entry: DLQEntry, reason: str):
        """Abandon entry and notify user."""
        entry.status = "abandoned"
        entry.resolution = reason
        entry.resolved_at = datetime.utcnow()
        self.dlq.update(entry)
        
        # Notify user with helpful message
        if entry.user_id:
            self.notifications.send_to_user(
                user_id=entry.user_id,
                subject="Unable to process your request",
                message=self._build_abandonment_message(entry, reason)
            )
    
    def _build_abandonment_message(self, entry: DLQEntry, reason: str) -> str:
        """Build user-friendly abandonment notification."""
        return f"""We were unable to process your request from {entry.created_at.strftime('%Y-%m-%d %H:%M')}.

Your question: "{entry.query[:200]}..."

Reason: {reason}

What you can do:
- Try submitting your question again
- If the problem persists, contact support

We apologize for the inconvenience.
"""
```

---

## Async Recovery Patterns

For long-running or unreliable operations, decouple the user response from processing.

### Pattern: Accept → Process Async → Notify

```
User Request
     │
     ▼
┌─────────────────────────────────────┐
│ Accept immediately                   │
│ Return: "Request received, ID: X"    │
│ Store in job queue                   │
└─────────────────────────────────────┘
     │
     ▼ (async)
┌─────────────────────────────────────┐
│ Process in background                │
│ Retry failures automatically         │
│ DLQ if all retries fail             │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────┐
│ Notify user when complete            │
│ Options: webhook, email, poll        │
└─────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from enum import Enum
import uuid
from datetime import datetime
from typing import Optional, Callable


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AsyncJob:
    """Represents an async processing job."""
    id: str
    query: str
    user_id: str
    status: JobStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    
    # Notification preferences
    webhook_url: Optional[str] = None
    notification_email: Optional[str] = None


class AsyncRequestHandler:
    """
    Handles requests asynchronously.
    
    Usage:
        handler = AsyncRequestHandler(job_queue, pipeline, notifier)
        
        # Accept request
        job_id = handler.accept_request(
            query="Complex research question",
            user_id="user_123",
            webhook_url="https://client.com/webhook"
        )
        
        # Returns immediately with job ID
        # Processing happens in background
        # User notified when complete
    """
    
    def __init__(
        self,
        job_store: "JobStore",
        pipeline,
        notifier: "NotificationService",
        dlq: "DeadLetterQueue"
    ):
        self.jobs = job_store
        self.pipeline = pipeline
        self.notifier = notifier
        self.dlq = dlq
    
    def accept_request(
        self,
        query: str,
        user_id: str,
        webhook_url: str = None,
        notification_email: str = None
    ) -> str:
        """
        Accept request for async processing.
        Returns job ID immediately.
        """
        job = AsyncJob(
            id=str(uuid.uuid4()),
            query=query,
            user_id=user_id,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            webhook_url=webhook_url,
            notification_email=notification_email
        )
        
        self.jobs.save(job)
        
        # Enqueue for background processing
        self._enqueue_for_processing(job.id)
        
        return job.id
    
    def get_status(self, job_id: str) -> dict:
        """Get current job status (for polling)."""
        job = self.jobs.get(job_id)
        if not job:
            return {"error": "Job not found"}
        
        return {
            "id": job.id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result if job.status == JobStatus.COMPLETED else None,
            "error": job.error if job.status == JobStatus.FAILED else None
        }
    
    def process_job(self, job_id: str):
        """Process a job (called by background worker)."""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        job.status = JobStatus.PROCESSING
        self.jobs.save(job)
        
        try:
            result = self.pipeline.execute(job.query)
            
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.utcnow()
            self.jobs.save(job)
            
            # Notify user
            self._notify_completion(job)
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            self.jobs.save(job)
            
            # Send to DLQ for potential retry
            dlq_entry = create_dlq_entry(
                query=job.query,
                error=e,
                pipeline_stage="async_processing",
                user_id=job.user_id
            )
            self.dlq.enqueue(dlq_entry)
            
            # Notify user of failure
            self._notify_failure(job)
    
    def _enqueue_for_processing(self, job_id: str):
        """Add job to processing queue."""
        # Implementation depends on your queue system
        # Could be Redis, Celery, SQS, etc.
        pass
    
    def _notify_completion(self, job: AsyncJob):
        """Notify user of successful completion."""
        if job.webhook_url:
            self.notifier.send_webhook(
                url=job.webhook_url,
                payload={
                    "job_id": job.id,
                    "status": "completed",
                    "result": job.result
                }
            )
        
        if job.notification_email:
            self.notifier.send_email(
                to=job.notification_email,
                subject="Your request has been processed",
                body=self._format_completion_email(job)
            )
    
    def _notify_failure(self, job: AsyncJob):
        """Notify user of failure."""
        if job.webhook_url:
            self.notifier.send_webhook(
                url=job.webhook_url,
                payload={
                    "job_id": job.id,
                    "status": "failed",
                    "error": job.error
                }
            )
        
        if job.notification_email:
            self.notifier.send_email(
                to=job.notification_email,
                subject="We couldn't process your request",
                body=self._format_failure_email(job)
            )
```

### User-Facing API

```python
# API endpoint for accepting async requests
@app.post("/api/query/async")
def submit_async_query(request: QueryRequest):
    """Submit a query for async processing."""
    job_id = async_handler.accept_request(
        query=request.query,
        user_id=request.user_id,
        webhook_url=request.webhook_url,
        notification_email=request.notification_email
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "status_url": f"/api/query/status/{job_id}",
        "message": "Your request is being processed. You'll be notified when complete."
    }


# API endpoint for polling status
@app.get("/api/query/status/{job_id}")
def get_query_status(job_id: str):
    """Get status of an async query."""
    return async_handler.get_status(job_id)
```

---

## Implementing DLQ Storage

### Simple: Database Table

Good for getting started. Uses your existing database.

```python
import sqlite3
import json
from datetime import datetime
from typing import List, Optional


class DatabaseDLQ:
    """SQLite-based DLQ for simplicity."""
    
    def __init__(self, db_path: str = "dlq.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dlq (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    next_retry_at TIMESTAMP,
                    INDEX idx_status (status),
                    INDEX idx_next_retry (next_retry_at)
                )
            """)
    
    def enqueue(self, entry: DLQEntry):
        """Add entry to DLQ."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO dlq (id, data, status, created_at, next_retry_at) VALUES (?, ?, ?, ?, ?)",
                (
                    entry.id,
                    json.dumps(entry.to_dict()),
                    entry.status,
                    entry.created_at.isoformat(),
                    entry.next_retry_at.isoformat() if entry.next_retry_at else None
                )
            )
    
    def get(self, entry_id: str) -> Optional[DLQEntry]:
        """Get entry by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data FROM dlq WHERE id = ?",
                (entry_id,)
            ).fetchone()
            
            if row:
                return DLQEntry.from_dict(json.loads(row[0]))
            return None
    
    def update(self, entry: DLQEntry):
        """Update existing entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE dlq SET data = ?, status = ?, next_retry_at = ? WHERE id = ?",
                (
                    json.dumps(entry.to_dict()),
                    entry.status,
                    entry.next_retry_at.isoformat() if entry.next_retry_at else None,
                    entry.id
                )
            )
    
    def get_pending(self) -> List[DLQEntry]:
        """Get all pending entries."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT data FROM dlq WHERE status = 'pending'"
            ).fetchall()
            
            return [DLQEntry.from_dict(json.loads(row[0])) for row in rows]
    
    def get_due_for_retry(self) -> List[DLQEntry]:
        """Get entries due for retry."""
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT data FROM dlq 
                   WHERE status = 'pending' 
                   AND (next_retry_at IS NULL OR next_retry_at <= ?)""",
                (now,)
            ).fetchall()
            
            return [DLQEntry.from_dict(json.loads(row[0])) for row in rows]
    
    def count_by_status(self) -> dict:
        """Get counts by status."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM dlq GROUP BY status"
            ).fetchall()
            
            return {row[0]: row[1] for row in rows}
```

### Production: Redis Queue

Better for production. Fast, supports TTL, distributed.

```python
import redis
import json
from datetime import datetime, timedelta
from typing import List, Optional


class RedisDLQ:
    """Redis-based DLQ for production use."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "dlq:",
        default_ttl_days: int = 7
    ):
        self.redis = redis.from_url(redis_url)
        self.prefix = key_prefix
        self.ttl_seconds = default_ttl_days * 24 * 3600
        
        # Keys
        self.entries_hash = f"{self.prefix}entries"      # Hash of all entries
        self.pending_set = f"{self.prefix}pending"       # Set of pending IDs
        self.retry_zset = f"{self.prefix}retry_queue"    # Sorted set by retry time
    
    def enqueue(self, entry: DLQEntry):
        """Add entry to DLQ."""
        entry_data = json.dumps(entry.to_dict())
        
        # Use pipeline for atomicity
        pipe = self.redis.pipeline()
        
        # Store entry data
        pipe.hset(self.entries_hash, entry.id, entry_data)
        
        # Add to pending set
        pipe.sadd(self.pending_set, entry.id)
        
        # Add to retry queue with score = retry timestamp
        if entry.next_retry_at:
            retry_score = entry.next_retry_at.timestamp()
        else:
            retry_score = datetime.utcnow().timestamp()
        pipe.zadd(self.retry_zset, {entry.id: retry_score})
        
        # Set TTL on entry
        pipe.expire(self.entries_hash, self.ttl_seconds)
        
        pipe.execute()
    
    def get(self, entry_id: str) -> Optional[DLQEntry]:
        """Get entry by ID."""
        data = self.redis.hget(self.entries_hash, entry_id)
        if data:
            return DLQEntry.from_dict(json.loads(data))
        return None
    
    def update(self, entry: DLQEntry):
        """Update existing entry."""
        entry_data = json.dumps(entry.to_dict())
        
        pipe = self.redis.pipeline()
        
        # Update entry data
        pipe.hset(self.entries_hash, entry.id, entry_data)
        
        # Update status sets
        if entry.status == "pending":
            pipe.sadd(self.pending_set, entry.id)
            if entry.next_retry_at:
                pipe.zadd(self.retry_zset, {entry.id: entry.next_retry_at.timestamp()})
        else:
            pipe.srem(self.pending_set, entry.id)
            pipe.zrem(self.retry_zset, entry.id)
        
        pipe.execute()
    
    def get_due_for_retry(self, limit: int = 100) -> List[DLQEntry]:
        """Get entries due for retry."""
        now = datetime.utcnow().timestamp()
        
        # Get IDs with score <= now
        entry_ids = self.redis.zrangebyscore(
            self.retry_zset,
            min="-inf",
            max=now,
            start=0,
            num=limit
        )
        
        entries = []
        for entry_id in entry_ids:
            entry = self.get(entry_id.decode() if isinstance(entry_id, bytes) else entry_id)
            if entry:
                entries.append(entry)
        
        return entries
    
    def get_stats(self) -> dict:
        """Get DLQ statistics."""
        pending_count = self.redis.scard(self.pending_set)
        retry_queue_size = self.redis.zcard(self.retry_zset)
        
        # Get oldest item age
        oldest = self.redis.zrange(self.retry_zset, 0, 0, withscores=True)
        oldest_age = None
        if oldest:
            oldest_timestamp = oldest[0][1]
            oldest_age = datetime.utcnow().timestamp() - oldest_timestamp
        
        return {
            "pending_count": pending_count,
            "retry_queue_size": retry_queue_size,
            "oldest_item_age_seconds": oldest_age
        }
```

---

## DLQ Monitoring

A DLQ that no one watches is useless. Monitor aggressively.

### Key Metrics

|Metric|Description|Alert Threshold|
|---|---|---|
|`dlq_depth`|Number of pending items|Growing trend|
|`dlq_oldest_age`|Age of oldest item|> 1 hour|
|`dlq_processing_rate`|Items processed per minute|Near zero|
|`dlq_success_rate`|% of retries that succeed|< 50%|
|`dlq_abandonment_rate`|% of items abandoned|Spike|

### Monitoring Implementation

```python
import time
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class DLQMetrics:
    """Snapshot of DLQ health."""
    timestamp: datetime
    pending_count: int
    processing_count: int
    succeeded_last_hour: int
    failed_last_hour: int
    abandoned_last_hour: int
    oldest_item_age_seconds: float
    avg_retry_count: float


class DLQMonitor:
    """Monitors DLQ health and alerts on problems."""
    
    def __init__(
        self,
        dlq: "DeadLetterQueue",
        alerter: "AlertService",
        depth_threshold: int = 100,
        age_threshold_seconds: int = 3600,
        check_interval_seconds: int = 60
    ):
        self.dlq = dlq
        self.alerter = alerter
        self.depth_threshold = depth_threshold
        self.age_threshold = age_threshold_seconds
        self.check_interval = check_interval_seconds
        
        self._previous_depth = 0
        self._depth_trend = []  # Track recent depths
    
    def check_health(self) -> DLQMetrics:
        """Check DLQ health and alert if needed."""
        stats = self.dlq.get_stats()
        metrics = self._compute_metrics(stats)
        
        # Check for problems
        alerts = []
        
        # Queue depth growing
        if metrics.pending_count > self.depth_threshold:
            alerts.append({
                "severity": "warning",
                "message": f"DLQ depth is {metrics.pending_count} (threshold: {self.depth_threshold})"
            })
        
        # Queue depth growing rapidly
        if self._is_depth_growing_rapidly(metrics.pending_count):
            alerts.append({
                "severity": "critical",
                "message": f"DLQ depth growing rapidly: {self._previous_depth} → {metrics.pending_count}"
            })
        
        # Old items
        if metrics.oldest_item_age_seconds > self.age_threshold:
            age_hours = metrics.oldest_item_age_seconds / 3600
            alerts.append({
                "severity": "warning",
                "message": f"Oldest DLQ item is {age_hours:.1f} hours old"
            })
        
        # Low success rate
        total_attempts = metrics.succeeded_last_hour + metrics.failed_last_hour
        if total_attempts > 10:  # Enough data to judge
            success_rate = metrics.succeeded_last_hour / total_attempts
            if success_rate < 0.5:
                alerts.append({
                    "severity": "warning",
                    "message": f"DLQ success rate is {success_rate:.0%}"
                })
        
        # Send alerts
        for alert in alerts:
            self.alerter.send(
                severity=alert["severity"],
                title="DLQ Health Issue",
                message=alert["message"],
                metrics=metrics.__dict__
            )
        
        # Track for trend analysis
        self._previous_depth = metrics.pending_count
        self._depth_trend.append(metrics.pending_count)
        if len(self._depth_trend) > 10:
            self._depth_trend.pop(0)
        
        return metrics
    
    def _compute_metrics(self, stats: dict) -> DLQMetrics:
        """Compute metrics from raw stats."""
        return DLQMetrics(
            timestamp=datetime.utcnow(),
            pending_count=stats.get("pending_count", 0),
            processing_count=stats.get("processing_count", 0),
            succeeded_last_hour=stats.get("succeeded_last_hour", 0),
            failed_last_hour=stats.get("failed_last_hour", 0),
            abandoned_last_hour=stats.get("abandoned_last_hour", 0),
            oldest_item_age_seconds=stats.get("oldest_item_age_seconds", 0),
            avg_retry_count=stats.get("avg_retry_count", 0)
        )
    
    def _is_depth_growing_rapidly(self, current_depth: int) -> bool:
        """Check if depth is growing rapidly."""
        if len(self._depth_trend) < 3:
            return False
        
        # Check if consistently growing
        recent = self._depth_trend[-3:]
        return all(recent[i] < recent[i+1] for i in range(len(recent)-1))


# Health endpoint for dashboards
@app.get("/health/dlq")
def dlq_health():
    """DLQ health check endpoint."""
    metrics = dlq_monitor.check_health()
    
    healthy = (
        metrics.pending_count < 100 and
        metrics.oldest_item_age_seconds < 3600
    )
    
    return {
        "healthy": healthy,
        "metrics": {
            "pending": metrics.pending_count,
            "oldest_age_minutes": metrics.oldest_item_age_seconds / 60,
            "success_rate_last_hour": (
                metrics.succeeded_last_hour / 
                max(1, metrics.succeeded_last_hour + metrics.failed_last_hour)
            )
        },
        "timestamp": metrics.timestamp.isoformat()
    }
```

---

## When to Use DLQ vs Immediate Fallback

### Decision Framework

```
User needs response NOW?
├── Yes → Immediate fallback, optionally DLQ for analysis
└── No → Is it worth retrying later?
         ├── Yes → DLQ for retry
         └── No → Drop (maybe log for analytics)

Error is recoverable with time?
├── Yes (rate limit, temp outage) → DLQ for scheduled retry
├── Maybe (unknown error) → DLQ for investigation
└── No (auth failure, invalid input) → Don't DLQ, fix the cause
```

### Hybrid Pattern: Fallback + DLQ

Best of both worlds: user gets immediate response, system learns from failures.

```python
def handle_query_hybrid(query: str, user_id: str) -> dict:
    """
    Hybrid approach:
    1. Try full pipeline
    2. If fails, give immediate fallback
    3. Also send to DLQ for investigation/retry
    """
    
    try:
        result = full_pipeline.execute(query)
        return {
            "response": result,
            "quality": "full"
        }
        
    except Exception as e:
        # Send to DLQ for later analysis/retry
        dlq_entry = create_dlq_entry(
            query=query,
            error=e,
            pipeline_stage=get_failed_stage(),
            user_id=user_id
        )
        dlq.enqueue(dlq_entry)
        
        # Give user immediate fallback
        fallback_response = fallback_handler.execute(query)
        
        return {
            "response": fallback_response.content,
            "quality": fallback_response.level_used,
            "note": "We're also processing this in the background for a more complete answer.",
            "job_id": dlq_entry.id  # User can check back later
        }
```

---

## Summary

**The problem:**

- Sync-only error handling makes users wait
- Some failures need investigation
- Some failures are recoverable later

**Dead Letter Queue:**

- Failed requests go to queue instead of being dropped
- Contains full context for reproduction and debugging
- Processed later: manual review, scheduled retry, conditional retry, or abandon

**DLQ entry must capture:**

- Original request (query, user_id, metadata)
- Error details (type, message, stack trace)
- Pipeline state (what succeeded, what failed)
- Retry tracking (attempt count, next retry time)

**Processing strategies:**

- Manual review: human investigates and resolves
- Scheduled retry: automatic retry after cooldown
- Conditional retry: retry when conditions met (circuit closed, rate limit reset)
- Abandon with notification: inform user and move on

**Async recovery:**

- Accept immediately, process in background
- Notify when complete (webhook, email, poll)
- DLQ as backstop for background failures

**Monitoring:**

- Track queue depth, age of oldest item, success rate
- Alert on growth trends
- Dashboard showing DLQ health

**When to use:**

- DLQ: background tasks, recoverable failures, investigation needed
- Immediate fallback: user needs response now
- Hybrid: both (user gets fallback, system retries in background)

---

## Connections

- **Note 1**: Failure taxonomy determines which errors go to DLQ
- **Note 2**: Retries happen before DLQ (DLQ is after retries exhausted)
- **Note 3**: Circuit breaker state can trigger conditional retry in DLQ
- **Note 4**: Fallback provides immediate response while DLQ handles background retry
- **Week 8**: LLMOps will integrate DLQ metrics into broader observability