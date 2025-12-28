import requests
from typing import List, Dict
from ..config import settings
import logging

logger = logging.getLogger(__name__)

# RESEARCH-GRADE SYSTEM PROMPT (ASSERTIVE MODE)
SYSTEM_PROMPT = """You are a research assistant for a PhD student or senior engineer. Your role is to provide direct, specific, and actionable answers.

### CRITICAL RULES:

1.  **Zero Evasion**: Never say "not explicitly stated" or "not mentioned" if the information IS in the context. You must extract it.
2.  **Directness**: Start with the answer immediately. No preambles like "Based on the context..." or "The paper discusses...".
3.  **Specificity**: Include numbers, metrics, BLEU scores, dataset names, and concrete details whenever present.
4.  **Citation**: Every factual claim MUST be followed by `[Source ID]` in the format `[file_id:chunk_index]`.
5.  **Smart Inference (Use Sparingly)**:
    - Use "Interpreting [vague term] as [specific concept]..." ONLY when the query is genuinely ambiguous (e.g., "formula core" → "Scaled Dot-Product Attention").
    - DO NOT use it for clear questions. If the user asks "what is the problem", and the Introduction states the problem, just answer it directly.
6.  **Summarization Structure**:
    - Problem: State the specific challenge addressed.
    - Method: Describe the approach (architecture, key components).
    - Key Result: Report exact metrics (e.g., "BLEU 28.4 on WMT 2014 EN-DE").
    - Implications: Explain why this matters (scalability, foundation for future work, etc.).
7.  **Formulas**: When asked for formulas, provide the LaTeX or plain-text representation clearly. Do NOT confuse conceptual descriptions with mathematical formulas.

### TONE:
Write like a research TA grading a paper: confident, precise, and intolerant of vagueness.

### CONTEXT FORMAT:
[Source ID: file_id:chunk_index] (Section: Method) Content...
"""

def _format_context(chunks: List[Dict]) -> str:
    """Format chunks into well-structured context with atomic IDs and sections."""
    if not chunks:
        return "No relevant context found."
    
    context_parts = []
    for idx, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        content = chunk.get("content", "")
        
        # Use existing stable ID logic
        fid = metadata.get("file_id", "0")
        cid = metadata.get("sub_chunk_index", metadata.get("chunk_index", idx))
        source_id = f"{fid}:{cid}"
        
        # Add SECTION info to context so LLM knows where it came from
        section = metadata.get("section", "General") 
        
        header = f"[Source ID: {source_id}] (Section: {section})"
        context_parts.append(f"{header}\n{content}\n")
    
    return "\n---\n".join(context_parts)

def generate_response(query: str, context_chunks: List[Dict]) -> str:
    """
    Generate high-quality response using Groq API.
    
    Uses production-grade prompt engineering for better answers.
    """
    # Format context with structure
    context = _format_context(context_chunks)
    
    # Limit context size
    MAX_CONTEXT_LENGTH = 8000
    if len(context) > MAX_CONTEXT_LENGTH:
        context = context[:MAX_CONTEXT_LENGTH] + "\n\n[Context truncated due to length...]"
    
    # Build messages with production prompt
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": f"""Context from documents:
{context}

Question: {query}

Please provide a comprehensive answer based on the context above. If the context contains relevant information, explain it clearly and cite specific sources using only the [Source ID] format."""
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
            return result["choices"][0]["message"]["content"]
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
