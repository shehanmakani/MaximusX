"""
Maximus-X Sentinel — Context Membrane
=======================================
The "Context Membrane" is a nightly auto-ingestion pipeline that pulls
your local notes, emails, and documents into Qdrant so every sub-agent
has access to YOUR personal context — not just generic LLM knowledge.

Collections:
  default   → general notes, emails, web clips
  chembiz   → ChemRich/ChemeNova docs, SDS sheets, price lists, leads

Run modes:
  python -m app.rag ingest       → one-shot full ingest
  python -m app.rag watch        → filesystem watch + incremental ingest
  python -m app.rag query "..."  → test a query
"""

import os
import sys
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)
from langchain_ollama import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger("context-membrane")

# ── Config ────────────────────────────────────────────────────────────────────

QDRANT_URL = os.getenv("VECTOR_DB_URL", "http://localhost:6333")
OLLAMA_HOST = os.getenv("MODEL_HOST", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"      # pull with: ollama pull nomic-embed-text
VECTOR_DIM = 768

COLLECTIONS = {
    "default": "maximus_context",
    "chembiz": "maximus_chembiz",
}

# Document source directories (mount into container via docker-compose)
INGEST_DIRS = {
    "default": [
        "/app/memory/notes",
        "/app/memory/emails",
        "/app/memory/web_clips",
    ],
    "chembiz": [
        "/app/memory/chembiz",         # SDS sheets, price lists, lead lists, COAs
        "/app/memory/intelliform",     # IntelliForm project docs
    ],
}

# ── Client setup ──────────────────────────────────────────────────────────────

def get_qdrant() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)

def get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_HOST)

def ensure_collections(client: QdrantClient):
    """Create collections if they don't exist."""
    for name, collection in COLLECTIONS.items():
        existing = [c.name for c in client.get_collections().collections]
        if collection not in existing:
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
            )
            logger.info(f"Created collection: {collection}")

# ── Ingestion ─────────────────────────────────────────────────────────────────

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()

def load_file(path: Path) -> str:
    """Read text from .txt, .md, .pdf, .docx, .html files."""
    suffix = path.suffix.lower()
    try:
        if suffix in (".txt", ".md"):
            return path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(str(path))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        elif suffix == ".docx":
            import docx
            doc = docx.Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        elif suffix in (".html", ".htm"):
            import html2text
            return html2text.html2text(path.read_text(errors="ignore"))
        else:
            return ""
    except Exception as e:
        logger.warning(f"Could not read {path}: {e}")
        return ""

def ingest_file(path: Path, collection_key: str, client: QdrantClient, embeddings: OllamaEmbeddings):
    """Chunk, embed, and upsert a single file into Qdrant."""
    text = load_file(path)
    if not text.strip():
        return 0

    chunks = splitter.split_text(text)
    vectors = embeddings.embed_documents(chunks)
    file_id = file_hash(path)
    collection = COLLECTIONS[collection_key]

    points = [
        PointStruct(
            id=abs(hash(f"{file_id}_{i}")) % (2**63),
            vector=vec,
            payload={
                "text": chunk,
                "source": str(path),
                "file_hash": file_id,
                "collection_key": collection_key,
                "ingested_at": datetime.utcnow().isoformat(),
            },
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]

    client.upsert(collection_name=collection, points=points)
    logger.info(f"Ingested {len(points)} chunks from {path.name} → {collection}")
    return len(points)

def run_full_ingest():
    """Ingest all documents from all configured source directories."""
    client = get_qdrant()
    embeddings = get_embeddings()
    ensure_collections(client)

    total = 0
    for collection_key, dirs in INGEST_DIRS.items():
        for dir_path in dirs:
            p = Path(dir_path)
            if not p.exists():
                logger.debug(f"Skipping missing dir: {dir_path}")
                continue
            for file_path in p.rglob("*"):
                if file_path.is_file():
                    n = ingest_file(file_path, collection_key, client, embeddings)
                    total += n

    logger.info(f"Full ingest complete. Total chunks: {total}")
    return total

# ── Search ────────────────────────────────────────────────────────────────────

def search_context_membrane(query: str, collection: str = "default", top_k: int = 5) -> str:
    """
    Search the Context Membrane for relevant personal context.
    Returns formatted text results for use by sub-agents.
    """
    client = get_qdrant()
    embeddings = get_embeddings()
    collection_name = COLLECTIONS.get(collection, COLLECTIONS["default"])

    try:
        query_vec = embeddings.embed_query(query)
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vec,
            limit=top_k,
        )

        if not results:
            return f"No relevant context found for: {query}"

        formatted = []
        for r in results:
            source = Path(r.payload.get("source", "unknown")).name
            text = r.payload.get("text", "")
            score = round(r.score, 3)
            formatted.append(f"[{source} | relevance: {score}]\n{text}")

        return "\n\n---\n\n".join(formatted)

    except Exception as e:
        return f"Context Membrane search error: {e}"

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ingest"

    if cmd == "ingest":
        n = run_full_ingest()
        print(f"Ingested {n} total chunks.")

    elif cmd == "query":
        q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "chemical formulation"
        col = "default"
        if "--chembiz" in sys.argv:
            col = "chembiz"
        result = search_context_membrane(q, collection=col)
        print(result)

    else:
        print("Usage: python -m app.rag [ingest|query <text>] [--chembiz]")
