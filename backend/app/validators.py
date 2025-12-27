import re
import html
from typing import Optional
from pydantic import validator
from fastapi import HTTPException

# Password requirements
PASSWORD_MIN_LENGTH = 6

def validate_password_strength(password: str) -> str:
    """Validate password meets security requirements"""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    return password

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and injection"""
    # Remove any path components
    filename = filename.replace('/', '').replace('\\', '')
    # Remove null bytes
    filename = filename.replace('\x00', '')
    # Only allow alphanumeric, dots, dashes, underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # Prevent hidden files
    if filename.startswith('.'):
        filename = '_' + filename[1:]
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    return filename

def sanitize_query(query: str, max_length: int = 1000) -> str:
    """Sanitize user query input"""
    # Trim whitespace
    query = query.strip()
    # Limit length
    if len(query) > max_length:
        query = query[:max_length]
    # Escape HTML entities
    query = html.escape(query)
    return query

def validate_email_domain(email: str, blocked_domains: list = None) -> str:
    """Validate email domain is not in blocklist"""
    blocked = blocked_domains or ['tempmail.com', 'throwaway.com', 'guerrillamail.com']
    domain = email.split('@')[-1].lower()
    if domain in blocked:
        raise ValueError("Disposable email addresses are not allowed")
    return email

# SQL injection prevention patterns
SQL_INJECTION_PATTERNS = [
    r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
    r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
    r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
    r"((\%27)|(\'))union",
]

def check_sql_injection(value: str) -> bool:
    """Check for SQL injection patterns"""
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False

def validate_input(value: str, field_name: str = "input") -> str:
    """Validate input for common attacks"""
    if check_sql_injection(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: potentially malicious content detected")
    return value
