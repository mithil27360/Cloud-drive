"""
Re-Ranking Module for Precision Improvement

Uses cross-encoder models to re-score and re-rank retrieved chunks.
Significantly improves relevance of top results.
"""

from sentence_transformers import CrossEncoder
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class ChunkReranker:
    """Production-grade re-ranking using cross-encoder models."""
    
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        """
        Initialize re-ranker with cross-encoder model.
        
        Args:
            model_name: HuggingFace model name for cross-encoder
        """
        try:
            self.model = CrossEncoder(model_name)
            self.logger = logger
            self.logger.info(f"Loaded cross-encoder model: {model_name}")
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
        
        try:
            # Prepare query-chunk pairs for cross-encoder
            pairs = [(query, chunk.get("content", "")) for chunk in chunks]
            
            # Get relevance scores
            scores = self.model.predict(pairs)
            
            # Combine chunks with scores
            scored_chunks = []
            for chunk, score in zip(chunks, scores):
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = float(score)
                scored_chunks.append(chunk_copy)
            
            # Sort by score (descending)
            scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
            
            # Return top-k
            top_chunks = scored_chunks[:top_k]
            
            self.logger.info(
                f"Re-ranked {len(chunks)} chunks, returning top {len(top_chunks)}"
            )
            
            return top_chunks
            
        except Exception as e:
            self.logger.error(f"Re-ranking failed: {str(e)}")
            return chunks[:top_k]
    
    def get_scores(self, query: str, texts: List[str]) -> List[float]:
        """
        Get relevance scores for query-text pairs.
        
        Args:
            query: User query
            texts: List of text snippets
            
        Returns:
            List of relevance scores
        """
        if not self.model:
            return [0.0] * len(texts)
        
        try:
            pairs = [(query, text) for text in texts]
            scores = self.model.predict(pairs)
            return [float(score) for score in scores]
        except Exception as e:
            self.logger.error(f"Scoring failed: {str(e)}")
            return [0.0] * len(texts)


# Singleton instance
reranker = ChunkReranker()
