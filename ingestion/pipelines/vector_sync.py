"""
VECTOR LAYER — Silver chunks → vector store + semantic index sync
=================================================================

Second task in the curriculum ETL DAG (see resources/curriculum_etl.yml).
Reads from the silver Delta table produced by silver_chunking.py, projects
the rows into the vector store's (id, text, metadata, created_at) shape, and
MERGEs them into the vector_store Delta table. Finally fires .sync() on the
TRIGGERED Delta Sync vector search index so the embedded copies catch up.

Why MERGE instead of overwrite:
    The original notebook used .mode("overwrite") and recreated the table
    on every run. That worked for a one-shot bootstrap but breaks the
    cascade-delete contract: deletes against the vector_store table by the
    /admin endpoint would be silently undone by the next ETL run. MERGE on
    `id` preserves cascade-delete state and is also a no-op for chunks that
    haven't changed since the previous sync.

Why we still call index.sync():
    The index is configured as `pipeline_type=TRIGGERED` in the original
    setup notebook — it doesn't auto-poll the source table. Without an
    explicit sync after the MERGE, the embedded chunks lag indefinitely.

CLI (all args optional — defaults match production):
    --catalog        Unity Catalog name (default: capstone)
    --silver-schema  Silver schema name (default: silver_layer)
    --vector-schema  Vector schema name (default: vector_layer)
    --endpoint       Vector search endpoint name (default: capstone_vector_endpoint)
    --wait-for-sync  If set, block until the index reports ONLINE_NO_PENDING_UPDATE
                     (default: false — task exits as soon as sync is dispatched)
"""

from __future__ import annotations

import argparse
import logging
import time

logger = logging.getLogger("vector_sync")


# ── Spark plumbing ───────────────────────────────────────────────────────────

def _ensure_vector_table(spark, vector_table: str) -> None:
    """
    Create the vector store Delta table on first run.

    CDC is required: the Databricks Vector Search Delta Sync index reads the
    change feed to detect inserts/updates/deletes between syncs. Without it
    the index would have to do a full re-embed on every .sync(), defeating
    the point of triggered sync.

    Schema deliberately mirrors what the original setup notebook created so
    pre-existing data (119 chunks at time of writing) merges cleanly without
    needing a table rewrite.
    """
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {vector_table} (
            id         STRING NOT NULL,
            text       STRING NOT NULL,
            metadata   STRING,
            created_at TIMESTAMP
        )
        USING DELTA
        TBLPROPERTIES (delta.enableChangeDataFeed = true)
    """)


def _project_silver_to_vector(spark, silver_table: str):
    """
    Project silver columns into the vector store schema.

    Field mapping mirrors the original notebook exactly because the silver
    chunk_id → vector id contract is what the cascade-delete endpoint
    depends on:

        chunk_id     → id          (primary key, stable)
        raw_content  → text        (clean text — what gets embedded)
        {doc_title, week, topic, content_type, section_title, concept_tags,
         chunk_index, total_chunks, source_file} → metadata (JSON string)
        current_timestamp()        → created_at

    `raw_content` (not `page_content`) is what feeds the embedder — the
    context-prefix header in page_content is useful for downstream callers
    but adds noise to vector similarity scores. See the notebook history in
    archive/ for the experiment that established this.
    """
    from pyspark.sql.functions import col, current_timestamp, struct, to_json

    return (
        spark.table(silver_table)
        .select(
            col("chunk_id").alias("id"),
            col("raw_content").alias("text"),
            to_json(struct(
                col("doc_title"),
                col("week"),
                col("topic"),
                col("content_type"),
                col("section_title"),
                col("concept_tags"),
                col("chunk_index"),
                col("total_chunks"),
                col("source_file"),
            )).alias("metadata"),
            current_timestamp().alias("created_at"),
        )
    )


def _merge_into_vector_table(spark, vector_table: str, projected_df) -> int:
    """
    MERGE the projected silver rows into the vector store table.

    Returns the count of rows in the staging view (== rows we attempted to
    merge). Note this is not the same as "rows changed" — MERGE will no-op
    on rows that are byte-identical to the existing target. That's the
    desired behavior: the CDC delta picks up only what truly changed, so the
    index sync that follows doesn't re-embed unchanged chunks.
    """
    staged = "_vector_sync_staged"
    projected_df.createOrReplaceTempView(staged)
    count = spark.table(staged).count()

    spark.sql(f"""
        MERGE INTO {vector_table} AS target
        USING {staged} AS source
        ON target.id = source.id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    return count


# ── Vector Search index sync ─────────────────────────────────────────────────

