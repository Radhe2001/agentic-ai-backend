import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session
import re
from app.db.database import get_db
from app.utils.aws_s3 import upload_to_s3, generate_download_url, download_s3_file
from app.utils.vector_embedding import create_embedding, retrieve_context
import pymupdf
from app.models.doc_reader.document_chunk import DocumentChunk
from app.models.doc_reader.chats import Chats
from app.models.doc_reader.document import Documents
from pydantic import BaseModel
from app.ai_model.open_router import generate_answer
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from fastapi.concurrency import run_in_threadpool
from botocore.exceptions import BotoCoreError, ClientError
from fastapi.responses import StreamingResponse
from sqlalchemy import and_

router = APIRouter(prefix="/embedding", tags=["embedding"])

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def create_chunks(text, chunk_size=1000, overlap=200):
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(current_chunk) + len(paragraph) <= chunk_size:
            current_chunk += paragraph + "\n\n"
        else:
            chunks.append(current_chunk.strip())
            # Keep the end of the previous chunk as overlap
            overlap_text = current_chunk[-overlap:]
            current_chunk = overlap_text + "\n\n" + paragraph
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    # Read uploaded PDF into memory
    pdf_bytes = await file.read()

    if not pdf_bytes:
        raise HTTPException(400, "Uploaded PDF is empty")

    try:
        # Extract text from PDF
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
            text_parts = []

            for page in pdf:
                page_text = page.get_text()
                page_text = re.sub(r"[ \t]+", " ", page_text)
                text_parts.append(page_text)

        text = " ".join(text_parts).strip()

        if not text:
            raise HTTPException(
                status_code=422,
                detail="No extractable text found in PDF",
            )

        # Avoid duplicate processing by filename
        file_name = file.filename or "document.pdf"

        existing_document = (
            db.query(Documents)
            .filter(
                and_(
                    Documents.filename == file_name,
                    Documents.created_by == request.state.user_id,
                )
            )
            .first()
        )

        if existing_document:
            return {
                "message": "Document already exists",
                "document_id": existing_document.id,
            }

        # Create chunks and embeddings using your existing functions
        chunk_list = create_chunks(text)
        vector_embeddings = create_embedding(chunk_list)

        if len(chunk_list) != len(vector_embeddings):
            raise RuntimeError("Chunk and embedding counts do not match")

        # Upload original PDF to S3 (optional)
        s3_key = f"pdf_reader/{uuid4().hex}.pdf"

        await file.seek(0)

        upload_to_s3(
            BytesIO(pdf_bytes),
            s3_key,
            "application/pdf",
        )

        # Save document metadata
        document = Documents(
            filename=file_name, s3_key=s3_key, created_by=request.state.user_id
        )

        db.add(document)
        db.flush()  # Generates document.id

        # Save chunks and their embeddings
        for index, (chunk, embedding) in enumerate(zip(chunk_list, vector_embeddings)):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=embedding,
                )
            )

        db.commit()
        db.refresh(document)
        return {
            "message": "Document uploaded and embeddings saved",
            "id": document.id,
            "filename": s3_key,
            "name": document.filename,
            "created_at": document.created_at,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to process uploaded PDF")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {type(exc).__name__}: {exc}",
        ) from exc


class ChatRequest(BaseModel):
    question: str
    pdf_id: int


@router.get("/documents")
async def get_document(request: Request, db: Session = Depends(get_db)):
    user_id = request.state.user_id

    documents = db.query(Documents).filter(Documents.created_by == user_id).all()

    return {"documents": documents}


@router.post("/chat")
async def chat(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
):
    try:
        question = payload.question
        pdf_id = payload.pdf_id
        user_id = request.state.user_id

        chunks = retrieve_context(
            db,
            question,
            top_k=5,
        )

        context = "\n\n".join(chunk.content for chunk in chunks)

        answer = generate_answer(question, context)

        chat_record = Chats(
            user_id=user_id,
            app_type_id=1,
            pdf_id=pdf_id,
            question=question,
            content=answer,
        )

        db.add(chat_record)
        db.commit()
        db.refresh(chat_record)

        return {"chat": chat_record}

    except Exception:
        db.rollback()
        raise


class MessageRequest(BaseModel):
    pdf_id: int


@router.post("/messages")
async def get_messages(
    request: Request,
    payload: MessageRequest,
    db: Session = Depends(get_db),
):
    pdf_id = payload.pdf_id
    user_id = request.state.user_id

    data = (
        db.query(Chats)
        .filter(and_(Chats.user_id == user_id, Chats.pdf_id == pdf_id))
        .all()
    )
    print(data)
    return {"chat": data}


class DownloadRequest(BaseModel):
    url: str


@router.post("/download_file")
def download_file(payload: DownloadRequest, request: Request):
    key = payload.url

    stream = download_s3_file(key)

    if stream is None:
        raise HTTPException(status_code=404, detail="Unable to download file from S3")

    filename = key.split("/")[-1]

    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
