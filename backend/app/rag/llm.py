import requests
from typing import List, Dict
from ..config import settings
import logging

logger = logging.getLogger(__name__)

# NEUTRAL SYSTEM PROMPT - NO FORCED FORMATTING
SYSTEM_PROMPT = """You are a helpful study assistant. Answer questions using the provided context.

### RULES:

1. **Answer naturally**: Respond in the most appropriate format for the question and content.
2. **Be direct**: Start with the answer, not preambles.
3. **Cite sources**: When referencing specific information, mention the page if available.
4. **No invention**: Only use information from the provided context.
5. **Match the content**: 
   - For exam questions/PYQs: List the questions and answers directly
   - For lecture notes: Explain the concepts clearly
   - For any document: Summarize the key points naturally

### CONTEXT FORMAT:
[Source: Section, p. X]
Content here...

### DO NOT:
- Force a "Problem/Method/Results" structure on non-research documents
- Treat exam papers or PYQs as research papers
- Add unnecessary academic formatting

Just answer naturally and helpfully.
"""

def _format_context(chunks: List[Dict]) -> str:
    """Format chunks with page metadata for LLM to cite."""
    if not chunks:
        return "No relevant context found."
    
    context_parts = []
    for idx, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        content = chunk.get("content", "")
        
        # Extract page information from metadata
        page_start = metadata.get("page_start", metadata.get("page", 1))
        page_end = metadata.get("page_end", page_start)
        section = metadata.get("section", "General")
        
        # Format page range
        if page_start == page_end:
            page_info = f"p. {page_start}"
        else:
            page_info = f"pp. {page_start}-{page_end}"
        
        # Build header with page info
        header = f"[Source: {section}, {page_info}]"
        context_parts.append(f"{header}\n{content}\n")
    
    return "\n---\n".join(context_parts)

def generate_response(query: str, context_chunks: List[Dict], filename: str = "document.pdf") -> str:
    """
    Generate high-quality response using Groq API.
    
    Uses 7-layer production pipeline:
    1. Document Type Detection
    2. Intent Routing
    3. Domain Rules
    4. Context Quality Check
    5. Answer Self-Validation
    6. Style Adapter
    7. Failure Logging
    """
    from .production_pipeline import run_pipeline, post_validate, log_failure
    
    # Format context with structure
    context = _format_context(context_chunks)
    
    # Limit context size
    MAX_CONTEXT_LENGTH = 8000
    if len(context) > MAX_CONTEXT_LENGTH:
        context = context[:MAX_CONTEXT_LENGTH] + "\n\n[Context truncated due to length...]"
    
    # Run 7-layer pipeline (Layers 1-4, 6)
    pipeline_result = run_pipeline(query, filename, context_chunks)
    logger.info(f"Pipeline: doc={pipeline_result.document_type.value}, intent={pipeline_result.intent.value}")
    
    if pipeline_result.issues:
        logger.warning(f"Pipeline issues: {pipeline_result.issues}")
    
    # Build messages with pipeline-generated prompt
    messages = [
        {
            "role": "system",
            "content": pipeline_result.system_prompt
        },
        {
            "role": "user",
            "content": f"""Context from documents:
{context}

Question: {query}

Answer based on the context above. Be direct and match the document style."""
        }
    ]
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": messages,
                "temperature": 0.3,  # Lower for more focused answers
                "max_tokens": 1024,
                "top_p": 0.95
            },
            timeout=settings.GROQ_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            answer = result["choices"][0]["message"]["content"]
            
            # Layer 5: Post-validation
            is_valid, issues = post_validate(answer, query, pipeline_result, context)
            if not is_valid:
                logger.warning(f"Answer validation failed: {issues}")
                # Don't regenerate for now, just log
                # Future: could retry with stricter prompt
            
            return answer
        else:
            return "No response generated."
            
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.json()
            logger.error(f"Groq API error: {error_detail}")
        except:
            logger.error(f"Groq API error: {e.response.text}")
        
        if e.response.status_code == 400:
            return "Error: Invalid request to AI service. The context may be too complex. Try a simpler question."
        elif e.response.status_code == 401:
            return "Error: Invalid Groq API key."
        elif e.response.status_code == 429:
            return "Error: Groq API rate limit exceeded. Please try again later."
        else:
            return f"Error: Groq API returned {e.response.status_code}"
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to Groq API. Check your internet connection."
    except requests.exceptions.Timeout:
        return "Error: Groq API request timed out."
    except Exception as e:
        logger.error(f"Unexpected error in generate_response: {str(e)}")
        return f"Error generating response: {str(e)}"
