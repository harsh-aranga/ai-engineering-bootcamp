# What its about?
For this topic, we are going to learn about LLM API patterns. Since we are going to exclusively learn using OpenAI LLMs, we are going with understanding the Responses API.

Responses API is a new offer from OpenAI that replaces the Chat Completions API. Chat Completions is still available but Responses is much better
## Why Responses is better?
### 1. Multiple outputs support
Chat completions only supports chat outputs but Responses can provide multiple outputs like one for prompt response, one containing image output, one containing next tool to be called, etc.
This is much better to handle than original chat completions. This is because right now LLMs are not just chatbots but also deal with a lot of other capabilities like chats, multi-modal, tool call, etc.
### 2. Task-oriented, not chat-oriented
Chat Completions is optimized for conversations.  
Responses is optimized for **completing a task**.
That makes it suitable for:
- Agents  
- Pipelines
- Batch jobs
- Non-interactive workloads
### 3. Tool calls are first-class, not bolted-on
In Chat Completions, tool/function calling was layered on top of chat.  
In Responses, tool calls are just another output type.
This makes **agent loops natural** instead of hacky.
### 4. Explicit execution lifecycle
Chat Completions relies on `finish_reason`.  
Responses exposes explicit **execution states** (completed, failed, incomplete, cancelled).
This matters for:
- Streaming
- Background jobs
- Reliable retry logic
---
