import requests
from typing import List, Dict
from ..config import settings
import logging

logger = logging.getLogger(__name__)

# Production-grade system prompt with STRICT citation binding
SYSTEM_PROMPT = """You are a precision-focused Research Assistant for academic papers. 
Your goal is to answer the user's question using ONLY the provided context.

CRITICAL RULES:
1.  **Citation is Mandatory**: Every single claim, fact, or number MUST be followed by its exact Source ID in the format `[file_id:chunk_index]`.
    - Correct: "The method achieves 95% accuracy [102:4]."
    - Incorrect: "The method achieves 95% accuracy."
2.  **No Hallucination**: If the answer is not in the context, state "This is not stated in the provided documents."
3.  **No Outside Knowledge**: Do not use external knowledge. Rely ONLY on the context.
4.  **Academic Tone**: Use professional, objective language.
5.  **Uncertainty**: If the context is ambiguous, state "The text suggests X but does not explicitly confirm it [102:5]."

Context format:
[Source ID: file_id:chunk_index] (Section: X, Page: Y) Content
...

Answer the question now."""

def _format_context(chunks: List[Dict]) -> str:
    """Format chunks into well-structured context with atomic IDs."""
    if not chunks:
        return "No relevant context found."
    
    context_parts = []
    for idx, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        content = chunk.get("content", "")
        
        # Construct Stable Source ID
        fid = metadata.get("file_id", "0")
        cid = metadata.get("sub_chunk_index", metadata.get("chunk_index", idx))
        source_id = f"{fid}:{cid}"
        
        # Meta info for context (helps LLM understand flow)
        section = metadata.get("section", "General")
        page = metadata.get("page", metadata.get("page_number", "?"))
        
        # Explicit format for LLM to adhere to
        header = f"[Source ID: {source_id}] (Section: {section}, Page: {page})"
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
