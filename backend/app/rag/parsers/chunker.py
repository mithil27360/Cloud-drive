"""
Semantic Chunking with Context Preservation

Implements intelligent text splitting that:
- Preserves semantic boundaries
- Maintains document structure
- Adds rich metadata
- Optimizes chunk size for embeddings
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer, util
from typing import List, Dict, Optional
import logging
import re
import numpy as np

logger = logging.getLogger(__name__)

def classify_importance(text: str, section_heading: str = "") -> str:
    """
    Classify chunk importance based on content and section heuristics.
    
    Returns: 'core_contribution', 'methodology', 'experiment', or 'background'
    """
    text_lower = text.lower()
    heading_lower = section_heading.lower() if section_heading else ""
    
    # Core Contribution: Abstract, Conclusion, Main findings
    core_keywords = ['abstract', 'conclusion', 'summary', 'key finding', 'contribution', 
                     'main result', 'we propose', 'we present', 'novel', 'state-of-the-art']
    if any(kw in heading_lower for kw in ['abstract', 'conclusion', 'summary']):
        return 'core_contribution'
    if any(kw in text_lower[:500] for kw in core_keywords):
        return 'core_contribution'
    
    # Methodology: Methods, Approach, Algorithm
    method_keywords = ['method', 'approach', 'algorithm', 'implementation', 'architecture',
                       'procedure', 'technique', 'design', 'model']
    if any(kw in heading_lower for kw in ['method', 'approach', 'algorithm']):
        return 'methodology'
    if any(kw in text_lower for kw in method_keywords):
        return 'methodology'
    
    # Experiment: Results, Evaluation, Data
    exp_keywords = ['experiment', 'result', 'evaluation', 'dataset', 'benchmark', 
                    'accuracy', 'performance', 'table', 'figure', 'ablation']
    if any(kw in heading_lower for kw in ['result', 'experiment', 'evaluation']):
        return 'experiment'
    if any(kw in text_lower for kw in exp_keywords):
        return 'experiment'
    
    # Default: Background
    return 'background'


class SemanticChunker:
    """
    Production-grade Semantic Chunking.
    
    Splits text based on semantic similarity between sentences rather than 
    arbitrary character counts. Finds "natural breaks" in conversation/text.
    """
    
    def __init__(
        self,
        model_name: str = 'all-MiniLM-L6-v2',
        breakpoint_percentile_threshold: int = 95,
        buffer_size: int = 1
    ):
        """
        Args:
            model_name: Embedding model for semantic comparison
            breakpoint_percentile_threshold: Higher = fewer chunks (more strict splitting)
            buffer_size: Number of sentences to look ahead/behind for context
        """
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None
            
        self.breakpoint_percentile_threshold = breakpoint_percentile_threshold
        self.buffer_size = buffer_size
        self.logger = logger
        
        # Fallback splitter
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )

    def _split_into_sentences(self, text: str) -> List[str]:
        # Simple robust sentence splitting
        # Look for periods, question marks, exclamations followed by space and capital letter
        sentences = re.split(r'(?<=[.?!])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]

    def _combine_sentences(self, sentences: List[dict], buffer_size: int = 1) -> List[dict]:
        # Add window context to sentences for better embedding representation
        for i in range(len(sentences)):
            combined_text = ""
            # Add previous sentences
            for j in range(i - buffer_size, i):
                if j >= 0:
                    combined_text += sentences[j]['sentence'] + " "
            
            combined_text += sentences[i]['sentence']
            
            # Add next sentences
            for j in range(i + 1, i + 1 + buffer_size):
                if j < len(sentences):
                    combined_text += " " + sentences[j]['sentence']
            
            sentences[i]['combined_sentence'] = combined_text
        return sentences

    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Chunk using semantic analysis.
        
        1. Split into sentences
        2. Embed sentences (with context buffer)
        3. Calculate cosine distances between adjacent sentences
        4. Split where distance is high (similarity is low)
        """
        if not text or not text.strip():
            return []
            
        # 0. Handle Page Markers (Recursive Strategy)
        # pdf_parser inserts "\n--- Page X ---\n". We use this to assign page numbers.
        page_pattern = r'\n--- Page (\d+) ---\n'
        # Check if text contains page markers
        if re.search(page_pattern, text):
            parts = re.split(page_pattern, text)
            # parts structure: [preamble, page_num_1, content_1, page_num_2, content_2, ...]
            
            all_chunks = []
            
            # Handle preamble (text before first page marker)
            if parts[0].strip():
                # Treat as Page 1 or metadata default
                # We'll just recurse with existing metadata
                all_chunks.extend(self.chunk_text(parts[0], metadata))
                
            # Iterate over page number/content pairs
            for i in range(1, len(parts), 2):
                try:
                    page_num = int(parts[i])
                    page_content = parts[i+1]
                    
                    if not page_content.strip():
                        continue
                        
                    # Update metadata for this page
                    page_metadata = (metadata or {}).copy()
                    page_metadata["page_number"] = page_num
                    
                    # Recurse: Chunk this page's content
                    # Since markers are removed, the recursive call will hit the core logic below
                    page_chunks = self.chunk_text(page_content, page_metadata)
                    all_chunks.extend(page_chunks)
                except Exception as e:
                    logger.warning(f"Error processing page split: {e}")
                    continue
                    
            return all_chunks

        # Fallback if model failed to load
        if not self.model:
            logger.warning("Semantic chunking model not loaded, using fallback.")
            chunks = self.fallback_splitter.split_text(text)
            return [{"content": c, "metadata": metadata or {}} for c in chunks]

        # 1. Split sentences
        single_sentences_list = self._split_into_sentences(text)
        if len(single_sentences_list) < 2:
             return [{"content": text, "metadata": metadata or {}}]
             
        sentences = [{'sentence': x, 'index': i} for i, x in enumerate(single_sentences_list)]
        
        # 2. Add Context Buffer & Embed
        sentences = self._combine_sentences(sentences, self.buffer_size)
        embeddings = self.model.encode([x['combined_sentence'] for x in sentences])
        
        # 3. Calculate Cosine Distances
        distances = []
        for i in range(len(embeddings) - 1):
            sim = util.pytorch_cos_sim(embeddings[i], embeddings[i+1]).item()
            distance = 1 - sim
            distances.append(distance)
            
        # 4. Determine Threshold
        # value at the Xth percentile (e.g. 95th percentile of distances = top 5% most different)
        # Any distance higher than this is a breakpoint.
        if not distances:
            breakpoint_distance_threshold = 0
        else:
            breakpoint_distance_threshold = np.percentile(distances, self.breakpoint_percentile_threshold)
            
        # 5. Group Chunks
        indices_above_thresh = [i for i, x in enumerate(distances) if x > breakpoint_distance_threshold]
        
        chunks = []
        start_index = 0
        
        # Iterate through breakpoints
        for index in indices_above_thresh:
            # The split happens AFTER the sentence at 'index'
            end_index = index + 1 # exclusive because list slicing is exclusive
            
            group = sentences[start_index:end_index]
            combined_text = " ".join([d['sentence'] for d in group])
            chunks.append(combined_text)
            start_index = end_index
            
        # Add the last chunk
        if start_index < len(sentences):
            group = sentences[start_index:]
            combined_text = " ".join([d['sentence'] for d in group])
            chunks.append(combined_text)
            
        # Format for return
        enriched_chunks = []
        total_chunks = len(chunks)
        
        for idx, chunk_text in enumerate(chunks):
            chunk_metadata = {
                "chunk_index": idx,
                "total_chunks": total_chunks,
                "chunk_method": "semantic",
                **(metadata or {})
            }
            enriched_chunks.append({
                "content": chunk_text,
                "metadata": chunk_metadata
            })
            
        logger.info(f"Semantic Chunking: {len(text)} chars -> {len(single_sentences_list)} sentences -> {total_chunks} chunks")
        return enriched_chunks

