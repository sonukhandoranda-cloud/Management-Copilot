
import chromadb
from collections import defaultdict, Counter
from hashlib import sha256
import json
import os

SOURCE_PATH = "NoteBooks/chroma_db"
TARGET_PATH = "NoteBooks/chroma_db_clean"

source_client = chromadb.PersistentClient(path=SOURCE_PATH)
source = source_client.get_collection("plant_documents")

# Never overwrite an existing clean database.
if os.path.exists(TARGET_PATH) and os.listdir(TARGET_PATH):
    raise RuntimeError(
        "Clean database already exists. Inspect it before proceeding."
    )

data = source.get(
    include=["documents", "metadatas", "embeddings"]
)

groups = defaultdict(list)

for i, (doc, meta) in enumerate(
    zip(data["documents"], data["metadatas"])
):
    source_file = meta.get("source_file") or meta.get("source", "")
    page = meta.get("page", meta.get("page_label", ""))

    # Preserve identical text when it belongs to a different source/page.
    key = (doc, str(source_file), str(page))
    groups[key].append(i)

print("Original chunks:", len(data["documents"]))
print("Unique source/page chunks:", len(groups))

target_client = chromadb.PersistentClient(path=TARGET_PATH)

clean = target_client.create_collection(
    name="plant_documents_clean",
    metadata=source.metadata,
    embedding_function=None
)

ids, docs, metas, embeddings = [], [], [], []
metadata_conflicts = 0

for key, indices in groups.items():
    # Select the most frequent metadata version.
    versions = [
        json.dumps(data["metadatas"][i], sort_keys=True)
        for i in indices
    ]
    if len(set(versions)) > 1:
        metadata_conflicts += 1

    selected = Counter(versions).most_common(1)[0][0]
    meta = json.loads(selected)

    doc = data["documents"][indices[0]]
    embedding = data["embeddings"][indices[0]]

    stable_key = json.dumps(key, ensure_ascii=False)
    doc_id = sha256(stable_key.encode("utf-8")).hexdigest()

    ids.append(doc_id)
    docs.append(doc)
    metas.append(meta)
    embeddings.append(embedding.tolist())

# Insert in batches.
for start in range(0, len(ids), 500):
    end = start + 500

    clean.add(
        ids=ids[start:end],
        documents=docs[start:end],
        metadatas=metas[start:end],
        embeddings=embeddings[start:end]
    )

print("\nCLEAN COLLECTION CREATED")
print("Original count:", source.count())
print("Clean count:", clean.count())
print("Metadata conflict groups:", metadata_conflicts)
