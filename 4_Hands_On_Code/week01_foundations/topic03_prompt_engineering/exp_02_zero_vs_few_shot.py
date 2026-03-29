"""
This script corresponds to Day 5-6->Day 5->Hour 2->Experiment->

Zero-shot vs. Few-shot:

Ask model to classify sentiment without examples
Then provide 3 examples first, ask again
Compare accuracy
"""
from typing import Literal
from openai.types.responses import Response

import sys

from common.logger import get_logger
from common.config import get_config

from openai import OpenAI

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
            max_output_tokens=100,
            temperature=0
        )

        if response is not None:
            return response
    except Exception as e:
        logger.error("Error %s", e)
        return None


def execute_zero_or_few_shot_prompt_and_print_results(sentences: list[tuple[str, str]],
                                                      prompt_type: Literal["few", "zero"] = "zero") -> None:
    """
    This method executes zero shot or few shot prompting on the sentences and prints results.
    :param prompt_type: Takes values 'few' or 'zero'. Selects prompt accordingly.
    :param sentences: Tuple that contains sentences and their correct sentiment classification. values negative, neutral and positive
    :return: None
    """
    correctness_counter = 0
    logger.info("Executing classification with %s shot prompting", prompt_type)
    for sentence, correct_classification in sentences:
        if prompt_type == "zero":
            prompt = f"""
                    Classify the sentiment of this statement.

                    Reply with ONLY one word:
                    positive, negative, or neutral.

                    Statement: {sentence}
                    """
        else:
            prompt = f"""
                    Classify the sentiment of this statement.
            
                    Reply with ONLY one word:
                    positive, negative, or neutral.
                    
                    Examples:
                    "I’ve seen worse." → positive
                    "It’s not bad." → neutral
                    "The design is great but performance is terrible." → negative
                    "Great, another delay." → negative
                    "It does the job." → neutral
            
            
                    Now classify Statement: {sentence}
                    """

        llm_response = generate_openai_gpt_response(prompt)
        if llm_response is None:
            logger.error("No llm response returned. Sentence %s classification skipped", sentence)
            continue

        classification = llm_response.output_text.strip().lower()

        if classification is None:
            logger.info("Error obtaining classification. Exiting")
            break

        if classification == correct_classification:
            correctness_counter += 1
            logger.info("Correct classification by LLM.")
        else:
            logger.info("Incorrect classification by LLM.")

        logger.info("Sentence: %s", sentence)
        logger.info("Correct Classification: %s", correct_classification)
        logger.info("Classification by LLM: %s", classification)
        logger.info("-" * 150)

    logger.info("Total correct classifications this %s run is %d out of %d sentences.",
                prompt_type,
                correctness_counter,
                len(sentences))


def zero_vs_few_shot_orchestrator(prompt_type: Literal["few", "zero"] = "zero") -> None:
    """
    Just an orchestrator for this script
    :param prompt_type: Takes values 'few' or 'zero'.
    :return: None
    """
    sentences = [
        ("Yeah, because waiting in line for 3 hours is exactly my idea of fun.", "negative"),
        ("It’s not bad, I guess.", "neutral"),
        ("The UI looks great, but it crashes every time.", "negative"),
        ("I’ve seen worse.", "positive"),
        ("Wow, another update that fixes nothing. Amazing.", "negative"),
        ("It does the job.", "neutral"),
        ("Honestly, I expected it to be terrible, but it’s okay.", "positive"),
        ("The battery lasts 3 hours.", "neutral"),
        ("Nice work breaking something that was already working.", "negative"),
        ("It’s fine if you don’t mind constant bugs.", "negative"),
    ]

    execute_zero_or_few_shot_prompt_and_print_results(sentences, prompt_type)


if __name__ == "__main__":
    prompt_type = sys.argv[1] if len(sys.argv) > 2 else "zero"

    if prompt_type not in ("zero", "few"):
        logger.error("Invalid prompt type: %s", prompt_type)
        sys.exit(1)

    zero_vs_few_shot_orchestrator(prompt_type)
