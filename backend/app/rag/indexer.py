import io
import tempfile
import os
from pydantic import BaseModel
from typing import List, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from ..config import settings
from .parsers.pdf_parser import pdf_parser
from .parsers.chunker import semantic_chunker
import logging

logger = logging.getLogger(__name__)

# Initialize ChromaDB Client (Lazy)
_chroma_client = None
_collection = None

def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=8000)
        _collection = _chroma_client.get_or_create_collection(name="documents")
    return _collection

# Initialize Embedding Model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

class DocumentChunk(BaseModel):
    id: str
    text: str
    metadata: dict
    embedding: Optional[List[float]] = None

def extract_text_from_file(file_content: bytes, content_type: str, file_id: int) -> tuple:
    """
    Extract text using production-grade parsers.
    
    Returns:
        Tuple of (text, metadata)
    """
    if "pdf" in content_type.lower():
        # Use advanced PDF parser
        try:
            # Save to temp file (PyMuPDF requires file path)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                result = pdf_parser.parse_pdf(tmp_path)
                
                if result["success"]:
                    logger.info(f"Successfully parsed PDF: {len(result['text'])} chars, {len(result['tables'])} tables")
                    return result["text"], result["metadata"]
                else:
                    logger.error(f"PDF parsing failed: {result.get('error', 'Unknown error')}")
                    # Fallback to basic extraction
                    return _fallback_pdf_extract(file_content), {}
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            logger.error(f"Advanced PDF extraction failed: {str(e)}, falling back to basic extraction")
            return _fallback_pdf_extract(file_content), {}
            
    elif "text" in content_type or "markdown" in content_type:
        text = file_content.decode("utf-8", errors="ignore")
        return text, {"content_type": content_type}
    else:
        return "", {}

def _fallback_pdf_extract(file_content: bytes) -> str:
    """Fallback PDF extraction using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except:
        return ""

def process_and_index_file(file_id: int, file_content: bytes, content_type: str, user_id: int):
    """
    Production-grade file processing and indexing.
    
    Uses:
    - Advanced PDF parsing (PyMuPDF + pdfplumber)
    - Semantic chunking (LangChain)
    - Metadata enrichment
    """
    logger.info(f"Processing file {file_id} for user {user_id}")
    
    # 1. Extract Text with Advanced Parser
    text, doc_metadata = extract_text_from_file(file_content, content_type, file_id)
    
    if not text or not text.strip():
        logger.warning(f"No text extracted for file {file_id}")
        return

    # 2. Semantic Chunking
    base_metadata = {
        "file_id": file_id,
        "user_id": user_id,
        **doc_metadata
    }
    
    chunks = semantic_chunker.chunk_text(text, metadata=base_metadata)
    logger.info(f"Created {len(chunks)} semantic chunks for file {file_id}")
    
    if not chunks:
        logger.warning(f"No chunks created for file {file_id}")
        return
    
    # 3. Create Embeddings
    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = embedding_model.encode(chunk_texts, show_progress_bar=False).tolist()
    
    # 4. Prepare Data for ChromaDB
    ids = [f"file_{file_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [chunk["metadata"] for chunk in chunks]
    
    # 5. Add to ChromaDB
    try:
        collection = get_collection()
        collection.add(
            documents=chunk_texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Successfully indexed file {file_id} with {len(chunks)} chunks")
    except Exception as e:
        logger.error(f"Failed to index file {file_id}: {str(e)}")
        raise
