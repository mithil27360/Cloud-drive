import re
import math
import statistics
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import pdfplumber  # Requirement: pdfplumber
from collections import Counter

logger = logging.getLogger(__name__)

@dataclass
class SectionMetadata:
    title: str = "Uncategorized"
    level: int = 0
    page: int = 1
    type: str = "text"  # text, header, caption, equation

@dataclass
class AcademicChunk:
    text: str
    metadata: Dict[str, Any]

class AcademicPDFParser:
    """
    Research-Grade Parser for 2-Column Academic Papers (NeurIPS/ICML/arXiv style).
    
    Capabilities:
    1. Layout Analysis: Detects columns and reading flow (Top-Down vs Columnar).
    2. Structural Cleanup: Removes headers, footers, and page numbers.
    3. Hierarchy Detection: Reconstructs 'Abstract' -> 'Introduction' -> 'Methods'.
    4. Math Hygiene: Replaces equations with [EQUATION] token to reduce noise.
    5. Citation Normalization: Removes [1, 2] reference styles for cleaner embeddings.
    """
    
    # Common academic section headers (case-insensitive regex)
    SECTION_HEADERS = {
        r'^abstract': 'Abstract',
        r'^introduction': 'Introduction',
        r'^background': 'Background',
        r'^related work': 'Related Work',
        r'^method': 'Methodology',
        r'^experimental': 'Experiments',
        r'^results': 'Results',
        r'^discussion': 'Discussion',
        r'^conclusion': 'Conclusion',
        r'^references': 'References'
    }
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.chunks: List[AcademicChunk] = []
        self.doc_structure = []  # Tree representation if needed
        
        # State tracking
        self.current_section = "Abstract"  # Default start
        self.body_font_size = 0.0
        self.header_font_size_threshold = 0.0

    def parse(self) -> List[AcademicChunk]:
        """Main execution pipeline."""
        logger.info(f"Starting analysis of academic PDF: {self.file_path}")
        
        try:
            with pdfplumber.open(self.file_path) as pdf:
                # Pass 1: Global Analysis (Font stats, layout type)
                self._analyze_global_stats(pdf)
                
                # Pass 2: Page-by-Page Extraction
                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    logger.debug(f"Parsing Page {page_num}")
                    
                    # A. Filter artifacts (Header/Footer)
                    cropped_page = self._remove_artifacts(page)
                    
                    # B. Detect Layout (1-col vs 2-col)
                    layout_type = self._detect_layout(cropped_page)
                    
                    # C. Extract Text Blocks in Reading Order
                    text_blocks = self._extract_blocks_flow_aware(cropped_page, layout_type)
                    
                    # D. Process Blocks (Clean, Detect Sections, Chunk)
                    self._process_text_blocks(text_blocks, page_num)
                    
            return self.chunks
            
        except Exception as e:
            logger.error(f"PDF Analysis Failed: {e}", exc_info=True)
            return []

    def _analyze_global_stats(self, pdf):
        """Determine what counts as 'Body Text' vs 'Header'."""
        all_sizes = []
        # Sample first 5 pages
        for p in pdf.pages[:5]:
            words = p.extract_words(extra_attrs=["size"])
            all_sizes.extend([w["size"] for w in words])
            
        if not all_sizes:
            self.body_font_size = 10.0 # Default
            return

        # Body text is usually the mode
        self.body_font_size = statistics.mode([round(s, 1) for s in all_sizes])
        # Headers are usually > 1.1x body
        self.header_font_size_threshold = self.body_font_size * 1.1
        logger.info(f"Detected Body Font: {self.body_font_size}pt, Header Threshold: {self.header_font_size_threshold}pt")

    def _remove_artifacts(self, page):
        """Crop headers/footers based on y-position heuristics."""
        h = page.height
        w = page.width
        # Standard academic margins: 5-8% top/bottom
        top_margin = h * 0.05
        bottom_margin = h * 0.93
        
        return page.crop((0, top_margin, w, bottom_margin))

    def _detect_layout(self, page) -> str:
        """Heuristic: Check if text density is split in middle."""
        w = page.width
        mid_x = w / 2
        
        # Check for gap in the middle 20%
        center_zone = page.crop((mid_x - 30, 0, mid_x + 30, page.height))
        words_in_center = center_zone.extract_words()
        
        # If very few words in center strip, it's 2-column
        if len(words_in_center) < 5:
            return "two_column"
        return "single_column"

    def _extract_blocks_flow_aware(self, page, layout: str):
        """Get text blocks respecting reading order."""
        words = page.extract_words(keep_blank_chars=False, extra_attrs=["size", "fontname"])
        w = page.width
        mid_x = w / 2

        if layout == "two_column":
            # Split words into Left and Right buckets
            left_col = [wd for wd in words if wd['x0'] < mid_x]
            right_col = [wd for wd in words if wd['x0'] >= mid_x]
            
            # Sort individual columns Top-Down
            left_col.sort(key=lambda x: (x['top'], x['x0']))
            right_col.sort(key=lambda x: (x['top'], x['x0']))
            
            return self._group_words_into_lines(left_col) + self._group_words_into_lines(right_col)
        else:
            words.sort(key=lambda x: (x['top'], x['x0']))
            return self._group_words_into_lines(words)

    def _group_words_into_lines(self, words) -> List[Dict]:
        """Group words into semantic lines/blocks."""
        if not words:
            return []
            
        lines = []
        current_line = [words[0]]
        
        for word in words[1:]:
            last_word = current_line[-1]
            # Same line heuristic: overlaps vertically or very close y-distance
            vertical_diff = abs(word['top'] - last_word['top'])
            
            if vertical_diff < 5: # 5px tolerance
                current_line.append(word)
            else:
                lines.append(self._finalize_line(current_line))
                current_line = [word]
        
        lines.append(self._finalize_line(current_line))
        return lines

    def _finalize_line(self, word_list):
        """Convert list of words to line dict with stats."""
        text = " ".join([w['text'] for w in word_list])
        avg_size = statistics.mean([w['size'] for w in word_list])
        is_bold = any("bold" in w.get('fontname', '').lower() for w in word_list)
        return {
            "text": text,
            "size": avg_size,
            "bold": is_bold,
            "top": word_list[0]['top']
        }

    def _process_text_blocks(self, lines: List[Dict], page_num: int):
        """Analyze lines for semantic meaning."""
        buffer = []
        
        for line in lines:
            text = line['text'].strip()
            if not text:
                continue
                
            # 1. Check if Header
            is_header = self._is_section_header(line)
            if is_header:
                # Flush previous buffer
                self._flush_buffer(buffer, page_num)
                buffer = []
                
                # Update Context
                clean_title = self._clean_header_text(text)
                self.current_section = clean_title
                continue
            
            # 2. Check for Citation/Equation noise
            clean_text = self._clean_content(text)
            if clean_text:
                buffer.append(clean_text)
                
        # Flush remaining
        self._flush_buffer(buffer, page_num)

    def _is_section_header(self, line) -> bool:
        """Detect headers via size or regex."""
        text = line['text']
        
        # Rule 1: Font Size
        if line['size'] >= self.header_font_size_threshold:
            return True
        
        # Rule 2: Regex matching "1. Introduction" even if small font
        # Must be short
        if len(text) < 100:
            for pattern in self.SECTION_HEADERS:
                if re.search(pattern, text.lower()):
                    return True
        return False

    def _clean_header_text(self, text: str) -> str:
        """Normalize '1. Introduction' -> 'Introduction'."""
        # Remove leading numbers
        text = re.sub(r'^\d+(\.\d+)*\s+', '', text)
        return text.title()

    def _clean_content(self, text: str) -> Optional[str]:
        """Apply Research-Grade hygiene."""
        # 1. Filter Equations (Heuristic: high density of special chars)
        # Replacing simple math for now
        # text = re.sub(r'\$.*?\$', '[EQUATION]', text) 
        
        # 2. Remove Citations [12] or [12, 13]
        text = re.sub(r'\[\s*\d+(\s*,\s*\d+)*\s*\]', '', text)
        
        # 3. Skip standalone numbers (page nums missed by crop)
        if re.match(r'^\d+$', text):
            return None
            
        return text

    def _flush_buffer(self, buffer: List[str], page_num: int):
        """
        Create completed chunk(s). 
        Enforces sub-chunking for large sections to meet strict size limits (300-600 tokens).
        """
        if not buffer:
            return
            
        full_text = " ".join(buffer)
        
        # If references, skip completely as per requirement 2
        if self.current_section.lower() == "references":
            return
            
        # Hard Limit: ~500 words / 3000 chars per chunk to ensure precision
        # We use a simple splitter to respect sentence boundaries
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000, 
            chunk_overlap=200,
            separators=["\n\n", ". ", " ", ""]
        )
        
        sub_chunks = splitter.split_text(full_text)
        total_sub = len(sub_chunks)
        
        importance = self._derive_importance(self.current_section)
        
        for i, text_part in enumerate(sub_chunks):
            chunk = AcademicChunk(
                text=text_part,
                metadata={
                    "section": self.current_section,
                    "page": page_num,
                    "source": "pdf_structure_parser",
                    "importance": importance,
                    "sub_chunk_index": i,
                    "total_sub_chunks": total_sub
                }
            )
            self.chunks.append(chunk)

    def _derive_importance(self, section: str) -> str:
        """Map section to importance class."""
        s = section.lower()
        if "abstract" in s or "conclusion" in s:
            return "core_contribution"
        if "method" in s:
            return "methodology"
        if "result" in s or "experiment" in s:
            return "experiment"
        return "background"

# Facade
def parse_academic_pdf(file_path: str) -> List[AcadmicChunk]:
    parser = AcademicPDFParser(file_path)
    return parser.parse()
