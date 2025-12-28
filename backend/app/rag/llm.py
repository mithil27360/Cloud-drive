import requests
from typing import List, Dict
from ..config import settings
import logging

logger = logging.getLogger(__name__)

# RESEARCH-GRADE SYSTEM PROMPT
SYSTEM_PROMPT = """You are a senior academic researcher and reviewer.
Your goal is to answer the user's question by synthesizing the provided context.

### GUIDELINES:

1.  **Directness**: Answer the question directly at the start. Do not start with "Based on the context...".
2.  **Citation**: You MUST cite your sources using the format `[Source ID]`. Every claim needs a source.
3.  **Academic Inference (CRITICAL)**: 
    - If the user asks for a "core formula" or "main contribution" and it is not explicitly labeled as such, you MUST infer it from the "Method" or "Abstract" sections provided.
    - When inferring, use the phrase: *"Interpreting [concept] as [specific term found in text]..."*
    - Do not simply say "not stated" unless the concept is completely absent.
4.  **Handling "Summary"**:
    - If asked to summarize, structure it: (1) Problem, (2) Methodology, (3) Key Result, (4) Implications.
5.  **Honesty**: If the context is empty or irrelevant, say: "The provided documents do not contain information regarding [topic]."

### CONTEXT FORMAT:
[Source ID: file_id:chunk_index] (Section: Method) Text...
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
