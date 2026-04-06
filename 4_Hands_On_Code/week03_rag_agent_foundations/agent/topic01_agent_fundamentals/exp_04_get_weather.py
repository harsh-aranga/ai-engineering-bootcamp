"""
This script corresponds to Day 5-6->Day 2->Hour 2->Experiments->
1. Using OpenAI playground or API, define a simple function (e.g., get_weather(city))
2. Ask the model a question that requires the function
3. See how the model responds — it doesn't call the function, it tells you it WANTS to call it
4. Understand: You (the code) actually execute the function and feed results back

Note: Though it asks to use OpenAI Playground, I am going to write my own code to do this.
"""
import json
from typing import Literal, Any, Iterable

from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError, AuthenticationError, APIError, \
    pydantic_function_tool
from openai.types.responses import Response, FunctionToolParam, ResponseFunctionToolCall
from pydantic import BaseModel, Field, ConfigDict

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")

openai_client = OpenAI(api_key=open_ai_key)

class GetWeather(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city_name:str = Field(description="Name of the city for which the weather must be obtained")
    unit:Literal["Celsius", "Fahrenheit"] = Field(description="The metric to be used to denote weather.")

tool_1 = {
    "type": "function",
    "name": "get_weather",
    "description": "Get weather for a city",
    "parameters": GetWeather.model_json_schema(),
    "strict": True
}

# tool_1 = pydantic_function_tool(GetWeather, name="get_weather", description="Get weather for a city")

def get_weather(city_name:str, unit:Literal["Celsius", "Fahrenheit"]) -> str:
    return "40 degrees Celsius"

def generate_openai_gpt_tool_calling(prompt: str, tools:Iterable[FunctionToolParam] | None = None,
                                     model: str = "gpt-5.4-mini") -> Response | None:
    """
    Takes a prompt and model. Returns the response
    :param tools: Tools used
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

# noinspection PyTypeChecker
def submit_tool_output(call_id: str, tool_output: str, previous_response_id:str, model: str = "gpt-5.4-mini") -> Response:
    """
    Just for submitting tool outputs
    :param previous_response_id:
    :param call_id:
    :param tool_output:
    :param model:
    :return:
    """
    return openai_client.responses.create(
        previous_response_id=previous_response_id,
        model=model,
        input=[
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": tool_output
            }
        ]
    )

def execute_tool(item:ResponseFunctionToolCall) -> str:
    if item.name == "get_weather":
        tool_args = json.loads(item.arguments)
        return get_weather(**tool_args)
    else:
        raise ValueError("Tool not found")

def tool_call_orchestrator(prompt:str, model:str="gpt-5.4-mini") -> None:
    """
    Prints output of LLM for prompt
    :param prompt:
    :param model:
    :return: None
    """
    tools = [tool_1]
    response = generate_openai_gpt_tool_calling(prompt=prompt, tools=tools)
    dump_json(response.model_dump(), "GPT Response For Run")
    logger.info(f"JSON Response: {response.output[0].to_dict()}")
    for item in response.output:
        if item.type == "function_call":
            tool_response = execute_tool(item)
            response = submit_tool_output(item.call_id, tool_response, previous_response_id=response.id)
            dump_json(response.model_dump(), "Final response from gpt")
            logger.info(f"Response for user: {response.output_text}")
        elif item.type == "message":
            logger.info(f"Answer from llm: {item.to_dict()}")

if __name__ == "__main__":
    tool_call_orchestrator("Get me the weather for tokyo")