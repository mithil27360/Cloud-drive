from typing import List, Dict, Optional
from .indexer import get_collection, embedding_model
from .retrievers.reranker import reranker
import logging

logger = logging.getLogger(__name__)

def query_documents(query_text: str, user_id: int, file_ids: Optional[List[int]] = None, n_results: int = 3) -> List[Dict]:
    """
    Production-grade query with re-ranking.
    
   Args:
        query_text: The search query
        user_id: User ID for privacy filtering
        file_ids: Optional list of file IDs to search within
        n_results: Number of final results to return
    """
    logger.info(f"Querying: '{query_text}' for user {user_id}")
    
    # 1. Embed Query
    query_embedding = embedding_model.encode([query_text]).tolist()
    
    # 2. Build ChromaDB filter (only user_id for privacy)
    where_filter = {"user_id": user_id}
    
    # 3. Initial Retrieval - Get more candidates for re-ranking
    collection = get_collection()
    # Retrieve 3x the final number for re-ranking
    initial_n = n_results * 5 if file_ids else n_results * 3
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=initial_n,
        where=where_filter
    )
    
    # 4. Format initial results
    candidates = []
    if results["documents"] and results["documents"][0]:
        for i in range(len(results["documents"][0])):
            metadata = results["metadatas"][0][i]
            
            # Filter by file_id if specified
            if file_ids and metadata.get("file_id") not in file_ids:
                continue
            
            candidates.append({
                "content": results["documents"][0][i],
                "metadata": metadata,
                "score": results["distances"][0][i] if results["distances"] else None
            })
    
    logger.info(f"Retrieved {len(candidates)} initial candidates")
    
    # 5. Re-rank for precision
    if candidates:
        reranked = reranker.rerank(query_text, candidates, top_k=n_results)
        logger.info(f"Re-ranked to top {len(reranked)} results")
        return reranked
    
    return []
