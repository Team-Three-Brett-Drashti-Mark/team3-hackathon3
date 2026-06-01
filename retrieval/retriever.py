import re
import logging
from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

_INDEX_NAME = "capstone.vector_layer.curriculum_semantic_index"
_COLUMNS = ["text"]


def _parse_metadata(text: str) -> dict:
    """Extract week and topic from the embedded text header.

    Chunks are prefixed with lines like:
        Document: summer10-strings-nup
        Week: week_01
        Section: ## Syntax
    """
    week = topic = None
    for line in text.splitlines():
        if line.startswith("Week:") and not week:
            week = line.split(":", 1)[1].strip()
        elif line.startswith("Section:") and not topic:
            topic = re.sub(r"^#+\s*", "", line.split(":", 1)[1].strip())
        elif line.startswith("Document:") and not topic:
            topic = line.split(":", 1)[1].strip()
        if "---" in line:
            break
    return {"week": week, "topic": topic}


def retrieve(query: str, k: int = 3) -> list[dict]:
    """Return the top-k curriculum chunks most relevant to query.

    Each chunk is a dict with keys: text, week, topic.

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
            columns=_COLUMNS,
            num_results=k,
        )
        rows = results.as_dict().get("result", {}).get("data_array", [])
        return [
            {"text": row[0], **_parse_metadata(row[0])}
            for row in rows if row
        ]
    except Exception as e:
        logger.warning("Vector search retrieval failed: %s", e)
        return []
