"""
Plant Knowledge Copilot -- Streamlit app.

This is the one .py file the project needs (Streamlit can't run from a
notebook). Everything else -- ingestion, graph build -- still happens in
the two notebooks; this app only *reads* what they built:

  - notebooks/chroma_db/        <- built by 01_vector_rag_langchain.ipynb
  - Neo4j (bolt://...)          <- built by 02_hybrid_graph_structured_rag.ipynb
  - the 4 Excel logs            <- loaded fresh into DuckDB on each app start (cheap, ~213 rows)

Run from the notebooks/ folder (same relative paths your notebooks use):
    streamlit run app.py
"""

import os
from pathlib import Path

import pandas as pd
import duckdb
import streamlit as st
from dotenv import load_dotenv
from google.genai.errors import ClientError

load_dotenv()

# ---------------------------------------------------------------------------
# Config -- same paths/values as your two notebooks
# ---------------------------------------------------------------------------
DATASET_DIR = Path(os.getenv("DATASET_DIR", r"C:\Users\BIT\Downloads\datasets\datasets"))
EQUIPMENT_XLSX = DATASET_DIR / "equipment_register" / "equipment_register.xlsx"
MAINTENANCE_XLSX = DATASET_DIR / "maintenance_reports" / "maintenance_reports.xlsx"
INSPECTION_XLSX = DATASET_DIR / "inspection_reports" / "inspection_reports.xlsx"
INCIDENT_XLSX = DATASET_DIR / "incident_reports" / "incident_reports.xlsx"

CHROMA_DIR = Path("./chroma_db_clean")
CHROMA_COLLECTION = "plant_documents_clean"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

TOP_K = 5

st.set_page_config(page_title="Plant Knowledge Copilot", layout="wide", page_icon="🏭")

