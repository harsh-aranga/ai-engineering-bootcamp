"""
This script corresponds to Day 3-4->Day 3->Hour 2->Experiment->
Using your Week 1 tokenizer, create a function count_messages_tokens(messages) that counts total tokens in a conversation
"""

from common.logger import get_logger

import tiktoken as tk

logger = get_logger(__file__)

# Approximate per-message overhead (role, separators, etc.)
# Actual value is model-specific; 5 is a middle-ground heuristic.
PER_MESSAGE_OVERHEAD = 5

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
        {
            "role": "system",
            "content": "You are a concise assistant that explains technical concepts clearly."
        },
        {
            "role": "user",
            "content": "Explain what cosine similarity is in simple terms."
        },
        {
            "role": "assistant",
            "content": "Cosine similarity measures how similar two vectors are by calculating the cosine of the angle between them. A value close to 1 means they are very similar, while a value close to 0 means they are different."
        },
        {
            "role": "user",
            "content": "Give a short example using numbers."
        },
        {
            "role": "assistant",
            "content": "If vector A = [1, 0] and vector B = [0, 1], the angle between them is 90 degrees, so cosine similarity is 0. If both are [1, 1], similarity is 1."
        }
    ]

    logger.info(f"Total token count for conversation: {count_conversation_tokens(conversation)}")