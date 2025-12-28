from typing import List, Dict, Any, Optional
import logging
import threading
from rank_bm25 import BM25Okapi
from ..indexer import get_collection

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    Production-Grade Hybrid Searcher.
    Combines Semantic (Vector) and Keyword (BM25) search results using Reciprocal Rank Fusion (RRF).
    
    Features:
    - Thread-safe Index Rebuilds
    - Configurable Fusion Weights
    - Robust Error Handling
    - Detailed Attribution Logging
    """
    
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k  # Smoothing constant for RRF
        self.bm25_model = None
        self.doc_registry = {}  # Map: index -> metadata
        self._lock = threading.RLock()
        self._is_ready = False
        
    def is_ready(self) -> bool:
        return self._is_ready

    def _tokenize(self, text: str) -> List[str]:
        """Robust tokenizer for BM25."""
        if not text:
            return []
        return text.lower().split()  # Could upgrade to NLTK/Spacy if needed

    def build_index(self, force: bool = False):
        """
        Builds the in-memory BM25 index from ChromaDB documents.
        Thread-safe operation.
        """
        if self._is_ready and not force:
            return

        with self._lock:
            try:
                logger.info("Initializing BM25 Index Build...")
                collection = get_collection()
                
                # Fetch all documents (Warning: In-memory approach scales to ~100k docs)
                # For >100k, use Elasticsearch/Typesense
                result = collection.get()
                docs = result.get("documents", [])
                metadatas = result.get("metadatas", [])
                ids = result.get("ids", [])
                
                if not docs:
                    logger.warning("BM25 Build Skipped: No documents found.")
                    return

                corpus = []
                registry = {}
                
                for idx, (content, meta, doc_id) in enumerate(zip(docs, metadatas, ids)):
                    # Guard against None content
                    clean_content = content or ""
                    tokens = self._tokenize(clean_content)
                    corpus.append(tokens)
                    registry[idx] = {
                        "content": clean_content,
                        "metadata": meta,
                        "id": doc_id
                    }
                
                self.bm25_model = BM25Okapi(corpus)
                self.doc_registry = registry
                self._is_ready = True
                
                logger.info(f"BM25 Index Ready: {len(docs)} documents indexed.")
                
            except Exception as e:
                logger.error(f"BM25 Index Build Failed: {e}", exc_info=True)
                self._is_ready = False

    def search_bm25(self, query: str, k: int = 5) -> List[Dict]:
        """Execute Keyword Search."""
        if not self._is_ready:
            self.build_index()
            
        if not self.bm25_model:
            return []
            
        try:
            tokens = self._tokenize(query)
            scores = self.bm25_model.get_scores(tokens)
            
            # Get Top-K indices
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            
            results = []
            for idx in top_indices:
                if scores[idx] > 0.0:  # Only return positive matches
                    item = self.doc_registry[idx].copy()
                    item["score"] = float(scores[idx])
                    results.append(item)
                    
            return results
        except Exception as e:
            logger.error(f"BM25 Search Error: {e}")
            return []

    def reciprocal_rank_fusion(self, 
                             vector_results: List[Dict], 
                             bm25_results: List[Dict], 
                             k: Optional[int] = None) -> List[Dict]:
        """
        Fuse results from multiple lists using RRF.
        Process:
        1. Assign 1/(k + rank) score to each doc in each list.
        2. Sum scores per doc.
        3. Sort desc.
        """
        k_val = k if k is not None else self.rrf_k
        fused_scores = {}
        doc_map = {}
        
        # Helper to process a result set
        def process_results(results: List[Dict], source_name: str):
            for rank, doc in enumerate(results):
                # Robust Key Generation: ID preferred, else content hash
                doc_id = doc.get("id") or doc.get("metadata", {}).get("file_id")
                # Fallback key logic
                if doc_id:
                    key = str(doc_id)
                    # If multiple chunks have same doc_id (common), we need unique chunk ID
                    # Assume Chroma ID is unique string
                    if "id" in doc: 
                        key = str(doc["id"]) # Precise ID from DB
                else:
                    key = str(hash(doc.get("content", "")[:100]))
                
                if key not in doc_map:
                    doc_map[key] = doc
                    doc_map[key]["fusion_sources"] = []
                
                if key not in fused_scores:
                    fused_scores[key] = 0.0
                    
                # RRF Formula
                score = 1.0 / (k_val + rank + 1)
                fused_scores[key] += score
                doc_map[key]["fusion_sources"].append(source_name)

        process_results(vector_results, "vector")
        process_results(bm25_results, "bm25")
        
        # Sort
        sorted_keys = sorted(fused_scores, key=fused_scores.get, reverse=True)
        
        final_list = []
        for key in sorted_keys:
            item = doc_map[key]
            item["rrf_score"] = fused_scores[key]
            final_list.append(item)
            
        return final_list

# Singleton Instance
hybrid_retriever = HybridRetriever(rrf_k=60)
