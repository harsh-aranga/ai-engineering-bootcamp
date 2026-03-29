"""
This script corresponds to Day 1-2->Day 1->Hour 2->Experiment->
Implement a simple retry with tenacity — test by simulating failures
"""

from typing import Literal
from openai.types.responses import Response

import sys
import random
import logging

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key=open_ai_key)


# --- Custom transient exception for testing retry ---
class TransientOpenAIError(Exception):
    pass


@retry(
    stop=stop_after_attempt(4),  # total attempts = 4
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(TransientOpenAIError),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_openai_gpt_response(prompt: str, model: str = "gpt-5.4-mini") -> Response | None:
    """
    Takes a prompt and model. Returns the response
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """
    logger.info("Entering retry enabled function")
    random_value = random.random()
    logger.info(f"Random value: {random_value}")
    try:
        # --- Simulate failure (remove after testing) ---
        if random_value < 0.9:
            logger.info("Simulating transient failure...")
            raise TransientOpenAIError("Fake failure to trigger retry")

        response = openai_client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=300,
            temperature=1
        )

        if response is not None:
            logger.info(f"Response created successfully: {response.output_text}")
            dump_json(response.model_dump(), "This worked within random")
            return response

    except TransientOpenAIError:
        # Let tenacity catch and retry
        raise

    except Exception as e:
        logger.error("Non-retryable error %s", e)
        return None


if __name__ == "__main__":
    try:
        result = generate_openai_gpt_response("Explain retries in distributed systems briefly.")
    except Exception as e:
        logger.error("Failed after retries:", str(e))