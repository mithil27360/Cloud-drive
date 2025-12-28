import logging
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from ..indexer import get_collection, embedding_model

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    Implements Hybrid Search (Vector + BM25) with Reciprocal Rank Fusion (RRF).
    
    Why: Vectors are great for semantics ("dog" ~= "puppy"), but bad at 
    exact keyword matching (e.g. acronyms "RAG vs DAG"). BM25 fixes this.
    """
    
    def __init__(self):
        self.bm25 = None
        self.bm25_corpus = []     # List of tokenized docs
        self.doc_map = {}         # Map index -> full document object
        self.is_initialized = False

    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def build_index(self):
        """
        Builds/Rebuilds the in-memory BM25 index from all documents in ChromaDB.
        Note: In production, this should be an async task or use a persistent text index (Elastic/Postgres).
        For this scale, in-memory is fine.
        """
        try:
            logger.info("Building BM25 index...")
            collection = get_collection()
            
            # Fetch all documents
            results = collection.get()
            docs = results["documents"]
            metadatas = results["metadatas"]
            ids = results["ids"]
            
            if not docs:
                logger.warning("No documents found for BM25 index.")
                return

            self.bm25_corpus = []
            self.doc_map = {}
            
            for idx, (doc_text, meta, doc_id) in enumerate(zip(docs, metadatas, ids)):
                tokens = self._tokenize(doc_text)
                self.bm25_corpus.append(tokens)
                self.doc_map[idx] = {
                    "content": doc_text,
                    "metadata": meta,
                    "id": doc_id
                }
                
            self.bm25 = BM25Okapi(self.bm25_corpus)
            self.is_initialized = True
            logger.info(f"BM25 index built with {len(docs)} documents.")
            
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")

    def search_bm25(self, query: str, k: int = 5) -> List[Dict]:
        if not self.is_initialized:
            self.build_index()
            
        if not self.bm25:
             return []
             
        tokenized_query = self._tokenize(query)
        # Get raw scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top K indices
        top_n = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        
        results = []
        for idx in top_n:
            if scores[idx] > 0: # Filter zero matches
                doc = self.doc_map[idx].copy()
                doc["score"] = scores[idx]
                results.append(doc)
                
        return results

    def reciprocal_rank_fusion(self, vector_results: List[Dict], bm25_results: List[Dict], k: int = 60) -> List[Dict]:
        """
        Combine results using RRF.
        Score = 1 / (k + rank)
        """
        fused_scores = {}
        doc_store = {}
        
        # Helper to normalize access
        def process_list(results, prefix):
            for rank, doc in enumerate(results):
                # Unique ID is essential
                doc_id = doc.get("id") or doc.get("metadata", {}).get("file_id") # Simplify for now
                if not doc_id:
                     # If from semantic query, we might not have ID easily if not passed?
                     # Actually Chroma returns IDs. Let's ensure query_documents returns them.
                     pass 
                
                # Use content as key if ID not unique enough (e.g. chunks)
                # Actually, let's assume content+metadata['chunk_index'] unique key
                key = doc["content"][:50] # loose key
                
                if key not in doc_store:
                    doc_store[key] = doc
                
                if key not in fused_scores:
                    fused_scores[key] = 0.0
                
                # specific RRF formula
                fused_scores[key] += 1 / (k + rank + 1)

        process_list(vector_results, "vec")
        process_list(bm25_results, "bm25")
        
        # Sort by fused score
        reranked_keys = sorted(fused_scores, key=fused_scores.get, reverse=True)
        
        return [doc_store[key] for key in reranked_keys]

# Singleton
hybrid_retriever = HybridRetriever()
