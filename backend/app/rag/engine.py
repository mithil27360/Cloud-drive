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
            # 1. Intent Classification & Importance
            importance_filter = self._analyze_importance(query_text)
            intent = query_optimizer.classify_intent(query_text)
            logger.info(f"[{trace_id}] Intent Detected: {intent}")
            
            # --- PHASE H: Query Optimization ---
            # 1a. Generate HyDE Document (for implicit context expansion)
            search_query = query_text
            if len(query_text.split()) < 10:
                hyde_doc = query_optimizer.generate_hyde_doc(query_text)
                if hyde_doc:
                    logger.info(f"[{trace_id}] HyDE Expanded: {hyde_doc[:50]}...")
                    search_query = hyde_doc 
            # -----------------------------------
            
            # 2. Strategy Selection
            final_candidates = []
            
            # STRATEGY A: Targeted Section Search (The "Research-Grade" logic)
            if intent != "GENERAL":
                target_sections = self._map_intent_to_sections(intent)
                logger.info(f"[{trace_id}] Targeting Sections: {target_sections}")
                
                if target_sections:
                    # Fetch more candidates for targeted search to ensure coverage
                    targeted_docs = self._vector_search_targeted(
                        search_query, user_id, file_ids, k=n_results*4, sections=target_sections
                    )
                    final_candidates.extend(targeted_docs)
                    logger.info(f"[{trace_id}] Targeted Search found {len(targeted_docs)} chunks")

            # STRATEGY B: Global Search (Fallback & Supplement)
            # We always run this but with fewer K if targeted found something, 
            # or full K if intent is General.
            global_k = n_results * 2 if final_candidates else n_results * 5
            
            global_docs = self._vector_search(
                search_query, user_id, file_ids, k=global_k, importance=importance_filter
            )
            
            # Merge & Deduplicate (Keep targeted docs first implicitly via ID check)
            seen_ids = {d["id"] for d in final_candidates}
            for d in global_docs:
                if d["id"] not in seen_ids:
                    final_candidates.append(d)
                    seen_ids.add(d["id"])

            # 3. Keyword Supplement (BM25) - Good for specific acronyms/names
            bm25_docs = self._bm25_search(query_text, user_id, file_ids, k=n_results*2)
            
            # 4. Fusion (RRF)
            # Fusing Targeted + Global + Keyword
            fused_docs = hybrid_retriever.reciprocal_rank_fusion(final_candidates, bm25_docs)
            logger.info(f"[{trace_id}] Fusion: {len(final_candidates)} vec + {len(bm25_docs)} bm25 -> {len(fused_docs)} candidates")
            
            # 5. Re-ranking
            final_docs = self._rerank_results(query_text, fused_docs, n_results)
            
            # 6. Context Expansion (Parent-Child)
            expanded_docs = self._expand_context(final_docs)
            
            return expanded_docs
            
        except Exception as e:
            logger.error(f"[{trace_id}] Query Failed: {e}", exc_info=True)
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
            
            # ChromaDB requires explicit $and for multiple conditions
            if importance:
                where_clause = {
                    "$and": [
                        {"user_id": user_id},
                        {"importance": importance}
                    ]
                }
            else:
                where_clause = {"user_id": user_id}
            
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
            
            return docs
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def _map_intent_to_sections(self, intent: str) -> List[str]:
        """Maps intents to the SECTION METADATA extracted by your PDF Parser."""
        mapping = {
            "FORMULA": ["Method", "Methodology", "Algorithm", "Model", "Appendix", "Implementation"],
            "OVERVIEW": ["Abstract", "Introduction", "related work", "background"],
            "METRICS": ["Experiment", "Results", "Discussion", "Evaluation", "Tables"],
            "LIMITATIONS": ["Conclusion", "Discussion", "Limitation", "Future Work"],
            "METHODOLOGY": ["Method", "Methodology", "Proposed Approach", "Architecture"]
        }
        return mapping.get(intent, [])

    # Targeted Search Cache (separate prefix to avoid pollution)
    @cache_manager.cached_operation(prefix="vector_target", ttl=3600)
    def _vector_search_targeted(self, query: str, user_id: int, file_ids: Optional[List[int]], k: int, sections: List[str]) -> List[Dict]:
        """Run Vector Search constrained to specific sections."""
        try:
            emb = embedding_model.encode([query]).tolist()
            
            # ChromaDB $or syntax for metadata fields can be tricky.
            # We use $in operator if supported, or iterative query if needed.
            # standard where: {"user_id": 1, "section": {"$in": sections}}
            # BUT ChromaDB where clause is strict.
            # Let's try simple $or at top level or iterative if simpler.
            # Actually simplest is to just query and post-filter since we can't easily do AND(ID, OR(Section)) in old Chroma versions.
            # Wait, we need "TARGETED" meaning we search ONLY there.
            # Efficient implementation: Just filter in the where clause.
            
            # Construct where clause
            # { "$and": [ {"user_id": uid}, {"section": {"$in": sections}} ] }
            where_clause = {
                "$and": [
                    {"user_id": user_id},
                    {"section": {"$in": sections}}
                ]
            }
            
            res = self.collection.query(
                query_embeddings=emb,
                n_results=k, # Fetch same K, but purely from target
                where=where_clause
            )
            
            docs = []
            if res["documents"] and res["documents"][0]:
                for i in range(len(res["documents"][0])):
                    meta = res["metadatas"][0][i]
                    if file_ids and meta.get("file_id") not in file_ids:
                        continue
                        
                    docs.append({
                        "content": res["documents"][0][i],
                        "metadata": meta,
                        "score": res["distances"][0][i] * 0.9, # Boost score (lower distance) logic handled in fusion?? 
                        # actually lower distance = better. 
                        # We just return them. RRF fusion (rank based) will be fine.
                        "id": res["ids"][0][i]
                    })
            return docs
            
        except Exception as e:
            logger.warning(f"Targeted search warning (fallback to global): {e}")
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
