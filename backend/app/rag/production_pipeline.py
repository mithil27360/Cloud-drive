"""
Production RAG Pipeline - 7 Layer System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive RAG with document detection, intent routing,
domain rules, context validation, answer self-check, and failure logging.

Total: ~500 lines

Layers:
1. Document Type Detection
2. User Intent Routing  
3. Domain Rule Enforcement
4. Context Quality Check
5. Answer Self-Validation
6. Answer Style Adapter
7. Failure Logging
"""

import re
import logging
from enum import Enum
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# LAYER 1: DOCUMENT TYPE DETECTION
# ============================================================================

class DocumentType(Enum):
    EXAM = "exam"
    RESEARCH = "research"
    LEGAL = "legal"
    MEDICAL = "medical"
    TECH_DOC = "tech_doc"
    LECTURE = "lecture"
    GENERAL = "general"


# Detection patterns per document type
DOC_PATTERNS = {
    DocumentType.EXAM: [
        r'\b(question|q\.?\s*\d+|answer|marks?|score|exam|test|quiz)\b',
        r'\b(solve|calculate|find|determine|prove|show that|write a (function|program|code))\b',
        r'\b(PYQ|previous year|mid.?term|end.?term|makeup|semester|internal)\b',
        r'\[\s*\d+\s*marks?\s*\]',
        r'\(\s*\d+\s*marks?\s*\)',
        r'\b(CSE|ECE|EEE|MECH|IT|B\.?Tech)\s*\d{4}\b',
    ],
    DocumentType.RESEARCH: [
        r'\b(abstract|introduction|methodology|conclusion|references|doi)\b',
        r'\b(we propose|this paper|our approach|state.?of.?the.?art|related work)\b',
        r'\b(BLEU|F1.?score|accuracy|precision|recall|baseline|benchmark)\b',
        r'\b(et al\.?|arXiv|IEEE|ACM|Springer|CVPR|NeurIPS|ICML)\b',
    ],
    DocumentType.LEGAL: [
        r'\b(hereby|whereas|notwithstanding|pursuant|hereinafter)\b',
        r'\b(clause|section|article|subsection|agreement|contract|law)\b',
        r'\b(court|plaintiff|defendant|jurisdiction|tribunal)\b',
        r'\b(shall|must not|liability|indemnify|warranty)\b',
    ],
    DocumentType.MEDICAL: [
        r'\b(patient|diagnosis|treatment|symptoms|prescription|dosage)\b',
        r'\b(mg|ml|tablet|injection|oral|intravenous)\b',
        r'\b(clinical|pathology|radiology|MRI|CT scan|X-ray)\b',
        r'\b(doctor|physician|nurse|hospital|ICU)\b',
    ],
    DocumentType.TECH_DOC: [
        r'\b(API|endpoint|request|response|JSON|REST|GraphQL)\b',
        r'\b(install|configure|setup|deployment|docker|kubernetes)\b',
        r'\b(function|method|class|parameter|return|async|await)\b',
        r'```[\w]*\n',  # Code blocks
    ],
    DocumentType.LECTURE: [
        r'\b(lecture|slide|chapter|topic|learning objectives)\b',
        r'\b(example|definition|theorem|lemma|proof|corollary)\b',
        r'\b(summary|recap|key points|takeaway)\b',
    ],
}


def detect_document_type(filename: str, content: str) -> DocumentType:
    """
    Detect document type from filename and content.
    Returns the most likely document type.
    """
    text = f"{filename.lower()} {content.lower()}"
    
    scores = {}
    for doc_type, patterns in DOC_PATTERNS.items():
        score = sum(
            len(re.findall(p, text, re.IGNORECASE | re.MULTILINE))
            for p in patterns
        )
        scores[doc_type] = score
    
    # Prioritize EXAM detection (most common use case)
    if scores.get(DocumentType.EXAM, 0) >= 3:
        return DocumentType.EXAM
    
    max_type = max(scores, key=scores.get)
    if scores[max_type] >= 2:
        return max_type
    
    return DocumentType.GENERAL


