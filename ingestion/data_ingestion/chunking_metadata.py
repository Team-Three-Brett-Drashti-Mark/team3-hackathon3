# Databricks notebook source
# Install required packages

%pip install -U \
  databricks-langchain==0.16.1 \
  langchain==1.2.10 \
  langchain-core==1.2.16 \
  langchain-text-splitters==1.1.1 \
  langchain-community==0.4.1 \
  langchain-experimental==0.4.1 \
  nltk==3.9.3 \
  pypdf==5.1.0
  
try:
    dbutils.library.restartPython()
except:
    pass

# COMMAND ----------

# =============================================================================
# SILVER LAYER — Curriculum Chunking & Metadata Enrichment
# =============================================================================
# Reads raw curriculum from Bronze volumes (markdown + JSON quiz files),
# chunks content, enriches with metadata, and writes to a Silver Delta table.
# =============================================================================
 
import json
import re
from pathlib import Path
from datetime import datetime
 
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
 
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType, TimestampType, ArrayType
)
import pyspark.sql.functions as F
 
spark = SparkSession.builder.getOrCreate()

# COMMAND ----------

# =============================================================================
# CONFIG — update these to match your Unity Catalog
# =============================================================================
 
CATALOG        = "capstone"
BRONZE_SCHEMA  = "bronze_layer"
SILVER_SCHEMA  = "silver_layer"
VOLUME_NAME    = "curriculum_raw"
SILVER_TABLE   = f"{CATALOG}.{SILVER_SCHEMA}.curriculum_chunks"
 
BRONZE_BASE    = f"/Volumes/{CATALOG}/{BRONZE_SCHEMA}/{VOLUME_NAME}"
 
# Chunking config
MARKDOWN_CHUNK_SIZE    = 400
MARKDOWN_CHUNK_OVERLAP = 50
QUIZ_CHUNK_SIZE        = 300   # Smaller — quiz questions are naturally short
QUIZ_CHUNK_OVERLAP     = 0     # No overlap for quiz questions — each is self-contained

# COMMAND ----------

# =============================================================================
# SILVER SCHEMA DEFINITION
# =============================================================================
 
silver_schema = StructType([
    StructField("chunk_id",          StringType(),   False),  # unique ID for vector store
    StructField("doc_title",         StringType(),   False),  # e.g. "intro_to_strings"
    StructField("source_file",       StringType(),   False),  # original filename
    StructField("source_path",       StringType(),   False),  # full volume path
    StructField("content_type",      StringType(),   False),  # markdown | quiz | rubric | pdf
    StructField("week",              StringType(),   False),  # e.g. "week_01"
    StructField("topic",             StringType(),   True),   # e.g. "python_strings"
    StructField("section_title",     StringType(),   True),   # heading the chunk came from
    StructField("concept_tags",      ArrayType(StringType()), True),  # ["string_indexing", ...]
    StructField("chunk_index",       IntegerType(),  False),  # position within doc
    StructField("total_chunks",      IntegerType(),  False),  # total chunks in doc
    StructField("chunk_strategy",    StringType(),   False),  # context_enriched | question_unit
    StructField("page_content",      StringType(),   False),  # the actual text sent to embeddings
    StructField("raw_content",       StringType(),   False),  # content without context prefix
    StructField("difficulty",        StringType(),   True),   # beginner | intermediate | advanced
    StructField("quiz_id",           StringType(),   True),   # populated for quiz chunks only
    StructField("question_id",       StringType(),   True),   # populated for quiz chunks only
    StructField("source_reference",  StringType(),   True),   # back-ref to markdown source
    StructField("ingested_at",       TimestampType(),False),
])

# COMMAND ----------

# =============================================================================
# HELPER — extract week and content_type from volume path
# =============================================================================
 
def parse_path_metadata(path: str) -> dict:
    """
    Extracts week and content_type from a volume path.
    e.g. /Volumes/.../week_01/markdown/intro_to_strings.md
         -> {"week": "week_01", "content_type": "markdown"}
    """
    parts = Path(path).parts
    week = next((p for p in parts if re.match(r"week_\d+", p)), "unknown")
    content_type = next(
        (p for p in parts if p in {"markdown", "pdfs", "quizzes"}),
        "unknown"
    )
    return {"week": week, "content_type": content_type}
 
# =============================================================================
# HELPER — extract section headings from markdown
# =============================================================================
 
def split_markdown_by_heading(text: str) -> list[tuple[str, str]]:
    """
    Splits a markdown file into (heading, content) tuples by ## headings.
    Falls back to ("General", full_text) if no headings found.
    """
    pattern = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
 
    if not matches:
        return [("General", text)]
 
    sections = []
    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start   = match.end()
        end     = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((heading, content))
 
    return sections

# COMMAND ----------

# =============================================================================
# CHUNKER — Markdown files
# =============================================================================
 
def chunk_markdown_file(file_path: str) -> list[dict]:
    """
    Reads a markdown file from the volume, splits by heading section,
    then chunks each section with context-enriched prefixes.
    """
    path_meta  = parse_path_metadata(file_path)
    doc_title  = Path(file_path).stem          # "intro_to_strings"
    source_file = Path(file_path).name         # "intro_to_strings.md"
 
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
 
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MARKDOWN_CHUNK_SIZE,
        chunk_overlap=MARKDOWN_CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )
 
    sections = split_markdown_by_heading(text)
    chunks   = []
    now      = datetime.utcnow()
 
    for section_title, section_content in sections:
        raw_chunks = splitter.create_documents([section_content])
        total      = len(raw_chunks)
 
        for i, chunk in enumerate(raw_chunks):
            context_prefix = (
                f"Document: {doc_title}\n"
                f"Section: {section_title}\n"
                f"Week: {path_meta['week']}\n"
                f"Chunk {i + 1} of {total}\n"
                "---\n"
            )
            raw_content  = chunk.page_content
            page_content = context_prefix + raw_content
 
            # Pull concept tags from ## headings in content
            concept_tags = re.findall(r"(?:^|\n)#{2,3} (.+)", raw_content)
            concept_tags = [t.lower().replace(" ", "_") for t in concept_tags] or None
 
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

