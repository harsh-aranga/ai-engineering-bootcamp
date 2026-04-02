"""
This script corresponds to Day 5-6->Day 1->Hour 2->Experiment->
Same call WITH JSON mode. Compare reliability.
"""
from openai.types.responses import Response

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError, AuthenticationError, APIError

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key=open_ai_key)


def generate_openai_gpt_response(prompt: str, model: str = "gpt-5.4-mini") -> Response | None:
    """
    Takes a prompt and model. Returns the response
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """

    try:
        response = openai_client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=300,
            temperature=0.5,
            text={
                "format": {
                    "type": "json_object"
                }
            }
        )

        if response is not None:
            logger.info("Response created successfully")
            return response

    except RateLimitError as e:
        logger.exception("Rate limit hit")
    except APIConnectionError as e:
        logger.exception("Network/API connection issue")
    except BadRequestError as e:
        logger.exception("Bad request: prompt/model/params issue")
    except AuthenticationError as e:
        logger.exception("Invalid API key")
    except APIError as e:
        logger.exception("OpenAI server/API error")
    except Exception as e:
        logger.exception("Unexpected failure")

    return None


def json_requester(prompt:str, model:str="gpt-5.4-mini") -> None:
    """
    Prints output of LLM for prompt
    :param prompt:
    :param model:
    :return: None
    """

    response = generate_openai_gpt_response(prompt=prompt)
    logger.info(f"JSON Response: {response.output_text}")
    dump_json(response.output_text, "with json mode")

if __name__ == "__main__":
    json_requester("Give me weather of five cities in json format.")