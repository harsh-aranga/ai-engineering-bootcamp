"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment 3->'Tokenize a paragraph in English, then same meaning in Hindi or another language'
"""

from common.logger import get_logger
import tiktoken as tk

logger = get_logger(__file__)

def create_token_reports_text(text: str) -> None:
    """
    Prints token reports for the given text. Prints token list, decoded token list and length of token list.
    :param text: Text on which the report is to be created.
    :return: Returns None
    """

    encoding = tk.encoding_for_model("gpt-4o")
    tokens = encoding.encode(text)
    decoded_tokens = [encoding.decode([t]) for t in tokens]
    logger.info("Text in concern: %s", text)
    logger.info("Tokens in text: %s", tokens)
    logger.info("Decoded tokens as text: %s", decoded_tokens)
    logger.info("Total tokens: %s", len(tokens))
    logger.info("-" * 100)


if __name__ == "__main__":
    english_text = """
    Tokenization is a fundamental step in natural language processing, where text is broken down into smaller units called tokens. These tokens may represent words, subwords, or even individual characters depending on the encoding strategy used. Different tokenization approaches can significantly impact how efficiently a model processes input, affecting both cost and performance. Understanding how text is split helps in designing better prompts and optimizing context usage.

In modern language models, tokenization is often based on subword algorithms such as Byte Pair Encoding (BPE) or unigram language models. This allows models to handle rare words and variations more effectively by decomposing them into smaller known units. However, this also means that seemingly simple sentences can result in a higher token count than expected. Experimenting with tokenization helps developers gain intuition about input structure and model behavior.
"""

    chinese_text = """
    分词是自然语言处理中的基础步骤，它将文本拆分为更小的单位，这些单位称为“标记”（token）。根据所使用的编码策略，这些标记可以是单词、子词，甚至是单个字符。不同的分词方式会显著影响模型处理输入的效率，从而影响成本和性能。理解文本是如何被拆分的，有助于设计更好的提示词并优化上下文的使用。

在现代语言模型中，分词通常基于子词算法，例如字节对编码（BPE）或单词概率模型。这使模型能够更有效地处理罕见词和各种词形变化，因为它们可以被拆分为更小的已知单位。然而，这也意味着看似简单的句子可能会产生比预期更多的标记。通过进行分词实验，开发者可以更直观地理解输入结构和模型行为。"""

    create_token_reports_text(english_text)
    create_token_reports_text(chinese_text)