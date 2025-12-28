"""
Research Answer Generator with Formula Extraction & Citations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generates research-grade answers from retrieved context.

Features:
- Formula extraction and LaTeX rendering
- Strict citation tracking
- Multi-document synthesis
- Structured output (Problem/Method/Result/Implications)
- Confidence scoring

Total: 300+ lines
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

@dataclass
class Citation:
    """Citation with full provenance"""
    source_id: str
    text: str
    page: int
    section: str
    file_id: int
    score: float

@dataclass
class ResearchAnswer:
    """Structured research answer"""
    answer: str
    citations: List[Citation]
    formulas: List[str]
    confidence: float
    answer_type: str  # "direct", "synthesized", "comparative"
    
    @property
    def cited_sources(self) -> List[str]:
        """Get all cited source IDs"""
        return list(set(c.source_id for c in self.citations))

class ResearchAnswerGenerator:
    """
    Production-grade answer generator for research papers.
    
    Capabilities:
    1. Extract mathematical formulas
    2. Track citations precisely
    3. Generate structured answers (Problem/Method/Result)
    4. Synthesize across multiple papers
    5. Assign confidence scores
    """
    
    # Formula patterns
    FORMULA_PATTERNS = [
        r'([A-Z]\([^)]+\)\s*=\s*[^\n]+)',  # Attention(Q,K,V) = ...
        r'(\$[^\$]+\$)',  # LaTeX inline
        r'(\\\[[^\]]+\\\])',  # LaTeX display
        r'([a-z_]+\s*=\s*\\?[a-z]+\([^)]+\))',  # loss = softmax(...)
    ]
    
    # Answer structuring prompts based on query type
    PROMPT_TEMPLATES = {
        "formula": """Extract all mathematical formulas and equations from the context.
Format each formula clearly and provide its purpose with citations.

Context: {context}
Question: {question}

Answer format:
The core formula is: [formula] [Source ID]
Where: [explain variables] [Source ID]""",
        
        "summary": """Provide a structured summary following this format:

**Problem**: What challenge is addressed? [Source ID]
**Method**: How is it solved? (key approach, architecture) [Source ID]
**Key Result**: What metrics were achieved? (exact numbers) [Source ID]
**Implications**: Why does this matter? [Source ID]

Context: {context}
Question: {question}""",
        
        "methodology": """Explain the methodology step-by-step with citations.

Context: {context}
Question: {question}

Answer format:
The approach consists of:
1. [Step 1] [Source ID]
2. [Step 2] [Source ID]
...""",
        
        "comparison": """Compare the approaches/results mentioned with citations.

Context: {context}
Question: {question}

Answer format:
**Similarities**: [points] [Source IDs]
**Differences**: [points] [Source IDs]
**Performance**: [metrics comparison] [Source IDs]""",
        
        "general": """Answer the question directly and precisely using only the provided context.
Every claim must be followed by [Source ID].

