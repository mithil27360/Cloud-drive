from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from .. import schemas, models, database, auth
from ..validators import validate_password_strength, validate_email_domain
from ..logging_config import logger
from pydantic import BaseModel

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # Validate password strength
    try:
        validate_password_strength(user.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Check for disposable emails
    try:
        validate_email_domain(user.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Check if email exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    
    # Create user with verification token if email verification is enabled
    from ..config import settings
    if settings.REQUIRE_EMAIL_VERIFICATION:
        import secrets
        verification_token = secrets.token_urlsafe(32)
        db_user = models.User(
            email=user.email,
            hashed_password=hashed_password,
            is_verified=False,
            verification_token=verification_token,
            verification_sent_at=datetime.utcnow()
        )
        
        # Send verification email
        from ..email.service import email_service
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            email_service.send_verification_email(user.email, verification_link)
            logger.info(f"Verification email sent to: {user.email}")
        else:
            logger.warning(f"Email not configured. Verification link: {verification_link}")
    else:
        # Auto-verify if email verification is disabled
        db_user = models.User(
            email=user.email,
            hashed_password=hashed_password,
            is_verified=True
        )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info(f"New user registered: {user.email}")
    return db_user

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated")
    
    # Check email verification if required
    from ..config import settings
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
        raise HTTPException(
            status_code=403, 
            detail="📧 Please verify your email first! Check your inbox for a verification link from Cloud Drive. Can't find it? Check spam folder or request a new link."
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    access_token_expires = timedelta(minutes=auth.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email, "user_id": user.id}, 
        expires_delta=access_token_expires
    )
    
    logger.info(f"User logged in: {user.email}")
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.User)
def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    """Get current user information"""
    return current_user

# Admin Auth
class AdminLogin(BaseModel):
    username: str
    password: str

@router.post("/admin/login")
def admin_login(creds: AdminLogin):
    if creds.username != auth.settings.ADMIN_USERNAME or creds.password != auth.settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create token with admin scope/flag (for now just a separate token key or subject prefix)
    access_token_expires = timedelta(minutes=auth.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": f"admin:{creds.username}", "role": "admin"}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Email Verification
@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(database.get_db)):
    """Verify user email with token."""
    user = db.query(models.User).filter(
        models.User.verification_token == token
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    # Check token expiration (24 hours)
    from ..config import settings
    if user.verification_sent_at:
        expiry_hours = settings.VERIFICATION_TOKEN_EXPIRE_HOURS
        token_age = datetime.utcnow() - user.verification_sent_at
        if token_age.total_seconds() > expiry_hours * 3600:
            raise HTTPException(status_code=400, detail="Verification token expired")
    
    # Verify user
    user.is_verified = True
    user.verification_token = None
    user.verification_sent_at = None
    db.commit()
    
    logger.info(f"User verified: {user.email}")

    # Auto-login: Generate access token
    access_token_expires = timedelta(minutes=auth.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email, "user_id": user.id}, 
        expires_delta=access_token_expires
    )
    
    return {
        "message": "Email verified successfully!",
        "access_token": access_token, 
        "token_type": "bearer"
    }

@router.post("/resend-verification")
def resend_verification(email: str, db: Session = Depends(database.get_db)):
    """Resend verification email."""
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    # Generate new token
    import secrets
    user.verification_token = secrets.token_urlsafe(32)
    user.verification_sent_at = datetime.utcnow()
    db.commit()
    
    # Send email
    from ..email.service import email_service
    from ..config import settings
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={user.verification_token}"
    
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        email_service.send_verification_email(email, verification_link)
        logger.info(f"Verification email resent to: {email}")
        return {"message": "Verification email sent!"}
    else:
        logger.warning(f"Email not configured. Verification link: {verification_link}")
        return {"message": "Email not configured", "link": verification_link}

@router.get("/me")
def read_users_me(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    """Get current user profile."""
    # Count files efficiently
    file_count = db.query(models.File).filter(models.File.owner_id == current_user.id).count()
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at,
        "role": "admin" if current_user.id == 0 else "user",
        "file_count": file_count
    }
