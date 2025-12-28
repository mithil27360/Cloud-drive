from typing import List, Dict, Optional
from .indexer import get_collection, embedding_model
from .retrievers.reranker import reranker
import logging

logger = logging.getLogger(__name__)

from .retrievers.hybrid import hybrid_retriever

def query_documents(query_text: str, user_id: int, file_ids: Optional[List[int]] = None, n_results: int = 3) -> List[Dict]:
    """
    Research-Grade query with Hybrid Search & Re-ranking (Phase 3).
    """
    logger.info(f"Querying: '{query_text}' for user {user_id}")
    
    # 1. Embed Query (for Vector Search)
    query_embedding = embedding_model.encode([query_text]).tolist()
    
    # 2. Build ChromaDB filter
    where_filter = {"user_id": user_id}
    
    # 3. Parallel Search: Vector + BM25
    collection = get_collection()
    initial_n = n_results * 5 if file_ids else n_results * 3
    
    # A. Vector Search
    vector_results_raw = collection.query(
        query_embeddings=query_embedding,
        n_results=initial_n,
        where=where_filter
    )
    
    vector_candidates = []
    if vector_results_raw["documents"] and vector_results_raw["documents"][0]:
        for i in range(len(vector_results_raw["documents"][0])):
            metadata = vector_results_raw["metadatas"][0][i]
            if file_ids and metadata.get("file_id") not in file_ids:
                continue
            vector_candidates.append({
                "content": vector_results_raw["documents"][0][i],
                "metadata": metadata,
                "score": vector_results_raw["distances"][0][i]
            })

    # B. BM25 Search
    # Note: Currently searches ALL docs in memory index. Filter by user_id post-hoc if needed.
    # For now, simplistic integration:
    bm25_candidates_raw = hybrid_retriever.search_bm25(query_text, k=initial_n)
    bm25_candidates = [
        res for res in bm25_candidates_raw 
        if res["metadata"].get("user_id") == user_id and 
        (not file_ids or res["metadata"].get("file_id") in file_ids)
    ]
    
    # 4. Fuse Results (RRF)
    candidates = hybrid_retriever.reciprocal_rank_fusion(vector_candidates, bm25_candidates)
    
    logger.info(f"Hybrid Search: {len(vector_candidates)} vector, {len(bm25_candidates)} bm25 -> {len(candidates)} fused")
    
    # 5. Re-rank for precision
    if candidates:
        # Limit to reasonable number before expensive re-ranking
        rerank_input = candidates[:initial_n] 
        reranked = reranker.rerank(query_text, rerank_input, top_k=n_results)
        
        # Expand Context: Swap Content with Parent if available
        final_results = []
        for res in reranked:
            metadata = res.get("metadata", {})
            if metadata.get("is_child", False) and metadata.get("parent_content"):
                res["content"] = metadata["parent_content"]
            final_results.append(res)
            
        return final_results
    
    return []