# COMMAND ----------

# =============================================================================
# CHUNKER — PDF files
# =============================================================================

from pypdf import PdfReader

def chunk_pdf_file(file_path: str) -> list[dict]:
    """
    Reads a PDF file from the volume,
    extracts text,
    chunks it,
    and enriches with metadata.
    """

    path_meta   = parse_path_metadata(file_path)
    doc_title   = Path(file_path).stem
    source_file = Path(file_path).name

    reader = PdfReader(file_path)

    page_texts = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()

        if text:
            page_texts.append(
                f"[Page {page_num}]\n{text.strip()}"
            )

    full_text = "\n\n".join(page_texts)

    if not full_text.strip():
        print(f"WARNING: No text extracted from {source_file}")
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=75,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks = splitter.create_documents([full_text])

    chunks = []
    now = datetime.utcnow()
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

        chunk_id = (
            f"{path_meta['week']}__{doc_title}__pdf__chunk_{i}"
        )

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

# COMMAND ----------

# DBTITLE 1,Cell 7
# =============================================================================
# MAIN — discover files, chunk, write to Silver Delta table
# =============================================================================

def run_silver_ingestion():

    all_chunks = []

    # =========================================================================
    # MARKDOWN FILES
    # =========================================================================

    md_dirs = [f.path for f in dbutils.fs.ls(f"{BRONZE_BASE}/") if f.isDir()]

    md_files = []

    for d in md_dirs:

        try:
            files = [
                f.path
                for f in dbutils.fs.ls(f"{d}markdown/")
                if f.path.endswith(".md")
            ]

            md_files.extend(files)

        except Exception:
            print(f"  Skipping {d}markdown/ (not found)")
            continue

    print(f"Found {len(md_files)} markdown files")

    for path in md_files:

        local_path = path.replace("dbfs:", "")

        chunks = chunk_markdown_file(local_path)

        all_chunks.extend(chunks)

        print(f"  ✓ {Path(local_path).name} → {len(chunks)} chunks")

    # =========================================================================
    # PDF FILES
    # =========================================================================

    pdf_dirs = [f.path for f in dbutils.fs.ls(f"{BRONZE_BASE}/") if f.isDir()]

    pdf_files = []

    for d in pdf_dirs:

        try:
            files = [
                f.path
                for f in dbutils.fs.ls(f"{d}pdfs/")
                if f.path.endswith(".pdf")
            ]

            pdf_files.extend(files)

        except Exception:
            print(f"  Skipping {d}pdfs/ (not found)")
            continue

    print(f"\nFound {len(pdf_files)} PDF files")

    for path in pdf_files:

        local_path = path.replace("dbfs:", "")

        chunks = chunk_pdf_file(local_path)

        all_chunks.extend(chunks)

        print(f"  ✓ {Path(local_path).name} → {len(chunks)} chunks")

    # =========================================================================
    # QUIZ FILES
    # =========================================================================

    quiz_dirs = [f.path for f in dbutils.fs.ls(f"{BRONZE_BASE}/") if f.isDir()]

    quiz_files = []

    for d in quiz_dirs:

        try:
            files = [
                f.path
                for f in dbutils.fs.ls(f"{d}quizzes/")
                if f.path.endswith(".json")
            ]

            quiz_files.extend(files)

        except Exception:
            print(f"  Skipping {d}quizzes/ (not found)")
            continue

    print(f"\nFound {len(quiz_files)} quiz files")

    for path in quiz_files:

        local_path = path.replace("dbfs:", "")

        chunks = chunk_quiz_file(local_path)

        all_chunks.extend(chunks)

        print(f"  ✓ {Path(local_path).name} → {len(chunks)} chunks")

    # =========================================================================
    # WRITE TO SILVER
    # =========================================================================

    print(f"\nTotal chunks: {len(all_chunks)}")

    df = spark.createDataFrame(all_chunks, schema=silver_schema)

    (
        df.write
          .format("delta")
          .mode("overwrite")
          .option("overwriteSchema", "true")
          .option("delta.enableChangeDataFeed", "true")
          .saveAsTable(SILVER_TABLE)
    )

    print(f"\n✓ Written to {SILVER_TABLE}")

    print(f"  Row count: {spark.table(SILVER_TABLE).count()}")

    return df

# --- Run ---

df = run_silver_ingestion()

display(df)

# COMMAND ----------

# =============================================================================
# QUICK VALIDATION QUERIES
# =============================================================================
 
# Chunk count by week and content type
spark.sql(f"""
    SELECT week, content_type, COUNT(*) as chunk_count
    FROM {SILVER_TABLE}
    GROUP BY week, content_type
    ORDER BY week, content_type
""").display()
 
# Confirm no correct_answers leaked into page_content (quiz guardrail check)
spark.sql(f"""
    SELECT chunk_id, page_content
    FROM {SILVER_TABLE}
    WHERE content_type = 'quiz'
    AND page_content LIKE '%correct_answer%'
""").display()