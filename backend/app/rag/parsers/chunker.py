"""
Semantic Chunking with Context Preservation

Implements intelligent text splitting that:
- Preserves semantic boundaries
- Maintains document structure
- Adds rich metadata
- Optimizes chunk size for embeddings
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SemanticChunker:
    """Production-grade semantic chunking with metadata enrichment."""
    
    def __init__(
        self,
        chunk_size: int = 1024,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ):
        """
        Initialize semantic chunker.
        
        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            separators: Custom separators (default: paragraph, sentence, word)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Default separators: preserve semantic boundaries
        self.separators = separators or [
            "\n\n",  # Paragraphs
            "\n",    # Lines
            ". ",    # Sentences
            "! ",    # Sentences
            "? ",    # Sentences
            "; ",    # Clauses
            ", ",    # Phrases
            " ",     # Words
            ""       # Characters (fallback)
        ]
        
        # Initialize LangChain splitter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False
        )
        
        self.logger = logger
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Chunk text with semantic awareness and metadata enrichment.
        
        Args:
            text: Full document text
            metadata: Optional base metadata to include
            
        Returns:
            List of chunks with enriched metadata
        """
        if not text or not text.strip():
            self.logger.warning("Empty text provided for chunking")
            return []
        
        try:
            # Split text using semantic boundaries
            chunks = self.splitter.split_text(text)
            
            total_chunks = len(chunks)
            self.logger.info(f"Created {total_chunks} semantic chunks from {len(text)} characters")
            
            # Enrich chunks with metadata
            enriched_chunks = []
            
            for idx, chunk_text in enumerate(chunks):
                chunk_metadata = {
                    "chunk_index": idx,
                    "total_chunks": total_chunks,
                    "chunk_size": len(chunk_text),
                    "position_ratio": round(idx / total_chunks, 3) if total_chunks > 0 else 0
                }
                
                # Add base metadata if provided
                if metadata:
                    chunk_metadata.update(metadata)
                
                # Determine chunk position description
                if idx == 0:
                    chunk_metadata["position"] = "beginning"
                elif idx == total_chunks - 1:
                    chunk_metadata["position"] = "end"
                else:
                    chunk_metadata["position"] = "middle"
                
                enriched_chunks.append({
                    "content": chunk_text.strip(),
                    "metadata": chunk_metadata
                })
            
            return enriched_chunks
            
        except Exception as e:
            self.logger.error(f"Chunking failed: {str(e)}")
            raise
    
    def chunk_with_headings(
        self,
        text: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Advanced chunking that tries to preserve section headings.
        
        This is useful for structured documents with clear sections.
        """
        # Simple heading detection (can be enhanced)
        lines = text.split('\n')
        sections = []
        current_section = {"heading": "", "content": []}
        
        for line in lines:
            # Simple heuristic: short lines (< 60 chars) followed by newline might be headings
            if len(line.strip()) < 60 and line.strip() and not line.strip().endswith('.'):
                # Might be a heading
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {
                    "heading": line.strip(),
                    "content": []
                }
            else:
                current_section["content"].append(line)
        
        # Add last section
        if current_section["content"]:
            sections.append(current_section)
        
        # Now chunk each section
        all_chunks = []
        
        for section in sections:
            section_text = "\n".join(section["content"])
            section_metadata = metadata.copy() if metadata else {}
            
            if section["heading"]:
                section_metadata["section_heading"] = section["heading"]
            
            section_chunks = self.chunk_text(section_text, section_metadata)
            all_chunks.extend(section_chunks)
        
        return all_chunks


# Singleton instance
semantic_chunker = SemanticChunker(
    chunk_size=1024,  # Good balance for most embedding models
    chunk_overlap=200  # 20% overlap for context preservation
)
