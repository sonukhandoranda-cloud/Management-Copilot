# Management Copilot

An AI-powered industrial maintenance and plant knowledge assistant that combines **Vector RAG, Structured SQL RAG, and Graph RAG** to answer questions using equipment manuals, maintenance records, inspection reports, and incident data.

## Overview

Management Copilot helps users retrieve operational knowledge and analyze industrial maintenance data through a natural-language interface.

Instead of relying on a single retrieval method, the system routes questions to different knowledge sources depending on the information required.

### Key Features

- **Vector RAG:** Semantic search across equipment manuals and technical documents.
- **Structured RAG:** Natural-language querying of industrial records using SQL and DuckDB.
- **Graph RAG:** Relationship-based queries across equipment, maintenance, inspections, and incidents using Neo4j.
- **LLM-powered responses:** Uses Google Gemini to classify questions and generate evidence-based answers.
- **Source attribution:** Provides document references, page numbers, and record-based evidence.

## Architecture

The application uses three retrieval paths:

| Component | Technology | Purpose |
|---|---|---|
| Vector database | ChromaDB | Search manuals and technical documents |
| Embeddings | all-MiniLM-L6-v2 | Semantic document representations |
| Structured database | DuckDB | Query equipment and maintenance records |
| Knowledge graph | Neo4j | Explore relationships between plant entities |
| LLM | Google Gemini | Routing, SQL/Cypher generation and answer generation |
| Interface | Streamlit | User interaction |

### Retrieval Workflow

1. User submits a natural-language question.
2. Gemini classifies the question into one or more retrieval routes.
3. The relevant retrieval components collect evidence.
4. Gemini generates an answer using the retrieved evidence.
5. The application displays the answer and supporting sources.

## Technology Stack

- Python
- Streamlit
- Google Gemini API
- LangChain
- ChromaDB
- Sentence Transformers
- DuckDB
- Neo4j
- Pandas

## Project Structure

```text
Management-Copilot/
│
├── app.py
├── clean_chroma.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env
│
├── chroma_db/
│
├── NoteBooks/
│   ├── chroma_db/
│   ├── chroma_db_clean/
│   ├── plant_data.duckdb
│   ├── Vector_rag_langchain.ipynb
│   └── graph_structured_rag.ipynb
│
└── venv/
```

**Note:** Database directories, virtual environments, and `.env` are local resources and should not be committed to GitHub.

## Installation and Setup

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd Management-Copilot
```

### 2. Create a virtual environment

Python 3.12 is recommended for the tested setup.

```bash
python -m venv venv
```

Activate it on Windows Git Bash:

```bash
source venv/Scripts/activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install streamlit langchain-classic
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

Never commit your `.env` file or expose API credentials.

### 5. Configure datasets

The application expects four Excel datasets:

```text
datasets/
├── equipment_register/
│   └── equipment_register.xlsx
│
├── maintenance_reports/
│   └── maintenance_reports.xlsx
│
├── inspection_reports/
│   └── inspection_reports.xlsx
│
└── incident_reports/
    └── incident_reports.xlsx
```

The default dataset location in the application is:

```text
C:\Users\BIT\Downloads\datasets\datasets
```

Configure `DATASET_DIR` in `.env` or adjust the application configuration to match your local dataset directory.

The existing DuckDB database contains the following tables:

- equipment
- maintenance
- inspection
- incident

### 6. Configure Neo4j

Install Neo4j Desktop or configure a Neo4j server.

Start a database and configure its connection details in `.env`.

The graph must be populated with the equipment, maintenance, inspection, and incident relationships before graph-based questions can return meaningful results.

### 7. Run the application

From the project root:

```bash
cd NoteBooks
streamlit run ../app.py
```

Open the local URL displayed in the terminal, normally:

```text
http://localhost:8501
```

## ChromaDB Deduplication Improvement

The original ChromaDB collection contained repeated document chunks caused by repeated ingestion.

An inspection identified:

| Metric | Original | Clean |
|---|---:|---:|
| Total chunks | 13,280 | 2,648 |
| Unique source/page chunks | — | 2,648 |
| Duplicate copies removed | — | 10,632 |
| Metadata conflict groups | — | 0 |

The deduplication process:

- Identifies repeated document content.
- Preserves source filename and page information.
- Reuses existing embeddings.
- Creates a separate clean collection.
- Leaves the original collection untouched.

The clean collection is stored at:

```text
NoteBooks/chroma_db_clean/
```

The application uses the clean collection:

```python
CHROMA_DIR = Path("./chroma_db_clean")
CHROMA_COLLECTION = "plant_documents_clean"
```

To reproduce the deduplication process:

```bash
python clean_chroma.py
```

The script expects the original collection to exist at `NoteBooks/chroma_db/`.

## Current Limitations

- Gemini API access requires a valid API key.
- Neo4j must be running and populated for graph-based queries.
- The required industrial Excel datasets must be available locally.
- Database files and document collections are not included in the Git repository.
- SQL and graph query generation should be validated and secured before production deployment.

## Future Improvements

- Conversation memory and contextual follow-up questions.
- Improved SQL query validation and execution safety.
- Better retrieval ranking and relevance filtering.
- Enhanced error handling and logging.
- Automated evaluation of retrieval quality.
- Improved graph query validation.
- Unit and integration testing.

## License

Add an appropriate license before distributing or reusing this project.
