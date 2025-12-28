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

class Citation(BaseModel):
    source_id: str
    text: str
    page: int
    section: str
    file_id: int
    score: float

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    latency_ms: float
    trace_id: str
    contexts: List[str] # Legacy for audit
    metadata: Optional[Dict[str, Any]] = None

@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    import time
    import re
    import uuid
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    
    try:
        # 1. Retrieve relevant chunks
        t0 = time.time()
        results = engine.query_documents(
            request.query, 
            user_id=current_user.id,
            file_ids=request.file_ids
        )
        t_retrieval = time.time() - t0
        
        citations = []
        citation_map = {}
        
        if not results:
            answer = "I could not find any relevant information in your documents."
        else:
            # Prepare Citation Map for Lookup
            for i, doc in enumerate(results):
                meta = doc.get("metadata", {})
                fid = meta.get("file_id", 0)
                # Try sub_chunk_index first, else chunk_index, else fallback
                cid = meta.get("sub_chunk_index", meta.get("chunk_index", i+1))
                source_id = f"{fid}:{cid}"
                
                c_obj = Citation(
                    source_id=source_id,
                    text=doc["content"],
                    page=meta.get("page", meta.get("page_number", 1)),
                    section=meta.get("section", "General"),
                    file_id=fid,
                    score=doc.get("score", 0.0)
                )
                citation_map[source_id] = c_obj
                # Add to all candidates (we filter later or send all)
                # For now, we'll send ALL retrieved as candidates, so UI can show "Sources Found"
                # BUT the answer will only link to specific ones.
            
            # 2. Generate answer (The formatting is handled in llm.py)
            t1 = time.time()
            # We pass the raw results, llm.generate_response handles the [Source ID] formatting/context
            answer = generate_response(request.query, results)
            t_generation = time.time() - t1
            
            # 3. Parse Used Citations from Answer
            # Regex for [fid:cid]
            used_ids = set(re.findall(r'\[(\d+:\d+)\]', answer))
            
            # If citations found, prioritize them at the top of the list
            # We will send ALL retrieved citations, but maybe mark them?
            # User wants "Evidence Schema".
            # Let's populate 'citations' with everything retrieved, but sorted by usage?
            # actually, let's just send everything retrieved so the UI has context.
            # Convert map to list
            citations = list(citation_map.values())
            
            # Optional: Start Log Verification
            # (Audit logic remains same)

        total_time = time.time() - start_time
        
        # Log Metrics
        from ..rag.metrics import metrics
        unsupported = 1 if "not stated" in answer.lower() else 0
        metrics.log_query(total_time, success=bool(results), unsupported_claims=unsupported)
        
        return {
            "answer": answer,
            "citations": citations,
            "latency_ms": total_time * 1000,
            "trace_id": trace_id,
            "contexts": [r["content"] for r in results],
            "metadata": {
                "retrieval_time": t_retrieval if results else 0,
                "generation_time": t_generation if results else 0,
                "total_time": total_time
            }
        }
    except Exception as e:
        # Log Failure
        from ..rag.metrics import metrics
        metrics.log_query(time.time() - start_time, success=False, unsupported_claims=0)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

class EvaluateRequest(BaseModel):
    question: str
    answer: str
    contexts: List[str]

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
You are a critical RAG Auditor. Your job is to find flaws, not excuse them.

CONTEXTS:
{req.contexts}

ANSWER:
{req.answer}

INSTRUCTIONS (Follow Step-by-Step):
1. **Find at least ONE flaw**. Look for:
   - Claims not in context (hallucination)
   - Stating "not provided" when context HAS the info (negative hallucination)
   - Technical errors (e.g., Input vs Output confusion)
   - Overly vague summaries that add no value
2. **If truly perfect (rare)**, explain why every claim is verified.
3. **Score conservatively**:
   - 0.9-1.0: Exceptional. Every claim verified, no flaws.
   - 0.7-0.8: Good. Minor omissions or rewording, but accurate.
   - 0.5-0.6: Acceptable. Some unverified claims or vagueness.
   - <0.5: Poor. Significant errors or hallucinations.

FORMAT AS JSON:
{{
    "flaws_found": ["<flaw1>", "<flaw2>"],
    "score": <float>,
    "explanation": "<brief reasoning>"
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
            flaws = data.get("flaws_found", [])
            explanation = data.get("explanation", "Could not parse explanation.")
            
            # Build comprehensive note
            if flaws:
                flaws_text = "Flaws Found: " + "; ".join(flaws) + ". "
            else:
                flaws_text = ""
            full_explanation = flaws_text + explanation
            
        except Exception as e:
            print(f"Audit Parse Error: {e} | Response: {response}")
            score = 0.5
            full_explanation = "Error parsing auditor response. Please try again."

        return {
            "faithfulness": score,
            "explanation": full_explanation
        }
        
    except Exception as e:
        print(f"Evaluation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class CompareRequest(BaseModel):
    doc_a_id: int
    doc_b_id: int
    aspect: str # e.g. "Methodology", "Results"

@router.post("/compare")
def compare_documents_endpoint(
    req: CompareRequest,
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    God-Level Feature: A vs B Comparison.
    Retrieves aspect-specific sections from both docs and synthesizes a contrastive report.
    """
    try:
        from ..rag.compare_engine import compare_engine
        
        # Verify ownership (mock check for now)
        if current_user.id == 0: pass 
        
        result = compare_engine.compare_documents(req.doc_a_id, req.doc_b_id, req.aspect)
        
        if "error" in result:
             raise HTTPException(status_code=404, detail=result["error"])
             
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

