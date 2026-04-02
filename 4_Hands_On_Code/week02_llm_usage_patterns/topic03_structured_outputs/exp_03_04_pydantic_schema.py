"""
This script corresponds to Day 5-6->Day 1->Hour 2->Experiment->
3. Define a simple Pydantic model (e.g., Person with name, age, city)
4. Use structured outputs with your Pydantic schema — see strict enforcement
"""
from typing import Literal



from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from pydantic import BaseModel
from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError, AuthenticationError, APIError
from openai.types.responses import Response, ParsedResponse

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key=open_ai_key)

class Person(BaseModel):
    name:str
    age:int
    gender: Literal["male", "female", "other"]
    email:str | None = None
    phone:str | None = None

class PersonList(BaseModel):
    people: list[Person]


def generate_openai_gpt_person_json(prompt: str, model: str = "gpt-5.4-mini") -> ParsedResponse | None:
    """
    Takes a prompt and model. Returns the response
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """

    try:
        response = openai_client.responses.parse(
            model=model,
            input=prompt,
            max_output_tokens=300,
            temperature=0.5,
            text_format=PersonList
        )

        if response is not None:
            logger.info("Response created successfully")
            dump_json(response.model_dump(), "GPT Response For Run")
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

    response = generate_openai_gpt_person_json(prompt=prompt)
    logger.info(f"JSON Response: {response.output_parsed}")
    dump_json(response.output_parsed.model_dump(), "just the parsed content")

if __name__ == "__main__":
    json_requester("Give me 5 sample persons")