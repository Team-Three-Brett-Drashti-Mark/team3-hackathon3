"""
SILVER LAYER — Curriculum chunking & metadata enrichment
==========================================================

Reads raw curriculum files from the bronze Unity Catalog volume, splits them
into chunks with metadata, and MERGEs the result into the silver Delta table.

Runs as a Spark Python task inside a Databricks Job. The job is triggered by
file-arrival on the bronze volume (see resources/curriculum_etl.yml), so this
script needs to be idempotent against re-runs:

    - First-pass on a new file:      MERGE inserts every chunk_id.
    - Re-upload of an existing file: MERGE replaces chunks with the same id.
    - File that's been deleted:      cleanup happens in the cascade-delete
                                     endpoint (app/admin.py), not here.

Folder → file format mapping:
    week_XX/markdown/  → .md / .markdown  → context-enriched section chunks
    week_XX/pdfs/      → .pdf             → pypdf text extraction → splitter chunks
    week_XX/quizzes/   → .json            → one chunk per quiz question

CLI (all args optional — defaults match the production catalog/schema):
    --catalog        Unity Catalog name (default: capstone)
    --bronze-schema  Bronze layer schema name (default: bronze_layer)
    --silver-schema  Silver layer schema name (default: silver_layer)
    --volume         Volume name under bronze schema (default: curriculum_raw)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("silver_chunking")


# ── Chunking config ──────────────────────────────────────────────────────────
# These knobs control how aggressively each content type gets split. The
# values match the original chunking_metadata.ipynb defaults and have been
# tuned against the existing curriculum corpus — changing them will reshuffle
# every existing chunk_id, so don't touch unless you intend a full re-embed.
MARKDOWN_CHUNK_SIZE    = 400
MARKDOWN_CHUNK_OVERLAP = 50
QUIZ_CHUNK_SIZE        = 300   # smaller — quiz questions are naturally short
QUIZ_CHUNK_OVERLAP     = 0     # no overlap — each question is self-contained
# PDFs get a larger window than markdown: extracted PDF text has no heading
# structure to split on, so bigger chunks keep related prose together instead
# of fragmenting mid-thought, and the overlap softens the hard cuts the
# splitter is forced to make in the absence of natural section boundaries.
PDF_CHUNK_SIZE         = 600
PDF_CHUNK_OVERLAP      = 75


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_path_metadata(path: str) -> dict:
    """
    Extract `week` and `content_type` from a volume path.

    Example::

        /Volumes/capstone/bronze_layer/curriculum_raw/week_01/markdown/intro.md
        -> {"week": "week_01", "content_type": "markdown"}

    Falls back to "unknown" rather than raising so a stray file in an
    unexpected location still produces a row (with content_type=unknown) that
    an operator can spot and clean up, instead of crashing the whole batch.
    """
    parts = Path(path).parts
    week = next((p for p in parts if re.match(r"week_\d+", p)), "unknown")
    content_type = next(
        (p for p in parts if p in {"markdown", "pdfs", "quizzes"}),
        "unknown",
    )
    return {"week": week, "content_type": content_type}


def split_markdown_by_heading(text: str) -> list[tuple[str, str]]:
    """
    Split a markdown document into ``(heading, content)`` tuples on H1-H3 lines.

    The chunker uses sections as the first-pass boundary so each chunk gets
    the heading-derived context prefix (see chunk_markdown_file). Falls back
    to a single ``("General", full_text)`` section when no headings exist, so
    flat markdown still produces chunks instead of being silently dropped.
    """
    pattern = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))

    if not matches:
        return [("General", text)]

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((heading, content))

    return sections


def chunk_markdown_file(file_path: str) -> list[dict]:
    """
    Read a markdown file and return a list of chunk dicts ready for silver.

    Each chunk carries a context prefix (Document/Section/Week/Chunk N of M)
    that's deliberately included in `page_content` for downstream RAG callers
    that want hierarchical context. The clean text without the prefix is
    stored separately in `raw_content` — that's what the vector store
    actually embeds, because the prefix noise hurts retrieval quality.

    The langchain import is local to the function so the rest of the module
    (path parsing, quiz chunking) stays importable in environments that don't
    have langchain installed — useful for unit-test style runs.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    path_meta = parse_path_metadata(file_path)
    doc_title = Path(file_path).stem        # "intro_to_strings"
    source_file = Path(file_path).name      # "intro_to_strings.md"

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Separators are ordered most-structural-first: we'd rather split on a
    # section header than mid-paragraph, and mid-paragraph than mid-word.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MARKDOWN_CHUNK_SIZE,
        chunk_overlap=MARKDOWN_CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )

    sections = split_markdown_by_heading(text)
    chunks: list[dict] = []
    now = datetime.now(timezone.utc)

    for section_title, section_content in sections:
        raw_chunks = splitter.create_documents([section_content])
        total = len(raw_chunks)

        for i, chunk in enumerate(raw_chunks):
            # Header attached to the embedded text so downstream callers can
            # see "where this came from" without joining back to the metadata.
            context_prefix = (
                f"Document: {doc_title}\n"
                f"Section: {section_title}\n"
                f"Week: {path_meta['week']}\n"
                f"Chunk {i + 1} of {total}\n"
                "---\n"
            )
            raw_content = chunk.page_content
            page_content = context_prefix + raw_content

            # Concept tags are derived from any H2/H3 headings found INSIDE
            # the chunk body — gives a coarse topic signal for filtering.
            concept_tag_matches = re.findall(r"(?:^|\n)#{2,3} (.+)", raw_content)
            concept_tags = (
                [t.lower().replace(" ", "_") for t in concept_tag_matches] or None
            )

            # chunk_id formula is the stable join key between silver and the
            # vector store. NEVER change without a full re-embed plan —
            # the cascade-delete endpoint depends on this exact shape.
            chunk_id = (
                f"{path_meta['week']}__{doc_title}__"
                f"{section_title.replace(' ', '_').lower()}__chunk_{i}"
            )

            chunks.append({
                "chunk_id":         chunk_id,
                "doc_title":        doc_title,
                "source_file":      source_file,
                "source_path":      file_path,
                "content_type":     "markdown",
                "week":             path_meta["week"],
                "topic":            doc_title,
                "section_title":    section_title,
                "concept_tags":     concept_tags,
                "chunk_index":      i,
                "total_chunks":     total,
                "chunk_strategy":   "context_enriched",
                "page_content":     page_content,
                "raw_content":      raw_content,
                "difficulty":       None,
                "quiz_id":          None,
                "question_id":      None,
                "source_reference": None,
                "ingested_at":      now,
            })

    return chunks


