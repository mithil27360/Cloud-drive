from typing import List, Dict, Optional, Tuple
import logging
import time
import uuid
from dataclasses import dataclass

# Core Components
from .indexer import get_collection, embedding_model
from .retrievers.reranker import reranker
from .retrievers.hybrid import hybrid_retriever
from .metrics import metrics
# Phase H Components
from .query_optimizer import query_optimizer
from .cache_manager import cache_manager

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    content: str
    metadata: Dict
    score: float
    source: str  # 'vector', 'bm25', 'hybrid'

class RAGEngine:
    """
    Production-Grade Query Engine.
    Orchestrates the Retrieval-Augmented Generation pipeline.
    
    Responsibilities:
    1. Query Analysis & Pre-filtering
    2. Query Optimization (HyDE / Multi-Query) [NEW]
    3. Parallel Hybrid Retrieval (Vector + Keyword)
    4. Result Fusion (RRF)
    5. Re-ranking (Cross-Encoder)
    6. Context Assembly (Parent-Child)
    7. Detailed Trace Logging
    """
    
    def __init__(self):
        self.collection = get_collection()
        
    def query(self, 
             query_text: str, 
             user_id: int, 
             file_ids: Optional[List[int]] = None, 
             n_results: int = 3) -> List[Dict]:
        """
        Execute full RAG retrieval pipeline with monitoring.
        """
        trace_id = str(uuid.uuid4())[:8]
        logger.info(f"[{trace_id}] Query Start: '{query_text}' (User: {user_id})")
        start_time = time.time()
        
        try:
            # 1. Importance Filter Analysis
            importance_filter = self._analyze_importance(query_text)
            
            # --- PHASE H: Query Optimization ---
            # 1a. Generate HyDE Document (for implicit context expansion)
            # Only use for short/vague queries (< 10 words) to avoid noise
            search_query = query_text
            if len(query_text.split()) < 10:
                hyde_doc = query_optimizer.generate_hyde_doc(query_text)
                if hyde_doc:
                    # Append HyDE concept to query for vector search (boosts recall)
                    # We blend it: 70% original, 30% hypothetical
                    # Simple Append Strategy for now:
                    logger.info(f"[{trace_id}] HyDE Expanded: {hyde_doc[:50]}...")
                    # We search using the generated answer as it mathematically aligns with target chunks
                    search_query = hyde_doc 
            # -----------------------------------
            
            # 2. Parallel Retrieval
            # Fetch more candidates for fusion (3x to 5x of final n)
            candidate_k = n_results * 5 if file_ids else n_results * 3
            
            # Vector Search uses ENHANCED query (HyDE)
            vector_docs = self._vector_search(search_query, user_id, file_ids, candidate_k, importance_filter)
            
            # BM25 uses ORIGINAL query (exact keyword match)
            bm25_docs = self._bm25_search(query_text, user_id, file_ids, candidate_k)
            
            # 3. Fusion
            fused_docs = hybrid_retriever.reciprocal_rank_fusion(vector_docs, bm25_docs)
            logger.info(f"[{trace_id}] Fusion: {len(vector_docs)} vec + {len(bm25_docs)} bm25 -> {len(fused_docs)} candidates")
            
            # 4. Re-ranking
            final_docs = self._rerank_results(query_text, fused_docs, n_results)
            
            # 5. Context Expansion (Parent-Child)
            expanded_docs = self._expand_context(final_docs)
            
            duration = time.time() - start_time
            logger.info(f"[{trace_id}] Query Complete in {duration:.3f}s. Returned {len(expanded_docs)} docs.")
            
            return expanded_docs
            
        except Exception as e:
            logger.error(f"[{trace_id}] Query Failed: {e}", exc_info=True)
            # Metrics logged at the route level usually, but we could add granular metrics here
            return []

    def _analyze_importance(self, query: str) -> Optional[str]:
        """Determine if query targets a specific importance section."""
        q_lower = query.lower()
        if any(kw in q_lower for kw in ['main', 'core', 'primary', 'key contribution', 'summary', 'abstract']):
            return 'core_contribution'
        return None

    @cache_manager.cached_operation(prefix="vector_search", ttl=3600)
    def _vector_search(self, query: str, user_id: int, file_ids: Optional[List[int]], k: int, importance: Optional[str]) -> List[Dict]:
        """Run Semantic Vector Search with ChromaDB."""
        try:
            emb = embedding_model.encode([query]).tolist()
            
            where_clause = {"user_id": user_id}
            
            # Note: ChromaDB 'where' clause is restrictive. 
            # Complex filtering (OR logic for importance) might need post-filtering if not supported by simple 'where'.
            # For now, if importance is set, strict filter.
            if importance:
                where_clause["importance"] = importance
            
            res = self.collection.query(
                query_embeddings=emb,
                n_results=k,
                where=where_clause
            )
            
            docs = []
            if res["documents"] and res["documents"][0]:
                for i in range(len(res["documents"][0])):
                    meta = res["metadatas"][0][i]
                    # Post-match file_id filter if needed (Chroma where logic limitation)
                    if file_ids and meta.get("file_id") not in file_ids:
                        continue
                        
                    docs.append({
                        "content": res["documents"][0][i],
                        "metadata": meta,
                        "score": res["distances"][0][i],
                        "id": res["ids"][0][i]
                    })
            return docs
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    # Short cache for BM25 as it's fast but good to avoid parsing if frequent
    @cache_manager.cached_operation(prefix="bm25_search", ttl=300) 
    def _bm25_search(self, query: str, user_id: int, file_ids: Optional[List[int]], k: int) -> List[Dict]:
        """Run Keyword Search via BM25."""
        try:
            candidates = hybrid_retriever.search_bm25(query, k=k)
            # Filter by user/file
            filtered = [
                d for d in candidates 
                if d["metadata"].get("user_id") == user_id
                and (not file_ids or d["metadata"].get("file_id") in file_ids)
            ]
            return filtered
        except Exception as e:
            logger.error(f"BM25 search error: {e}")
            return []

    @cache_manager.cached_operation(prefix="rerank", ttl=3600)
    def _rerank_results(self, query: str, docs: List[Dict], top_k: int) -> List[Dict]:
        """Apply Cross-Encoder Reranking."""
        if not docs:
            return []
        # Fallback if too many docs passed (latency guard)
        rerank_pool = docs[:top_k * 3] 
        return reranker.rerank(query, rerank_pool, top_k=top_k)

    def _expand_context(self, docs: List[Dict]) -> List[Dict]:
        """Swap child chunks for parent context if available."""
        expanded = []
        for d in docs:
            meta = d.get("metadata", {})
            if meta.get("is_child", False) and meta.get("parent_content"):
                # Use Parent Content for LLM
                d["content"] = meta["parent_content"]
                # Maybe mark as expanded for debug
                d["expanded"] = True
            expanded.append(d)
        return expanded

# Singleton Export
engine = RAGEngine()

# Facade for backward compatibility
def query_documents(query_text: str, user_id: int, file_ids: Optional[List[int]] = None, n_results: int = 3):
    return engine.query(query_text, user_id, file_ids, n_results)
