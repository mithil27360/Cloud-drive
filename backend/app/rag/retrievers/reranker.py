"""
Re-Ranking Module for Precision Improvement

Uses cross-encoder models to re-score and re-rank retrieved chunks.
Significantly improves relevance of top results.
"""

from sentence_transformers import CrossEncoder
from typing import List, Dict, Tuple, Optional
import logging
import math

logger = logging.getLogger(__name__)


class ChunkReranker:
    """
    Production-grade re-ranking using cross-encoder models.
    
    Features:
    - Batched Inference (Memory Safety)
    - Input Validation
    - Error Fallback
    """
    
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2', batch_size: int = 32):
        """
        Initialize re-ranker with cross-encoder model.
        
        Args:
            model_name: HuggingFace model name for cross-encoder
            batch_size: Max pairs to process at once to avoid OOM
        """
        self.batch_size = batch_size
        try:
            self.model = CrossEncoder(model_name)
            self.logger = logger
            self.logger.info(f"Loaded cross-encoder model: {model_name} (Batch Size: {batch_size})")
        except Exception as e:
            self.logger.error(f"Failed to load cross-encoder: {str(e)}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_k: int = 3
    ) -> List[Dict]:
        """
        Re-rank chunks based on query relevance.
        
        Args:
            query: User query
            chunks: List of chunks from initial retrieval
            top_k: Number of top chunks to return
            
        Returns:
            Re-ranked and filtered chunks
        """
        if not self.model:
            self.logger.warning("Re-ranker not available, returning original chunks")
            return chunks[:top_k]
        
        if not chunks:
            return []
        
        # Limit candidate pool safeguard (e.g. don't rerank 1000 docs)
        MAX_CANDIDATES = 100
        candidate_chunks = chunks[:MAX_CANDIDATES]
        
        try:
            # Prepare query-chunk pairs
            pairs = [(query, chunk.get("content", "")) for chunk in candidate_chunks]
            
            # Predict in batches
            all_scores = []
            for i in range(0, len(pairs), self.batch_size):
                batch = pairs[i : i + self.batch_size]
                if not batch:
                    continue
                scores = self.model.predict(batch)
                # Ensure scores is a list (single item batch might return float)
                if isinstance(scores, (float, int)):
                    all_scores.append(float(scores))
                else:
                    all_scores.extend(scores.tolist())
            
            # Combine chunks with scores
            scored_chunks = []
            for chunk, score in zip(candidate_chunks, all_scores):
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = float(score)
                scored_chunks.append(chunk_copy)
            
            # Sort by score (descending)
            scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
            
            # Return top-k
            top_chunks = scored_chunks[:top_k]
            
            self.logger.info(
                f"Re-ranked {len(chunks)} chunks -> {len(top_chunks)} (Top Score: {top_chunks[0]['rerank_score']:.3f})"
            )
            
            return top_chunks
            
        except Exception as e:
            self.logger.error(f"Re-ranking failed: {str(e)}", exc_info=True)
            # Fallback to original order
            return chunks[:top_k]
    
    def get_scores(self, query: str, texts: List[str]) -> List[float]:
        """
        Get relevance scores for query-text pairs (Batched).
        """
        if not self.model or not texts:
            return [0.0] * len(texts)
        
        try:
            pairs = [(query, text) for text in texts]
            all_scores = []
            
            for i in range(0, len(pairs), self.batch_size):
                batch = pairs[i : i + self.batch_size]
                scores = self.model.predict(batch)
                if isinstance(scores, (float, int)):
                    all_scores.append(float(scores))
                else:
                    all_scores.extend(scores.tolist())
                    
            return all_scores
        except Exception as e:
            self.logger.error(f"Scoring failed: {str(e)}")
            return [0.0] * len(texts)


# Singleton instance
reranker = ChunkReranker()
