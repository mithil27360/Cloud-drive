from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    name: Optional[str] = None
    profile_photo: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class FileBase(BaseModel):
    filename: str

class File(FileBase):
    id: int
    content_type: str
    size: int
    upload_date: datetime
    is_indexed: bool
    owner_id: int
    share_token: Optional[str] = None

    class Config:
        from_attributes = True

# Profile Management
class ProfileUpdate(BaseModel):
    name: Optional[str] = None