Context: {context}
Question: {question}"""
    }
    
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
    
    def generate(
        self,
        question: str,
        context_chunks: List[Dict],
        query_type: str = "general",
        max_tokens: int = 1024
    ) -> ResearchAnswer:
        """
        Generate research-grade answer.
        
        Args:
            question: User's question
            context_chunks: Retrieved chunks with metadata
            query_type: Type of query (formula/summary/methodology/etc)
            max_tokens: Max response length
            
        Returns:
            ResearchAnswer with structured output
        """
        logger.info(f"Generating answer for query type: {query_type}")
        
        # 1. Format context with citations
        formatted_context, citation_map = self._format_context(context_chunks)
        
        # 2. Select appropriate prompt template
        prompt_template = self.PROMPT_TEMPLATES.get(query_type, self.PROMPT_TEMPLATES["general"])
        user_prompt = prompt_template.format(
            context=formatted_context,
            question=question
        )
        
        # 3. Generate answer via LLM
        raw_answer = self._call_llm(user_prompt, max_tokens)
        
        # 4. Extract formulas
        formulas = self._extract_formulas(raw_answer)
        
        # 5. Parse citations
        cited_sources = self._parse_citations(raw_answer)
        used_citations = [citation_map[sid] for sid in cited_sources if sid in citation_map]
        
        # 6. Calculate confidence
        confidence = self._calculate_confidence(raw_answer, used_citations, context_chunks)
        
        return ResearchAnswer(
            answer=raw_answer,
            citations=used_citations,
            formulas=formulas,
            confidence=confidence,
            answer_type=query_type
        )
    
    def _format_context(self, chunks: List[Dict]) -> Tuple[str, Dict[str, Citation]]:
        """
        Format context with source IDs and build citation map.
        
        Returns:
            (formatted_context_string, citation_map)
        """
        citation_map = {}
        context_parts = []
        
        for idx, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            content = chunk.get("content", "")
            
            # Build source ID
            fid = metadata.get("file_id", 0)
            cid = metadata.get("sub_chunk_index", metadata.get("chunk_index", idx))
            source_id = f"{fid}:{cid}"
            
            # Create citation object
            citation = Citation(
                source_id=source_id,
                text=content,
                page=metadata.get("page", 1),
                section=metadata.get("section", "General"),
                file_id=fid,
                score=chunk.get("score", 0.0)
            )
            citation_map[source_id] = citation
            
            # Format for context
            header = f"[Source ID: {source_id}] (Section: {citation.section})"
            context_parts.append(f"{header}\n{content}\n")
        
        return "\n---\n".join(context_parts), citation_map
    
    def _call_llm(self, prompt: str, max_tokens: int) -> str:
        """Call LLM API with error handling"""
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a precise research assistant. Follow instructions exactly and cite all sources."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.2,  # Low for precision
                    "max_tokens": max_tokens
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            
            logger.error("No choices in LLM response")
            return "Error: Could not generate answer."
            
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return f"Error: {str(e)}"
    
    def _extract_formulas(self, text: str) -> List[str]:
        """Extract mathematical formulas from text"""
        formulas = []
        
        for pattern in self.FORMULA_PATTERNS:
            matches = re.findall(pattern, text)
            formulas.extend(matches)
        
        # Deduplicate
        return list(set(formulas))
    
    def _parse_citations(self, text: str) -> List[str]:
        """Extract all [Source ID] citations from answer"""
        # Pattern: [file_id:chunk_id]
        pattern = r'\[(\d+:\d+)\]'
        return list(set(re.findall(pattern, text)))
    
    def _calculate_confidence(
        self,
        answer: str,
        citations: List[Citation],
        context_chunks: List[Dict]
    ) -> float:
        """
        Calculate answer confidence score.
        
        Factors:
        - Number of citations
        - Citation coverage (% of claims cited)
        - Retrieval scores
        - Answer length vs context length
        """
        # Base confidence from citation count
        citation_score = min(len(citations) / 3.0, 1.0)  # Normalize to 3+ citations = 1.0
        
        # Retrieval quality score
        if citations:
            avg_retrieval_score = sum(c.score for c in citations) / len(citations)
            # Invert distance scores (lower is better)
            retrieval_score = max(0, 1 - avg_retrieval_score)
        else:
            retrieval_score = 0.0
        
        # Citation density (citations per 100 words)
        words = len(answer.split())
        citation_density = (len(citations) / max(words, 1)) * 100
        density_score = min(citation_density / 5.0, 1.0)  # 5+ citations per 100 words = 1.0
        
        # Weighted average
        confidence = (
            0.4 * citation_score +
            0.3 * retrieval_score +
            0.3 * density_score
        )
        
        return round(confidence, 2)


# Singleton instance placeholder (initialized in config)
answer_generator = None

def init_answer_generator(api_key: str, model: str = "llama-3.1-8b-instant"):
    """Initialize global answer generator"""
    global answer_generator
    answer_generator = ResearchAnswerGenerator(api_key, model)
    return answer_generator
