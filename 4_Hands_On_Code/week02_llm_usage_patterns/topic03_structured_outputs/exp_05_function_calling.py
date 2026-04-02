"""
This script corresponds to Day 5-6->Day 1->Hour 2->Experiment->
3. Define a simple Pydantic model (e.g., Person with name, age, city)
4. Use structured outputs with your Pydantic schema — see strict enforcement
"""
import json
from typing import Literal



from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from pydantic import BaseModel, Field, ConfigDict
from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError, AuthenticationError, APIError, \
    pydantic_function_tool
from openai.types.responses import Response, ParsedResponse

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key=open_ai_key)

tool_1 = {
        "type": "function",
        "name": "extract_person",
        "description": "Extract person information from text",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The person's full name"
                },
                "age": {
                    "type": "integer",
                    "description": "The person's age in years"
                },
                "gender": {
                    "type": "string",
                    "enum": ["male", "female", "other"],
                    "description": "The gender of the person"
                },
                "email": {
                    "type": "string",
                    "description": "The email of the person"
                },
                "phone": {
                    "type": "string",
                    "description": "The contact number of the person"
                }
            },
            "required": ["name", "age", "gender", "email", "phone"],
            "additionalProperties": False
        },
        "strict": True  # Enable schema enforcement
    }

class GetWeather(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city_name:str = Field(description="Name of the city for which the weather must be obtained")
    unit:Literal["Celsius", "Fahrenheit"] = Field(description="The metric to be used to denote weather.")

tool_2 = {
    "type": "function",
    "name": "get_weather",
    "description": "Get weather for a city",
    "parameters": GetWeather.model_json_schema(),
    "strict": True
}

tools = [tool_1, tool_2]

def generate_openai_gpt_function_calling(prompt: str, model: str = "gpt-5.4-mini") -> Response | None:
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
            tools=tools,
            tool_choice="required"
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
    response = generate_openai_gpt_function_calling(prompt=prompt)
    logger.info(f"JSON Response: {json.loads(response.output[0].arguments)}")

if __name__ == "__main__":
    # json_requester("Extract the person from this: My friend Jackie is 32 years old, male, jackie@email.com")
    json_requester("Get me the weather for tokyo")
    json_requester("Get me the weather for san francisco")