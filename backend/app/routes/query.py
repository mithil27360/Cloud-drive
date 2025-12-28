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
    contexts: List[str] # Added for audit
    metadata: Optional[Dict[str, Any]] = None # Added for latency

class EvaluateRequest(BaseModel):
    question: str
    answer: str
    contexts: List[str]

@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    import time
    start_time = time.time()
    
    try:
        if current_user.id == 0:
             pass # Mock admin handling if needed
             
        # 1. Retrieve relevant chunks
        t0 = time.time()
        results = engine.query_documents(
            request.query, 
            user_id=current_user.id,
            file_ids=request.file_ids
        )
        t_retrieval = time.time() - t0
        
        contexts = []
        if not results:
            answer = """I couldn't find relevant information for that query in your documents. 

**Try asking more specific questions about the content**, such as:
- "What is the main topic of [document name]?"
- "Explain the concept of [topic] from my files."
- "What does the document say about [specific subject]?"

Your uploaded files: You can see your file list in the sidebar."""
            sources = []
        else:
            # 2. Generate answer using LLM
            t1 = time.time()
            answer = generate_response(request.query, results)
            t_generation = time.time() - t1
            sources = results
            contexts = [res["content"] for res in results]
        
        # 3. Save to Chat History (Skip for admin/id=0 to avoid FK error)
        if current_user.id != 0:
            chat_entry = models.ChatHistory(
                user_id=current_user.id,
                query=request.query,
                answer=answer
            )
            db.add(chat_entry)
            db.commit()

        total_time = time.time() - start_time
        
        return {
            "answer": answer,
            "sources": sources,
            "contexts": contexts,
            "metadata": {
                "retrieval_time": t_retrieval if results else 0,
                "generation_time": t_generation if results else 0,
                "total_time": total_time
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@router.post("/evaluate")
def evaluate_response(req: EvaluateRequest):
    """
    Run RAGAS Faithfulness check on a specific Q&A pair.
    """
    try:
        import os
        from ragas import evaluate
        from ragas.metrics import faithfulness
        from datasets import Dataset
        from langchain_groq import ChatGroq
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not set")
            
        # 1. Configure LLM
        # Ragas needs an LLM    # Use smaller model to save tokens/latency
        llm = ChatGroq(model="llama-3.1-8b-instant", api_key=api_key)
        
        # 2. Format data
        data = {
            'question': [req.question],
            'answer': [req.answer],
            'contexts': [req.contexts], 
            # Ground truth optional for faithfulness
        }
        dataset = Dataset.from_dict(data)
        
        # 3. Optimized Audit: Generate Score AND Explanation in one pass (Latency < 3s)
        audit_prompt = f"""
        You are a strict RAG Outcome Auditor.
        Task: Verify if the ANSWER is supported by the CONTEXTS.
        
        CONTEXTS:
        {req.contexts}
        
        ANSWER:
        {req.answer}
        
        CRITICAL INSTRUCTIONS (Follow these steps mentally):
        1. **Check "Negative Claims"**: If the Answer says "The text does not provide details about X", LOOK at the Contexts. IF the Contexts DO have a table/list about X, the Answer is LYING (Hallucination).
        2. **Check "False Accusations"**: Before saying "The Answer failed to mention Y", SEARCH the Answer for "Y". If it's there, do NOT penalize.
        3. **Check Logic**: Verify technical details (e.g., Inputs vs Outputs). mistaking an Output for an Input is a Hallucination.
        
        SCORING RUBRIC:
        - **1.0**: Perfect.
        - **0.8**: Mostly correct, minor missed nuance.
        - **0.5**: Notable error (e.g., claiming data is missing when it's there).
        - **0.0**: Complete hallucination.

        FORMAT YOUR RESPONSE AS VALID JSON:
        {{
            "score": <float>,
            "explanation": "<string concise_reasoning>"
        }}
        """
        
        # Invoke LLM
        response = llm.invoke(audit_prompt).content
        
        # Parse JSON output (Handle potential formatting noise)
        import json
        import re
        
        try:
            # Extract JSON block if wrapped in code fences
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(response)
                
            score = data.get("score", 0.0)
            explanation = data.get("explanation", "Could not parse explanation.")
            
        except Exception as e:
            print(f"Audit Parse Error: {e} | Response: {response}")
            score = 0.5
            explanation = "Error parsing auditor response. Please try again."

        return {
            "faithfulness": score,
            "explanation": explanation
        }
        
    except Exception as e:
        print(f"Evaluation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