# ============================================================================
# LAYER 2: USER INTENT ROUTING
# ============================================================================

class UserIntent(Enum):
    WHAT_IS_THIS = "what_is_this"
    SUMMARIZE = "summarize"
    ANSWER_QUESTION = "answer_question"
    EXPLAIN_CONCEPT = "explain_concept"
    WRITE_CODE = "write_code"
    DERIVE_FORMULA = "derive_formula"
    COMPARE = "compare"
    VALIDATE_SOLUTION = "validate_solution"
    LIST_ITEMS = "list_items"
    GENERAL = "general"


INTENT_PATTERNS = {
    UserIntent.WHAT_IS_THIS: [
        r'^what (is|are) (this|these)',
        r'^tell me about (this|the) (document|file|pdf)',
    ],
    UserIntent.SUMMARIZE: [
        r'\b(summarize|summary|summarise|overview|brief|tl;?dr)\b',
        r'^(give|provide) (a|me) (summary|overview)',
        r'what does (this|the) (document|file|paper) (say|contain|cover)',
    ],
    UserIntent.ANSWER_QUESTION: [
        r'^(solve|answer|find|calculate|compute|determine)\b',
        r'^(what|which|where|when|who|how many|how much)\b',
        r'\?$',
        r'^(q\d+|question\s*\d+)',
    ],
    UserIntent.EXPLAIN_CONCEPT: [
        r'^(explain|describe|clarify|elaborate)',
        r'^(how does|how do|why does|why do)',
        r'^(what is|what are) (the|a) ',
        r'(help me understand|break down)',
    ],
    UserIntent.WRITE_CODE: [
        r'\b(write|generate|create|implement) (a |the )?(code|function|program|script)\b',
        r'\b(coding|programming|algorithm)\b',
        r'\b(python|java|c\+\+|javascript|code)\b',
    ],
    UserIntent.DERIVE_FORMULA: [
        r'\b(derive|derivation|formula|equation|proof|prove)\b',
        r'\b(show that|demonstrate that)\b',
    ],
    UserIntent.COMPARE: [
        r'\b(compare|comparison|difference|versus|vs\.?|distinguish)\b',
        r'\b(better|worse|advantage|disadvantage)\b',
    ],
    UserIntent.VALIDATE_SOLUTION: [
        r'\b(check|validate|verify|correct|wrong|mistake|error)\b',
        r'\b(is this (right|correct|wrong))\b',
    ],
    UserIntent.LIST_ITEMS: [
        r'\b(list|enumerate|give me all|what are the)\b',
        r'\b(steps|points|items|features|types|kinds)\b',
    ],
}


def detect_intent(query: str) -> UserIntent:
    """Detect user intent from query."""
    query_lower = query.lower().strip()
    
    for intent, patterns in INTENT_PATTERNS.items():
        if any(re.search(p, query_lower) for p in patterns):
            return intent
    
    return UserIntent.GENERAL


# ============================================================================
# LAYER 3: DOMAIN RULE ENFORCEMENT
# ============================================================================

@dataclass
class DomainRule:
    """A single domain rule."""
    name: str
    check: str  # Regex pattern to check
    violation_message: str
    fix_instruction: str


# Domain-specific rules
DOMAIN_RULES = {
    "data_structures": [
        DomainRule(
            name="queue_fifo",
            check=r"queue.*(lifo|last.?in.?first.?out)",
            violation_message="Queue must be FIFO, not LIFO",
            fix_instruction="Queue follows FIFO (First In First Out) principle"
        ),
        DomainRule(
            name="stack_lifo",
            check=r"stack.*(fifo|first.?in.?first.?out)",
            violation_message="Stack must be LIFO, not FIFO",
            fix_instruction="Stack follows LIFO (Last In First Out) principle"
        ),
    ],
    "research": [
        DomainRule(
            name="cite_formulas",
            check=r"(formula|equation).*(not (stated|mentioned|provided|found))",
            violation_message="Core formulas should be extracted if present",
            fix_instruction="Extract and cite the formula from the paper"
        ),
    ],
    "medical": [
        DomainRule(
            name="no_dosage_guess",
            check=r"(might be|could be|probably|approximately)\s*\d+\s*(mg|ml|tablet)",
            violation_message="Never guess medical dosages",
            fix_instruction="Only provide exact dosages from the source document"
        ),
    ],
    "legal": [
        DomainRule(
            name="exact_quotes",
            check=r"(paraphrasing|in other words|essentially means)",
            violation_message="Legal clauses should be quoted exactly",
            fix_instruction="Quote the exact legal text, do not paraphrase"
        ),
    ],
}


