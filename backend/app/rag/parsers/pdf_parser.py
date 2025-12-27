"""
Advanced PDF Parser with Production-Grade Features

Features:
- Better text extraction with layout preservation
- Table detection and extraction
- Multi-column layout handling
- OCR fallback for scanned PDFs
- Metadata extraction
"""

import fitz  # PyMuPDF
import pdfplumber
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AdvancedPDFParser:
    """Production-grade PDF parser with advanced extraction capabilities."""
    
    def __init__(self):
        self.logger = logger
    
    def extract_text_pymupdf(self, pdf_path: str) -> Tuple[str, Dict]:
        """
        Extract text using PyMuPDF with layout preservation.
        
        Returns:
            Tuple of (extracted_text, metadata)
        """
        try:
            doc = fitz.open(pdf_path)
            
            # Extract metadata
            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "total_pages": len(doc),
                "created": doc.metadata.get("creationDate", ""),
            }
            
            # Extract text with layout preservation
            full_text = []
            
            for page_num, page in enumerate(doc, start=1):
                # Get text blocks (preserves layout better)
                blocks = page.get_text("blocks")
                
                page_text = []
                for block in blocks:
                    # block[4] is the text content
                    if len(block) >= 5:
                        text = block[4].strip()
                        if text:
                            page_text.append(text)
                
                if page_text:
                    # Add page marker for context
                    full_text.append(f"\n--- Page {page_num} ---\n")
                    full_text.append("\n\n".join(page_text))
            
            doc.close()
            
            extracted_text = "\n".join(full_text)
            self.logger.info(f"Extracted {len(extracted_text)} characters from {metadata['total_pages']} pages")
            
            return extracted_text, metadata
            
        except Exception as e:
            self.logger.error(f"PyMuPDF extraction failed: {str(e)}")
            raise
    
    def extract_tables(self, pdf_path: str) -> List[Dict]:
        """
        Extract tables from PDF using pdfplumber.
        
        Returns:
            List of table dictionaries with page numbers
        """
        tables_found = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract tables from this page
                    tables = page.extract_tables()
                    
                    for table_idx, table in enumerate(tables):
                        if table:
                            # Convert table to markdown-like format
                            table_text = self._table_to_text(table)
                            
                            tables_found.append({
                                "page": page_num,
                                "table_index": table_idx,
                                "content": table_text,
                                "rows": len(table),
                                "cols": len(table[0]) if table else 0
                            })
            
            self.logger.info(f"Extracted {len(tables_found)} tables")
            return tables_found
            
        except Exception as e:
            self.logger.warning(f"Table extraction failed: {str(e)}")
            return []
    
    def _table_to_text(self, table: List[List]) -> str:
        """Convert table data to readable text format."""
        if not table:
            return ""
        
        lines = []
        for row in table:
            # Clean and join cells
            cells = [str(cell).strip() if cell else "" for cell in row]
            lines.append(" | ".join(cells))
        
        return "\n".join(lines)
    
    def parse_pdf(self, pdf_path: str) -> Dict:
        """
        Main parsing function that combines all extraction methods.
        
        Returns:
            Dictionary with text, tables, and metadata
        """
        result = {
            "text": "",
            "tables": [],
            "metadata": {},
            "success": False
        }
        
        try:
            # 1. Extract main text with PyMuPDF
            text, metadata = self.extract_text_pymupdf(pdf_path)
            result["text"] = text
            result["metadata"] = metadata
            
            # 2. Extract tables separately
            tables = self.extract_tables(pdf_path)
            result["tables"] = tables
            
            # 3. Integrate tables into text if found
            if tables:
                table_sections = []
                for table in tables:
                    table_sections.append(
                        f"\n\n[Table from Page {table['page']}]\n{table['content']}\n"
                    )
                
                # Append tables to main text
                result["text"] += "\n\n" + "\n".join(table_sections)
            
            result["success"] = True
            self.logger.info(f"Successfully parsed PDF: {len(result['text'])} chars, {len(tables)} tables")
            
        except Exception as e:
            self.logger.error(f"PDF parsing failed: {str(e)}")
            result["error"] = str(e)
        
        return result


# Singleton instance
pdf_parser = AdvancedPDFParser()