def chunk_pdf_file(file_path: str) -> list[dict]:
    """
    Read a PDF file and return a list of chunk dicts ready for silver.

    PDFs have no heading structure we can lean on the way markdown does, so the
    strategy is different: extract every page's text, stitch the pages together
    with ``[Page N]`` markers (so a chunk that straddles a page boundary still
    carries a breadcrumb back to the source page), then hand the whole document
    to the recursive splitter. There's no section-level first pass — the splitter
    is the only boundary mechanism here.

    Like chunk_markdown_file, the context prefix lives in `page_content` for
    callers that want hierarchical context, while `raw_content` holds the clean
    extracted text that the vector store actually embeds.

    Both imports (pypdf, langchain) are local to the function for the same reason
    the other chunkers keep their heavy deps local: the module must stay
    importable for unit-test runs on machines without these packages installed.

    Returns an empty list (not an error) when extraction yields no text — that's
    the expected outcome for scanned/image-only PDFs, which need OCR we don't do
    here. Swallowing it as "0 chunks" keeps one un-OCR-able file from failing the
    whole batch; the warning log is the operator's signal to investigate.
    """
    from pypdf import PdfReader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    path_meta = parse_path_metadata(file_path)
    doc_title = Path(file_path).stem
    source_file = Path(file_path).name

    reader = PdfReader(file_path)

    # Per-page extraction with explicit page markers. We tag each page so that
    # when the splitter later carves the joined text into chunks, a chunk can
    # still be traced back to roughly which page(s) it came from. Pages that
    # extract to nothing (blank or image-only) are dropped rather than emitting
    # an empty "[Page N]" header with no body.
    page_texts: list[str] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text and text.strip():
            page_texts.append(f"[Page {page_num}]\n{text.strip()}")

    full_text = "\n\n".join(page_texts)
    if not full_text.strip():
        # No extractable text — almost always a scanned/image PDF. Not a hard
        # failure (see docstring); log so an operator can decide whether OCR is
        # worth adding for this file.
        logger.warning("No text extracted from %s — skipping (likely scanned/image PDF)", source_file)
        return []

    # Separators omit the markdown-heading patterns the markdown splitter uses
    # (there are none in extracted PDF text) and fall through paragraph → line →
    # sentence → word → character so the splitter always has a legal cut point.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=PDF_CHUNK_SIZE,
        chunk_overlap=PDF_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks = splitter.create_documents([full_text])
    chunks: list[dict] = []
    now = datetime.now(timezone.utc)
    total = len(raw_chunks)

    for i, chunk in enumerate(raw_chunks):
        context_prefix = (
            f"Document: {doc_title}\n"
            f"Content Type: pdf\n"
            f"Week: {path_meta['week']}\n"
            f"Chunk {i + 1} of {total}\n"
            "---\n"
        )
        raw_content = chunk.page_content
        page_content = context_prefix + raw_content

        # Distinct "__pdf__" namespace in the chunk_id keeps these from ever
        # colliding with markdown ("__<section>__chunk_N") or quiz ("__quiz__")
        # ids for the same week/doc — important because the MERGE keys on
        # chunk_id, so a collision would silently overwrite another file's chunk.
        chunk_id = f"{path_meta['week']}__{doc_title}__pdf__chunk_{i}"

        chunks.append({
            "chunk_id":         chunk_id,
            "doc_title":        doc_title,
            "source_file":      source_file,
            "source_path":      file_path,
            "content_type":     "pdf",
            "week":             path_meta["week"],
            "topic":            doc_title,
            "section_title":    "PDF Content",
            "concept_tags":     None,
            "chunk_index":      i,
            "total_chunks":     total,
            "chunk_strategy":   "pdf_text_extraction",
            "page_content":     page_content,
            "raw_content":      raw_content,
            "difficulty":       None,
            "quiz_id":          None,
            "question_id":      None,
            "source_reference": None,
            "ingested_at":      now,
        })

    return chunks