# ... (SemanticChunker class remains above)

class ParentChildChunker:
    """
    Implements 'Small-to-Big' Retrieval Strategy.
    
    1. Splits text into large 'Parent' chunks (e.g., 1024-2048 chars) for full context.
    2. Splits each Parent into small 'Child' chunks (e.g., 256-512 chars) for precise retrieval.
    3. Child chunks store the Parent's content in metadata.
    """
    
    def __init__(self, parent_chunk_size=1024, child_chunk_size=256, chunk_overlap=0):
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size, 
            chunk_overlap=chunk_overlap
        )
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size, 
            chunk_overlap=chunk_overlap
        )
        self.semantic_chunker = SemanticChunker() # Use semantic for finding good parents?
        
    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        if not text or not text.strip():
            return []
            
        # 1. Create Parent Chunks (Legacy: fixed size, Future: Semantic Parents)
        # Using Semantic Chunker for Parents ensures parents are topic-coherent
        parents = self.semantic_chunker.chunk_text(text, metadata)
        
        all_children = []
        
        for p_idx, parent in enumerate(parents):
            parent_text = parent["content"]
            parent_meta = parent["metadata"]
            
            # 2. Create Child Chunks from this Parent
            children_texts = self.child_splitter.split_text(parent_text)
            
            for c_idx, child_text in enumerate(children_texts):
                # 3. Link Child to Parent + Classify Importance
                section = parent_meta.get("section_heading", "")
                importance = classify_importance(child_text, section)
                
                child_meta = parent_meta.copy()
                child_meta.update({
                    "parent_content": parent_text,  # The "Big" chunk
                    "is_child": True,
                    "parent_index": p_idx,
                    "child_index": c_idx,
                    "chunk_method": "parent_child",
                    "importance": importance  # NEW: core_contribution/methodology/experiment/background
                })
                
                all_children.append({
                    "content": child_text, # The "Small" chunk (for vector search)
                    "metadata": child_meta
                })
        
        logger.info(f"Parent-Child Chunking: {len(parents)} parents -> {len(all_children)} children")
        return all_children

# Singleton instance (switched to Parent-Child as default for Research-Grade)
# You can swap this back to semantic_chunker if desired
semantic_chunker = ParentChildChunker()
