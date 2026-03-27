"""
This script corresponds to Day 1-2->Day 2->Hour 1->Mini Challenge->
Build a Python function that:

Input: A string + model name
Output: Token count, estimated cost (input), warning if > 50% of context window
Success Criteria:

Correctly counts tokens for GPT-4o (o200k_base encoding)
Correctly counts tokens for GPT-3.5 (cl100k_base encoding)
Returns accurate cost estimate (use current pricing: GPT-4o ~$2.50/1M input tokens)
Warns when input exceeds 50% of context window (GPT-4o = 128K context)
Handles empty string, very long string (10K+ chars), and non-English text without crashing

NOTE: This program uses old models supported by tiktoken deliberately.
The goal is to understand token-economics and build a simple calculator
"""

from common.logger import get_logger
import tiktoken as tk

logger = get_logger(__file__)

MODEL_METADATA = {
    "gpt-4o": {
        "encoding": "o200k_base",
        "context_window_size": 128_000,
        "input_cost_per_million": 2.5
    },
    "gpt-3.5-turbo": {
        "encoding": "cl100k_base",
        "context_window_size": 16_000,
        "input_cost_per_million": 0.50
    }
}

def get_encoder(model_name: str) -> tk.Encoding:
    """
    Returns an encoder based on the model supplied.
    :param model_name: Model to be used. Supported for now "gpt-4o" and "gpt-3.5-turbo"
    :return: Encoding object of the model.
    """
    try:
        return tk.encoding_for_model(model_name)
    except KeyError:
        logger.warning("Unknown model supplied: %s. Falling back to default model: gpt-4o")
        return tk.encoding_for_model("gpt-4o")

def get_model_details(model_name: str) -> dict:
    """
    Get model metadata from stored constant dictionary of models.
    :param model_name: Model to be used. Supported for now "gpt-4o" and "gpt-3.5-turbo"
    :return: dictionary of model metadata containing "encoding", "context_window_size" and "input_cost_per_million"
    """
    model_details = MODEL_METADATA.get(model_name)

    if not model_details:
        logger.warning("Unknown model supplied: %s. Fetching details for default model: gpt-4o", model_name)
        model_details = MODEL_METADATA.get("gpt-4o")

    return model_details

def output_tokenomics_report(text: str, model_name: str) -> None:
    """
    This method will take in a text and model as input.
    Based on the model, it will create an appropriate encoder.
    It will use said encoder to calculate and output the following
    token_count: Total token cost of text
    estimated_cost: input token cost incurred wrt to the model
    warning: True/False, True if text is 50% greater than context window. Else False
    :param text: Text to be tokenized.
    :param model_name: Model to be used. Supported for now "gpt-4o" and "gpt-3.5-turbo"
    :return:
    """
    model_details = get_model_details(model_name)
    encoding = get_encoder(model_name)

    tokens = encoding.encode(text)
    decoded_tokens = [encoding.decode([t]) for t in tokens]
    token_length = len(tokens)
    cost = (token_length / 1_000_000) * model_details.get("input_cost_per_million")
    context_window_used_in_percentage = (token_length / model_details.get("context_window_size")) * 100

    logger.info("Text in concern: %s", text)
    logger.info("Tokens in text: %s", tokens)
    logger.info("Decoded tokens as text: %s", decoded_tokens)
    logger.info("Total tokens: %s", token_length)
    logger.info("Total cost for input text: %s", cost)

    if context_window_used_in_percentage > 50:
        logger.warning("Exceeded context window size by 50%. Optimization to be considered")
    else:
        logger.info("Well within context window limits. Used %s percentage of context window", context_window_used_in_percentage)
    logger.info("-" * 100)

if __name__ == "__main__":
    org_text = """I'm going to make him an offer he can't refuse. It's not personal, it's strictly business. A man who doesn't spend time with his family can never be a real man. Great men are not born great, they grow great. Friendship is everything. Friendship is more than talent. It is more than the government. It is almost the equal of family."""

    simplified_chinese_text = """我会给他一个无法拒绝的条件。这不是私人恩怨，这是纯粹的生意。不花时间陪伴家人的男人，永远不可能成为真正的男人。伟大的人不是天生的，而是在成长中变得伟大。友谊就是一切。友谊比天赋更重要。它比政府更重要。它几乎可以与家庭相提并论。"""

    empty_string = ""
    forty_six_whitespace_filled_string = "                                              "

    output_tokenomics_report(text = forty_six_whitespace_filled_string, model_name="gpt-4o")