def chunk_quiz_file(file_path: str) -> list[dict]:
    """
    Split a quiz JSON file into one chunk per question.

    Expected shape (flexible — we read defensively):
        {
          "quiz_id": "...",            # optional, falls back to filename stem
          "topic":   "...",            # optional, falls back to filename stem
          "difficulty": "beginner",    # optional
          "source_reference": "...",   # optional back-ref to markdown
          "questions": [
            {
              "question_id": "...",    # optional, falls back to f"q{i}"
              "question":    "...",    # required — the prompt text
              "options":     [...],    # optional list of choices
              "correct_answer": "...", # IGNORED in page_content — guardrail
              "explanation": "...",    # optional
            },
            ...
          ]
        }

    Critical: the `correct_answer` field is never written into page_content
    or raw_content — the assistant must never serve the answer back. The
    notebook's QUICK_VALIDATION block asserts no chunk leaks "correct_answer"
    text; that contract is preserved here.
    """
    path_meta = parse_path_metadata(file_path)
    doc_title = Path(file_path).stem
    source_file = Path(file_path).name

    with open(file_path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    quiz_id = data.get("quiz_id") or doc_title
    quiz_topic = data.get("topic") or doc_title
    difficulty = data.get("difficulty")
    source_reference = data.get("source_reference")

    questions = data.get("questions") or []
    chunks: list[dict] = []
    now = datetime.now(timezone.utc)
    total = len(questions)

    for i, q in enumerate(questions):
        # Defensive defaults — a malformed entry shouldn't kill the whole job.
        question_id = q.get("question_id") or f"q{i}"
        prompt = (q.get("question") or "").strip()
        if not prompt:
            logger.warning(
                "Skipping empty question in %s (index %d, qid=%s)",
                source_file, i, question_id,
            )
            continue

        # Body of the chunk: question + options + explanation, but NEVER the
        # correct_answer. Options are rendered as a flat list so the embedder
        # sees them as plain context.
        body_parts = [f"Question: {prompt}"]
        options = q.get("options") or []
        if options:
            options_block = "\n".join(f"- {opt}" for opt in options)
            body_parts.append(f"Options:\n{options_block}")
        explanation = (q.get("explanation") or "").strip()
        if explanation:
            body_parts.append(f"Explanation: {explanation}")
        raw_content = "\n\n".join(body_parts)

        context_prefix = (
            f"Document: {doc_title}\n"
            f"Quiz: {quiz_id}\n"
            f"Week: {path_meta['week']}\n"
            f"Question {i + 1} of {total}\n"
            "---\n"
        )
        page_content = context_prefix + raw_content

        chunk_id = f"{path_meta['week']}__{doc_title}__quiz__{question_id}"

        chunks.append({
            "chunk_id":         chunk_id,
            "doc_title":        doc_title,
            "source_file":      source_file,
            "source_path":      file_path,
            "content_type":     "quiz",
            "week":             path_meta["week"],
            "topic":            quiz_topic,
            "section_title":    None,
            "concept_tags":     None,
            "chunk_index":      i,
            "total_chunks":     total,
            "chunk_strategy":   "question_unit",
            "page_content":     page_content,
            "raw_content":      raw_content,
            "difficulty":       difficulty,
            "quiz_id":          quiz_id,
            "question_id":      question_id,
            "source_reference": source_reference,
            "ingested_at":      now,
        })

    return chunks


# ── Spark + Delta plumbing ───────────────────────────────────────────────────

def silver_schema():
    """
    Return the StructType for the silver table.

    Defined as a function (not a module-level constant) so the pyspark import
    can stay inside this function — keeps the module importable on machines
    without Spark installed, which matters for unit-testing the chunkers in
    isolation.
    """
    from pyspark.sql.types import (
        StructType, StructField,
        StringType, IntegerType, TimestampType, ArrayType,
    )
    return StructType([
        StructField("chunk_id",          StringType(),   False),
        StructField("doc_title",         StringType(),   False),
        StructField("source_file",       StringType(),   False),
        StructField("source_path",       StringType(),   False),
        StructField("content_type",      StringType(),   False),
        StructField("week",              StringType(),   False),
        StructField("topic",             StringType(),   True),
        StructField("section_title",     StringType(),   True),
        StructField("concept_tags",      ArrayType(StringType()), True),
        StructField("chunk_index",       IntegerType(),  False),
        StructField("total_chunks",      IntegerType(),  False),
        StructField("chunk_strategy",    StringType(),   False),
        StructField("page_content",      StringType(),   False),
        StructField("raw_content",       StringType(),   False),
        StructField("difficulty",        StringType(),   True),
        StructField("quiz_id",           StringType(),   True),
        StructField("question_id",       StringType(),   True),
        StructField("source_reference",  StringType(),   True),
        StructField("ingested_at",       TimestampType(),False),
    ])


def _ensure_silver_table(spark, silver_table: str) -> None:
    """
    Create the silver Delta table on first run if it doesn't already exist.

    CDC is enabled so the downstream vector_sync.py task can rely on the same
    "MERGE produces a clean delta" semantics it uses for the vector table.
    Schema mirrors silver_schema() above — keep in sync.
    """
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {silver_table} (
            chunk_id         STRING NOT NULL,
            doc_title        STRING NOT NULL,
            source_file      STRING NOT NULL,
            source_path      STRING NOT NULL,
            content_type     STRING NOT NULL,
            week             STRING NOT NULL,
            topic            STRING,
            section_title    STRING,
            concept_tags     ARRAY<STRING>,
            chunk_index      INT NOT NULL,
            total_chunks     INT NOT NULL,
            chunk_strategy   STRING NOT NULL,
            page_content     STRING NOT NULL,
            raw_content      STRING NOT NULL,
            difficulty       STRING,
            quiz_id          STRING,
            question_id      STRING,
            source_reference STRING,
            ingested_at      TIMESTAMP NOT NULL
        )
        USING DELTA
        TBLPROPERTIES (delta.enableChangeDataFeed = true)
    """)


def _list_files_under(volume_root: str, subfolder: str, suffixes: tuple[str, ...]) -> list[str]:
    """
    Walk ``{volume_root}/week_*/{subfolder}/`` and return absolute paths of
    files whose extension matches one of ``suffixes`` (case-insensitive).

    We use os.walk against the UC Volume mount rather than dbutils.fs.ls
    because:
      - os.walk lets us skip the per-week try/except dance the notebook
        needed to handle missing subdirectories.
      - The volume is FUSE-mounted on the cluster, so plain Python file IO
        works on absolute /Volumes/... paths.
    """
    found: list[str] = []
    lowered = tuple(s.lower() for s in suffixes)
    for dirpath, _dirs, files in os.walk(volume_root):
        # Restrict to {week_XX}/{subfolder}/ depth so e.g. random files at the
        # week root or in a different folder don't get pulled in.
        parts = Path(dirpath).parts
        if subfolder not in parts:
            continue
        for name in files:
            if name.lower().endswith(lowered):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def run(spark, catalog: str, bronze_schema: str, silver_schema_name: str,
        volume_name: str) -> int:
    """
    Discover, chunk, and MERGE every supported file under the bronze volume.

    Returns the number of chunks written. Pure function over (spark, config)
    so the entrypoint can stay lean and a future caller (e.g. an admin
    "rebuild silver" endpoint) can reuse the same logic without re-parsing
    CLI args.
    """
    silver_table = f"{catalog}.{silver_schema_name}.curriculum_chunks"
    volume_root = f"/Volumes/{catalog}/{bronze_schema}/{volume_name}"

    logger.info("Silver chunking starting:")
    logger.info("  volume_root:  %s", volume_root)
    logger.info("  silver_table: %s", silver_table)

    _ensure_silver_table(spark, silver_table)

    # ── Discover and chunk markdown ─────────────────────────────────────────
    md_files = _list_files_under(volume_root, "markdown", (".md", ".markdown"))
    logger.info("Found %d markdown file(s)", len(md_files))
    all_chunks: list[dict] = []
    for path in md_files:
        try:
            file_chunks = chunk_markdown_file(path)
        except Exception as exc:
            # Don't let a single bad file kill the whole batch — log and skip.
            logger.exception("Failed to chunk markdown %s: %s", path, exc)
            continue
        all_chunks.extend(file_chunks)
        logger.info("  ✓ %s → %d chunks", Path(path).name, len(file_chunks))

    # ── Discover and chunk quizzes ──────────────────────────────────────────
    quiz_files = _list_files_under(volume_root, "quizzes", (".json",))
    logger.info("Found %d quiz file(s)", len(quiz_files))
    for path in quiz_files:
        try:
            file_chunks = chunk_quiz_file(path)
        except Exception as exc:
            logger.exception("Failed to chunk quiz %s: %s", path, exc)
            continue
        all_chunks.extend(file_chunks)
        logger.info("  ✓ %s → %d chunks", Path(path).name, len(file_chunks))

    # ── Discover and chunk PDFs ─────────────────────────────────────────────
    # Mirrors the markdown/quiz loops: per-file try/except so one un-parseable
    # PDF (corrupt, encrypted, exotic encoding) gets logged and skipped instead
    # of aborting the batch. Note chunk_pdf_file also returns [] for scanned
    # image-only PDFs — those land here as "0 chunks", which is intentional.
    pdf_files = _list_files_under(volume_root, "pdfs", (".pdf",))
    logger.info("Found %d PDF file(s)", len(pdf_files))
    for path in pdf_files:
        try:
            file_chunks = chunk_pdf_file(path)
        except Exception as exc:
            logger.exception("Failed to chunk PDF %s: %s", path, exc)
            continue
        all_chunks.extend(file_chunks)
        logger.info("  ✓ %s → %d chunks", Path(path).name, len(file_chunks))

    if not all_chunks:
        # No work to do isn't a failure — the trigger may have fired for a
        # PDF (currently skipped) or for a file that was deleted before the
        # job started. Exit cleanly.
        logger.info("No chunks produced; nothing to MERGE.")
        return 0

    # ── Stage chunks in a temp view, then MERGE into silver ─────────────────
    # MERGE on chunk_id makes the operation idempotent: re-running on the
    # same file replaces its chunks; a partially-failed previous run is
    # cleaned up automatically; concurrent uploads to different files don't
    # stomp each other. The downside is we touch every row in `all_chunks`
    # even if only one file changed — fine for hackathon scale (<10k chunks),
    # would want trigger_info-based filtering at larger scale.
    df = spark.createDataFrame(all_chunks, schema=silver_schema())
    staged = "_silver_chunking_staged"
    df.createOrReplaceTempView(staged)

    # Explicit column lists rather than UPDATE SET * / INSERT *.
    # Reason: the deployed silver table has accumulated additional columns
    # over time (e.g. page_content_clean from an earlier experiment) that
    # aren't in our staging schema. With UPDATE SET *, Spark requires every
    # target column to appear in source and the MERGE fails with
    # DELTA_MERGE_UNRESOLVED_EXPRESSION. Listing only the columns we manage
    # leaves unmanaged columns untouched on UPDATE and NULL on INSERT,
    # which is the safe behavior — future schema additions in the target
    # won't break this ETL.
    managed_columns = [
        "chunk_id", "doc_title", "source_file", "source_path", "content_type",
        "week", "topic", "section_title", "concept_tags", "chunk_index",
        "total_chunks", "chunk_strategy", "page_content", "raw_content",
        "difficulty", "quiz_id", "question_id", "source_reference", "ingested_at",
    ]
    update_clause = ", ".join(f"target.{c} = source.{c}" for c in managed_columns)
    insert_cols   = ", ".join(managed_columns)
    insert_values = ", ".join(f"source.{c}" for c in managed_columns)

    spark.sql(f"""
        MERGE INTO {silver_table} AS target
        USING {staged} AS source
        ON target.chunk_id = source.chunk_id
        WHEN MATCHED THEN UPDATE SET {update_clause}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_values})
    """)

    written = len(all_chunks)
    logger.info("✓ MERGE complete: %d chunks staged into %s", written, silver_table)
    return written


# ── Entrypoint ───────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", default="capstone",
                   help="Unity Catalog name (default: capstone)")
    p.add_argument("--bronze-schema", default="bronze_layer",
                   help="Bronze schema name (default: bronze_layer)")
    p.add_argument("--silver-schema", default="silver_layer",
                   help="Silver schema name (default: silver_layer)")
    p.add_argument("--volume", default="curriculum_raw",
                   help="Volume name under bronze schema (default: curriculum_raw)")
    return p


def main(argv: list[str] | None = None) -> None:
    """
    Spark Python task entrypoint.

    Note on error handling: we deliberately do NOT call sys.exit() here, even
    on success. Databricks' Spark Python task runner treats ANY SystemExit
    exception — including SystemExit(0) — as a workload failure, which marks
    the task FAILED in the Jobs UI even when our code ran perfectly. The
    correct shape for a Spark Python task is "raise on error, return on
    success" — the runner inspects un-caught exceptions, not exit codes.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _build_arg_parser().parse_args(argv)

    # SparkSession import is local so the module is importable for unit tests
    # on a machine without Spark installed.
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    # Re-raising on failure (rather than returning a non-zero code) is what
    # the Databricks task runner expects to mark the task FAILED. The log
    # call gives us a structured trace in the task driver log alongside the
    # JVM stack trace the runner appends automatically.
    try:
        run(
            spark,
            catalog=args.catalog,
            bronze_schema=args.bronze_schema,
            silver_schema_name=args.silver_schema,
            volume_name=args.volume,
        )
    except Exception:
        logger.exception("Silver chunking failed")
        raise


if __name__ == "__main__":
    main()
