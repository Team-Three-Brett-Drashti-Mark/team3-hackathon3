# Databricks notebook source
# MAGIC %md
# MAGIC ## Set up catalog and schema variables.

# COMMAND ----------

catalog = "capstone"
schema  = f"bronze_layer"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create the schema

# COMMAND ----------


# Cell 2 — Create personal schema
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
print(f"Schema ready: {catalog}.{schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create three volumes

# COMMAND ----------

for vol in ["code", "markdown", "pdfs"]:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{vol}")
    print(f"Volume ready: /Volumes/{catalog}/{schema}/{vol}/")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify everything exists

# COMMAND ----------

display(spark.sql(f"SHOW VOLUMES IN {catalog}.{schema}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Grant privileges on schema and volumes for all Dbrix users

# COMMAND ----------

# DBTITLE 1,Cell 10
statements = [
    f"GRANT USE SCHEMA ON SCHEMA {catalog}.{schema} TO `account users`",
    f"GRANT READ VOLUME ON VOLUME {catalog}.{schema}.code TO `account users`",
    f"GRANT WRITE VOLUME ON VOLUME {catalog}.{schema}.markdown TO `account users`",
    f"GRANT WRITE VOLUME ON VOLUME {catalog}.{schema}.pdfs TO `account users`",
]
for stmt in statements:
    spark.sql(stmt)

display(spark.sql(f"SHOW GRANTS ON SCHEMA {catalog}.{schema}"))

# COMMAND ----------