def check_domain_rules(answer: str, doc_type: DocumentType) -> List[DomainRule]:
    """
    Check if answer violates any domain rules.
    Returns list of violated rules.
    """
    violations = []
    
    # Map document types to rule sets
    doc_to_domain = {
        DocumentType.EXAM: "data_structures",  # Most exam papers are DS/Algo
        DocumentType.RESEARCH: "research",
        DocumentType.MEDICAL: "medical",
        DocumentType.LEGAL: "legal",
    }
    
    domain = doc_to_domain.get(doc_type)
    if not domain:
        return violations
    
    rules = DOMAIN_RULES.get(domain, [])
    answer_lower = answer.lower()
    
    for rule in rules:
        if re.search(rule.check, answer_lower, re.IGNORECASE):
            violations.append(rule)
    
    return violations


# ============================================================================
# LAYER 4: CONTEXT QUALITY CHECK
# ============================================================================

@dataclass
class ContextQuality:
    """Assessment of context quality."""
    is_sufficient: bool
    relevance_score: float  # 0-1
    has_page_numbers: bool
    has_sections: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


def assess_context_quality(
    query: str,
    chunks: List[Dict],
    min_chunks: int = 1,
    min_relevance: float = 0.3
) -> ContextQuality:
    """
    Assess if retrieved context is sufficient for answering.
    """
    issues = []
    suggestions = []
    
    if not chunks:
        return ContextQuality(
            is_sufficient=False,
            relevance_score=0.0,
            has_page_numbers=False,
            has_sections=False,
            issues=["No context retrieved"],
            suggestions=["Try broader search terms"]
        )
    
    # Check chunk count
    if len(chunks) < min_chunks:
        issues.append(f"Only {len(chunks)} chunks retrieved (need {min_chunks})")
        suggestions.append("Consider retrieving more chunks")
    
    # Check for page numbers
    has_pages = any(
        chunk.get("metadata", {}).get("page") or 
        chunk.get("metadata", {}).get("page_start")
        for chunk in chunks
    )
    if not has_pages:
        issues.append("No page numbers in metadata")
    
    # Check for sections
    has_sections = any(
        chunk.get("metadata", {}).get("section")
        for chunk in chunks
    )
    
    # Calculate average relevance (if scores available)
    scores = [chunk.get("score", 0.5) for chunk in chunks]
    avg_relevance = sum(scores) / len(scores) if scores else 0.5
    
    if avg_relevance < min_relevance:
        issues.append(f"Low relevance score: {avg_relevance:.2f}")
        suggestions.append("Query may need reformulation")
    
    # Determine sufficiency
    is_sufficient = len(chunks) >= min_chunks and avg_relevance >= min_relevance
    
    return ContextQuality(
        is_sufficient=is_sufficient,
        relevance_score=avg_relevance,
        has_page_numbers=has_pages,
        has_sections=has_sections,
        issues=issues,
        suggestions=suggestions
    )


# ============================================================================
# LAYER 5: ANSWER SELF-VALIDATION
# ============================================================================

@dataclass
class ValidationResult:
    """Result of answer self-validation."""
    is_valid: bool
    confidence: float  # 0-1
    issues: List[str] = field(default_factory=list)
    should_regenerate: bool = False


