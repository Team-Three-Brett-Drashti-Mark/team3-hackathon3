import json
import os
import re
import logging
from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)


def _workspace_client() -> WorkspaceClient:
    """Build a WorkspaceClient that works both in a Databricks App and locally.

    In a Databricks App the runtime injects BOTH a PAT (DATABRICKS_TOKEN) and the
    app service principal's OAuth creds (DATABRICKS_CLIENT_ID/SECRET). With both
    present the SDK refuses to choose — it raises "validate: more than one
    authorization method configured: oauth and pat" — and EVERY query_index call
    throws. Because retrieve() swallows that exception and returns [], the
    deployed app silently lost all curriculum grounding. Pinning auth_type="pat"
    resolves the ambiguity, matching how app/admin.py builds its client.

    Locally (and in unit tests) there's no DATABRICKS_TOKEN, so we fall back to
    the default SDK credential chain, letting a ~/.databrickscfg profile work.
    """
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    if host and token:
        return WorkspaceClient(host=host, token=token, auth_type="pat")
    return WorkspaceClient()

_INDEX_NAME = "capstone.vector_layer.curriculum_semantic_index"

# We select BOTH the embedded text and the `metadata` sidecar column.
#
# Why metadata is non-negotiable: the index's `text` column holds the CLEAN
# chunk body (silver's raw_content) with NO "Document:/Week:/Section:" header,
# so there is nothing in `text` to parse week/topic out of. The only reliable
# source of attribution is the `metadata` JSON column the silver→vector sync
# writes alongside each chunk. Before this column was selected, every chunk
# came back with week=None/topic=None, the prompt's citation header was always
# blank, and the LLM fabricated references ("Week 3, Topic 5") to fill the gap.
_COLUMNS = ["text", "metadata"]


def _parse_metadata(metadata_json: str | None) -> dict:
    """Extract week and topic from the chunk's `metadata` JSON column.

    The vector store's `metadata` column is a JSON string written by the
    silver→vector sync, e.g.::

        {"doc_title": "intro_to_strings", "week": "week_01",
         "topic": "intro_to_strings", "section_title": "## What is a String?",
         "content_type": "markdown", ...}

    We surface just week and topic for prompt attribution. Parsing is
    deliberately defensive — a missing or malformed blob degrades to
    {"week": None, "topic": None} rather than raising, because the chunk's TEXT
    is still useful grounding even when we can't label which week it came from.
    Dropping the whole chunk over a bad metadata string would be the wrong
    trade.

    Topic preference mirrors the original header-parsing logic: the section
    heading is the most specific human label, so prefer it (stripped of its
    leading markdown ``#`` characters), then fall back to the explicit `topic`
    field, then the `doc_title`.
    """
    if not metadata_json:
        return {"week": None, "topic": None}
    try:
        meta = json.loads(metadata_json)
    except (ValueError, TypeError):
        # Not valid JSON — treat as unattributed rather than crashing retrieval.
        return {"week": None, "topic": None}

    topic = None
    section = meta.get("section_title")
    # "PDF Content" is the generic placeholder the PDF chunker writes as
    # section_title (PDFs have no heading structure to split on), so it's a
    # useless citation label — skip it and let PDF chunks attribute to their
    # doc_title instead. Real markdown section headings ("## Slicing") are kept.
    if section and section.strip() != "PDF Content":
        topic = re.sub(r"^#+\s*", "", section).strip()
    if not topic:
        topic = meta.get("topic") or meta.get("doc_title")

    return {"week": meta.get("week"), "topic": topic}


def retrieve(query: str, k: int = 3) -> list[dict]:
    """Return the top-k curriculum chunks most relevant to query.

    Each chunk is a dict with keys: text, week, topic, score.

    `score` is the index's relevance score (higher = closer match) and is
    surfaced — not just consumed internally — so callers can GATE on it. Vector
    search always returns the k nearest neighbors, even for a question with no
    real curriculum match (e.g. recursion when only week_01 strings is loaded):
    those come back at a low score (~0.5) versus ~0.65+ for a genuine hit.
    Exposing the score lets retrieve_context drop weak matches instead of
    letting the LLM treat an irrelevant chunk as grounding and confabulate
    around it.

    Auth is resolved by the Databricks SDK credential chain:
      1. DATABRICKS_HOST + DATABRICKS_TOKEN env vars (recommended for deployment)
      2. DATABRICKS_CONFIG_PROFILE env var pointing to a ~/.databrickscfg profile
      3. Default profile in ~/.databrickscfg

    Returns an empty list on failure so the LLM still responds, just without
    retrieved context. Check logs for auth or network errors.
    """
    try:
        w = _workspace_client()
        results = w.vector_search_indexes.query_index(
            index_name=_INDEX_NAME,
            query_text=query,
            columns=_COLUMNS,
            num_results=k,
        )
        rows = results.as_dict().get("result", {}).get("data_array", [])
        # Each row is [text, metadata_json, score]: the requested columns in
        # _COLUMNS order, with the index's relevance score always appended last.
        chunks = []
        for row in rows:
            if not row:
                continue
            text = row[0]
            metadata_json = row[1] if len(row) >= 3 else None
            score = row[-1]
            chunks.append({
                "text": text,
                **_parse_metadata(metadata_json),
                "score": score,
            })
        return chunks
    except Exception as e:
        logger.warning("Vector search retrieval failed: %s", e)
        return []
