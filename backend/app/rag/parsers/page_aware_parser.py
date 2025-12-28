"""
Page-Aware PDF Parser using PyMuPDF
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Extracts text page-by-page and preserves page metadata through chunking.

This is the CORRECT way to handle page citations:
1. Extract text per page (PyMuPDF)
2. Chunk with page metadata
3. Store metadata in vector DB
4. Retrieve with page info
5. LLM cites using metadata (not guessing)

Total: 250+ lines
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

@dataclass
class PageExtraction:
    """Represents text extracted from a single page"""
    page_num: int  # 1-indexed human-readable
    text: str
    section: Optional[str] = None  # Detected section name

@dataclass
class AcademicChunk:
    """Chunk with page metadata"""
    text: str
    page_start: int
    page_end: int
    section: str
    importance: str
    file_id: int
    chunk_index: int

class PageAwarePDFParser:
    """
    Production-grade PDF parser that preserves page numbers.
    
    Flow:
    1. Extract text page-by-page (PyMuPDF)
    2. Detect sections per page
    3. Chunk while preserving page boundaries
    4. Each chunk knows its page range
    """
    
    # Section detection patterns (same as before)
    SECTION_PATTERNS = [
        (r'^abstract\s*$', 'Abstract'),
        (r'^(\d+\.?\s+)?introduction', 'Introduction'),
        (r'^(\d+\.?\s+)?related\s+work', 'Related Work'),
        (r'^(\d+\.?\s+)?background', 'Background'),
        (r'^(\d+\.?\s+)?method(ology)?', 'Method'),
        (r'^(\d+\.?\s+)?approach', 'Method'),
        (r'^(\d+\.?\s+)?model', 'Method'),
        (r'^(\d+\.?\s+)?experiment(s)?', 'Experiments'),
        (r'^(\d+\.?\s+)?results?', 'Results'),
        (r'^(\d+\.?\s+)?evaluation', 'Results'),
        (r'^(\d+\.?\s+)?discussion', 'Discussion'),
        (r'^(\d+\.?\s+)?conclusion(s)?', 'Conclusion'),
        (r'^references?\s*$', 'References'),
    ]
    
    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def parse(self, pdf_path: str, file_id: int, user_id: int) -> List[Dict]:
        """
        Main entry point for parsing.
        
        Returns:
            List of chunks with page metadata ready for vector DB
        """
        logger.info(f"Parsing PDF with page tracking: {pdf_path}")
        
        try:
            # Step 1: Extract pages
            pages = self._extract_pages(pdf_path)
            logger.info(f"Extracted {len(pages)} pages")
            
            # Step 2: Detect sections
            pages_with_sections = self._detect_sections_per_page(pages)
            
            # Step 3: Chunk with page metadata
            chunks = self._chunk_with_pages(pages_with_sections, file_id, user_id)
            logger.info(f"Created {len(chunks)} chunks")
            
            return chunks
            
        except Exception as e:
            logger.error(f"PDF parsing failed: {e}", exc_info=True)
            return []
    
    def _extract_pages(self, pdf_path: str) -> List[PageExtraction]:
        """
        Extract text page-by-page using PyMuPDF.
        
        This is CRITICAL: we must loop per page, not per document.
        """
        pages = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc, start=1):
                # Extract text
                text = page.get_text()
                
                # Clean text
                text = self._clean_text(text)
                
                if text.strip():
                    pages.append(PageExtraction(
                        page_num=page_num,
                        text=text
                    ))
            
            doc.close()
            
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {e}")
            # Fallback to pdfplumber if PyMuPDF fails
            pages = self._fallback_extraction(pdf_path)
        
        return pages
    
    def _fallback_extraction(self, pdf_path: str) -> List[PageExtraction]:
        """Fallback to pdfplumber if PyMuPDF fails"""
        import pdfplumber
        pages = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text:
                        pages.append(PageExtraction(
                            page_num=page_num,
                            text=self._clean_text(text)
                        ))
        except Exception as e:
            logger.error(f"Fallback extraction also failed: {e}")
        
        return pages
    
    def _clean_text(self, text: str) -> str:
        """Remove noise"""
        import re
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove standalone page numbers
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        return text.strip()
    
    def _detect_sections_per_page(self, pages: List[PageExtraction]) -> List[PageExtraction]:
        """
        Detect which section each page belongs to.
        
        Strategy: Scan for section headers, track current section
        """
        import re
        current_section = "General"
        
        for page in pages:
            # Check if this page starts a new section
            lines = page.text.split('\n')
            for line in lines[:10]:  # Check first 10 lines
                line_clean = line.strip().lower()
                if len(line_clean) > 100:  # Too long to be a header
                    continue
                
                for pattern, section_name in self.SECTION_PATTERNS:
                    if re.match(pattern, line_clean):
                        current_section = section_name
                        logger.debug(f"Page {page.page_num}: Section = {section_name}")
                        break
            
            page.section = current_section
        
        return pages
    
    def _chunk_with_pages(
        self, 
        pages: List[PageExtraction], 
        file_id: int, 
        user_id: int
    ) -> List[Dict]:
        """
        Chunk text while preserving page information.
        
        CRITICAL: Each chunk must know its page range.
        """
        chunks = []
        chunk_index = 0
        
        # Process pages in groups by section for better chunk boundaries
        current_section_pages = []
        current_section = None
        
        for page in pages:
            if page.section != current_section and current_section_pages:
                # Section changed, flush accumulated pages
                section_chunks = self._chunk_section(
                    current_section_pages, 
                    file_id, 
                    user_id, 
                    chunk_index
                )
                chunks.extend(section_chunks)
                chunk_index += len(section_chunks)
                current_section_pages = []
            
            current_section = page.section
            current_section_pages.append(page)
        
        # Flush final section
        if current_section_pages:
            section_chunks = self._chunk_section(
                current_section_pages, 
                file_id, 
                user_id, 
                chunk_index
            )
            chunks.extend(section_chunks)
        
        return chunks
    
    def _chunk_section(
        self, 
        section_pages: List[PageExtraction], 
        file_id: int, 
        user_id: int, 
        start_index: int
    ) -> List[Dict]:
        """
        Chunk a group of pages from same section.
        """
        # Concatenate all text from these pages
        full_text = " ".join(p.text for p in section_pages)
        section_name = section_pages[0].section if section_pages else "General"
        
        # Get page range
        page_start = section_pages[0].page_num
        page_end = section_pages[-1].page_num
        
        # Classify importance
        importance = self._classify_importance(section_name)
        
        # Split into chunks
        if len(full_text) > self.chunk_size:
            text_chunks = self.splitter.split_text(full_text)
        else:
            text_chunks = [full_text]
        
        # Build chunk objects
        chunks = []
        for idx, text_chunk in enumerate(text_chunks):
            # Calculate page range for this chunk
            # Simple heuristic: distribute pages across chunks
            chars_per_page = len(full_text) / len(section_pages)
            chunk_start_char = sum(len(text_chunks[i]) for i in range(idx))
            chunk_end_char = chunk_start_char + len(text_chunk)
            
            chunk_page_start = page_start + int(chunk_start_char / chars_per_page)
            chunk_page_end = page_start + int(chunk_end_char / chars_per_page)
            
            # Clamp to actual range
            chunk_page_start = max(page_start, min(chunk_page_start, page_end))
            chunk_page_end = max(page_start, min(chunk_page_end, page_end))
            
            chunks.append({
                "text": text_chunk,
                "metadata": {
                    "file_id": file_id,
                    "user_id": user_id,
                    "chunk_index": start_index + idx,
                    "page_start": chunk_page_start,
                    "page_end": chunk_page_end,
                    "section": section_name,
                    "importance": importance,
                    "source": "page_aware_parser"
                }
            })
        
        return chunks
    
    def _classify_importance(self, section: str) -> str:
        """Classify section importance"""
        section_lower = section.lower()
        
        if any(s in section_lower for s in ['abstract', 'introduction', 'conclusion']):
            return 'core_contribution'
        elif any(s in section_lower for s in ['method', 'approach', 'model']):
            return 'methodology'
        elif any(s in section_lower for s in ['experiment', 'result', 'evaluation']):
            return 'experiment'
        else:
            return 'general'


# Convenience function
def parse_pdf_with_pages(pdf_path: str, file_id: int, user_id: int) -> List[Dict]:
    """Parse PDF and return chunks with page metadata"""
    parser = PageAwarePDFParser()
    return parser.parse(pdf_path, file_id, user_id)