def validate_answer(
    answer: str,
    query: str,
    doc_type: DocumentType,
    intent: UserIntent,
    context_text: str
) -> ValidationResult:
    """
    Validate generated answer for correctness.
    """
    issues = []
    confidence = 1.0
    
    answer_lower = answer.lower()
    
    # Check 1: Domain rule violations
    violations = check_domain_rules(answer, doc_type)
    if violations:
        for v in violations:
            issues.append(f"Domain violation: {v.violation_message}")
            confidence -= 0.3
    
    # Check 2: Defensive language when context exists
    defensive_patterns = [
        r"(not mentioned|not stated|not provided|not found) in (the |this )?(context|document)",
        r"(cannot|can't|unable to) (find|locate|determine)",
        r"(no information|no data) (about|on|regarding)",
    ]
    
    for pattern in defensive_patterns:
        if re.search(pattern, answer_lower) and len(context_text) > 100:
            issues.append("Defensive response despite having context")
            confidence -= 0.2
    
    # Check 3: For exam answers - should be direct
    if doc_type == DocumentType.EXAM and intent == UserIntent.ANSWER_QUESTION:
        vague_patterns = [r"^(it depends|this varies|generally speaking)"]
        if any(re.search(p, answer_lower) for p in vague_patterns):
            issues.append("Vague answer for exam question")
            confidence -= 0.2
    
    # Check 4: Answer too short for summarize intent
    if intent == UserIntent.SUMMARIZE and len(answer) < 200:
        issues.append("Summary too short")
        confidence -= 0.1
    
    # Check 5: No code for code request
    if intent == UserIntent.WRITE_CODE and "```" not in answer:
        issues.append("No code block for code request")
        confidence -= 0.3
    
    # Determine validity
    is_valid = confidence >= 0.5 and len(violations) == 0
    should_regenerate = not is_valid
    
    return ValidationResult(
        is_valid=is_valid,
        confidence=max(0, confidence),
        issues=issues,
        should_regenerate=should_regenerate
    )


# ============================================================================
# LAYER 6: ANSWER STYLE ADAPTER
# ============================================================================

STYLE_GUIDES = {
    DocumentType.EXAM: """
Format your answer like an exam solution:
- Be concise and to-the-point
- Use textbook definitions
- Show step-by-step working for calculations
- No unnecessary elaboration
""",
    DocumentType.RESEARCH: """
Format as academic response:
- Formal and precise language
- Cite specific sections/pages
- Include metrics when available
- Structure: Problem → Method → Result
""",
    DocumentType.LECTURE: """
Format as study notes:
- Clear concept explanations
- Include examples where helpful
- Use bullet points for key ideas
- Simple language
""",
    DocumentType.LEGAL: """
Format for legal context:
- Quote exact clauses
- No paraphrasing of legal terms
- Cite section/article numbers
- Use cautious language
""",
    DocumentType.MEDICAL: """
Format for medical context:
- Never guess dosages or treatments
- Always cite the source
- Use cautious language ("according to document")
- Recommend consulting professionals
""",
    DocumentType.TECH_DOC: """
Format for technical documentation:
- Include code examples if relevant
- Use precise technical terms
- Structure: What → How → Example
- Include parameter details
""",
    DocumentType.GENERAL: """
Format clearly:
- Direct and helpful
- Use simple language
- Cite sources when possible
""",
}


def get_style_guide(doc_type: DocumentType) -> str:
    """Get style guide for document type."""
    return STYLE_GUIDES.get(doc_type, STYLE_GUIDES[DocumentType.GENERAL])


# ============================================================================
# LAYER 7: FAILURE LOGGING
# ============================================================================

@dataclass
class FailureLog:
    """Log entry for RAG failures."""
    timestamp: str
    domain: str
    document_type: str
    intent: str
    query: str
    failure_type: str
    violation: str
    suggested_fix: str


# In-memory failure log (in production, use database)
_failure_logs: List[FailureLog] = []


