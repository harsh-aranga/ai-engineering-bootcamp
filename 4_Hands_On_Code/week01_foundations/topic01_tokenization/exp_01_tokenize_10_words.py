"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment 1->"Tokenize 10 different sentences — predict count first, then verify"
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
    test_sentence_list = [
    "The cat didn't sat on the mat.",
    "Artificial intelligence is transforming the world rapidly.",
    "I had coffee this morning and it tasted great.",
    "Distributed systems fail in unexpected ways under load.",
    "He quickly realized that something was seriously wrong.",
    "OpenAI builds powerful models for language understanding.",
    "My name is Harshavardhanan and I love system design.",
    "The quick brown fox jumps over the lazy dog.",
    "Tokenization depends on frequency and subword patterns.",
    "This is a simple test sentence for counting tokens."
    ]

    tokenize_list_of_sentences(sentences_list = test_sentence_list)