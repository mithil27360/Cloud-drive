import requests
from typing import List, Dict
from ..config import settings
import logging

logger = logging.getLogger(__name__)

# Production-grade system prompt
SYSTEM_PROMPT = """You are an expert AI research assistant helping users understand and analyze their documents.

Your responsibilities:
1. Provide accurate, comprehensive answers based ONLY on the provided context
2. Cite specific sections when making claims
3. If the context doesn't contain enough information, clearly state this
4. Use clear, professional language
5. Organize complex information into structured responses

Guidelines:
- Be precise and factual
- Use bullet points for clarity when appropriate
- Quote relevant passages when helpful
- Acknowledge limitations in the available information
- If asked tocompare or analyze, provide balanced insights
"""

def _format_context(chunks: List[Dict]) -> str:
    """Format chunks into well-structured context."""
    if not chunks:
        return "No relevant context found."
    
    context_parts = []
    for idx, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        content = chunk.get("content", "")
        
        # Add metadata if available
        meta_info = []
        if "section_heading" in metadata:
            meta_info.append(f"Section: {metadata['section_heading']}")
        if "position" in metadata:
            meta_info.append(f"Position: {metadata['position']}")
        
        meta_str = f" ({', '.join(meta_info)})" if meta_info else ""
        
        context_parts.append(f"[Source {idx}{meta_str}]\n{content}\n")
    
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

Please provide a comprehensive answer based on the context above. If the context contains relevant information, explain it clearly and cite specific sources. If the information is incomplete or missing, state this explicitly."""
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