def log_failure(
    doc_type: DocumentType,
    intent: UserIntent,
    query: str,
    failure_type: str,
    violation: str,
    suggested_fix: str
):
    """Log a RAG failure for improvement."""
    log_entry = FailureLog(
        timestamp=datetime.now().isoformat(),
        domain=doc_type.value,
        document_type=doc_type.value,
        intent=intent.value,
        query=query[:100],  # Truncate
        failure_type=failure_type,
        violation=violation,
        suggested_fix=suggested_fix
    )
    _failure_logs.append(log_entry)
    logger.warning(f"RAG Failure: {failure_type} - {violation}")


def get_failure_logs() -> List[Dict]:
    """Get all failure logs."""
    return [
        {
            "timestamp": f.timestamp,
            "domain": f.domain,
            "failure_type": f.failure_type,
            "violation": f.violation,
            "fix": f.suggested_fix
        }
        for f in _failure_logs
    ]


# ============================================================================
# MAIN PIPELINE ORCHESTRATOR
# ============================================================================

@dataclass
class PipelineResult:
    """Complete result from RAG pipeline."""
    document_type: DocumentType
    intent: UserIntent
    context_quality: ContextQuality
    validation: ValidationResult
    style_guide: str
    system_prompt: str
    should_proceed: bool
    issues: List[str] = field(default_factory=list)


def run_pipeline(
    query: str,
    filename: str,
    chunks: List[Dict]
) -> PipelineResult:
    """
    Run the complete 7-layer RAG pipeline.
    
    Returns PipelineResult with all analysis and the appropriate system prompt.
    """
    # Combine chunk content for analysis
    context_text = "\n".join(c.get("content", "") for c in chunks)
    
    # Layer 1: Document Type Detection
    doc_type = detect_document_type(filename, context_text)
    logger.info(f"[Layer 1] Document Type: {doc_type.value}")
    
    # Layer 2: Intent Routing
    intent = detect_intent(query)
    logger.info(f"[Layer 2] Intent: {intent.value}")
    
    # Layer 3-4: Get style guide (domain rules checked post-generation)
    style_guide = get_style_guide(doc_type)
    
    # Layer 4: Context Quality Check
    ctx_quality = assess_context_quality(query, chunks)
    logger.info(f"[Layer 4] Context Quality: sufficient={ctx_quality.is_sufficient}, relevance={ctx_quality.relevance_score:.2f}")
    
    # Build system prompt
    base_prompt = f"""You are a helpful assistant answering questions about {doc_type.value} documents.
Document Type Detected: {doc_type.value.upper()}
User Intent: {intent.value}

{style_guide}

RULES:
1. Answer based ONLY on the provided context
2. Be direct - start with the answer
3. Cite page numbers when available
4. Match the document's style and expectations
"""
    
    # Determine if we should proceed
    issues = []
    should_proceed = True
    
    if not ctx_quality.is_sufficient:
        issues.extend(ctx_quality.issues)
        # Still proceed but with warning
    
    return PipelineResult(
        document_type=doc_type,
        intent=intent,
        context_quality=ctx_quality,
        validation=ValidationResult(is_valid=True, confidence=1.0),  # Placeholder
        style_guide=style_guide,
        system_prompt=base_prompt,
        should_proceed=should_proceed,
        issues=issues
    )


def post_validate(
    answer: str,
    query: str,
    pipeline_result: PipelineResult,
    context_text: str
) -> Tuple[bool, List[str]]:
    """
    Post-generation validation (Layer 5).
    Returns (is_valid, issues).
    """
    validation = validate_answer(
        answer=answer,
        query=query,
        doc_type=pipeline_result.document_type,
        intent=pipeline_result.intent,
        context_text=context_text
    )
    
    # Log failures
    if not validation.is_valid:
        for issue in validation.issues:
            log_failure(
                doc_type=pipeline_result.document_type,
                intent=pipeline_result.intent,
                query=query,
                failure_type="validation_failed",
                violation=issue,
                suggested_fix="Regenerate with stricter constraints"
            )
    
    return validation.is_valid, validation.issues
