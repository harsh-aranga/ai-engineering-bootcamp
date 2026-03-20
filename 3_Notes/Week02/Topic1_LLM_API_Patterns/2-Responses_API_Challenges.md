# Week 2, Days 1-2: Responses API Challenges

**Focus: API Patterns, Streaming, Retries, Error Handling, Timeouts**

**Time Budget: 2-3 hours total (15-20 min per challenge)**

---

## Challenge 1: Make Your First Responses API Call

**Goal:** Understand basic request/response structure

**Scenario:** You need to make a simple API call and inspect what comes back. Unlike Chat Completions which returns `choices`, Responses API has a different structure.

**What to Implement:**

- Make a basic non-streaming call to Responses API
- Ask it to "Explain HTTP 429 errors in 2 sentences"
- Print the entire response object
- Extract and print just the text output
- Print the usage stats (tokens consumed)

**What to Observe in Response:**

- Response has `output` field (array of items)
- Each output item has a `type` field (probably "message")
- Text is nested inside the output structure (not at top level)
- Response includes `id`, `created_at`, `model`, `status`
- `usage` field shows `input_tokens`, `output_tokens`, `total_tokens`

**Failure Indicators:**

- Can't find the text output (looking in wrong field)
- No `usage` field (didn't wait for completion)
- Error: "model not found" (wrong model name)
- Error: 401 (API key not set or invalid)

**Research Questions:**

1. What's the endpoint URL for Responses API?
2. How is the response structure different from Chat Completions API?
3. Where is the actual text in the response object?
4. What does the `status` field indicate?

**Time: 10-15 minutes**

---

## Challenge 2: Stream a Response and Collect Chunks

**Goal:** Understand streaming events and how to reassemble text

**Scenario:** You want to show users text as it's generated (like ChatGPT does). You need to set `stream=True` and handle incoming events.

**What to Implement:**

- Make a streaming request with `stream=True`
- Iterate over the stream and print each event's type
- Collect all text deltas into a single string
- Print the final assembled text
- Count how many delta events you received

**What to Observe in Response:**

- Stream returns an iterator, not a single response
- First event type: `response.created`
- Many events with type: `response.output_text.delta`
- Each delta event has small text chunks
- Final event type: `response.completed`
- Events arrive in sequence, not all at once

**Failure Indicators:**

- Only see one event (streaming not actually working)
- Can't find the text in delta events (wrong field)
- Text appears jumbled or out of order (not buffering correctly)
- Stream never ends (no completion event received)
- Exception: "object is not iterable" (treating stream like regular response)

**Research Questions:**

1. What does `stream=True` actually return?
2. What field contains the text chunk in a delta event?
3. How do you know when streaming is complete?
4. Can you get token usage from a stream?

**Time: 15-20 minutes**

---

## Challenge 3: Handle Different finish_reason Values

**Goal:** Understand why responses end and detect truncation

**Scenario:** Responses can end for different reasons: completed normally, hit token limit, content filter triggered. You need to detect WHY it ended.

**What to Implement:**

- Make 3 separate API calls:
    1. Normal completion (short prompt, normal response)
    2. Truncated (set `max_output_tokens=20` and ask for a 500-word essay)
    3. Your choice of third test case
- For each response, check the completion status
- Print why each response ended

**What to Observe in Response:**

- Normal response: `status: "completed"`
- Truncated response: `status: "incomplete"` or similar
- Check `incomplete_details` field for reason
- Usage shows actual tokens consumed (may be less than requested)

**Failure Indicators:**

- All responses look the same (not checking status/incomplete_details)
- Truncated response treated as success (didn't validate completion)
- Can't find completion reason (looking in wrong field)
- No difference between normal and truncated (max_tokens not working)

**Research Questions:**

1. What field tells you if a response completed successfully?
2. What's the difference between `status` and `incomplete_details`?
3. What happens when you set `max_output_tokens` too low?
4. How can you detect content filter triggers?

**Time: 15-20 minutes**

---

## Challenge 4: Extract and Calculate Token Costs

**Goal:** Track token usage and estimate API costs

**Scenario:** You're building a production app. Every API call costs money. You need to track tokens per request and estimate monthly costs.

**What to Implement:**

- Make an API call with gpt-4o-mini
- Extract `usage.input_tokens`, `usage.output_tokens`, `usage.total_tokens`
- Calculate cost using current pricing:
    - gpt-4o-mini: $0.150 per 1M input tokens, $0.600 per 1M output tokens
- Print: "This request cost $X.XXXXXX"
- Verify: total_tokens = input_tokens + output_tokens

**What to Observe in Response:**

- Input tokens ≈ your prompt length (rough: 1 token ≈ 4 chars)
- Output tokens ≈ response length
- Output tokens cost 4x input tokens (for gpt-4o-mini)
- Costs are tiny per request (fractions of a cent)

**Failure Indicators:**

- Can't find usage field (looking in wrong place)
- Math doesn't add up (wrong pricing, forgot to divide by 1M)
- Total tokens ≠ input + output (calculation error)
- Cost seems way too high or too low (check your math)

**Research Questions:**

1. Where is the `usage` field in a Responses API response?
2. What's the current pricing for gpt-4o-mini input vs output tokens?
3. Why does output cost more than input?
4. How would you track cumulative costs across 1000 requests?

**Time: 15 minutes**

---

## Challenge 5: Force and Handle a Rate Limit Error

**Goal:** Understand what 429 errors look like and when they happen

**Scenario:** You're testing your app. You want to see what happens when you hit rate limits. You need to trigger a 429 error intentionally.

**What to Implement:**

- Send 50-100 rapid API requests in a loop (no sleep between them)
- Catch the exception when rate limit hits
- Print the error message and type
- Note which request number triggered the error

**What to Observe in Response:**

- First 10-50 requests succeed (depends on your tier)
- Then you get a `RateLimitError` exception
- Error message mentions "rate limit" or "429"
- The error tells you to wait before retrying

**Failure Indicators:**

- All 100 requests succeed (you're on high tier, or requests too slow)
- Different error than rate limit (maybe auth or quota issue)
- No exception caught (not handling errors)
- Can't tell which request failed (no logging)

**Research Questions:**

1. What exception type does OpenAI SDK raise for rate limits?
2. What HTTP status code is a rate limit?
3. How many requests can you make before hitting limit? (depends on tier)
4. What information is in the rate limit error message?

**Time: 10-15 minutes**

---

## Challenge 6: Implement Basic Retry with Tenacity

**Goal:** Use tenacity library to automatically retry on rate limits

**Scenario:** When you hit a rate limit, you want to automatically retry after waiting. Tenacity library makes this easy.

**What to Implement:**

- Install tenacity: `pip install tenacity`
- Import: `from tenacity import retry, stop_after_attempt, retry_if_exception_type`
- Create a function decorated with `@retry` that calls the API
- Configure it to retry only on `RateLimitError`
- Stop after 3 attempts
- Test by triggering rate limits

**What to Observe in Response:**

- When rate limit hits, function automatically retries
- You see multiple attempts for the same request
- After 3 failed attempts, final exception is raised
- Successful requests don't retry (only failures)

**Failure Indicators:**

- Function doesn't retry (decorator not working)
- Retries on all errors including 400 (wrong config)
- Retries forever (no stop condition)
- Immediate retry with no wait (need wait strategy - next challenge)

**Research Questions:**

1. How does the `@retry` decorator work?
2. What does `retry_if_exception_type()` do?
3. What's the difference between `stop_after_attempt` and `stop_after_delay`?
4. Why shouldn't you retry 400 errors?

**Time: 20 minutes**

---

## Challenge 7: Add Exponential Backoff to Retries

**Goal:** Implement exponential backoff wait strategy

**Scenario:** You retry on rate limits, but immediately retrying makes it worse. You need exponential backoff: wait 1s, then 2s, then 4s, then 8s...

**What to Implement:**

- Extend your retry decorator from Challenge 6
- Add `wait_exponential` from tenacity
- Configure: `wait=wait_exponential(multiplier=1, min=1, max=60)`
- This means: wait 1s, 2s, 4s, 8s, 16s, 32s, max 60s
- Print timestamps to see wait times

**What to Observe in Response:**

- First retry waits ~1 second
- Second retry waits ~2 seconds
- Third retry waits ~4 seconds
- Wait times double each attempt
- Max wait caps at 60 seconds

**Failure Indicators:**

- All retries happen immediately (backoff not working)
- Fixed delay instead of exponential (wrong config)
- Waits are too short or too long (wrong multiplier)
- No visible delay (not logging retry attempts)

**Research Questions:**

1. What is exponential backoff and why is it better than linear?
2. What does the `multiplier` parameter control?
3. Why set a `max` wait time?
4. What happens if you don't set `min`?

**Time: 15 minutes**

---

## Challenge 8: Add Timeout Configuration

**Goal:** Prevent requests from hanging forever

**Scenario:** You ask for a very long response. The API takes 45 seconds. Your HTTP client times out at 30 seconds by default. Request fails. You need custom timeouts.

**What to Implement:**

- Configure OpenAI client with custom timeout
- Use: `client = OpenAI(timeout=httpx.Timeout(60.0, connect=10.0))`
    - 60s total timeout
    - 10s connection timeout
- Make a request that might take 30+ seconds
- Catch timeout exceptions

**What to Observe in Response:**

- With proper timeout, request completes even if slow
- With too-short timeout, you get `TimeoutException`
- Connection timeout vs total timeout are different
- Error message clearly indicates timeout

**Failure Indicators:**

- Timeout config has no effect (wrong syntax)
- All requests timeout (timeout too short)
- Requests hang forever (no timeout set)
- Can't catch timeout exception (wrong exception type)

**Research Questions:**

1. What's the difference between connection timeout and total timeout?
2. What exception is raised on timeout?
3. What's a reasonable default timeout for LLM APIs?
4. How do you configure timeout in the OpenAI Python client?

**Time: 15 minutes**

---

## Challenge 9: Handle Streaming Errors Gracefully

**Goal:** Detect errors during streaming and preserve partial output

**Scenario:** You're streaming a response. Halfway through, something breaks (network issue, token limit, etc.). You need to handle this gracefully.

**What to Implement:**

- Start a streaming request
- Wrap stream iteration in try/except
- Buffer all text chunks as they arrive
- If stream fails, print partial output + error
- Test by setting very low `max_output_tokens`

**What to Observe in Response:**

- Partial text is collected before error
- You can access buffered content even after failure
- Error is caught, doesn't crash your app
- Final event might indicate incomplete status

**Failure Indicators:**

- No partial output (didn't buffer chunks)
- Exception kills the app (not caught)
- Can't tell stream failed vs completed (not checking status)
- Lost all progress on error (no buffering)

**Research Questions:**

1. What exceptions can happen during streaming?
2. How do you preserve partial output if stream fails?
3. Should you retry streaming requests that fail mid-stream?
4. What's the difference between network error and completion error?

**Time: 20 minutes**

---

## Challenge 10: Build the `robust_response()` Function

**Goal:** Combine everything into a production-ready wrapper

**Scenario:** This is your Day 2 mini-build. Combine all patterns into one reusable function.

**What to Implement:** Create a function with this signature:

```python
def robust_response(
    input_text: str,
    model: str = "gpt-4o-mini",
    stream: bool = False,
    max_retries: int = 3,
    timeout_seconds: float = 60.0
):
    """
    Production-ready Responses API wrapper with:
    - Exponential backoff retries on rate limits
    - Timeout handling
    - Streaming support
    - Error logging
    - Token usage tracking
    """
    pass
```

**Must handle:**

- Retry on `RateLimitError` with exponential backoff
- Custom timeout configuration
- Streaming mode returns iterator
- Non-streaming returns dict with `{content, usage, status}`
- Log all retries with timestamps
- Catch and log errors gracefully

**Success Criteria:**

- [ ] Retries on 429 with exponential backoff (1s, 2s, 4s...)
- [ ] Does NOT retry on 400 errors
- [ ] Has configurable timeout (default 60s)
- [ ] Streaming mode yields events
- [ ] Non-streaming returns structured response
- [ ] Logs retry attempts
- [ ] Returns token usage in response
- [ ] Tested with: success, rate limit, timeout scenarios

**Failure Indicators:**

- Retries on all errors (no exception filtering)
- No timeout (can hang)
- Streaming mode broken (returns wrong type)
- No logging (can't debug)
- Doesn't track token usage

**Research Questions:**

1. How do you make a function work in both streaming and non-streaming modes?
2. Should you log before or after retry attempts?
3. What should the function return on total failure?
4. How do you test this without actually hitting rate limits every time?

**Time: 30-40 minutes**

---

## Implementation Order

**Day 1 (1.5 hours):**

1. Challenge 1 - Basic API call (10 min)
2. Challenge 2 - Streaming (15 min)
3. Challenge 3 - Finish reasons (15 min)
4. Challenge 4 - Token costs (15 min)
5. Challenge 5 - Force rate limit (10 min)
6. Challenge 6 - Basic retry (20 min)

**Day 2 (1.5 hours):** 7. Challenge 7 - Exponential backoff (15 min) 8. Challenge 8 - Timeouts (15 min) 9. Challenge 9 - Streaming errors (20 min) 10. Challenge 10 - Build robust function (30-40 min)

---

## What You'll Learn

**By End of Day 1:**

- ✅ Responses API structure (different from Chat Completions)
- ✅ Streaming events and text assembly
- ✅ Token tracking and cost calculation
- ✅ Rate limit errors (what they look like)
- ✅ Basic retry with tenacity

**By End of Day 2:**

- ✅ Exponential backoff (prevents retry storms)
- ✅ Timeout configuration (prevents hangs)
- ✅ Graceful error handling in streams
- ✅ Production-ready API wrapper function
- ✅ Ready for Week 4 RAG and Week 5 Agents

---

## Mental Models Summary

|Challenge|Mental Model|
|---|---|
|1-2|Responses API ≠ Chat Completions (different structure)|
|3|Not all completions are successful (check status)|
|4|Tokens = money (track religiously)|
|5-6|Rate limits are normal (handle, don't panic)|
|7|Exponential backoff prevents retry storms|
|8|Timeouts are guardrails (set them)|
|9|Streaming can fail mid-way (buffer output)|
|10|Production = all patterns combined|

---

## Success Criteria

After these 10 challenges, you should be able to:

- [ ] Make Responses API calls confidently
- [ ] Stream responses and handle events
- [ ] Track token usage and estimate costs
- [ ] Handle rate limits with proper retry logic
- [ ] Configure timeouts appropriately
- [ ] Handle streaming errors gracefully
- [ ] Build production-ready API wrappers

**This is your foundation for Week 4 (RAG) and Week 5 (Agents).**