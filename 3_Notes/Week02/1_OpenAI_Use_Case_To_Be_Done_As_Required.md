# OpenAI Responses API - Progressive Challenges

**Week 2, Days 1-2: API Patterns & Production Robustness**

**IMPORTANT:** These are CHALLENGES, not tutorials. No code provided. You implement from scratch.
These are challenges that will improve my skills do them at leisure. 

---

## Challenge 1: Basic Streaming Response Lifecycle

**Goal:** Understand the event-driven streaming model and typed events

**Scenario:** You need to build a streaming response handler. Instead of waiting for the entire response, you want to display text as it arrives (like ChatGPT does). The Responses API uses typed events, not raw text chunks.

**What to Implement:**

- Create a streaming response with `stream=True`
- Iterate over the stream and print each event type
- Print the text deltas as they arrive
- Capture the final usage stats (tokens consumed)

**What to Observe in Response:**

- First event type is `response.created`
- Multiple events with type `response.output_text.delta` containing text chunks
- Final event type is `response.completed`
- Each event has a `type` field and structured data (not raw strings)
- Completed response includes `usage` field with input/output/total tokens

**Failure Indicators:**

- You only see one event instead of multiple (not actually streaming)
- Events arrive but you can't find the text (looking in wrong field)
- No `response.created` or `response.completed` events (streaming broke)
- Stream hangs forever without completing (network issue or timeout)
- No `usage` field at the end (streaming didn't complete properly)

**Research Questions:**

1. What does `stream=True` return? Is it a string or an iterable?
2. What fields does each event object have?
3. How do you know when streaming is complete?
4. Where is the actual text content in a delta event?

**Mental Model:** Responses API uses semantic events, not raw SSE chunks. Think event-driven, not string parsing.

---

## Challenge 2: Background Execution for Long-Running Tasks

**Goal:** Handle async execution without blocking the main thread

**Scenario:** You're building a report generation system. Reports can take 30-120 seconds to generate. You can't block the API call for that long - timeouts will kill you. You need background execution with polling.

**What to Implement:**

- Create a response with `background=True` for a long-running task
- Capture the response ID immediately
- Build a polling loop that checks status every 2 seconds
- Retrieve the final response when status is no longer "queued" or "in_progress"
- Extract and print the final output text

**What to Observe in Response:**

- Initial API call returns in <1 second with `status: "queued"` or `status: "in_progress"`
- Response object has an `id` field (you MUST capture this)
- When you poll using the `id`, status transitions: `queued` → `in_progress` → `completed`
- The `output` field is empty initially, populated when complete
- Final response has `usage` field showing token consumption

**Failure Indicators:**

- Status stuck in `queued` for >60 seconds (rate limit, quota issue, or API degradation)
- Status becomes `failed` with an `error` object (task failed, check error message)
- Empty `output` array despite `status: "completed"` (known OpenAI bug, check forums)
- Your code hangs forever (no exit condition in polling loop)
- Polling every 100ms (you're hammering the API, add sleep)

**Research Questions:**

1. What HTTP method do you use to retrieve a response by ID?
2. What are the possible values for the `status` field?
3. How do you know when to stop polling?
4. What's the right polling interval? (Hint: not 100ms, not 30 seconds)
5. What happens if you lose the response ID?

**Mental Model:** Background mode = fire-and-forget + polling. Separate request initiation from result retrieval.

---

## Challenge 3: Multi-Turn Conversation with `previous_response_id`

**Goal:** Chain responses while preserving context server-side

**Scenario:** You're building a chatbot. User asks "What's exponential backoff?" and then asks "Give me a Python example". The second question uses "it" - the model needs to remember what "it" refers to. Unlike Chat Completions, you don't want to manually build message history.

**What to Implement:**

- Create first response asking "What's exponential backoff?"
- Create second response asking "Give me a Python example" using `previous_response_id`
- Verify the second response understands "it" refers to exponential backoff
- Print both outputs

**What to Observe in Response:**

- Second response has full context about exponential backoff WITHOUT you sending the first response text
- No need to manually construct a `messages` array
- Server automatically preserves conversation history
- Response metadata shows `previous_response_id` field populated
- Token usage in second response includes ALL tokens from first response (you're billed for context)

**Failure Indicators:**

- Second response has no idea what "it" refers to (you forgot a critical parameter)
- Error: "Response not found" (response expired, or you set wrong parameter)
- Second response ignores your `instructions` parameter from first call (expected - config doesn't carry over, only context)
- Token costs double/triple with each turn (context window growing, you're paying for all history)
- Context lost after 30 days (responses auto-expire)

**Research Questions:**

1. What parameter do you need to set on the FIRST request to enable chaining?
2. What parameter on the SECOND request links it to the first?
3. Does the model configuration (temperature, max_tokens) carry over from previous response?
4. How long does OpenAI store responses for chaining?
5. What happens to your token costs as conversation grows?

**Mental Model:** `previous_response_id` is like passing a session cookie. Server remembers, you don't build history.

---

## Challenge 4: Streaming Resumption After Network Failure

**Goal:** Resume streaming from where it dropped using `sequence_number`

**Scenario:** You're streaming a long response (1000+ word essay). Network connection drops mid-stream. In Chat Completions, you're fucked - start over. In Responses API, you can resume from exactly where you left off.

**What to Implement:**

- Start a background streaming response (yes, both `background=True` AND `stream=True`)
- Track the `sequence_number` of each event as it arrives
- Simulate a network failure after 10 events (raise an exception)
- Note: Full resumption requires additional API calls beyond basic SDK (research needed)

**What to Observe in Response:**

- Each streaming event has a `sequence_number` field
- Numbers are monotonically increasing (1, 2, 3, 4...)
- When you set `background=True` + `stream=True`, you get a response ID immediately
- Response continues processing even if stream drops
- You can re-attach to the stream later using the response ID

**Failure Indicators:**

- Sequence numbers are missing or null (using wrong API mode)
- Sequence numbers skip (e.g., 1, 2, 5, 9) - API bug or missed events
- Can't resume stream (forgot to capture `response.id` and last `sequence_number`)
- On resume, you get duplicate events (not filtering by sequence number on client side)
- Resume attempts fail (forgot `background=True` - can't resume non-background streams)

**Research Questions:**

1. Can you use `stream=True` and `background=True` together?
2. What field in each event tells you the position in the stream?
3. How would you resume a stream from sequence number 50?
4. What's the difference between this and Kafka consumer offsets?
5. Why can't Chat Completions do this?

**Mental Model:** Streaming is cursor-based. Track `sequence_number` like Kafka offsets.

---

## Challenge 5: Handling Rate Limits with Retry Logic

**Goal:** Build robust retry wrapper for 429 errors without causing retry storms

**Scenario:** You're processing 100 documents. Each needs an API call. You WILL hit rate limits (OpenAI has strict limits by tier). Your code needs to handle this gracefully - retry when throttled, but don't hammer the API (causes ban).

**What to Implement:**

- Create a wrapper function around `client.responses.create()`
- When you get a rate limit error (429), retry with exponential backoff
- Wait 1s, then 2s, then 4s, then 8s, then 16s between retries
- Stop after 5 attempts
- Add random jitter (±20%) to wait times
- Test by sending 100 rapid requests

**What to Observe in Response:**

- First 10-50 requests succeed (depends on your OpenAI tier)
- Then you start getting `RateLimitError` exceptions
- Your retry logic kicks in - you see wait messages
- Some requests succeed after waiting
- After 5 retries, requests fail permanently with final error

**Failure Indicators:**

- All 100 requests succeed (you're on a high tier, try 1000 requests)
- All requests fail immediately (no retry happening at all)
- Requests retry forever (no stop condition - infinite loop)
- Fixed 1-second delays (linear backoff - causes retry storm)
- Retrying 400 errors (those are YOUR bugs, not transient failures)
- No jitter (all clients retry at exactly 1s, 2s, 4s - thundering herd problem)

**Research Questions:**

1. What Python library is commonly used for retry logic?
2. What's the difference between exponential backoff and linear backoff?
3. What is jitter and why does it prevent thundering herd?
4. Which HTTP status codes should trigger retry? (429 yes, but what about 500, 503, 400?)
5. Why is retrying on 400 Bad Request always wrong?

**Mental Model:** Rate limits are transient. Exponential backoff + jitter prevents retry storms.

---

## Challenge 6: Observing Token Usage and Costs

**Goal:** Track input/output tokens to predict costs before they surprise you

**Scenario:** You're building a production app. You need to track token usage per request to predict monthly costs. One surprise $10K bill and you're explaining to the CFO why you didn't monitor this.

**What to Implement:**

- Make a simple API call
- Extract the `usage` field from response
- Print: input tokens, output tokens, total tokens
- Calculate estimated cost using current pricing (gpt-4o-mini: $0.15/1M input, $0.60/1M output)
- Verify your math: total tokens should equal input + output (+ reasoning if o1/o3)

**What to Observe in Response:**

- Response has a `usage` field (or `usage` is in completion event if streaming)
- `usage.input_tokens` ≈ length of your prompt (1 token ≈ 4 characters, roughly)
- `usage.output_tokens` ≈ length of model's response
- `usage.total_tokens` = input + output
- For reasoning models (o1, o3): `usage.output_tokens_details.reasoning_tokens` shows hidden CoT tokens

**Failure Indicators:**

- `usage` field is `null` or missing (streaming not complete, or background task still running)
- Input tokens WAY higher than expected (you used `previous_response_id` - all history counted)
- Output tokens exceed your `max_output_tokens` setting (response was truncated)
- Your cost calculation is off by 10x (forgot reasoning tokens, or used wrong model pricing)
- Total tokens ≠ input + output (forgot reasoning tokens in o1/o3 models)

**Research Questions:**

1. Where is the `usage` field in a non-streaming response?
2. Where is the `usage` field in a streaming response?
3. How many characters roughly equal 1 token? (Ballpark estimate)
4. What are "reasoning tokens" in o1/o3 models?
5. What's the current pricing for gpt-4o-mini vs gpt-4o vs o1?

**Mental Model:** Tokens = money. Monitor usage like you monitor database queries.

---

## Challenge 7: Handling Streaming Errors Mid-Stream

**Goal:** Detect and recover from errors during streaming without losing data

**Scenario:** You're streaming a long response. You set `max_output_tokens=100` but ask for a 500-word essay. The stream will terminate mid-sentence. How do you detect this gracefully and preserve partial output?

**What to Implement:**

- Create a streaming response with intentionally small `max_output_tokens`
- Collect all streamed text chunks into a buffer
- Listen for error events in the stream
- Check the final `response.completed` event for status and incomplete details
- Print partial output even if truncated

**What to Observe in Response:**

- Stream delivers chunks normally at first
- Stream completes (you get `response.completed` event)
- But response status is `incomplete` or similar (not `completed`)
- Response has `incomplete_details` field explaining WHY (e.g., hit `max_tokens`)
- Your text buffer has partial content (not lost despite truncation)

**Failure Indicators:**

- No error event, stream just stops silently (you didn't check completion status)
- Exception thrown instead of graceful incomplete status (API changed behavior)
- Partial output lost (you didn't buffer streamed chunks)
- You treat truncation as success (didn't check `incomplete_details` field)
- Text ends mid-word with no indication why (ignored completion event)

**Research Questions:**

1. What event types indicate errors during streaming?
2. What field in the `response.completed` event tells you if response is incomplete?
3. What are possible reasons for incomplete responses?
4. If you don't buffer chunks during streaming, can you retrieve them later?
5. Should you retry on truncation, or is that wasting money?

**Mental Model:** Streaming can fail gracefully. Always check completion status, not just event count.

---

## Challenge 8: Timeout Handling for Slow Responses

**Goal:** Prevent hanging requests with client-side timeouts

**Scenario:** You ask for a 5000-word essay. It takes 2 minutes to generate. Your default HTTP client times out after 30 seconds. Request fails, but you've already consumed tokens. You need timeout strategy.

**What to Implement:**

- Configure OpenAI client with custom timeout (30 seconds total, 5 seconds connect)
- Make a request for long content that will timeout
- Catch the timeout exception
- On timeout, retry the SAME request with `background=True` instead
- Poll the background task to completion

**What to Observe in Response:**

- First attempt: Large request times out after 30 seconds with `TimeoutException`
- Second attempt: Same prompt with `background=True` returns immediately with response ID
- Background task succeeds even though sync version failed
- You get the full content via polling

**Failure Indicators:**

- No timeout configured - request hangs forever (blocks your app)
- Timeout too short (5 seconds) - all requests fail unnecessarily
- You retry the sync request again (same timeout will hit again)
- You don't capture response ID when switching to background (lost track of task)
- You pay for tokens twice (first request failed but was billed, second request also billed)

**Research Questions:**

1. How do you configure timeout in the OpenAI Python client?
2. What exception is raised on timeout?
3. What's a reasonable timeout for API calls? (Hint: AWS Lambda default is 30s)
4. Can you set different timeouts for connect vs total request?
5. Does background mode have timeouts, or can tasks run indefinitely?

**Mental Model:** Timeouts are guardrails. Long tasks → background mode.

---

## Challenge 9: Context Window Management in Multi-Turn Conversations

**Goal:** Track token usage across conversation turns to avoid hitting context limits

**Scenario:** You're building a chatbot. Each turn adds to conversation history. After 10-20 turns, you hit the context window limit (4096 tokens for gpt-4o-mini, 128K for gpt-4o). Request fails. You need to monitor and truncate proactively.

**What to Implement:**

- Create a multi-turn conversation (5+ turns) using `previous_response_id`
- Track cumulative token usage across all turns
- Calculate rough token estimate: 1 token ≈ 4 characters
- Set a warning threshold at 80% of model's context limit
- Print warning when approaching limit

**What to Observe in Response:**

- Each turn's `usage.input_tokens` includes ALL previous turn tokens
- Token count grows with each turn
- By turn 5, input tokens might be 5x the first turn
- Warning triggers before hitting actual limit
- You can see how fast you're approaching the cliff

**Failure Indicators:**

- Error after turn 10: "Context length exceeded" (didn't monitor)
- Response quality degrades over turns (model auto-truncated early messages)
- Costs spike unexpectedly (re-processing entire history every turn)
- No truncation strategy (conversation becomes unusable after N turns)
- You don't know the model's context limit (look it up per model)

**Research Questions:**

1. What's the context window size for gpt-4o-mini? gpt-4o? o1?
2. How are tokens counted when using `previous_response_id`?
3. What happens when you exceed context window - error or truncation?
4. How would you implement conversation summarization to reduce tokens?
5. What's the cost difference between turn 1 and turn 10 in a conversation?

**Mental Model:** Context window is a FIFO buffer with size limit. Monitor and truncate proactively.

---

## Challenge 10: Combining Streaming + Previous Response ID

**Goal:** Stream a follow-up response in a multi-turn conversation

**Scenario:** User asks "What is jitter in retry logic?" (you respond normally). Then asks "Show me a Python implementation" (you want to stream this for better UX). Can you combine conversation chaining with streaming?

**What to Implement:**

- First turn: Non-streaming response about jitter
- Second turn: Streaming response with Python code, using `previous_response_id` from first turn
- Verify second response understands "it" refers to jitter
- Stream the response and print text as it arrives
- Capture the final response ID from the streaming completion event (for potential turn 3)

**What to Observe in Response:**

- Second response has full context about jitter WITHOUT you repeating the question
- Streaming works normally even though you're chaining responses
- `response.completed` event includes `response.id` field (you can chain turn 3)
- Context preserved despite switching between non-streaming and streaming modes

**Failure Indicators:**

- Second response has no idea what "it" refers to (forgot critical parameter on turn 1)
- Stream starts but has no context (chaining broke)
- Can't extract response ID from streaming events (didn't handle `response.completed`)
- Stream never completes (network issue, no timeout)
- Mixing streaming and non-streaming broke conversation (shouldn't happen, but verify)

**Research Questions:**

1. Can you chain responses even if one is streaming and one isn't?
2. Where do you get the response ID from a streaming response?
3. Does streaming mode affect token billing compared to non-streaming?
4. Can you stream turn 1, chain to non-streaming turn 2, then stream turn 3?
5. What's the UX advantage of streaming follow-up responses?

**Mental Model:** Streaming is orthogonal to conversation state. Chain responses regardless of delivery mode.

---

## Implementation Order

**Day 1 (Learning Phase):**

1. Use Case 1 (Streaming Lifecycle) - understand events
2. Use Case 6 (Token Usage) - understand costs
3. Use Case 5 (Rate Limits) - build retry wrapper

**Day 2 (Challenge Phase):** 4. Use Case 3 (Multi-Turn) - conversation state 5. Use Case 7 (Streaming Errors) - error handling 6. Use Case 8 (Timeouts) - timeout strategy 7. Use Case 2 (Background Mode) - async execution

**Bonus (If Time):** 8. Use Case 10 (Streaming + Chaining) - combine patterns 9. Use Case 4 (Stream Resumption) - advanced resilience 10. Use Case 9 (Context Windows) - production planning

---

## Mental Models Summary

|Use Case|Mental Model|
|---|---|
|1|Event-driven, not string parsing|
|2|Fire-and-forget + polling|
|3|Session cookie (server remembers)|
|4|Cursor-based streaming (Kafka offsets)|
|5|Exponential backoff prevents retry storms|
|6|Tokens = money. Monitor usage.|
|7|Streaming can fail gracefully|
|8|Timeouts are guardrails|
|9|Context window = FIFO buffer|
|10|Streaming orthogonal to state|

---

## What These Cases Teach You

1. **API Patterns (Day 1 Goal):**
    
    - Semantic events vs raw chunks
    - Sync vs async (background mode)
    - Streaming lifecycle and error handling
    - Token-based cost tracking
2. **Production Robustness (Day 2 Goal):**
    
    - Retry logic with exponential backoff
    - Timeout handling
    - Error recovery during streaming
    - Context window management
    - Resumable streams for reliability
3. **Where Chat Completions Breaks:**
    
    - Background execution (Chat Completions blocks)
    - Server-side conversation state (Chat Completions requires client to manage history)
    - Resumable streaming (Chat Completions has no sequence numbers)
    - Typed events (Chat Completions uses raw SSE)

---

## Notes for Bootcamp Alignment

- **No toy examples:** Every case simulates production scenarios (rate limits, timeouts, context limits)
- **Observable failures:** Each case includes "what indicates failure" so you learn to debug
- **Progressive complexity:** Starts with basics (streaming events), builds to advanced (resumable streams)
- **Week 2 focus:** All cases align with API patterns, retries, streaming, and error handling
- **Production-ready patterns:** Retry wrappers, timeout configs, cost tracking, context management