# Topic 03: Retrieval Basics (Day 5)

## Status: Covered in Prior Experiments

Most Day 5 objectives were already completed during Day 3-4 indexing experiments:

| Objective | Where Covered |
|-----------|---------------|
| ChromaDB query parameters (`n_results`, `where`, `where_document`) | `exp_01_chroma_crud.py` |
| Simple retrieval function | `query_chroma_store()` |
| Different top-k values | Tested with `n_results=1, 3` |

## Remaining Gaps → Covered in Day 6

- **Similarity scores** — Will add `include=["distances"]` in `SimpleRAG`
- **Score thresholds for relevance** — Will implement in `SimpleRAG.query()`

No separate experiments here. Moving directly to Day 6 mini-challenge.