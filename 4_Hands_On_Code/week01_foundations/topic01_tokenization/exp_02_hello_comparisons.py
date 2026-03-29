"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment 2->'Compare: "Hello" vs "hello" vs "HELLO"'
"""
from common.logger import get_logger
import tiktoken as tk

logger = get_logger(__file__)

def compare_different_hellos() -> None:
    """
    Compare differently cased hellos and print their token details
    :return: Returns None. But prints comparison report for  "Hello" vs "hello" vs "HELLO"
    """
    list_of_hellos = ["Hello", "hello", "HELLO"]

    encoding = tk.encoding_for_model("gpt-4o")
    for hello in list_of_hellos:
        tokens = encoding.encode(hello)
        decoded_tokens = [encoding.decode([t]) for t in tokens]
        length_of_tokens = len(tokens)

        logger.info("Token reports for word %s", hello)
        logger.info("Tokens: %s", tokens)
        logger.info("Decoded tokens as text: %s", decoded_tokens)
        logger.info("Total tokens: %s", length_of_tokens)
        logger.info("-" * 100)

if __name__ == "__main__":
    compare_different_hellos()