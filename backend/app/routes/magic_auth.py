"""
Magic Link (Passwordless) Authentication Routes

Provides endpoints for passwordless email-based authentication.
Users receive a secure login link via email.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import logging

from .. import database, models, auth
from ..config import settings
from ..email.service import email_service

router = APIRouter(prefix="/auth/magic-link", tags=["magic-link-auth"])
logger = logging.getLogger(__name__)


class MagicLinkRequest(BaseModel):
    """Request model for magic link generation."""
    email: EmailStr


@router.post("/request")
async def request_magic_link(
    request: MagicLinkRequest,
    db: Session = Depends(database.get_db)
):
    """
    Request a magic link for passwordless login.
    Creates account if doesn't exist.
    """
    email = request.email.lower()
    
    # Find or create user
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        # Create new user (passwordless)
        user = models.User(
            email=email,
            is_verified=True,  # Auto-verified via magic link
            is_active=True
        )
        db.add(user)
    
    # Generate secure token
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(minutes=15)
    
    # Store token
    user.magic_link_token = token
    user.magic_link_expires = expires
    
    db.commit()
    
    # Generate magic link URL
    # For development, use localhost; for production, use actual domain
    base_url = "http://localhost:3000"  # TODO: Make configurable
    magic_link = f"{base_url}/auth/magic-link/verify?token={token}"
    
    # Send email or log to console
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        # Send real email
        success = email_service.send_magic_link_email(email, magic_link)
        if not success:
            logger.error(f"Failed to send magic link to {email}")
            # Still return success but log link for development
            logger.info(f"Magic link for {email}: {magic_link}")
    else:
        # Development mode: log to console
        logger.info(f"\n{'='*60}")
        logger.info(f"MAGIC LINK for {email}:")
        logger.info(f"{magic_link}")
        logger.info(f"Expires: {expires}")
        logger.info(f"{'='*60}\n")
    
    return {
        "success": True,
        "message": "Magic link sent! Check your email.",
        "email": email,
        # Include link in response for development (remove in production)
        "magic_link": magic_link if not (settings.SMTP_USERNAME and settings.SMTP_PASSWORD) else None
    }


@router.get("/verify")
async def verify_magic_link(
    token: str,
    db: Session = Depends(database.get_db)
):
    """
    Verify magic link token and log user in.
    Single-use token that expires after 15 minutes.
    """
    # Find user with this token
    user = db.query(models.User).filter(
        models.User.magic_link_token == token
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired magic link"
        )
    
    # Check expiration
    if not user.magic_link_expires or user.magic_link_expires < datetime.utcnow():
        # Clear expired token
        user.magic_link_token = None
        user.magic_link_expires = None
        db.commit()
        
        raise HTTPException(
            status_code=400,
            detail="Magic link has expired. Please request a new one."
        )
    
    # Valid token - log user in
    # Clear token (single-use)
    user.magic_link_token = None
    user.magic_link_expires = None
    user.last_login = datetime.utcnow()
    user.is_verified = True
    
    db.commit()
    db.refresh(user)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    # Redirect to frontend with token
    return RedirectResponse(
        url=f"/?token={access_token}&email={user.email}"
    )
