import re
from typing import Dict, List
import chromadb
from chromadb.utils import embedding_functions

def row_to_document(row: Dict[str, str]) -> str:
    track_type = row.get('track_type', 'yearly')
    return (
        f"Task Name: {row['task_name']}\n"
        f"Description: {row['description']}\n"
        f"Help Text: {row['help_text']}\n"
        f"Company Name: {row['company_name']}\n"
        f"Unit Name: {row['unit_name']}\n"
        f"State: {row['state']}\n"
        f"Due Date: {row['due_date']}\n"
        f"Track Type: {track_type}"
    )

def build_collection():
    client = chromadb.PersistentClient(path="./chroma_db")
    # Device="cpu" prevents the PyTorch Meta Tensor crash
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2",
        device="cpu"
    )
    return client.get_or_create_collection(
        name="semantic_search",
        embedding_function=embedding_fn,
    )

def index_tasks(collection, task_rows: List[Dict[str, str]]) -> None:
    ids, docs, metas = [], [], []

    for i, row in enumerate(task_rows, start=1):
        task_id = str(row.get('id', i))
        ids.append(task_id)
        docs.append(row_to_document(row))
        metas.append(
            {
                "task_name": row["task_name"],
                "description": row["description"],
                "due_date": row["due_date"],
                "company_name": row["company_name"],
                "unit_name": row["unit_name"],
                "state": row["state"],
                "help_text": row["help_text"],
                "track_type": row.get("track_type", "yearly"),
            }
        )

    collection.upsert(ids=ids, documents=docs, metadatas=metas)

def index_single_task(collection, task_row: Dict) -> None:
    doc = row_to_document(task_row)
    task_id = str(task_row.get("id"))
    meta = {
        "task_name": task_row["task_name"],
        "description": task_row["description"],
        "due_date": task_row["due_date"],
        "company_name": task_row["company_name"],
        "unit_name": task_row["unit_name"],
        "state": task_row["state"],
        "help_text": task_row["help_text"],
        "track_type": task_row.get("track_type", "yearly"),
    }
    collection.upsert(ids=[task_id], documents=[doc], metadatas=[meta])

def search_tasks(collection, query_text: str, top_k: int = 5):
    results = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    
    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "distance": float(results["distances"][0][i]),
            "metadata": results["metadatas"][0][i],
            "document": results["documents"][0][i]
        })
    return hits

def rerank_with_word_overlap(query_text: str, candidates: List[Dict]) -> List[Dict]:
    query_words = set(re.findall(r"[a-zA-Z0-9]+", query_text.lower()))
    scored = []

    for c in candidates:
        doc_words = set(re.findall(r"[a-zA-Z0-9]+", c["document"].lower()))
        overlap = len(query_words.intersection(doc_words))
        score = (1.0 / (1.0 + c["distance"])) + (overlap * 0.05)
        scored.append({**c, "overlap_score": overlap, "final_score": score})

    return sorted(scored, key=lambda x: x["final_score"], reverse=True)

def confidence_from_distance(distance: float) -> str:
    if distance <= 0.35: return "High"
    if distance <= 0.50: return "Medium"
    return "Low"
