"""
This script corresponds to Day 3-4->Day 3->Hour 2->Experiment->
Simulate a long conversation (20+ messages). Calculate total tokens. Does it fit in GPT-4o-mini's context?
"""

from common.logger import get_logger

import tiktoken as tk

logger = get_logger(__file__)

# Approximate per-message overhead (role, separators, etc.)
# Actual value is model-specific; 5 is a middle-ground heuristic.
PER_MESSAGE_OVERHEAD = 5
GPT_4O_CONTEXT_WINDOW_SIZE = 128_000

def count_conversation_tokens(conversation: list[dict[str, str]]) -> int:
    """
    For a given conversational history, counts the total tokens and returns it.
    :param conversation: The conversation history dict
    :return: int - Total token cost of the conversation
    """
    encoding = tk.encoding_for_model("gpt-4o")
    count_of_tokens = 0

    for conv_item in conversation:
        token_list = encoding.encode(conv_item.get("content"))
        count_of_tokens += len(token_list)

    # Adding 5 tokens extra for internal representation tokens
    final_token_count = count_of_tokens + (len(conversation) * PER_MESSAGE_OVERHEAD)

    return final_token_count

if __name__ == "__main__":
    conversation = [
        {"role": "system", "content": "You are a senior backend architect helping with system design and AI concepts."},

        {"role": "user", "content": "I am trying to understand embeddings. Can you explain what they are?"},
        {"role": "assistant",
         "content": "Embeddings are numerical vector representations of text that capture semantic meaning. Similar texts produce similar vectors."},

        {"role": "user", "content": "How are they different from keyword search?"},
        {"role": "assistant",
         "content": "Keyword search matches exact terms, while embeddings capture meaning. For example, 'car' and 'vehicle' may not match in keyword search but are close in embedding space."},

        {"role": "user", "content": "What is cosine similarity then?"},
        {"role": "assistant",
         "content": "Cosine similarity measures how close two vectors are by computing the cosine of the angle between them. Values closer to 1 indicate similarity."},

        {"role": "user", "content": "How are embeddings stored in real systems?"},
        {"role": "assistant",
         "content": "They are stored in vector databases like Pinecone, Qdrant, or even traditional DBs with extensions. These systems allow efficient similarity search."},

        {"role": "user", "content": "What is chunking in RAG?"},
        {"role": "assistant",
         "content": "Chunking is splitting large documents into smaller pieces so they can be embedded and retrieved efficiently."},

        {"role": "user", "content": "How do I decide chunk size?"},
        {"role": "assistant",
         "content": "It depends on context window and use case. Typically 200–500 tokens per chunk is a good starting point."},

        {"role": "user", "content": "What happens if chunk is too large?"},
        {"role": "assistant",
         "content": "You lose retrieval precision. Irrelevant parts get included and the model gets noisy context."},

        {"role": "user", "content": "And if too small?"},
        {"role": "assistant",
         "content": "You lose context continuity. The model may not have enough information to answer properly."},

        {"role": "user", "content": "How does streaming work in OpenAI APIs?"},
        {"role": "assistant",
         "content": "Streaming sends tokens incrementally as they are generated instead of waiting for the full response."},

        {"role": "user", "content": "What events are involved in streaming?"},
        {"role": "assistant",
         "content": "Events like response.created, response.output_text.delta, and response.completed are emitted during streaming."},

        {"role": "user", "content": "When do I get token usage?"},
        {"role": "assistant", "content": "You typically receive usage details only when the response is completed."},

        {"role": "user", "content": "Can usage ever be missing?"},
        {"role": "assistant", "content": "Yes, in incomplete or failed responses usage may be absent or partial."},

        {"role": "user", "content": "How do I estimate tokens before sending request?"},
        {"role": "assistant",
         "content": "You can use tiktoken to estimate content tokens and add a small overhead per message."},

        {"role": "user", "content": "What overhead should I assume?"},
        {"role": "assistant", "content": "Typically 3 to 6 tokens per message depending on the model."},

        {"role": "user", "content": "What is the context window of GPT-4o-mini?"},
        {"role": "assistant", "content": "GPT-4o-mini supports a large context window, roughly around 128k tokens."},

        {"role": "user", "content": "So will long chats hit limit easily?"},
        {"role": "assistant",
         "content": "Not easily, but poor message management can still waste tokens and hit limits."},

        {"role": "user", "content": "What is the biggest mistake people make?"},
        {"role": "assistant",
         "content": "Keeping too much irrelevant history and not trimming or summarizing context."},

        {"role": "user", "content": "What would you recommend for production systems?"},
        {"role": "assistant",
         "content": "Use sliding window context, summarization, and RAG instead of passing full history."}
    ]

    token_count = count_conversation_tokens(conversation)
    logger.info(f"Total token count for conversation: {token_count}")

    context_window_usage_percentage = (token_count / GPT_4O_CONTEXT_WINDOW_SIZE) * 100
    logger.info(f"Context used: {token_count} of {GPT_4O_CONTEXT_WINDOW_SIZE} tokens for gpt-40")
    logger.info(f"Using {context_window_usage_percentage:.4f} percentage of gpt-4o context window")