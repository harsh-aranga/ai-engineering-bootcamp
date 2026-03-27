"""
Build a Python script that:

Input: A list of 20 sentences (you create them — mix of similar and different topics)
Output: A similarity matrix + identification of the 3 most similar pairs
Success Criteria:

Uses OpenAI text-embedding-3-small (or free alternative: sentence-transformers locally)
Correctly computes cosine similarity between all pairs
Identifies top 3 most similar pairs — and they should make semantic sense
Identifies the least similar pair — should be obviously different topics
Prints similarity scores alongside the pairs

Bonus (if time):
Visualize the 20 embeddings in 2D using UMAP or t-SNE (search: "visualize embeddings umap python")
"""
from typing import Literal

from numpy._typing import NDArray
from openai.types import CreateEmbeddingResponse, Embedding
from openai import OpenAI
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from common.logger import get_logger
from common.dumper import dump_json
from common.config import get_config

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key = open_ai_key)

def generate_embeddings_from_openai(text: list[str],
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

def generate_embeddings_for_texts(text_list: list[str], dump_message: str="Default Statements",
                                  embedding_model: str | None = None) -> list[list[float]] | None:
    """
    For a given list of text passed, this method either prints the embedding response on success or prints error if embedding failed
    :param dump_message: A utility parameter to name the json dumps accordingly
    :param embedding_model: model to use for creating embeddings
    :param text_list: list of texts for which embeddings are to be generated
    :return: list[list[float]] or None
    """
    if not embedding_model:
        logger.warning("Embedding model not sent. Defaulting to 'text-embedding-3-small'")

    embedding_response_list = generate_embeddings_from_openai(text_list, embedding_model)

    if embedding_response_list:
        dump_json(embedding_response_list.model_dump(), dump_message)
        embedding_list = [item.embedding for item in embedding_response_list.data]
        return embedding_list
    else:
        return None

def calculate_cosine_similarity_matrix(embedding_list: list[list[float]]) -> NDArray[np.float64]:
    """
    This method calculates the cosine similarity among the members of a single list and prints the report.
    :param embedding_list: the list whose embedding are to be compared.
    :return: NDArray[np.float64] - Cosine Similarity matrix of the embedding list
    """
    embeddings_array = np.array([item for item in embedding_list])
    cosine_matrix = cosine_similarity(embeddings_array)
    logger.info("\n%s", cosine_matrix)

    return cosine_matrix

def top_k_pairs_from_similarity_matrix(similarity_matrix:NDArray[np.float64],
                                       top_k: int=3,
                                       mode: Literal["similar", "dissimilar"] = "similar")-> list[tuple[float, int, int]]:
    """
    Returns the top k similar statements based on whether mode is 'similar' or 'dissimilar'
    :param similarity_matrix: The cosine similarity matrix to be used for calculating top-k
    :param top_k: The top K number to be returned from the matrix. Defaults to 3
    :param mode: If 'similar', returns top-k similar statements. If 'dissimilar', returns top-k dissimilar statements. Defaults to 'similar'
    :return: list[tuple[float, int, int]] - Float for score. Ints for statement indexes
    """
    pairs = []

    n = len(similarity_matrix)
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((similarity_matrix[i, j], i, j))

    reverse = True if mode == "similar" else False
    pairs.sort(reverse=reverse, key=lambda x: x[0])

    top_pairs = pairs[:top_k]

    return top_pairs

def cosine_similarity_matrix_orchestrator(sentence_list: list[str], top_k: int=3,
                                          mode: Literal["similar", "dissimilar"] = "similar") -> None:
    """
    The method that orchestrates the scripts. It calls in following order
    1. Calls generate_embeddings_for_texts to generate embeddings for list from openai
    2. Calls calculate_cosine_similarity_matrix to get the matrix for above embedding list
    3. Calls top_k_pairs_from_similarity_matrix to print the top 3 similar or dissimilar statements
    :param sentence_list: the natural language sentences for which the matrix is built
    :param top_k: The top K number to be returned from the matrix. Defaults to 3
    :param mode: If 'similar', returns top-k similar statements. If 'dissimilar', returns top-k dissimilar statements. Defaults to 'similar'
    :return: None
    """
    embedding_list = generate_embeddings_for_texts(text_list=sentence_list)

    if not embedding_list:
        logger.error("Error retrieving embedding list. Exiting flow")
        return None

    similarity_matrix = calculate_cosine_similarity_matrix(embedding_list)

    if similarity_matrix is None:
        logger.error("Error calculating similarity matrix. Exiting flow")
        return None

    top_k_sentences = top_k_pairs_from_similarity_matrix(similarity_matrix, top_k, mode)

    if not top_k_sentences:
        logger.error("Error getting top k sentences. Exiting flow")
        return None

    logger.info("Printing top %d statements by %s", top_k, mode)
    count = 1
    for score, i, j in top_k_sentences:
        logger.info("Top %d statement score: %.4f. Statements compared <%s> and <%s>", count, score, sentence_list[i], sentence_list[j])
        count = count + 1

    return None


if __name__ == "__main__":
    sentences = [
        "The cat sat on the mat.",
        "A cat is sitting on a mat.",
        "Dogs are running in the park.",
        "A dog plays outside in the park.",
        "I love eating pizza."
    ]

    long_list_sentences = [
        "The cat sat on the mat.",
        "A cat is sitting on a mat.",
        "Dogs are running in the park.",
        "A dog plays outside in the park.",
        "Artificial intelligence is transforming industries.",
        "AI is changing how businesses operate.",
        "The stock market crashed yesterday.",
        "Shares fell sharply in the market.",
        "I love eating pizza on weekends.",
        "Pizza is my favorite weekend food.",
        "The car engine failed suddenly.",
        "My vehicle broke down unexpectedly.",
        "He is reading a science book.",
        "She studies physics every evening.",
        "Cloud computing enables scalable systems.",
        "Distributed systems scale using cloud infrastructure.",
        "The movie was thrilling and suspenseful.",
        "It was an exciting and intense film.",
        "He is learning to play guitar.",
        "She practices music daily on her instrument."
    ]

    # cosine_similarity_matrix_orchestrator(sentences)
    # cosine_similarity_matrix_orchestrator(long_list_sentences)
    cosine_similarity_matrix_orchestrator(long_list_sentences, top_k=5, mode="similar")
    # cosine_similarity_matrix_orchestrator(long_list_sentences, top_k=5, mode="dissimilar")