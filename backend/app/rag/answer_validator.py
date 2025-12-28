"""
Answer Validator & Quality Control System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validates research answers for common mistakes.

Features:
- Problem vs Method confusion detection
- Citation verification
- Formula validation
- Metric extraction
- Structural checks

Total: 250+ lines
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ValidationIssue(Enum):
    """Types of validation issues"""
    PROBLEM_METHOD_CONFUSION = "problem_method_confusion"
    MISSING_METRICS = "missing_metrics"
    MISSING_CITATIONS = "missing_citations"
    FORMULA_NOT_RENDERED = "formula_not_rendered"
    VAGUE_LANGUAGE = "vague_language"
    COMPUTATION_PATH_CONFUSION = "computation_path_confusion"

@dataclass
class ValidationResult:
    """Result of answer validation"""
    is_valid: bool
    issues: List[Tuple[ValidationIssue, str]]  # (issue_type, description)
    score: float  # 0.0 to 1.0
    suggestions: List[str]

class ResearchAnswerValidator:
    """
    Validates research answers for common academic mistakes.
    
    Checks:
    1. Problem vs Method distinction
    2. Presence of metrics/numbers
    3. Citation coverage
    4. Formula formatting
    5. Vague language detection
    """
    
    # Problem-indicating keywords
    PROBLEM_KEYWORDS = [
        'challenge', 'issue', 'difficulty', 'limitation', 'bottleneck',
        'inefficient', 'slow', 'expensive', 'difficult', 'hard'
    ]
    
    # Method-indicating keywords
    METHOD_KEYWORDS = [
        'model', 'architecture', 'approach', 'technique', 'algorithm',
        'mechanism', 'layer', 'attention', 'transformer', 'network'
    ]
    
    # Vague phrases to avoid
    VAGUE_PHRASES = [
        'the paper discusses', 'it is mentioned', 'not explicitly stated',
        'appears to', 'seems to', 'might be', 'could be', 'based on the context'
    ]
    
    # Metric patterns
    METRIC_PATTERNS = [
        r'\b\d+\.?\d*%\b',  # 95.3%
        r'\bBLEU\s+\d+\.?\d*\b',  # BLEU 28.4
        r'\bF1\s+\d+\.?\d*\b',  # F1 0.87
        r'\baccuracy\s+\d+\.?\d*\b',  # accuracy 94.5
        r'\b\d+\.?\d*\s+(ms|seconds|hours)\b',  # 5.2 seconds
    ]
    
    def validate(
        self, 
        answer: str, 
        query: str, 
        query_type: str,
        citations: List[Dict]
    ) -> ValidationResult:
        """
        Validate answer quality.
        
        Args:
            answer: Generated answer text
            query: Original query
            query_type: Type (summary/formula/etc)
            citations: List of citations used
            
        Returns:
            ValidationResult with issues and score
        """
        issues = []
        
        # 1. Check for Problem vs Method confusion (for summaries)
        if query_type == "summary":
            problem_method_issue = self._check_problem_method_confusion(answer)
            if problem_method_issue:
                issues.append(problem_method_issue)
        
        # 2. Check for metrics (required for results/summary)
        if query_type in ["summary", "results"]:
            if not self._has_metrics(answer):
                issues.append((
                    ValidationIssue.MISSING_METRICS,
                    "No numerical metrics found (BLEU, accuracy, F1, etc.)"
                ))
        
        # 3. Check citation coverage
        citation_issue = self._check_citations(answer, citations)
        if citation_issue:
            issues.append(citation_issue)
        
        # 4. Check for vague language
        vague_issues = self._check_vague_language(answer)
        issues.extend(vague_issues)
        
        # 5. Check formulas (for formula queries)
        if query_type == "formula":
            formula_issue = self._check_formulas(answer)
            if formula_issue:
                issues.append(formula_issue)
        
        # 6. Check for O(n²) vs O(1) confusion
        if "o(1)" in answer.lower() and "o(n" in answer.lower():
            if "path length" not in answer.lower():
                issues.append((
                    ValidationIssue.COMPUTATION_PATH_CONFUSION,
                    "Conflating computation complexity O(n²) with path length O(1)"
                ))
        
        # Calculate score
        score = self._calculate_score(issues)
        
        # Generate suggestions
        suggestions = self._generate_suggestions(issues)
        
        return ValidationResult(
            is_valid=(score >= 0.7),
            issues=issues,
            score=score,
            suggestions=suggestions
        )
    
    def _check_problem_method_confusion(self, answer: str) -> Optional[Tuple[ValidationIssue, str]]:
        """Check if Problem section contains method keywords"""
        # Look for "Problem:" section
        problem_match = re.search(r'\*\*Problem\*\*:([^*]+)', answer, re.IGNORECASE)
        if not problem_match:
            return None
        
        problem_text = problem_match.group(1).lower()
        
        # Check if problem section mentions methods
        method_count = sum(1 for kw in self.METHOD_KEYWORDS if kw in problem_text)
        problem_count = sum(1 for kw in self.PROBLEM_KEYWORDS if kw in problem_text)
        
        if method_count > problem_count:
            return (
                ValidationIssue.PROBLEM_METHOD_CONFUSION,
                f"Problem section contains {method_count} method keywords but only {problem_count} problem keywords. "
                "Problem should describe the challenge, not the solution."
            )
        
        return None
    
    def _has_metrics(self, answer: str) -> bool:
        """Check if answer contains numerical metrics"""
        for pattern in self.METRIC_PATTERNS:
            if re.search(pattern, answer, re.IGNORECASE):
                return True
        return False
    
    def _check_citations(self, answer: str, citations: List[Dict]) -> Optional[Tuple[ValidationIssue, str]]:
        """Check citation quality"""
        # Extract citation markers from answer
        cited_ids = set(re.findall(r'\[(\d+:\d+)\]', answer))
        
        if not cited_ids:
            return (
                ValidationIssue.MISSING_CITATIONS,
                "No citations found. Every claim must have [Source ID]."
            )
        
        # Check citation density (should have at least 1 per 100 words)
        word_count = len(answer.split())
        expected_citations = max(word_count // 100, 1)
        
        if len(cited_ids) < expected_citations:
            return (
                ValidationIssue.MISSING_CITATIONS,
                f"Low citation density: {len(cited_ids)} citations for {word_count} words. "
                f"Expected at least {expected_citations}."
            )
        
        return None
    
    def _check_vague_language(self, answer: str) -> List[Tuple[ValidationIssue, str]]:
        """Check for vague academic language"""
        issues = []
        answer_lower = answer.lower()
        
        for phrase in self.VAGUE_PHRASES:
            if phrase in answer_lower:
                issues.append((
                    ValidationIssue.VAGUE_LANGUAGE,
                    f"Vague phrase detected: '{phrase}'. Be more direct."
                ))
        
        return issues
    
    def _check_formulas(self, answer: str) -> Optional[Tuple[ValidationIssue, str]]:
        """Check if formulas are properly rendered"""
        # Look for equation patterns
        has_equation_word = any(w in answer.lower() for w in ['formula', 'equation'])
        
        # Check for mathematical notation
        has_math = any([
            '=' in answer,
            'sqrt' in answer.lower(),
            'softmax' in answer.lower(),
            '_' in answer,  # Subscripts
            '^' in answer,  # Superscripts
        ])
        
        if has_equation_word and not has_math:
            return (
                ValidationIssue.FORMULA_NOT_RENDERED,
                "Answer mentions formulas but doesn't show them mathematically"
            )
        
        return None
    
    def _calculate_score(self, issues: List[Tuple[ValidationIssue, str]]) -> float:
        """Calculate quality score"""
        if not issues:
            return 1.0
        
        # Weight different issue types
        weights = {
            ValidationIssue.PROBLEM_METHOD_CONFUSION: 0.3,
            ValidationIssue.MISSING_METRICS: 0.2,
            ValidationIssue.MISSING_CITATIONS: 0.3,
            ValidationIssue.FORMULA_NOT_RENDERED: 0.2,
            ValidationIssue.VAGUE_LANGUAGE: 0.1,
            ValidationIssue.COMPUTATION_PATH_CONFUSION: 0.2,
        }
        
        penalty = sum(weights.get(issue_type, 0.1) for issue_type, _ in issues)
        score = max(0.0, 1.0 - penalty)
        
        return round(score, 2)
    
    def _generate_suggestions(self, issues: List[Tuple[ValidationIssue, str]]) -> List[str]:
        """Generate actionable suggestions"""
        suggestions = []
        
        issue_types = {issue_type for issue_type, _ in issues}
        
        if ValidationIssue.PROBLEM_METHOD_CONFUSION in issue_types:
            suggestions.append(
                "Rewrite Problem section to focus on the challenge/limitation, not the solution architecture."
            )
        
        if ValidationIssue.MISSING_METRICS in issue_types:
            suggestions.append(
                "Add specific metrics: BLEU scores, accuracy percentages, training time, etc."
            )
        
        if ValidationIssue.MISSING_CITATIONS in issue_types:
            suggestions.append(
                "Add [Source ID] citations after each factual claim."
            )
        
        if ValidationIssue.VAGUE_LANGUAGE in issue_types:
            suggestions.append(
                "Replace vague phrases ('seems to', 'appears to') with direct statements."
            )
        
        if ValidationIssue.FORMULA_NOT_RENDERED in issue_types:
            suggestions.append(
                "Show formulas in mathematical notation: Attention(Q,K,V) = softmax(QK^T/sqrt(d_k))V"
            )
        
        if ValidationIssue.COMPUTATION_PATH_CONFUSION in issue_types:
            suggestions.append(
                "Clarify: 'O(n²) computation cost' vs 'O(1) sequential path length'"
            )
        
        return suggestions


# Singleton
answer_validator = ResearchAnswerValidator()
