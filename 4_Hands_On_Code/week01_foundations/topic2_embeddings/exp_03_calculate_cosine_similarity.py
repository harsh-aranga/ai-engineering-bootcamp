"""
This script corresponds to Day 3-4->Day 1->Hour 2->Experiments->
Calculate cosine similarity between all pairs
Verify: similar meanings = high similarity, different meanings = low similarity
"""
from openai.types import CreateEmbeddingResponse, Embedding

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key = open_ai_key)

def generate_embeddings_in_batches(text: list[str],
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

def generate_embeddings_for_texts(text_list: list[str], dump_message: str, embedding_model: str | None = None) -> list[Embedding] | None:
    """
    For a given list of text passed, this method either prints the embedding response on success or prints error if embedding failed
    :param dump_message: A utility parameter to name the json dumps accordingly
    :param embedding_model: model to use for creating embeddings
    :param text_list: list of texts for which embeddings are to be generated
    :return: list[Embedding] or None
    """
    if not embedding_model:
        logger.warning("Embedding model not sent. Defaulting to 'text-embedding-3-small'")

    embedding_response_list = generate_embeddings_in_batches(text_list, embedding_model)

    if embedding_response_list:
        dump_json(embedding_response_list.model_dump(), dump_message)
        return embedding_response_list.data
    else:
        return None

def calculate_cosine_similarity_within_list(embedding_list: list[Embedding], original_list: list[str]) -> None:
    """
    This method calculates the cosine similarity among the members of a single list and prints the report.
    :param original_list: the original list of natural language text
    :param embedding_list: the list whose embedding are to be compared.
    :return: None
    """
    embeddings = [item.embedding for item in embedding_list]
    embeddings_np = [np.array(e) for e in embeddings]

    for i in range(0, len(embeddings_np)):
        for j in range(i + 1, len(embeddings_np)):
            similarity = cosine_similarity([embeddings_np[i]], [embeddings_np[j]])[0][0]
            logger.info("Similarity between statements <<%s>> and <<%s>> is %.4f", original_list[i], original_list[j], similarity)

    return None

def calculate_cosine_similarity_between_lists(embedding_list_1: list[Embedding], embedding_list_2: list[Embedding],
                                              original_list_1: list[str], original_list_2: list[str]) -> None:
    """
    This method calculates the cosine similarity between members of two lists and prints the report.
    :param original_list_1: the original list 1 of natural language text
    :param original_list_2: the original list 2 of natural language text
    :param embedding_list_1: the first list containing embedding objects
    :param embedding_list_2: the second list containing embedding objects
    :return: None
    """
    embeddings_1 = [item.embedding for item in embedding_list_1]
    embeddings_np_1 = [np.array(e) for e in embeddings_1]

    embeddings_2 = [item.embedding for item in embedding_list_2]
    embeddings_np_2 = [np.array(e) for e in embeddings_2]

    for i in range(0, len(embeddings_np_1)):
        for j in range(0, len(embeddings_np_2)):
            similarity = cosine_similarity([embeddings_np_1[i]], [embeddings_np_2[j]])[0][0]
            logger.info("Similarity between statements <<%s>> and <<%s>> is %.4f", original_list_1[i], original_list_2[j],
                        similarity)

    return None

def cosine_similarity_orchestrator():
    similar_sentences = [
        "The weather is nice today.",
        "It's a beautiful day outside.",
        "The weather feels really pleasant.",
        "Such a lovely day today.",
        "The day is bright and enjoyable."
    ]

    dissimilar_sentences = [
        "May the Force be with you.",
        "I'll be back.",
        "I think, therefore I am.",
        "To be or not to be.",
        "Stay hungry, stay foolish."
    ]

    logger.info("STARTING COSINE SIMILARITY FOR SIMILAR STATEMENTS")
    similar_embedding_list = generate_embeddings_for_texts(similar_sentences, "Similar Sentences")
    calculate_cosine_similarity_within_list(similar_embedding_list, similar_sentences)
    logger.info("-" * 150)

    logger.info("STARTING COSINE SIMILARITY FOR DISSIMILAR STATEMENTS")
    dissimilar_embedding_list = generate_embeddings_for_texts(dissimilar_sentences, "Dissimilar Sentences")
    calculate_cosine_similarity_within_list(dissimilar_embedding_list, dissimilar_sentences)
    logger.info("-" * 150)

    logger.info("STARTING COSINE SIMILARITY BETWEEN SIMILAR & DISSIMILAR STATEMENTS")
    calculate_cosine_similarity_between_lists(similar_embedding_list, dissimilar_embedding_list, similar_sentences, dissimilar_sentences)
    logger.info("-" * 150)

if __name__ == "__main__":
    cosine_similarity_orchestrator()