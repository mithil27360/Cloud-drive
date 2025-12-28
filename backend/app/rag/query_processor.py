"""
Query Processor with Intent Detection & Section Targeting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles query understanding and routing for research queries.

Features:
- Intent classification (Formula, Summary, Comparison, General)
- Query rewriting and expansion
- Section targeting based on intent
- Entity extraction (paper names, authors, concepts)

Total: 200+ lines
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    """Query intent types for research papers"""
    FORMULA = "formula"
    SUMMARY = "summary"
    METHODOLOGY = "methodology"
    RESULTS = "results"
    COMPARISON = "comparison"
    LIMITATIONS = "limitations"
    GENERAL = "general"

@dataclass
class ProcessedQuery:
    """Container for processed query information"""
    original: str
    intent: QueryIntent
    target_sections: List[str]
    expanded_queries: List[str]
    entities: Dict[str, List[str]]
    confidence: float

class ResearchQueryProcessor:
    """
    Production-grade query processor for academic papers.
    
    Responsibilities:
    1. Classify query intent
    2. Identify target sections
    3. Expand query with synonyms
    4. Extract entities (papers, authors, concepts)
    """
    
    # Intent detection patterns
    INTENT_PATTERNS = {
        QueryIntent.FORMULA: [
            r'\b(formula|equation|math|algorithm|notation|implementation|code)\b',
            r'\bwhat is the (core|main|primary)? ?(formula|equation)\b',
            r'\b(derive|show|prove)\b.*\b(equation|formula)\b',
        ],
        QueryIntent.SUMMARY: [
            r'\b(summarize|summary|overview|tldr|explain|describe)\b',
            r'\bwhat\s+(is|are)\s+the\s+(main|core|key)\s+(idea|contribution|point)',
            r'\bwhat does.*do\b',
            r'\bgive me (a|an)? ?(summary|overview)',
        ],
        QueryIntent.METHODOLOGY: [
            r'\b(how|method|approach|technique|architecture|model|setup)\b',
            r'\bwhat\s+is\s+the\s+(approach|method|technique)\b',
            r'\bhow\s+(do|does|did).*work\b',
        ],
        QueryIntent.RESULTS: [
            r'\b(result|performance|score|accuracy|metric|benchmark|evaluation)\b',
            r'\bhow\s+(well|good)\b',
            r'\bwhat\s+(score|accuracy|performance)\b',
        ],
        QueryIntent.COMPARISON: [
            r'\b(compare|comparison|versus|vs|difference|better|worse)\b',
            r'\bcompare.*to\b',
            r'\bhow\s+does.*compare\b',
        ],
        QueryIntent.LIMITATIONS: [
            r'\b(limitation|drawback|weakness|problem|issue|challenge|gap)\b',
            r'\bwhat\s+(are|is)\s+the\s+limit',
            r'\bwhat.*fail',
        ]
    }
    
    # Section mapping for each intent
    INTENT_TO_SECTIONS = {
        QueryIntent.FORMULA: ["Method", "Methodology", "Algorithm", "Model", "Appendix", "Implementation"],
        QueryIntent.SUMMARY: ["Abstract", "Introduction", "Conclusion"],
        QueryIntent.METHODOLOGY: ["Method", "Methodology", "Approach", "Model", "Architecture"],
        QueryIntent.RESULTS: ["Results", "Experiments", "Evaluation", "Discussion"],
        QueryIntent.COMPARISON: ["Related Work", "Discussion", "Results"],
        QueryIntent.LIMITATIONS: ["Conclusion", "Discussion", "Future Work"],
        QueryIntent.GENERAL: []  # No specific sections
    }
    
    # Query expansion synonyms
    SYNONYMS = {
        "formula": ["equation", "mathematical expression", "formulation"],
        "method": ["approach", "technique", "methodology"],
        "result": ["performance", "outcome", "finding"],
        "limitation": ["drawback", "weakness", "shortcoming"],
    }
    
    def process(self, query: str) -> ProcessedQuery:
        """
        Main processing pipeline.
        
        Args:
            query: Raw user query
            
        Returns:
            ProcessedQuery with all analysis results
        """
        logger.info(f"Processing query: {query}")
        
        # 1. Classify intent
        intent, confidence = self._classify_intent(query)
        logger.debug(f"Intent: {intent.value} (confidence: {confidence:.2f})")
        
        # 2. Get target sections
        target_sections = self._get_target_sections(intent)
        
        # 3. Expand query
        expanded = self._expand_query(query, intent)
        
        # 4. Extract entities
        entities = self._extract_entities(query)
        
        return ProcessedQuery(
            original=query,
            intent=intent,
            target_sections=target_sections,
            expanded_queries=expanded,
            entities=entities,
            confidence=confidence
        )
    
    def _classify_intent(self, query: str) -> Tuple[QueryIntent, float]:
        """
        Classify query intent using pattern matching.
        
        Returns:
            (intent, confidence_score)
        """
        query_lower = query.lower()
        scores = {intent: 0 for intent in QueryIntent}
        
        # Score each intent based on pattern matches
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    scores[intent] += 1
        
        # Get best match
        if max(scores.values()) > 0:
            best_intent = max(scores, key=scores.get)
            confidence = min(scores[best_intent] / 3.0, 1.0)  # Normalize to [0, 1]
            return best_intent, confidence
        
        # Default to GENERAL
        return QueryIntent.GENERAL, 0.5
    
    def _get_target_sections(self, intent: QueryIntent) -> List[str]:
        """Get section names to prioritize for this intent"""
        return self.INTENT_TO_SECTIONS.get(intent, [])
    
    def _expand_query(self, query: str, intent: QueryIntent) -> List[str]:
        """
        Expand query with synonyms and variations.
        
        Returns:
            List of query variations (including original)
        """
        expanded = [query]
        query_lower = query.lower()
        
        # Add synonym-based expansions
        for word, synonyms in self.SYNONYMS.items():
            if word in query_lower:
                for syn in synonyms:
                    expanded.append(query_lower.replace(word, syn))
        
        # Intent-specific expansions
        if intent == QueryIntent.FORMULA:
            if "formula" not in query_lower:
                expanded.append(f"{query} formula")
                expanded.append(f"{query} equation")
        elif intent == QueryIntent.SUMMARY:
            if "summary" not in query_lower and "summarize" not in query_lower:
                expanded.append(f"summary of {query}")
        
        # Limit to top 3 variations
        return list(set(expanded))[:3]
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract named entities from query.
        
        Returns:
            Dict with entity types and values
        """
        entities = {
            "papers": [],
            "authors": [],
            "concepts": []
        }
        
        # Extract paper names (capitalized phrases in quotes or standalone)
        paper_pattern = r'"([^"]+)"'
        entities["papers"] = re.findall(paper_pattern, query)
        
        # Extract potential author names (capitalized words)
        # Simple heuristic: 2+ consecutive capitalized words
        author_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b'
        entities["authors"] = re.findall(author_pattern, query)
        
        # Extract concepts (for now, just all capitalized words not in authors/papers)
        concept_pattern = r'\b([A-Z][a-zA-Z]+)\b'
        all_caps = re.findall(concept_pattern, query)
        entities["concepts"] = [
            c for c in all_caps 
            if c not in entities["authors"] and c not in entities["papers"]
        ]
        
        return entities


