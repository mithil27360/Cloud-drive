"""
Google OAuth Authentication Routes

Provides endpoints for Google Sign-In authentication.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from authlib.jose import jwt
from datetime import datetime, timedelta
import httpx

from .. import database, models, auth
from ..config import settings

router = APIRouter(prefix="/auth/google", tags=["google-auth"])

# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)


class GoogleAuthRequest(BaseModel):
    """Request model for Google credential verification."""
    credential: str  # Google JWT token


@router.get("/login")
async def google_login():
    """
    Initiate Google OAuth flow.
    Redirects user to Google sign-in page.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(redirect_uri)


@router.get("/callback")
async def google_callback(code: str, db: Session = Depends(database.get_db)):
    """
    Handle OAuth callback from Google.
    Exchanges code for user info and creates/updates user.
    """
    try:
        # Exchange code for token
        token = await oauth.google.authorize_access_token(code=code)
        
        # Get user info from Google
        user_info = token.get('userinfo')
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")
        
        # Extract user data
        google_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')
        
        if not google_id or not email:
            raise HTTPException(status_code=400, detail="Invalid user data from Google")
        
        # Find or create user
        user = db.query(models.User).filter(models.User.google_id == google_id).first()
        
        if not user:
            # Check if user exists with this email (from old auth)
            user = db.query(models.User).filter(models.User.email == email).first()
            if user:
                # Link Google account to existing user
                user.google_id = google_id
                user.is_verified = True
            else:
                # Create new user
                user = models.User(
                    email=email,
                    google_id=google_id,
                    name=name,
                    is_verified=True,  # Auto-verified via Google
                    is_active=True
                )
                db.add(user)
        
        # Update user info
        if name and not user.name:
            user.name = name
        user.last_login = datetime.utcnow()
        
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
            url=f"http://localhost:3000?token={access_token}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")


@router.post("/verify")
async def verify_google_token(
    request: GoogleAuthRequest,
    db: Session = Depends(database.get_db)
):
    """
    Verify Google JWT token (for frontend direct integration).
    This is used when using Google Sign-In JavaScript library.
    """
    try:
        # Verify the Google JWT token
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={request.credential}"
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google token")
            
            user_info = response.json()
            
            # Verify token is for our app
            if user_info.get('aud') != settings.GOOGLE_CLIENT_ID:
                raise HTTPException(status_code=401, detail="Token not for this application")
            
            # Extract user data
            google_id = user_info.get('sub')
            email = user_info.get('email')
            name = user_info.get('name')
            picture = user_info.get('picture')
            email_verified = user_info.get('email_verified', False)
            
            if not google_id or not email:
                raise HTTPException(status_code=400, detail="Invalid user data")
            
            # Find or create user
            user = db.query(models.User).filter(models.User.google_id == google_id).first()
            
            if not user:
                # Check if email exists
                user = db.query(models.User).filter(models.User.email == email).first()
                if user:
                    # Link Google account
                    user.google_id = google_id
                    user.is_verified = True
                else:
                    # Create new user
                    user = models.User(
                        email=email,
                        google_id=google_id,
                        name=name,
                        is_verified=True,
                        is_active=True
                    )
                    db.add(user)
            
            # Update info
            if name and not user.name:
                user.name = name
            user.last_login = datetime.utcnow()
            
            db.commit()
            db.refresh(user)
            
            # Create our access token
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = auth.create_access_token(
                data={"sub": user.email},
                expires_delta=access_token_expires
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "email": user.email,
                    "name": user.name
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {str(e)}")
