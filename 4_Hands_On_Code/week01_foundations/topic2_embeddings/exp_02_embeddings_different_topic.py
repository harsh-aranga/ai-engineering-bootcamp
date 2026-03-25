"""
This script corresponds to Day 3-4->Day 1->Hour 2->Experiment->
Generate embeddings for 5 sentences about completely different topics
"""
from openai.types import CreateEmbeddingResponse

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key = open_ai_key)

def generate_embeddings(text: str,
                        embedding_model: str | None = None) -> CreateEmbeddingResponse | None:
    """
    Generates embeddings for the provided text by calling the embedding model passed.
    :param text: text to be converted into embeddings
    :param embedding_model: model to use for creating embeddings
    :return: Returns CreateEmbeddingResponse if success | None if exception
    """
    model = embedding_model or "text-embedding-3-small"

    try:
        response = openai_client.embeddings.create(
            input=text,
            model=model)
        return response
    except Exception as e:
        logger.exception("Error generating embedding")

def generate_embeddings_for_string_list(text_list: list[str], embedding_model: str | None = None) -> None:
    """
    For a given list of text passed, this method either prints the embedding response on success or prints error if embedding failed
    :param embedding_model: model to use for creating embeddings
    :param text_list: list of texts for which embeddings are to be generated
    :return: None
    """
    if not embedding_model:
        logger.warning("Embedding model not sent. Defaulting to 'text-embedding-3-small'")

    for text in text_list:
        embedding_response = generate_embeddings(text, embedding_model)
        if embedding_response is None:
            logger.error("Embedding generation failed for %s", text)
        else:
            logger.info("Embedding for text '%s' is : %s", text, embedding_response.data[0].embedding[:5])
            dump_json(embedding_response.model_dump(), f"embedding_response for {text}")

if __name__ == "__main__":
    sentences = [
        "May the Force be with you.",
        "I'll be back.",
        "I think, therefore I am.",
        "To be or not to be.",
        "Stay hungry, stay foolish."
    ]

    generate_embeddings_for_string_list(sentences)