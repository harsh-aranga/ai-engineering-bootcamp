"""
This script corresponds to Day 3-4->Day 3->Hour 2->Experiment->
Implement basic truncation: if over limit, remove oldest messages until under limit
Test: Start with messages that fit, keep adding until truncation kicks in
Edge case: What if a single message exceeds the limit? How should you handle it?

Note: this code targets all 3 experiements above.
"""

from common.logger import get_logger
from common.dumper import dump_json

import tiktoken as tk

logger = get_logger(__file__)

# Approximate per-message overhead (role, separators, etc.)
# Actual value is model-specific; 5 is a middle-ground heuristic.
PER_MESSAGE_OVERHEAD = 5

def trunc_by_token_count(conversation: list[dict[str, str]],
                         max_tokens: int | None,  model: str = "gpt-4o") -> list[dict[str, str]]:
    """
    Truncates conversation by removing oldest messages until total tokens fit within limit.
    Preserves system message if present. Iterates from newest to oldest, keeping messages that fit.
    :param conversation: List of message dicts with 'role' and 'content' keys
    :param max_tokens: Maximum allowed token count for the conversation
    :param model: Model name for tiktoken encoding lookup
    :return: Truncated conversation list with system message preserved if originally present
    """
    encoding = tk.encoding_for_model(model)
    truncated_conversation:list[dict[str, str]] = []

    total_tokens = 0
    system_message = None

    if conversation and conversation[0].get("role") == "system":
        system_message = conversation[0]
        system_message_content = conversation[0].get("content")
        token_count = len(encoding.encode(system_message_content))
        total_tokens += token_count + PER_MESSAGE_OVERHEAD
        conversation = conversation[1:]

    for message in reversed(conversation):
        total_tokens += PER_MESSAGE_OVERHEAD
        for key, value in message.items():
            token_count = len(encoding.encode(value))
            total_tokens += token_count
        if total_tokens <= max_tokens:
            truncated_conversation.insert(0, message)
        else:
            break

    if system_message is not None:
        truncated_conversation.insert(0, system_message)

    return truncated_conversation

def trunc_by_message_count(conversation: list[dict[str, str]],
                         max_messages: int | None) -> list[dict[str, str]]:
    """
    Truncates conversation by removing the oldest messages until message count fits within limit.
    Preserves system message if present, reserving one slot for it in the count.
    :param conversation: List of message dicts with 'role' and 'content' keys
    :param max_messages: Maximum allowed number of messages in the conversation
    :return: Truncated conversation list with system message preserved if originally present
    """
    if conversation[0].get("role") == "system":
        trunc_message = conversation[1:][-(max_messages - 1):]
        trunc_message.insert(0, conversation[0])
        return trunc_message
    else:
        return conversation[-max_messages:]


def crosses_token_threshold(conversation, max_tokens, model) -> bool:
    """
    Checks whether the single-message conversation crosses the provided max token threshold.
    :param conversation:
    :param max_tokens:
    :param model:
    :return: True if token count is greater than or equal to max_tokens, else False
    """
    encoding = tk.encoding_for_model(model)
    message_content = conversation[0].get("content")
    token_count = len(encoding.encode(message_content))
    return token_count >= max_tokens

def truncate_conversation(
        conversation: list[dict[str, str]],
        max_tokens: int | None,
        max_messages: int | None,
        model: str = "gpt-4o" ) -> list[dict[str, str]]:
    """
    Truncates conversation passed to it until it matches either the max token or the max messages' constraint.
    If both max_token and max_messages are passed, then it will trunc conversation until both requirements are met with priority to max_tokens.
    :param conversation:
    :param max_tokens:
    :param max_messages:
    :param model:
    :return:
    """
    if max_tokens is not None and len(conversation) == 1 and crosses_token_threshold(conversation, max_tokens, model):
        logger.error("Single message conversation crosses max token threshold. Avoid truncation.")
        raise ValueError("Cannot truncate: single-message conversation exceeds max token limit.")

    if max_messages is not None and max_tokens is not None:
        logger.info("Truncating conversation by max tokens first")
        truncated_convo = trunc_by_token_count(conversation, max_tokens, model)
        if len(truncated_convo) <= max_messages:
            logger.info("Conversation length meets max token and max messages criteria. Returning truncated conversation...")
            return truncated_convo
        else:
            logger.info("Conversation does not meet max messages criteria. Truncating by max messages")
            truncated_convo = trunc_by_message_count(truncated_convo, max_messages)
            logger.info(
                "Token count truncated conversation now meets max messages criteria. Returning truncated conversation...")
            return truncated_convo
    elif max_messages is not None:
        logger.info("Truncating conversation by max messages")
        truncated_convo = trunc_by_message_count(conversation, max_messages)
        return truncated_convo
    elif max_tokens is not None:
        logger.info("Truncating conversation by max tokens")
        truncated_convo = trunc_by_token_count(conversation, max_tokens, model)
        return truncated_convo
    else:
        logger.error("max_tokens and max_messages are missing. Either one or both must be supplied as parameters.")
        raise ValueError("At least one of max_tokens or max_messages must be provided")

if __name__ == "__main__":
    original_conversation = [
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

    logger.info(f"Original Conversation: {original_conversation}")
    dump_json(original_conversation, "Original Conversation")
    logger.info("=" * 175)
    logger.info("=" * 175)

    logger.info("Starting a run that truncates by both max messages and max tokens")
    truncated_conversation = truncate_conversation(original_conversation, 450, 15)
    logger.info(f"Truncated Conversation: {truncated_conversation}")
    dump_json(truncated_conversation, "By max tokens and max messages")
    logger.info("=" * 175)
    logger.info("=" * 175)

    logger.info("Starting a run that truncates by max messages")
    truncated_conversation = truncate_conversation(original_conversation, max_messages = 15, max_tokens = None)
    logger.info(f"Truncated Conversation: {truncated_conversation}")
    dump_json(truncated_conversation, "By max messages")
    logger.info("=" * 175)
    logger.info("=" * 175)

    logger.info("Starting a run that truncates by max tokens")
    truncated_conversation = truncate_conversation(original_conversation, max_tokens = 450, max_messages = None)
    logger.info(f"Truncated Conversation: {truncated_conversation}")
    dump_json(truncated_conversation, "By max tokens")
    logger.info("=" * 175)
    logger.info("=" * 175)

    logger.info("Starting a run that does not send both params")
    truncated_conversation = truncate_conversation(original_conversation, max_tokens = None, max_messages = None)
    logger.info(f"Truncated Conversation: {truncated_conversation}")
    logger.info("=" * 175)