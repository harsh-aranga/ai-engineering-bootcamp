"""
This script corresponds to Day 1-2->Day 2->Hour 1->Mini Challenge->
Build a function robust_response() that:

def robust_response(
    input: str | list[dict],
    model: str = "gpt-4o-mini",
    instructions: str | None = None,
    stream: bool = False,
    max_retries: int = 3
) -> dict | Generator:
    ```
    Makes a Responses API call with:
    - Automatic retries with exponential backoff for transient errors
    - Proper handling of rate limits (wait and retry)
    - Timeout handling
    - Streaming support
    - Returns structured response with content + usage stats
    ```
    pass
Success Criteria:
Retries on 429 (rate limit) with exponential backoff
Retries on 500/502/503 (server errors) up to max_retries
Does NOT retry on 400 (bad request) — that's your bug, not transient
Streaming mode yields chunks as they arrive
Non-streaming mode returns: {"content": "...", "usage": {...}, "status": "...", "id": "..."}
Logs retries so you know when they happen
Has a timeout (30 seconds default) — doesn't hang forever
Tested with at least 3 scenarios: success, simulated retry, simulated failure
"""

from typing import Any

from tenacity import Retrying, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

import logging

from openai import OpenAI, APIStatusError, RateLimitError

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key=open_ai_key,  timeout=30.0)


def is_retryable_error(exception: BaseException) -> bool:
    """Returns True for transient errors that warrant a retry."""
    if isinstance(exception, RateLimitError):
        return True
    if isinstance(exception, APIStatusError):
        return exception.status_code in (500, 502, 503)
    return False


def get_final_response(content: str, usage: dict[str, Any] | None) -> dict[str, Any]:
    """
    Returns a formated dictionary of content and usage
    :param content: The response from LLM
    :param usage: The usage stats
    :return: dict[str, Any]
    """
    return {
        "content": content,
        "usage": usage
    }


def robust_response(input: str | list[dict],
                    model: str = "gpt-5.4-mini",
                    instructions: str | None = None,
                    stream: bool = False,
                    max_retries: int = 3) -> dict | None:
    """
    Makes a Responses API call with:
    - Automatic retries with exponential backoff for transient errors
    - Proper handling of rate limits (wait and retry)
    - Timeout handling
    - Streaming support
    - Returns structured response with content + usage stats
    :param input:
    :param model:
    :param instructions:
    :param stream:
    :param max_retries:
    :return:
    """

    retryer = Retrying(
        retry=retry_if_exception(is_retryable_error),
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )

    try:
        for attempt in retryer:
            with attempt:
                if stream:
                    return _handle_streaming(input, model, instructions)
                else:
                    return _handle_non_streaming(input, model, instructions)
    except APIStatusError as e:
        logger.error("API error (status %d): %s", e.status_code, e.message)
        return None
    except Exception:
        logger.exception("Unexpected error during API call")
        return None


def _handle_streaming(
        input: str | list[dict],
        model: str,
        instructions: str | None) -> dict[str, Any]:
    """Handles streaming response, returns assembled result."""
    content = ""

    stream = openai_client.responses.create(
        input=input,
        instructions=instructions,
        model=model,
        stream=True,
        max_output_tokens=300,
        temperature=0
    )

    for event in stream:
        if event.type == "response.output_text.delta":
            logger.info("%s", event.delta)
            content += event.delta
        elif event.type == "response.completed":
            return get_final_response(content, event.response.usage.model_dump())
        elif event.type == "response.incomplete":
            logger.warning("Incomplete response: %s", event.response.incomplete_details.reason)
            return get_final_response(content, event.response.usage.model_dump())

    # Stream ended without completed/incomplete event
    logger.warning("Stream ended unexpectedly")
    return get_final_response(content, None)


def _handle_non_streaming(
        input: str | list[dict],
        model: str,
        instructions: str | None ) -> dict[str, Any]:
    """Handles non-streaming response."""
    response = openai_client.responses.create(
        input=input,
        instructions=instructions,
        model=model,
        max_output_tokens=300,
        temperature=0
    )
    return get_final_response(response.output_text, response.usage.model_dump())

if __name__ == "__main__":
    final_response = robust_response(
        input = "What happens when our sun becomes a red giant",
        stream=True
    )

    # final_response = robust_response(
    #     input="What happens when our sun becomes a red giant"
    # )
    logger.info(f"Final response: {final_response}")
    dump_json(final_response, "Normal Response")
