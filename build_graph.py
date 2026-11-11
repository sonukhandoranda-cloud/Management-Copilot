
import os
import math
import duckdb

from dotenv import load_dotenv
from neo4j import GraphDatabase

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv(".env")

DUCKDB_PATH = "NoteBooks/plant_data.duckdb"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

BATCH_SIZE = 500

if not NEO4J_PASSWORD:
    raise ValueError("NEO4J_PASSWORD missing from .env")


# --------------------------------------------------
# DATA HELPERS
# --------------------------------------------------

def clean_value(value):
    """Convert database values into Neo4j-compatible values."""
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    return value


def fetch_records(db, table):
    """Read all records from a DuckDB table."""
    cursor = db.execute(f'SELECT * FROM "{table}"')

    columns = [column[0] for column in cursor.description]

    records = []

    for row in cursor.fetchall():
        record = {
            column: clean_value(value)
            for column, value in zip(columns, row)
        }
        records.append(record)

    return records


def import_batches(session, query, records):
    """Import records in batches."""
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]

        session.execute_write(
            lambda tx, rows: tx.run(query, rows=rows).consume(),
            batch
        )


# --------------------------------------------------
# NEO4J CONSTRAINTS
# --------------------------------------------------

CONSTRAINTS = [
    """
    CREATE CONSTRAINT equipment_id_unique IF NOT EXISTS
    FOR (e:Equipment)
    REQUIRE e.equipment_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT maintenance_id_unique IF NOT EXISTS
    FOR (m:MaintenanceRecord)
    REQUIRE m.report_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT inspection_id_unique IF NOT EXISTS
    FOR (i:InspectionRecord)
    REQUIRE i.inspection_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
    FOR (x:IncidentRecord)
    REQUIRE x.incident_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT manual_name_unique IF NOT EXISTS
    FOR (m:Manual)
    REQUIRE m.name IS UNIQUE
    """
]


# --------------------------------------------------
# CYPHER IMPORT QUERIES
# --------------------------------------------------

EQUIPMENT_QUERY = """
UNWIND $rows AS row

MERGE (e:Equipment {equipment_id: row.equipment_id})
SET e += row

WITH e, row
WHERE row.linked_manual IS NOT NULL
  AND trim(row.linked_manual) <> ''

MERGE (man:Manual {name: row.linked_manual})
MERGE (e)-[:HAS_MANUAL]->(man)
"""


MAINTENANCE_QUERY = """
UNWIND $rows AS row

MATCH (e:Equipment {equipment_id: row.equipment_id})

MERGE (m:MaintenanceRecord {report_id: row.report_id})
SET m += row

MERGE (e)-[:UNDERWENT_MAINTENANCE]->(m)
"""


INSPECTION_QUERY = """
UNWIND $rows AS row

MATCH (e:Equipment {equipment_id: row.equipment_id})

MERGE (i:InspectionRecord {inspection_id: row.inspection_id})
SET i += row

MERGE (e)-[:WAS_INSPECTED]->(i)
"""


INCIDENT_QUERY = """
UNWIND $rows AS row

MATCH (e:Equipment {equipment_id: row.equipment_id})

MERGE (x:IncidentRecord {incident_id: row.incident_id})
SET x += row

MERGE (e)-[:HAD_INCIDENT]->(x)
"""


# --------------------------------------------------
# MAIN GRAPH BUILD FUNCTION
# --------------------------------------------------

def build_graph():

    print("\n========== CONNECTING TO DATABASES ==========")

    db = duckdb.connect(DUCKDB_PATH, read_only=True)

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )

    driver.verify_connectivity()

    print("DuckDB connected.")
    print("Neo4j connected.")

    try:
        with driver.session() as session:

            # Check existing graph before importing
            before = session.run("""
                MATCH (n)
                RETURN count(n) AS nodes
            """).single()["nodes"]

            print("\nExisting Neo4j nodes:", before)

            # Create uniqueness constraints
            print("\nCreating uniqueness constraints...")

            for query in CONSTRAINTS:
                session.run(query).consume()

            print("Constraints ready.")

            # Read source records
            print("\nReading records from DuckDB...")

            equipment = fetch_records(db, "equipment")
            maintenance = fetch_records(db, "maintenance")
            inspection = fetch_records(db, "inspection")
            incident = fetch_records(db, "incident")

            print("Equipment:", len(equipment))
            print("Maintenance:", len(maintenance))
            print("Inspection:", len(inspection))
            print("Incident:", len(incident))

            # Import equipment first
            print("\nImporting equipment and manuals...")

            import_batches(
                session, EQUIPMENT_QUERY, equipment
            )

            # Import maintenance
            print("Importing maintenance records...")

            import_batches(
                session, MAINTENANCE_QUERY, maintenance
            )

            # Import inspections
            print("Importing inspection records...")

            import_batches(
                session, INSPECTION_QUERY, inspection
            )

            # Import incidents
            print("Importing incident records...")

            import_batches(
                session, INCIDENT_QUERY, incident
            )

            # Final graph statistics
            print("\n========== GRAPH BUILD RESULTS ==========")

            labels = session.run("""
                MATCH (n)
                UNWIND labels(n) AS label
                RETURN label, count(*) AS total
                ORDER BY label
            """).data()

            for item in labels:
                print(f"{item['label']}: {item['total']}")

            relationships = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS relationship, count(*) AS total
                ORDER BY relationship
            """).data()

            for item in relationships:
                print(
                    f"{item['relationship']}: {item['total']}"
                )

            after = session.run("""
                MATCH (n)
                RETURN count(n) AS nodes
            """).single()["nodes"]

            print("\nNodes before import:", before)
            print("Nodes after import:", after)
            print("New nodes:", after - before)

            print("\nGRAPH BUILD COMPLETED SUCCESSFULLY")

    finally:
        db.close()
        driver.close()


if __name__ == "__main__":
    build_graph()
