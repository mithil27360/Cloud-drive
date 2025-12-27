from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .. import database, models, auth
from ..rag import engine
from ..rag.llm import generate_response

router = APIRouter(
    prefix="/api",
    tags=["query"]
)

class QueryRequest(BaseModel):
    query: str
    file_ids: Optional[List[int]] = None  # Optional list of file IDs to search

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]

@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        # 1. Retrieve relevant chunks
        results = engine.query_documents(
            request.query, 
            user_id=current_user.id,
            file_ids=request.file_ids
        )
        
        if not results:
            answer = "I couldn't find any relevant information in your uploaded documents."
            sources = []
        else:
            # 2. Generate answer using LLM
            answer = generate_response(request.query, results)
            sources = results
        
        # 3. Save to Chat History
        chat_entry = models.ChatHistory(
            user_id=current_user.id,
            query=request.query,
            answer=answer
        )
        db.add(chat_entry)
        db.commit()

        return {
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