def _trigger_index_sync(endpoint_name: str, index_name: str,
                        wait_for_completion: bool, timeout_seconds: int = 600) -> str:
    """
    Fire .sync() on the TRIGGERED Delta Sync index.

    By default we return as soon as the sync request is accepted. The job's
    task duration stays bounded by the MERGE, not by the embedding pipeline,
    which can take 30-90s depending on how many chunks changed. Pass
    ``wait_for_completion=True`` from the CLI when running this manually and
    you want to know whether retrieval is "live" against the new data.

    Returns the last observed `detailed_state` from the index status — useful
    for stdout in the Databricks task log.
    """
    from databricks.vector_search.client import VectorSearchClient

    # disable_notice=True silences the SDK's "Hello! Welcome to Vector Search"
    # banner that otherwise pollutes the task driver log on every run.
    vsc = VectorSearchClient(disable_notice=True)
    index = vsc.get_index(endpoint_name=endpoint_name, index_name=index_name)
    index.sync()
    logger.info("✓ Index sync triggered: endpoint=%s index=%s",
                endpoint_name, index_name)

    if not wait_for_completion:
        return "SYNC_TRIGGERED"

    # Poll loop: TRIGGERED Delta Sync usually takes 20-60s for a small batch.
    # Cap at timeout_seconds so a hung sync doesn't pin the cluster forever.
    logger.info("Waiting for index sync to complete (timeout=%ds)...", timeout_seconds)
    deadline = time.time() + timeout_seconds
    last_status = "UNKNOWN"
    while time.time() < deadline:
        info = index.describe()
        last_status = info.get("status", {}).get("detailed_state", "UNKNOWN")
        if last_status == "ONLINE_NO_PENDING_UPDATE":
            logger.info("✓ Index sync complete: %s", last_status)
            return last_status
        logger.info("  status: %s — still syncing...", last_status)
        time.sleep(10)

    logger.warning(
        "Index sync did not reach ONLINE_NO_PENDING_UPDATE within %ds (last: %s). "
        "The sync continues in the background and will complete on its own.",
        timeout_seconds, last_status,
    )
    return last_status


# ── Top-level run() ──────────────────────────────────────────────────────────

def run(spark, catalog: str, silver_schema: str, vector_schema: str,
        endpoint_name: str, wait_for_sync: bool) -> dict:
    """
    Orchestrate the silver → vector_store → index sync flow.

    Returns a small status dict — primarily for human-readable stdout in the
    job log. Not consumed programmatically by anything yet, but stable enough
    that a future task could depend on it via task_values.
    """
    silver_table = f"{catalog}.{silver_schema}.curriculum_chunks"
    vector_table = f"{catalog}.{vector_schema}.capstone_vector_store"
    index_name   = f"{catalog}.{vector_schema}.curriculum_semantic_index"

    logger.info("Vector sync starting:")
    logger.info("  source: %s", silver_table)
    logger.info("  target: %s", vector_table)
    logger.info("  index:  %s @ %s", index_name, endpoint_name)

    # Ensure schema exists (idempotent; cheap on subsequent runs).
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{vector_schema}")
    _ensure_vector_table(spark, vector_table)

    projected_df = _project_silver_to_vector(spark, silver_table)
    merged_count = _merge_into_vector_table(spark, vector_table, projected_df)
    logger.info("✓ MERGE complete: %d row(s) staged into %s",
                merged_count, vector_table)

    final_status = _trigger_index_sync(
        endpoint_name=endpoint_name,
        index_name=index_name,
        wait_for_completion=wait_for_sync,
    )

    return {
        "silver_table": silver_table,
        "vector_table": vector_table,
        "merged_rows":  merged_count,
        "index_status": final_status,
    }


# ── Entrypoint ───────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", default="capstone",
                   help="Unity Catalog name (default: capstone)")
    p.add_argument("--silver-schema", default="silver_layer",
                   help="Silver schema name (default: silver_layer)")
    p.add_argument("--vector-schema", default="vector_layer",
                   help="Vector schema name (default: vector_layer)")
    p.add_argument("--endpoint", default="capstone_vector_endpoint",
                   help="Vector search endpoint name (default: capstone_vector_endpoint)")
    p.add_argument("--wait-for-sync", action="store_true",
                   help="Block until the index reaches ONLINE_NO_PENDING_UPDATE "
                        "(default: return as soon as sync is triggered)")
    return p


def main(argv: list[str] | None = None) -> None:
    """
    Spark Python task entrypoint.

    Same convention as silver_chunking.main(): we re-raise on error and
    return None on success rather than calling sys.exit(). Databricks'
    Spark Python task runner interprets any SystemExit (even SystemExit(0))
    as a workload failure, which would mark the task FAILED in the Jobs UI
    even after a successful sync.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _build_arg_parser().parse_args(argv)

    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    try:
        result = run(
            spark,
            catalog=args.catalog,
            silver_schema=args.silver_schema,
            vector_schema=args.vector_schema,
            endpoint_name=args.endpoint,
            wait_for_sync=args.wait_for_sync,
        )
        logger.info("Vector sync result: %s", result)
    except Exception:
        logger.exception("Vector sync failed")
        raise


if __name__ == "__main__":
    main()
