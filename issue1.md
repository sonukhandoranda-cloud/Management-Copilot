from pathlib import Path
import pypandoc

content = """# Issue 1 — Make Structured RAG independent of local Excel files and fix DuckDB schema reflection

## Summary

Structured RAG depended on Excel files stored at a hardcoded local Windows path. This made the application difficult to run on another machine or deploy to a server. After removing that dependency, a second compatibility issue appeared: LangChain's `SQLDatabase` used SQLAlchemy schema reflection that queried PostgreSQL catalog objects not available in the expected form in DuckDB.

Both issues were addressed in `app.py`. Structured RAG now uses the existing DuckDB database directly, reads its schema through DuckDB's native Python API, generates SQL from that schema, and executes queries through a read-only DuckDB connection.

## Issue 1A — Hardcoded local Excel dependency

### What was happening

The original `get_sql_tools()` function read four Excel files (equipment, maintenance, inspection, and incident reports) with `pandas.read_excel()`. It then connected to `plant_data.duckdb` and recreated the four tables using `CREATE OR REPLACE TABLE`.

The Excel paths were configured as local Windows paths. A server or another developer's machine would not necessarily have the same directory or source files.

### Root cause

The application treated local Excel workbooks as a required runtime dependency even though the structured records were already available in the DuckDB database.

### Resolution

Removed the Excel-reading and table-recreation logic from `get_sql_tools()`. The application now checks that `plant_data.duckdb` exists and connects to that existing database. It no longer needs the original Excel files at runtime and does not overwrite the tables when a user asks a question.

**Clarification:** The Excel files were not literally stored inside DuckDB. The old code loaded Excel files into pandas DataFrames and copied those DataFrames into DuckDB tables. The deployment problem was the hardcoded local Excel-file dependency.

## Issue 1B — LangChain schema reflection failed with DuckDB

### What was happening

After switching to the existing DuckDB database, this call failed:

```python
SQLDatabase.from_uri(f"duckdb:///{duckdb_path}")
```

The error referenced `pg_catalog.pg_collation`:

```text
Binder Error: Referenced table "pg_catalog.pg_collation" not found
```

The failure occurred while `SQLDatabase`/SQLAlchemy attempted to inspect and reflect the database schema. The reflection query referenced a PostgreSQL catalog object that was not available as expected through the DuckDB engine.

### Root cause

The problem was not that DuckDB could not open the database or that the tables were missing. The incompatibility occurred in the SQLAlchemy-based schema-inspection path used by `SQLDatabase`.

### Resolution

Removed `SQLDatabase` and `QuerySQLDataBaseTool` from the Structured RAG execution path.

The updated implementation:

1. Opens DuckDB using its native Python API.
2. Reads available tables using `SHOW TABLES`.
3. Reads each table's columns and types using `DESCRIBE`.
4. Builds a schema description and supplies it to the SQL-generation prompt.
5. Uses the LLM to generate SQL based on the actual schema.
6. Executes the generated query using a native DuckDB connection opened with `read_only=True`.
7. Returns the query result to the existing evidence-gathering and answer-generation flow.

The schema is supplied using `prompt.partial(schema=schema)`, so `structured_search()` only needs to pass the user's question.

The SQL execution path checks that the generated statement begins with `SELECT` or `WITH`, rejects multiple statements, and executes against a read-only connection. Read-only mode provides database-level protection against writes.

## Files changed

- `app.py`
  - Removed runtime loading of local Excel workbooks and replacement of DuckDB tables.
  - Reworked `get_sql_tools()` to inspect the schema using native DuckDB.
  - Reworked `structured_search()` to execute SQL using native DuckDB in read-only mode.
  - Preserved the existing natural-language question flow and downstream answer generation.

## Verification performed

- `python -m py_compile app.py` — passed.
- Streamlit launched from the `NoteBooks` directory using `streamlit run ../app.py`.
- Equipment query returned all 22 equipment records with IDs and current statuses.
- Maintenance count query returned the expected 87 records.
- Recent incidents query returned results successfully.
- Existing database was preserved; structured queries execute in read-only mode.

## Outcome

**Structured RAG is working without requiring local Excel files.**

The application uses the existing DuckDB database as its structured-data source and avoids the SQLAlchemy schema-reflection path that caused the DuckDB catalog error.

## Deployment note

This change removes the hardcoded Excel-directory dependency, but it does not by itself make the entire application deployment-ready. The deployed environment must still provide the DuckDB database file at the configured relative path, along with the required Python packages, environment variables, ChromaDB data, and Neo4j service/configuration if those features are enabled.
"""

out = Path("/mnt/data/issue1.md")
pypandoc.convert_text(content, "md", format="md", outputfile=str(out), extra_args=["--standalone"])
print(f"Created: {out}")
