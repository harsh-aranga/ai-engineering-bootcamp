"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment 5->"Find a sentence where token count surprises you — understand why"
"""

from common.logger import get_logger
import tiktoken as tk

logger = get_logger(__file__)

def calculate_token_count_using_tiktoken(sentence: str) -> None:
    """
    Calculates token count for sentences passed and prints them

    :param sentence: the sentence whose token count is to be calculated
    :return: Returns None. This method will print the token count of a sentence along with its tokens.
    """

    encoding = tk.encoding_for_model("gpt-4o")
    tokens = encoding.encode(sentence)
    decoded_tokens = [encoding.decode([t]) for t in tokens]
    logger.info("Sentence in concern: %s", sentence)
    logger.info("Tokens in sentence: %s", tokens)
    logger.info("Decoded tokens as text: %s", decoded_tokens)
    logger.info("Total tokens: %s", len(tokens))
    logger.info("-" * 100)

def tokenize_list_of_sentences(sentences_list: list[str]) -> None:
    """
    Receives a list of sentences, tokenizes them and prints count of tokens and the tokens themselves.
    :param sentences_list: List of sentences to be tokenized. eg: ["how are you?", "That's wonderful!!! What is your name?"]
    :return: Returns nothing. Prints token count and tokens
    """
    for sentence in sentences_list:
        calculate_token_count_using_tiktoken(sentence = sentence)

if __name__ == "__main__":
    # Test code to see if tokenization works
    surprise_sentences = [
        "The price is $1000000000",
        "hello      world",
        "def __init__(self, x: int) -> None:",
        "🔥🔥🔥🔥🔥",
        "https://www.example.com/search?q=tokenization&lang=en",
        "         ",
        "naïve café résumé",
        "¯\\_(ツ)_/¯",
        "GPT-4o-mini-2024-07-18",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ]

    tokenize_list_of_sentences(sentences_list = surprise_sentences)