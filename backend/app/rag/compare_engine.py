import logging
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from langchain_groq import ChatGroq
from langchain.schema import SystemMessage, HumanMessage
from ..config import settings
from .engine import RAGEngine
from .indexer import get_collection

logger = logging.getLogger(__name__)

class CompareEngine:
    """
    God-Level Comparison Engine.
    
    Capabilities:
    1. Targeted Retrieval: Palls 'Method' chunks from Doc A and Doc B.
    2. Contrastive synthesis: "Doc A uses BERT, whereas Doc B uses LSTM."
    3. Structural Awareness: Knows which sections to pull based on user query.
    """
    
    def __init__(self):
        self.llm = ChatGroq(
            model_name="llama-3.1-8b-instant",
            api_key=settings.GROQ_API_KEY,
            temperature=0.2
        )
        self.rag_engine = RAGEngine() # Reuse for vector search
        
    def compare_documents(self, doc_a_id: int, doc_b_id: int, aspect: str) -> Dict:
        """
        Compare two documents on a specific aspect.
        """
        start_time = time.time()
        
        # 1. Map 'aspect' to query + section filter
        query_text = f"What is the {aspect}?"
        section_filter = self._map_aspect_to_section(aspect)
        
        # 2. Retrieve from Doc A
        context_a = self._get_focused_context(doc_a_id, query_text, section_filter)
        
        # 3. Retrieve from Doc B
        context_b = self._get_focused_context(doc_b_id, query_text, section_filter)
        
        # 4. Generate Comparison
        if not context_a and not context_b:
            return {"error": "Insufficient data in both documents for this aspect."}
            
        report = self._generate_comparison(aspect, context_a, context_b)
        
        return {
            "aspect": aspect,
            "report": report,
            "latency_ms": (time.time() - start_time) * 1000,
            "sources": {
                "doc_a": [c["metadata"].get("page", "?") for c in context_a],
                "doc_b": [c["metadata"].get("page", "?") for c in context_b]
            }
        }

    def _get_focused_context(self, file_id: int, query: str, section: Optional[str]) -> List[Dict]:
        """Fetch chunks for a specific file and optional section."""
        # We leverage RAGEngine's vector search but constrain by file_id strictly
        # We bypass the full engine.query pipeline to avoid re-ranking overhead on massive mismatch
        # We go direct to vector search for speed + precision on scope
        
        # Actually RAGEngine._vector_search is cached and robust. Let's use it.
        # But we need access to it. It's a method on instance.
        # We'll use the collection directly for maximum control or public methods.
        # Let's use RAGEngine.query with file_ids=[file_id]
        
        results = self.rag_engine.query(
            query, 
            user_id=1, # Default or pass in
            file_ids=[file_id],
            n_results=5 
        )
        
        # Post-filter by section if strictly required
        if section:
            filtered = [
                d for d in results 
                if section.lower() in d["metadata"].get("section", "").lower()
            ]
            if filtered:
                return filtered
        
        return results

    def _map_aspect_to_section(self, aspect: str) -> Optional[str]:
        aspect = aspect.lower()
        if "method" in aspect or "approach" in aspect:
            return "Method"
        if "result" in aspect or "performance" in aspect:
            return "Experiment"
        if "limitation" in aspect:
            return "Conclusion"
        return None

    def _generate_comparison(self, aspect: str, ctx_a: List[Dict], ctx_b: List[Dict]) -> str:
        text_a = "\n".join([c["content"] for c in ctx_a])
        text_b = "\n".join([c["content"] for c in ctx_b])
        
        prompt = f"""You are a Comparative Research Expert.
Task: Compare Document A and Document B regarding: "{aspect}".

Document A Context:
{text_a[:4000]}

Document B Context:
{text_b[:4000]}

Instructions:
1. Highlight key SIMILARITIES.
2. Highlight key DIFFERENCES.
3. Conclude which one is superior or more rigorous regarding {aspect} (if applicable).
4. Use a structured Markdown table for the differences.

Response:"""

        response = self.llm.invoke([
            SystemMessage(content="You are a precise academic analyst."),
            HumanMessage(content=prompt)
        ])
        return response.content

# Singleton
compare_engine = CompareEngine()
