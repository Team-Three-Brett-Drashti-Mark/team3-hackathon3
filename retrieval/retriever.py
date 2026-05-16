import logging
from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

_INDEX_NAME = "capstone.vector_layer.curriculum_semantic_index"


def retrieve(query: str, k: int = 3) -> list[str]:
    """Return the top-k curriculum text chunks most relevant to query.

    Auth is resolved by the Databricks SDK credential chain:
      1. DATABRICKS_HOST + DATABRICKS_TOKEN env vars (recommended for deployment)
      2. DATABRICKS_CONFIG_PROFILE env var pointing to a ~/.databrickscfg profile
      3. Default profile in ~/.databrickscfg

    Returns an empty list on failure so the LLM still responds, just without
    retrieved context. Check logs for auth or network errors.
    """
    try:
        w = WorkspaceClient()
        results = w.vector_search_indexes.query_index(
            index_name=_INDEX_NAME,
            query_text=query,
            columns=["text"],
            num_results=k,
        )
        rows = results.as_dict().get("result", {}).get("data_array", [])
        return [row[0] for row in rows if row]
    except Exception as e:
        logger.warning("Vector search retrieval failed: %s", e)
        return []