st.markdown(
    """
    <style>
    /* ---- page background ---- */
    .stApp {
        background: linear-gradient(160deg, #0f1a24 0%, #16232f 45%, #0f1a24 100%);
        color: #e6edf3;
    }

    /* ---- main title ---- */
    h1 {
        background: linear-gradient(90deg, #2dd4bf, #f59e0b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    [data-testid="stCaptionContainer"] {
        color: #9fb3c8 !important;
    }

    /* ---- chat input box ---- */
    [data-testid="stChatInput"] textarea {
        background-color: #16232f;
        color: #e6edf3;
        border: 1px solid #2dd4bf55;
        border-radius: 10px;
    }

    /* ---- chat message bubbles ---- */
    [data-testid="stChatMessage"] {
        background-color: #16232f;
        border-radius: 14px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.6rem;
        border: 1px solid #24354533;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        border-left: 4px solid #2dd4bf;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        border-left: 4px solid #f59e0b;
    }

    /* ---- expander (sources) ---- */
    [data-testid="stExpander"] {
        background-color: #16232f;
        border: 1px solid #2dd4bf33;
        border-radius: 10px;
    }
    [data-testid="stExpander"] summary {
        color: #2dd4bf;
        font-weight: 600;
    }

    /* ---- code blocks (SQL/Cypher) ---- */
    .stCodeBlock, pre {
        border-radius: 8px !important;
        border: 1px solid #f59e0b33 !important;
    }

    /* ---- alert boxes ---- */
    [data-testid="stAlert"] {
        border-radius: 10px;
    }

    /* ---- spinner text ---- */
    .stSpinner > div {
        color: #2dd4bf;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY is not set. Add it to your .env file and restart.")
    st.stop()


# ---------------------------------------------------------------------------
# Cached resources -- built once per app session, not on every rerun/message
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading LLM...")
def get_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY, temperature=0)


@st.cache_resource(show_spinner="Loading vector store...")
def get_retriever():
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )
    count = vectorstore._collection.count()
    return vectorstore.as_retriever(search_kwargs={"k": TOP_K}), count


@st.cache_resource(show_spinner="Connecting to structured data...")
def get_sql_tools():
    from langchain_community.utilities import SQLDatabase
    from langchain_classic.chains import create_sql_query_chain
    from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool

    df_equipment = pd.read_excel(EQUIPMENT_XLSX)
    df_maintenance = pd.read_excel(MAINTENANCE_XLSX)
    df_inspection = pd.read_excel(INSPECTION_XLSX)
    df_incident = pd.read_excel(INCIDENT_XLSX)

    duckdb_path = "plant_data.duckdb"
    con = duckdb.connect(duckdb_path)
    con.execute("CREATE OR REPLACE TABLE equipment AS SELECT * FROM df_equipment")
    con.execute("CREATE OR REPLACE TABLE maintenance AS SELECT * FROM df_maintenance")
    con.execute("CREATE OR REPLACE TABLE inspection AS SELECT * FROM df_inspection")
    con.execute("CREATE OR REPLACE TABLE incident AS SELECT * FROM df_incident")
    con.close()

    sql_db = SQLDatabase.from_uri(f"duckdb:///{duckdb_path}")
    write_sql_query = create_sql_query_chain(get_llm(), sql_db)
    run_sql_query = QuerySQLDataBaseTool(db=sql_db)
    return write_sql_query, run_sql_query


@st.cache_resource(show_spinner="Connecting to Neo4j...")
def get_graph_chain():
    from langchain_community.graphs import Neo4jGraph
    from langchain_classic.chains import GraphCypherQAChain

    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASSWORD)
    graph.refresh_schema()
    return GraphCypherQAChain.from_llm(
        llm=get_llm(),
        graph=graph,
        verbose=False,
        allow_dangerous_requests=True,
        # NOTE: return_direct=False (the default) on purpose. With
        # return_direct=True, this chain hands back bare Cypher rows (e.g.
        # raw Equipment node properties) with no explanation of *why* they
        # matched -- our downstream answer_chain then can't see the
        # incident/maintenance details that justified the match and ends up
        # saying "no evidence" even when the graph traversal was correct.
        # With return_direct=False, GraphCypherQAChain synthesizes its own
        # natural-language answer from the actual query results, which we
        # then pass along as evidence -- much more reliable.
    )


# ---------------------------------------------------------------------------
# Tools -- same logic as notebook 2
# ---------------------------------------------------------------------------
import re


def _clean_sql(raw: str) -> str:
    """Strip prompt scaffolding and markdown code fences from the LLM's SQL
    output. create_sql_query_chain's output format varies -- sometimes plain
    SQL, sometimes wrapped in ```sql ... ``` -- and a bare .strip("`") only
    removes the backtick characters, leaving a stray "sql" language tag on
    its own line that breaks the startswith("SELECT") check downstream."""
    s = raw.strip()
    s = s.split("SQLQuery:")[-1].strip()
    s = re.sub(r"^```(?:sql)?\s*\n?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\n?```\s*$", "", s)
    s = re.sub(r"^sql\s*\n", "", s, flags=re.IGNORECASE)
    return s.strip()


def structured_search(question: str):
    write_sql_query, run_sql_query = get_sql_tools()
    raw_sql = write_sql_query.invoke({"question": question})
    sql = _clean_sql(raw_sql)
    if not sql.upper().startswith("SELECT"):
        return {"sql": sql, "result": None, "error": f"Refused: generated query was not a SELECT (got: {sql[:80]!r})"}
    try:
        result = run_sql_query.invoke(sql)
        return {"sql": sql, "result": result, "error": None}
    except Exception as e:
        return {"sql": sql, "result": None, "error": str(e)}


ROUTE_SYSTEM_PROMPT = """Classify a plant-maintenance question into one or more routes:
- vector: needs free-text knowledge from manuals/SOPs (procedures, specs, safety steps)
- structured: needs counting/filtering/aggregating over tabular logs
- graph: needs multi-hop relationships between equipment, maintenance, inspections, incidents

Return ONLY a comma-separated list using these three words, nothing else."""

ANSWER_SYSTEM_PROMPT = """You are a plant maintenance and safety assistant.
Answer using ONLY the evidence provided. Cite the source file/page for manual/SOP facts,
and the record id for structured/graph facts. If evidence is missing, say so plainly."""


def classify_routes(question: str):
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    route_prompt = ChatPromptTemplate.from_messages(
        [("system", ROUTE_SYSTEM_PROMPT), ("human", "{question}")]
    )
    route_chain = route_prompt | get_llm() | StrOutputParser()
    raw = route_chain.invoke({"question": question})
    routes = [r.strip().lower() for r in raw.split(",") if r.strip().lower() in ("vector", "structured", "graph")]
    return routes or ["vector"]


def gather_evidence(question: str, routes: list):
    retriever, _ = get_retriever()
    evidence_parts = []
    detail = {}

    if "vector" in routes:
        docs = retriever.invoke(question)
        detail["vector"] = docs
        evidence_parts.append("DOCUMENT EXCERPTS:")
        for d in docs:
            evidence_parts.append(f"- [{d.metadata.get('source_file')}, p.{d.metadata.get('page')}] {d.page_content[:400]}")

    if "structured" in routes:
        s = structured_search(question)
        detail["structured"] = s
        evidence_parts.append(f"\nSTRUCTURED QUERY (SQL): {s['sql']}")
        evidence_parts.append(f"Result: {s['result'] if not s['error'] else s['error']}")

    if "graph" in routes:
        graph_chain = get_graph_chain()
        g = graph_chain.invoke({"query": question})
        detail["graph"] = g
        evidence_parts.append(f"\nGRAPH ANSWER: {g['result']}")

    return "\n".join(evidence_parts), detail


def answer_question(question: str):
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    routes = classify_routes(question)
    evidence_text, detail = gather_evidence(question, routes)

    answer_prompt = ChatPromptTemplate.from_messages(
        [("system", ANSWER_SYSTEM_PROMPT), ("human", "Question: {question}\n\nEvidence:\n{evidence}")]
    )
    answer_chain = answer_prompt | get_llm() | StrOutputParser()
    final_answer = answer_chain.invoke({"question": question, "evidence": evidence_text})

    return {"routes": routes, "answer": final_answer, "detail": detail}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("🏭 Plant Knowledge Copilot")
st.caption("Ask about manuals, SOPs, or equipment history. Answers are grounded in your dataset.")
st.markdown("<hr style='border-color:#2dd4bf33; margin-top:0;'>", unsafe_allow_html=True)

_, vector_count = get_retriever()
expected_count = 2656  # from notebook 1's clean build: 849 pages -> 2656 chunks
if vector_count > expected_count * 1.5:
    st.warning(
        f"Vector store has {vector_count} chunks, but a clean build should have ~{expected_count}. "
        f"This usually means notebook 1's ingestion cell was run more than once and duplicated chunks. "
        f"Fix: delete the `chroma_db/` folder and re-run notebook 1's ingestion cell exactly once."
    )

if "history" not in st.session_state:
    st.session_state.history = []

question = st.chat_input("Ask a question about your plant...")

for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                result = answer_question(question)
        except ClientError as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                st.error(
                    f"Gemini free-tier rate limit hit for `{GEMINI_MODEL}` "
                    f"(this model's free tier allows a limited number of requests per day). "
                    f"Wait a bit and try again, or switch GEMINI_MODEL in .env to a model with "
                    f"a higher free quota."
                )
            else:
                st.error(f"LLM call failed: {e}")
            st.stop()

        st.markdown(result["answer"])

        with st.expander(f"Sources used (routes: {', '.join(result['routes'])})"):
            detail = result["detail"]
            if "vector" in detail:
                st.markdown("**Document excerpts**")
                for d in detail["vector"]:
                    st.markdown(f"- `{d.metadata.get('source_file')}` (page {d.metadata.get('page')}): {d.page_content[:200]}...")
            if "structured" in detail:
                st.markdown("**Structured query**")
                st.code(detail["structured"]["sql"], language="sql")
                if detail["structured"]["error"]:
                    st.error(detail["structured"]["error"])
                else:
                    st.write(detail["structured"]["result"])
            if "graph" in detail:
                st.markdown("**Graph answer**")
                st.write(detail["graph"]["result"])

    st.session_state.history.append({"role": "assistant", "content": result["answer"]})
