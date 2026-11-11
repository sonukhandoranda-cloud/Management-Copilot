from pathlib import Path

content = """# Issue 2 — Graph RAG Integration and Troubleshooting

## Overview

The project had a Graph RAG implementation based on Neo4j, but getting it working end-to-end with the Streamlit application required resolving several integration and data-access issues.

## Problems encountered

### 1. Graph data was not available in Neo4j

The original graph-building notebook depended on Excel files stored at a local machine path. Those files were not available in the current project environment, so the notebook could not be used as-is to populate Neo4j.

### 2. Graph schema initialization failed

When the application initialized `Neo4jGraph`, schema refresh failed because the required APOC procedure `apoc.meta.data` was unavailable in the Neo4j installation.

### 3. Graph RAG returned an unhelpful answer in the application

The standalone graph query test could retrieve the expected records, but the integrated `GraphCypherQAChain` sometimes returned an unhelpful natural-language response. This made it difficult for the final answer-generation step to use the actual graph records.

### 4. Graph results needed to retain their query context

Returning only the final graph-chain answer did not expose enough information for the application to pass reliable graph evidence to the final response-generation stage.

## How the issues were resolved

### 1. Built the graph from the existing DuckDB database

Instead of relying on unavailable Excel files, a separate graph-building script was created to read the existing DuckDB database in read-only mode and populate Neo4j.

The script uses `MERGE` operations and uniqueness constraints so that rerunning the import does not create duplicate nodes.

The graph was populated with these node types:

- Equipment
- MaintenanceRecord
- InspectionRecord
- IncidentRecord
- Manual

The following relationships were created:

- `HAS_MANUAL`
- `UNDERWENT_MAINTENANCE`
- `WAS_INSPECTED`
- `HAD_INCIDENT`

### 2. Enabled the required APOC functionality

The APOC Core plugin was installed through Neo4j Desktop, and the database was restarted. After that, `Neo4jGraph` schema initialization and refresh completed successfully.

### 3. Returned raw graph records from the chain

The `GraphCypherQAChain` configuration was changed to use `return_direct=True`. This allowed the application to receive the database records directly instead of relying on the chain to turn them into a natural-language answer.

### 4. Included intermediate steps in graph evidence

The chain was configured with `return_intermediate_steps=True`.

In `gather_evidence()`, the graph branch now extracts:
- The generated Cypher query
- The graph database context/results

Both are added to the evidence passed to the final answer-generation stage. This preserves the query and its supporting records, allowing the final response to explain the graph findings.

## Validation performed

The graph import and integration were tested successfully.

### Imported data

| Node type | Count |
|---|---:|
| Equipment | 22 |
| MaintenanceRecord | 87 |
| InspectionRecord | 75 |
| IncidentRecord | 25 |
| Manual | 10 |
| **Total nodes** | **219** |

| Relationship type | Count |
|---|---:|
| `HAS_MANUAL` | 22 |
| `UNDERWENT_MAINTENANCE` | 87 |
| `WAS_INSPECTED` | 75 |
| `HAD_INCIDENT` | 25 |
| **Total relationships** | **209** |

### Query tests

- Retrieved equipment with incident and maintenance information.
- Identified the Cooling Water Pump with the highest inspection count: 6.
- Tested the Graph RAG path through the Streamlit application.
- Confirmed that the final application response could use the generated Cypher and returned graph records.

### Combined RAG test

The following question was tested through the application:

> For the Cooling Water Pump, summarize its maintenance history, incident history, and relevant operating instructions from its OEM manual.

The application selected all three sources:
- Structured RAG for maintenance and incident records
- Graph RAG for equipment relationships and graph context
- Vector RAG for relevant OEM manual excerpts

The final response successfully combined the evidence and identified the relevant maintenance events, incidents, and manual information.

## Outcome

Graph RAG is now populated, independently validated, and integrated into the Streamlit application's multi-source evidence pipeline.

The graph import is repeatable through `MERGE`, and the application passes the generated Cypher query and graph results to the final answer-generation stage.

## Follow-up improvements

The following items are separate refinements and are not blockers for the Graph RAG integration:

- Improve formatting of raw graph results in the Sources section.
- Review Cypher patterns that can multiply rows when several one-to-many relationships are matched together.
- Continue testing graph-only and multi-source questions with different equipment.
"""

path = Path("/mnt/data/issue2.md")
path.write_text(content, encoding="utf-8")
print(f"Created: {path} ({path.stat().st_size} bytes)")
