"""
Curriculum ETL pipeline scripts.

These modules run as Databricks Spark Python tasks. They are intentionally
kept out of `app/` so the FastAPI process doesn't pull in Spark/LangChain at
import time. Each module is runnable as `python -m ingestion.pipelines.<name>`
or via a `spark_python_task` pointing at its file path.
"""