class QueryRewriter:
    """
    Advanced query rewriting for better retrieval.
    
    Techniques:
    - Remove stopwords
    - Normalize terminology
    - Handle abbreviations
    """
    
    STOPWORDS = {'the', 'a', 'an', 'is', 'are', 'what', 'how', 'why', 'when', 'where'}
    
    ABBREVIATIONS = {
        'ml': 'machine learning',
        'dl': 'deep learning',
        'nlp': 'natural language processing',
        'cv': 'computer vision',
        'rl': 'reinforcement learning',
        'gnn': 'graph neural network',
        'rnn': 'recurrent neural network',
        'cnn': 'convolutional neural network',
        'lstm': 'long short-term memory',
        'gpt': 'generative pre-trained transformer',
        'bert': 'bidirectional encoder representations from transformers',
    }
    
    def rewrite(self, query: str) -> str:
        """
        Rewrite query for better matching.
        
        Args:
            query: Original query
            
        Returns:
            Rewritten query
        """
        # Convert to lowercase
        rewritten = query.lower()
        
        # Expand abbreviations
        for abbr, full in self.ABBREVIATIONS.items():
            rewritten = re.sub(r'\b' + abbr + r'\b', full, rewritten)
        
        # Remove stopwords (but keep important question words)
        words = rewritten.split()
        important_words = ['how', 'what', 'why', 'when', 'where']
        filtered = [w for w in words if w not in self.STOPWORDS or w in important_words]
        
        return ' '.join(filtered)


# Singleton instances
query_processor = ResearchQueryProcessor()
query_rewriter = QueryRewriter()
