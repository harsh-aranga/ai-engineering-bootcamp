"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment 3->'Compare: "ChatGPT" vs "chatgpt" vs "chat gpt"'
"""
from common.logger import get_logger
import tiktoken as tk

logger = get_logger(__file__)

def compare_different_chatgpt() -> None:
    """
    Compare differently cased chatgpt and print their token details
    :return: Returns None. But prints comparison report for  "ChatGPT" vs "chatgpt" vs "chat gpt"
    """
    list_of_chatgpt = ["ChatGPT", "chatgpt", "chat gpt"]

    encoding = tk.encoding_for_model("gpt-4o")
    for gpt in list_of_chatgpt:
        tokens = encoding.encode(gpt)
        decoded_tokens = [encoding.decode([t]) for t in tokens]
        length_of_tokens = len(tokens)

        logger.info("Token reports for word %s", gpt)
        logger.info("Tokens: %s", tokens)
        logger.info("Decoded tokens as text: %s", decoded_tokens)
        logger.info("Total tokens: %s", length_of_tokens)
        logger.info("-" * 100)

if __name__ == "__main__":
    compare_different_chatgpt()