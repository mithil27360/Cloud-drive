from typing import List, Dict, Optional
import logging
from langchain_groq import ChatGroq
from ..config import settings
from .cache_manager import cache_manager

logger = logging.getLogger(__name__)

class QueryOptimizer:
    """
    Research-Grade Query Rewriting & Expansion Module.
    
     techniques:
    1. HyDE (Hypothetical Document Embeddings): 
       We hallucinate a "perfect" answer, then embed that. 
       Significantly improves zero-shot retrieval for vague queries.
       
    2. Multi-Query Expansion:
       Break a vague query into 3 distinct search angles.
       "how to fix bug" -> ["python debugging", "bug fix examples", "error handling"]
       
    3. Decomposition:
       Break complex multi-hop queries into sub-steps.
       
    Performance:
    - All LLM calls are cached via Layer 2 cache (TTL 24h) to ensure speed on repeat.
    """
    
    def __init__(self):
        self.llm = ChatGroq(
            model_name="llama-3.1-8b-instant",
            api_key=settings.GROQ_API_KEY,
            temperature=0.3
        )
        
    @cache_manager.cached_operation(prefix="hyde", ttl=86400)
    def generate_hyde_doc(self, query: str) -> str:
        """
        Generate a Hypothetical Document (HyDE) for the query.
        """
        prompt = f"""You are a helpful expert assistant. 
Please write a short, plausible passage that answers the following question. 
It doesn't need to be factually correct (we will use it for semantic search matching), but it should contain the right keywords and concepts.

Question: {query}
Hypothetical Answer:"""
        
        try:
            logger.info(f"Generating HyDE for: {query}")
            response = self.llm.invoke(prompt).content
            return response.strip()
        except Exception as e:
            logger.error(f"HyDE Failed: {e}")
            return query # Fallback to original

    @cache_manager.cached_operation(prefix="multi_query", ttl=86400)
    def expand_query(self, query: str) -> List[str]:
        """
        Expand a complex query into 3 distinct search variations.
        """
        prompt = f"""You are an AI research assistant. 
Break down the following user query into 3 distinct, specific search queries that would help find the answer in a technical documentation database.
Return ONLY the 3 queries, one per line. Do not number them.

Current Query: {query}
"""
        try:
            logger.info(f"Expanding Query: {query}")
            response = self.llm.invoke(prompt).content
            lines = [line.strip() for line in response.split('\n') if line.strip()]
            return lines[:3] # Limit to top 3
        except Exception as e:
            logger.error(f"Expansion Failed: {e}")
            return [query]

    def decompose_query(self, query: str) -> List[str]:
        """
        Decomposes complex multi-hop queries.
        (Placeholder for future expansion - simply mirrors expand for now)
        """
        return self.expand_query(query)
    
    def classify_intent(self, query: str) -> str:
        """
        Maps user query to specific academic section targets.
        """
        q = query.lower()
        
        # 1. Formula / Math / Implementation
        if any(w in q for w in ["formula", "equation", "math", "algorithm", "notation", "implementation", "code"]):
            return "FORMULA"
            
        # 2. Main Idea / Overview / Goal
        if any(w in q for w in ["main idea", "core idea", "summary", "abstract", "contribution", "goal", "purpose", "problem"]):
            return "OVERVIEW"
            
        # 3. Metrics / Results / SOTA
        if any(w in q for w in ["result", "performance", "score", "accuracy", "f1", "table", "graph", "benchmark", "sota"]):
            return "METRICS"
            
        # 4. Limitations / Critique
        if any(w in q for w in ["limitation", "drawback", "failure", "weakness", "critique", "gap"]):
             return "LIMITATIONS"
             
        # 5. Methodology / Specifics
        if any(w in q for w in ["how", "method", "approach", "architecture", "setup", "training"]):
            return "METHODOLOGY"

        return "GENERAL"

# Singleton
query_optimizer = QueryOptimizer()
