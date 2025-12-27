from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)  # Nullable for passwordless users
    google_id = Column(String, unique=True, nullable=True, index=True)  # Google OAuth ID
    name = Column(String, nullable=True)  # User display name
    profile_photo = Column(String, nullable=True)  # MinIO path to profile photo
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Magic Link (Passwordless Auth)
    magic_link_token = Column(String, nullable=True, index=True)
    magic_link_expires = Column(DateTime, nullable=True)
    
    # Email verification (auto-verified for OAuth/Magic Link users)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_sent_at = Column(DateTime, nullable=True)
    
    # Account security
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    can_upload = Column(Boolean, default=True) # Admin control

    files = relationship("File", back_populates="owner")
    chats = relationship("ChatHistory", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Admin or System (null)
    action = Column(String) # e.g. "suspend_user", "delete_file"
    target_id = Column(Integer, nullable=True) # ID of affected user/file
    target_type = Column(String, nullable=True) # "user", "file"
    metadata_json = Column(String, nullable=True) # JSON details

    actor = relationship("User", foreign_keys=[actor_id])



class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    query = Column(String)
    answer = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chats")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String) # MinIO path
    content_type = Column(String)
    size = Column(Integer)
    upload_date = Column(DateTime, default=datetime.utcnow)
    is_indexed = Column(Boolean, default=False)
    share_token = Column(String, unique=True, nullable=True) # For public sharing
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="files")

class FileShare(Base):
    __tablename__ = "file_shares"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"))
    shared_with_id = Column(Integer, ForeignKey("users.id"))
    permission = Column(String, default="read") # read, write
    created_at = Column(DateTime, default=datetime.utcnow)

