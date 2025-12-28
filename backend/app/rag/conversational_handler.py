"""
Conversational Query Handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Detects and handles greetings, small talk, and system queries
WITHOUT triggering document retrieval.

Handles:
- Greetings: hi, hello, hey
- Farewells: bye, goodbye
- Gratitude: thank you, thanks
- System queries: what can you do, help, capabilities

Total: 150 lines
"""

import re
from typing import Optional, Tuple

class ConversationalHandler:
    """
    Detects conversational queries and provides direct responses.
    Prevents unnecessary document retrieval for small talk.
    """
    
    # Greeting patterns
    GREETINGS = [
        r'^\s*(hi|hello|hey|greetings|good morning|good afternoon|good evening)\s*[!.?]*\s*$',
    ]
    
    # Farewell patterns
    FAREWELLS = [
        r'^\s*(bye|goodbye|see you|farewell|take care)\s*[!.?]*\s*$',
    ]
    
    # Gratitude patterns
    GRATITUDE = [
        r'^\s*(thank you|thanks|thx|appreciate it)\s*[!.?]*\s*$',
        r'thanks\s+(a lot|so much|very much)',
    ]
    
    # Help/capability patterns
    HELP_QUERIES = [
        r'^\s*what can you (do|help)\s*[?]*\s*$',
        r'^\s*help\s*[!.?]*\s*$',
        r'^\s*how (do|does) (this|it) work\s*[?]*\s*$',
        r'^\s*what (is|are) your (capabilities|features)\s*[?]*\s*$',
        r'^\s*show me what you can do\s*[?]*\s*$',
    ]
    
    # Small talk patterns
    SMALL_TALK = [
        r'^\s*how are you\s*[?]*\s*$',
        r'^\s*what\'s up\s*[?]*\s*$',
        r'^\s*how\'s it going\s*[?]*\s*$',
    ]
    
    @classmethod
    def is_conversational(cls, query: str) -> bool:
        """Check if query is conversational (not document-related)"""
        query_lower = query.lower().strip()
        
        all_patterns = (
            cls.GREETINGS + 
            cls.FAREWELLS + 
            cls.GRATITUDE + 
            cls.HELP_QUERIES + 
            cls.SMALL_TALK
        )
        
        for pattern in all_patterns:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return True
        
        return False
    
    @classmethod
    def get_response(cls, query: str) -> Optional[str]:
        """
        Get direct response for conversational query.
        Returns None if not conversational.
        """
        query_lower = query.lower().strip()
        
        # Check greetings
        for pattern in cls.GREETINGS:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return cls._greeting_response()
        
        # Check farewells
        for pattern in cls.FAREWELLS:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return cls._farewell_response()
        
        # Check gratitude
        for pattern in cls.GRATITUDE:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return cls._gratitude_response()
        
        # Check help queries
        for pattern in cls.HELP_QUERIES:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return cls._help_response()
        
        # Check small talk
        for pattern in cls.SMALL_TALK:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return cls._small_talk_response()
        
        return None
    
    @staticmethod
    def _greeting_response() -> str:
        return "Hello! I'm your AI research assistant. I can help you search and analyze your documents. What would you like to know?"
    
    @staticmethod
    def _farewell_response() -> str:
        return "Goodbye! Feel free to come back anytime you need help with your documents."
    
    @staticmethod
    def _gratitude_response() -> str:
        return "You're welcome! Let me know if you need anything else."
    
    @staticmethod
    def _help_response() -> str:
        return """I can help you with your documents in several ways:

📄 **Document Search**: Ask questions about your uploaded files
📊 **Summaries**: "Summarize my files" or "Summarize [filename]"
🔍 **Specific Information**: "What is the formula in...", "Explain the methodology in..."
📈 **Comparisons**: "Compare approach A vs B"
⚡ **Direct Answers**: I cite page numbers so you can verify sources

**Examples:**
- "What is the main contribution of the Transformer paper?"
- "Summarize lecture 5"
- "Explain Booth's algorithm"
- "What formulas are in my documents?"

Just type your question naturally, and I'll search your documents!"""
    
    @staticmethod
    def _small_talk_response() -> str:
        return "I'm doing well, thank you! I'm here to help you with your documents. What can I assist you with today?"


# Singleton instance
conversational_handler = ConversationalHandler()
