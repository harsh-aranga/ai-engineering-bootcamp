## OpenAI Responses API — Streaming Event Lifecycle (with **Why each event exists**)

### Object hierarchy

* **Response**

  * **Output Item**

    * **Content Part**

      * **Delta**

> The API streams **structure first, data second**. Each “added” / “done” event exists so clients never have to infer structure from tokens.

---

## Response-level events

### `response.created`

**Why it exists**

* Confirms request acceptance before any generation
* Assigns a stable `response.id`
* Enables cancellation, chaining (`previous_response_id`), and correlation

---

### `response.in_progress`

**Why it exists**

* Explicit signal that the model is actively generating
* Allows UIs / agents to show “working” state
* Distinguishes silence vs stalled vs completed

---

### `response.completed`

**Why it exists**

* Single, unambiguous commit point
* Guarantees all outputs, parts, and usage stats are final

---

### `response.failed`

**Why it exists**

* Terminal error signal distinct from transport failure
* Allows partial outputs to be discarded or marked invalid

---

### `response.incomplete`

**Why it exists**

* Separates “partial but usable” from “hard failure”
* Supports cases like max tokens, user cancel, safety stop

---

## Output item lifecycle

### `response.output_item.added`

**Why it exists**

* Declares **what kind of thing** is being produced before content arrives
  (assistant message, tool call, image, web search, etc.)
* Enables clients to:

  * Allocate buffers
  * Route handling logic
  * Render placeholders (chat bubble, tool panel)

Without this:

* Clients would have to guess intent from early tokens (brittle)

---

### `response.output_item.done`

**Why it exists**

* Explicitly closes an output item
* Guarantees:

  * No more parts will be attached
  * No more deltas for any part in that item
* Can fire even if the overall response is incomplete

This allows:

* Safe persistence per-item
* Partial success handling in agent workflows

---

## Content part lifecycle

### `response.content_part.added`

**Why it exists**

* Declares **how the content should be interpreted**

  * text vs refusal vs reasoning vs tool arguments
* Allows:

  * Type-safe rendering
  * Correct downstream handling (e.g., don’t render reasoning)

Without this:

* Clients would have to infer semantics from token patterns

---

### `response.content_part.done`

**Why it exists**

* Closes a single semantic unit inside an item
* Allows items to contain multiple parts safely

  * e.g., text → refusal → text
* Prevents clients from assuming a part is complete just because text paused

---

## Text streaming events

### `response.output_text.delta`

**Why it exists**

* Streams tokens with minimal latency
* Enables real-time rendering and progress feedback
* Avoids buffering the entire response

---

### `response.output_text.done`

**Why it exists**

* Signals that **this text part** is complete
* Allows:

  * Final formatting
  * Sentence-level post-processing
  * Safe handoff to storage or UI

Important:

* This does **not** mean the output item is done

---

## Tool / function call streaming

### `response.function_call_arguments.delta`

**Why it exists**

* Allows large argument payloads without blocking
* Reduces time-to-first-byte for tool-aware UIs
* Avoids forcing the model to emit valid JSON mid-generation

---

### `response.function_call_arguments.done`

**Why it exists**

* Declares JSON completeness
* Safe parse + execution boundary
* Prevents premature tool invocation

---

## Ordering and separation guarantees

**Why the separation matters**

* Items can interleave
* Parts can interleave
* Deltas can interleave

Explicit “added” and “done” events:

* Remove ambiguity
* Enable concurrency-safe consumers
* Make streaming deterministic

---

## Design principle (core insight)

The Responses API streams **a growing AST**, not a message.

Every lifecycle event exists to answer one of these questions explicitly:

1. *What is being produced?* → `output_item.added`
2. *How should it be interpreted?* → `content_part.added`
3. *Is this chunk final?* → `*.done`
4. *Is the whole response finished?* → `response.completed`

No inference. No guessing. No heuristics.

---

## Implementation takeaway

* Never infer structure from tokens
* Never finalize on silence
* Always commit on `*.done`, not on timing or buffer size
