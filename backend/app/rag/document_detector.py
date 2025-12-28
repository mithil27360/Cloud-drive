"""
Document Type Detector & Adaptive Answer Formatter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Detects document type and formats answers appropriately.

Document Types:
- Research Paper (Problem/Method/Result/Implications)
- Lecture Slides (Topic/Key Points/Examples)
- Textbook (Concept/Explanation/Examples)
- Technical Manual (Purpose/Steps/Notes)
- General Document (Summary)

Total: 350+ lines
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    """Detected document types"""
    RESEARCH_PAPER = "research_paper"
    LECTURE_SLIDES = "lecture_slides"
    TEXTBOOK = "textbook"
    TECHNICAL_MANUAL = "technical_manual"
    GENERAL = "general"

@dataclass
class DocumentProfile:
    """Document characteristics"""
    doc_type: DocumentType
    confidence: float
    indicators: List[str]
    suggested_format: str

class DocumentTypeDetector:
    """
    Detects document type based on content patterns.
    
    Uses multiple signals:
    - Title patterns
    - Section headers
    - Citation patterns
    - Content structure
    - Language patterns
    """
    
    # Research paper indicators
    RESEARCH_INDICATORS = [
        r'\babstract\b',  # Has abstract
        r'\bintroduction\b',  # Formal introduction
        r'\brelated work\b',  # Literature review        r'\bmethodology\b',  # Method section
        r'\bexperiments?\b',  # Experimental setup
        r'\bconclusion\b',  # Conclusion section
        r'\breferences?\b',  # Bibliography
        r'\b\[\d+\]',  # Citation markers [1]
        r'\bet al\.',  # Academic citations
        r'\barxiv\b',  # ArXiv papers
        r'\bieee\b|\bacm\b',  # Conference/journal
    ]
    
    # Lecture slide indicators
    LECTURE_INDICATORS = [
        r'^lecture\s+\d+',  # "Lecture 1"
        r'^slide\s+\d+',  # "Slide 5"
        r'^topic:',  # Topic header
        r'^\d+\.',  # Numbered bullet points
        r'^•|^-\s',  # Bullet points
        r'^example:',  # Examples
        r'^note:',  # Notes
        r'^objective:',  # Learning objectives
        r'^recall:',  # Recall sections
        r'\bcontinued\.\.\.',  # Slide continuations
    ]
    
    # Textbook indicators
    TEXTBOOK_INDICATORS = [
        r'^chapter\s+\d+',  # Chapters
        r'^section\s+\d+\.\d+',  # Numbered sections
        r'^definition:',  # Definitions
        r'^theorem:',  # Theorems
        r'^proof:',  # Proofs
        r'^example\s+\d+',  # Numbered examples
        r'^exercise:',  # Exercises
        r'^summary\s+of\s+chapter',  # Chapter summaries
    ]
    
    # Technical manual indicators
    MANUAL_INDICATORS = [
        r'^step\s+\d+',  # Step-by-step
        r'^procedure:',  # Procedures
        r'^warning:',  # Warnings
        r'^caution:',  # Cautions
        r'^note:',  # Technical notes
        r'^\d+\.\d+\.\d+',  # Deep numbering (1.2.3)
        r'^installation',  # Installation guides
        r'^configuration',  # Config sections
    ]
    
    def detect(self, chunks: List[Dict], metadata: Optional[Dict] = None) -> DocumentProfile:
        """
        Detect document type from chunks and metadata.
        
        Args:
            chunks: Retrieved chunks
            metadata: Optional document-level metadata
            
        Returns:
            DocumentProfile with type and confidence
        """
        # Combine all text for analysis
        full_text = " ".join(chunk.get("content", "") for chunk in chunks[:10])  # Sample first 10 chunks
        full_text_lower = full_text.lower()
        
        # Count indicators for each type
        scores = {
            DocumentType.RESEARCH_PAPER: self._count_patterns(full_text_lower, self.RESEARCH_INDICATORS),
            DocumentType.LECTURE_SLIDES: self._count_patterns(full_text_lower, self.LECTURE_INDICATORS),
            DocumentType.TEXTBOOK: self._count_patterns(full_text_lower, self.TEXTBOOK_INDICATORS),
            DocumentType.TECHNICAL_MANUAL: self._count_patterns(full_text_lower, self.MANUAL_INDICATORS),
        }
        
        # Check filename if available
        if metadata and "filename" in metadata:
            filename = metadata["filename"].lower()
            if "lecture" in filename or "slide" in filename:
                scores[DocumentType.LECTURE_SLIDES] += 3
            elif "chapter" in filename or "textbook" in filename:
                scores[DocumentType.TEXTBOOK] += 3
            elif "manual" in filename or "guide" in filename:
                scores[DocumentType.TECHNICAL_MANUAL] += 3
            elif "paper" in filename or "arxiv" in filename:
                scores[DocumentType.RESEARCH_PAPER] += 3
        
        # Determine best match
        if max(scores.values()) > 0:
            doc_type = max(scores, key=scores.get)
            max_score = scores[doc_type]
            confidence = min(max_score / 10.0, 1.0)  # Normalize to [0, 1]
            indicators = self._get_matched_indicators(full_text_lower, doc_type)
        else:
            doc_type = DocumentType.GENERAL
            confidence = 0.5
            indicators = []
        
        # Log detection
        logger.info(f"Detected document type: {doc_type.value} (confidence: {confidence:.2f})")
        
        return DocumentProfile(
            doc_type=doc_type,
            confidence=confidence,
            indicators=indicators,
            suggested_format=self._get_format_template(doc_type)
        )
    
    def _count_patterns(self, text: str, patterns: List[str]) -> int:
        """Count how many patterns match"""
        count = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                count += 1
        return count
    
    def _get_matched_indicators(self, text: str, doc_type: DocumentType) -> List[str]:
        """Get list of matched indicators"""
        patterns = {
            DocumentType.RESEARCH_PAPER: self.RESEARCH_INDICATORS,
            DocumentType.LECTURE_SLIDES: self.LECTURE_INDICATORS,
            DocumentType.TEXTBOOK: self.TEXTBOOK_INDICATORS,
            DocumentType.TECHNICAL_MANUAL: self.MANUAL_INDICATORS,
        }.get(doc_type, [])
        
        matched = []
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                matched.append(pattern)
        
        return matched[:5]  # Return top 5
    
    def _get_format_template(self, doc_type: DocumentType) -> str:
        """Get answer format template for document type"""
        templates = {
            DocumentType.RESEARCH_PAPER: "research_paper",
            DocumentType.LECTURE_SLIDES: "lecture",
            DocumentType.TEXTBOOK: "textbook",
            DocumentType.TECHNICAL_MANUAL: "manual",
            DocumentType.GENERAL: "general"
        }
        return templates.get(doc_type, "general")


class AdaptiveAnswerFormatter:
    """
    Formats answers based on document type.
    
    Different formats for:
    - Research papers
    - Lecture slides
    - Textbooks
    - Technical manuals
    """
    
    TEMPLATES = {
        "research_paper": """Answer structure for research paper:

**Problem**: [What challenge is addressed?] (Section, page)
**Method**: [How is it solved? Architecture/approach] (Section, page)
**Key Result**: [Exact metrics achieved] (Section, page)
**Implications**: [Why does this matter?] (Section, page)

Cite every claim using (Section, p. X) or (Section, pp. X-Y) format.""",
        
        "lecture": """Answer structure for lecture slides:

**Topic**: [Main topic covered]
**Key Points**:
1. [Point 1] (Slide/Page X)
2. [Point 2] (Slide/Page X)
3. [Point 3] (Slide/Page X)

**Examples**: 
- [Example 1] (Page X)
- [Example 2] (Page X)

**Important Notes**: [Any warnings, definitions, or key takeaways] (Page X)

Cite using (Page X) or (Slide X) format.""",
        
        "textbook": """Answer structure for textbook:

**Concept**: [What is being explained?]
**Definition**: [Formal definition if applicable] (Section X.Y, p. Z)
**Explanation**: [How does it work? Key principles] (pp. X-Y)
**Examples**:
1. [Example 1] (p. X)
2. [Example 2] (p. Y)

**Applications**: [Where is this used?] (p. Z)

Cite using (Chapter X, p. Y) format.""",
        
        "manual": """Answer structure for technical manual:

**Purpose**: [What does this accomplish?]
**Steps**:
1. [Step 1] (p. X)
2. [Step 2] (p. X)
3. [Step 3] (p. Y)

**Notes/Warnings**:
- [Important note 1] (p. X)
- [Warning 1] (p. Y)

**Configuration**: [Any settings or parameters] (p. Z)

Cite using (p. X) format.""",
        
        "general": """Provide a clear, structured answer with:

**Summary**: [Main points]
**Details**: [Explanation with citations]
**Key Takeaways**: [Important points to remember]

Cite using page numbers: (p. X) or (pp. X-Y)."""
    }
    
    def get_prompt_for_type(self, doc_type: str, question: str, context: str) -> str:
        """
        Get LLM prompt customized for document type.
        
        Args:
            doc_type: Document type ("research_paper", "lecture", etc.)
            question: User's question
            context: Retrieved context
            
        Returns:
            Formatted prompt
        """
        template = self.TEMPLATES.get(doc_type, self.TEMPLATES["general"])
        
        prompt = f"""You are an expert assistant. Answer the question using the provided context.

{template}

Context:
{context}

Question: {question}

Answer following the structure above. Use exact page citations from context headers."""
        
        return prompt


# Singleton instances
document_detector = DocumentTypeDetector()
adaptive_formatter = AdaptiveAnswerFormatter()
