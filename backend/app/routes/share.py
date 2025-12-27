from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import secrets
from .. import models, database, auth
from ..storage.minio_client import minio_client
from fastapi.responses import StreamingResponse

router = APIRouter(
    prefix="/api",
    tags=["share"]
)

class ShareRequest(BaseModel):
    file_id: int
    
class ShareResponse(BaseModel):
    share_url: str
    share_token: str

@router.post("/share", response_model=ShareResponse)
def create_share_link(
    request: ShareRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Create a public share link for a file"""
    file = db.query(models.File).filter(
        models.File.id == request.file_id,
        models.File.owner_id == current_user.id
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Generate or return existing token
    if not file.share_token:
        file.share_token = secrets.token_urlsafe(16)
        db.commit()
    
    return {
        "share_url": f"/api/shared/{file.share_token}",
        "share_token": file.share_token
    }

@router.delete("/share/{file_id}")
def revoke_share_link(
    file_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Revoke a share link"""
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.owner_id == current_user.id
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file.share_token = None
    db.commit()
    
    return {"message": "Share link revoked"}

@router.get("/shared/{share_token}")
def download_shared_file(
    share_token: str,
    db: Session = Depends(database.get_db)
):
    """Download a file via share link (no auth required)"""
    file = db.query(models.File).filter(
        models.File.share_token == share_token
    ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="Shared file not found or link expired")
    
    try:
        response = minio_client.get_file_content(file.file_path)
        media_type = file.content_type or "application/octet-stream"
        
        return StreamingResponse(
            response,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{file.filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download: {str(e)}")
