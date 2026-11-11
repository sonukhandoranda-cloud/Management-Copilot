
import os
from dotenv import load_dotenv

from langchain_community.graphs import Neo4jGraph
from langchain_classic.chains import GraphCypherQAChain
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv(".env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

if not NEO4J_PASSWORD or not GEMINI_API_KEY:
    raise ValueError("Missing Neo4j or Gemini credentials in .env")

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GEMINI_API_KEY,
    temperature=0
)

print("Gemini initialized.")

graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USER,
    password=NEO4J_PASSWORD,
    enhanced_schema=False
)

graph.refresh_schema()

print("\n========== NEO4J SCHEMA ==========")
print(graph.schema)

chain = GraphCypherQAChain.from_llm(
    llm=llm,
    graph=graph,
    verbose=True,
    allow_dangerous_requests=True,
    return_direct=False
)

questions = [
    "Which equipment has experienced incidents and also undergone maintenance?Return the equipment ID, equipment name, and equipment code.",
    "Which equipment has the highest number of inspection records?"
]

for index, question in enumerate(questions, start=1):
    print(f"\n========== TEST {index} ==========")
    print("QUESTION:", question)

    try:
        result = chain.invoke({"query": question})
        print("\nANSWER:")
        print(result["result"])
    except Exception as error:
        print("\nQUERY FAILED:")
        print(error)


print("\nGRAPH RAG TEST COMPLETED")
