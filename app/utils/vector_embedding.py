from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.models.doc_reader.document_chunk import DocumentChunk

model = SentenceTransformer("all-MiniLM-L6-v2")


def create_embedding(chunks):
    embeddings = []

    for chunk in chunks:
        embedding = model.encode(chunk, normalize_embeddings=True)
        embeddings.append(embedding.tolist())

    return embeddings


def search_similar_chunks(db: Session, query_embedding, top_k=5):
    chunks = (
        db.query(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
        .all()
    )

    return chunks


def retrieve_context(db: Session, question: str, top_k=5):
    query_embedding = model.encode(question, normalize_embeddings=True).tolist()
    chunks = search_similar_chunks(db, query_embedding, top_k)
    return chunks
