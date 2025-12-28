"""
Simple Document Type Detection & Intent Routing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Lightweight detection without overengineering.

Document Types: EXAM_PAPER, LECTURE_NOTES, RESEARCH_PAPER, GENERAL
Intent Types: EXPLAIN, SUMMARIZE, ANSWER_QUESTION, GENERAL

~150 lines, focused and simple.
"""

import re
from enum import Enum
from typing import Tuple

class DocumentType(Enum):
    EXAM_PAPER = "exam_paper"
    LECTURE_NOTES = "lecture_notes"  
    RESEARCH_PAPER = "research_paper"
    GENERAL = "general"

class QueryIntent(Enum):
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    ANSWER_QUESTION = "answer_question"
    GENERAL = "general"


# ============== DOCUMENT TYPE DETECTION ==============

EXAM_PATTERNS = [
    r'\b(question|q\.?\s*\d+|answer|marks?|score|exam|test|quiz)\b',
    r'\b(solve|find|calculate|determine|prove|show that|write a function)\b',
    r'\b(PYQ|previous year|mid.?term|end.?term|makeup|semester)\b',
    r'\[\d+\s*marks?\]',
    r'\(\d+\s*marks?\)',
]

RESEARCH_PATTERNS = [
    r'\b(abstract|introduction|methodology|conclusion|references|doi)\b',
    r'\b(we propose|this paper|our approach|state.?of.?the.?art|related work)\b',
    r'\b(BLEU|F1.?score|accuracy|precision|recall|baseline)\b',
    r'\b(et al\.?|arXiv|IEEE|ACM|Springer)\b',
]

LECTURE_PATTERNS = [
    r'\b(lecture|slide|chapter|topic|learning objectives)\b',
    r'\b(example|definition|theorem|lemma|proof)\b',
    r'^\s*•\s*',  # Bullet points
    r'^\s*\d+\.\s+\w+',  # Numbered lists
]


def detect_document_type(text: str) -> DocumentType:
    """
    Detect document type from content.
    Simple pattern matching - no heavy ML.
    """
    text_lower = text.lower()
    
    # Count pattern matches
    exam_score = sum(1 for p in EXAM_PATTERNS if re.search(p, text_lower, re.IGNORECASE | re.MULTILINE))
    research_score = sum(1 for p in RESEARCH_PATTERNS if re.search(p, text_lower, re.IGNORECASE))
    lecture_score = sum(1 for p in LECTURE_PATTERNS if re.search(p, text_lower, re.IGNORECASE | re.MULTILINE))
    
    # Determine type by highest score
    scores = {
        DocumentType.EXAM_PAPER: exam_score,
        DocumentType.RESEARCH_PAPER: research_score,
        DocumentType.LECTURE_NOTES: lecture_score,
    }
    
    max_type = max(scores, key=scores.get)
    max_score = scores[max_type]
    
    # Require minimum confidence
    if max_score >= 2:
        return max_type
    return DocumentType.GENERAL


# ============== INTENT DETECTION ==============

EXPLAIN_PATTERNS = [
    r'^(explain|describe|what is|what are|define|clarify|elaborate)',
    r'(how does|how do|why does|why do)',
    r'(tell me about|help me understand)',
]

SUMMARIZE_PATTERNS = [
    r'^(summarize|summary|summarise|give me a summary)',
    r'(overview|brief|key points|main points|tldr|tl;dr)',
    r'(what does this (document|file|paper) (say|contain|cover))',
]

ANSWER_PATTERNS = [
    r'^(solve|calculate|find|compute|determine)',
    r'^(what|which|where|when|who|how many|how much)',
    r'(answer|solution)',
    r'\?$',
]


def detect_intent(query: str) -> QueryIntent:
    """
    Detect user intent from query.
    Simple pattern matching.
    """
    query_lower = query.lower().strip()
    
    # Check explain intent
    if any(re.search(p, query_lower) for p in EXPLAIN_PATTERNS):
        return QueryIntent.EXPLAIN
    
    # Check summarize intent
    if any(re.search(p, query_lower) for p in SUMMARIZE_PATTERNS):
        return QueryIntent.SUMMARIZE
    
    # Check answer/solve intent
    if any(re.search(p, query_lower) for p in ANSWER_PATTERNS):
        return QueryIntent.ANSWER_QUESTION
    
    return QueryIntent.GENERAL


# ============== PROMPT SELECTION ==============

PROMPTS = {
    (DocumentType.EXAM_PAPER, QueryIntent.SUMMARIZE): """
You are helping a student with their exam preparation.
The document contains exam questions/PYQs.

List the questions clearly with their answers or solutions.
Format like exam solutions - direct and clear.
Do NOT use research paper formatting.
""",

    (DocumentType.EXAM_PAPER, QueryIntent.ANSWER_QUESTION): """
You are helping a student solve an exam question.
Answer like an exam solution - step by step, clear, and concise.
Show your working where applicable.
""",

    (DocumentType.RESEARCH_PAPER, QueryIntent.SUMMARIZE): """
Summarize this research paper with:
- Problem addressed
- Method/Approach
- Key results with metrics
- Implications
""",

    (DocumentType.LECTURE_NOTES, QueryIntent.SUMMARIZE): """
Summarize these lecture notes with:
- Main topic
- Key concepts
- Important examples
- Takeaways
""",

    (DocumentType.LECTURE_NOTES, QueryIntent.EXPLAIN): """
Explain this concept from the lecture notes clearly.
Use simple language and examples where helpful.
""",
}

DEFAULT_PROMPT = """
You are a helpful study assistant.
Answer the question using the provided context.
Be direct and clear. Cite page numbers when available.
"""


def get_prompt_for_context(doc_type: DocumentType, intent: QueryIntent) -> str:
    """Get appropriate prompt based on document type and intent."""
    key = (doc_type, intent)
    return PROMPTS.get(key, DEFAULT_PROMPT)


def analyze_query(query: str, context_text: str) -> Tuple[DocumentType, QueryIntent, str]:
    """
    Main function: Analyze query and context, return appropriate prompt.
    
    Returns: (document_type, intent, system_prompt)
    """
    doc_type = detect_document_type(context_text)
    intent = detect_intent(query)
    prompt = get_prompt_for_context(doc_type, intent)
    
    return doc_type, intent, prompt
