from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from .. import database, models, schemas, auth
from ..storage import minio_client
import uuid
import io

router = APIRouter(
    prefix="/api/profile",
    tags=["profile"]
)

@router.get("", response_model=schemas.User)
def get_profile(current_user: models.User = Depends(auth.get_current_user)):
    """Get current user profile"""
    return current_user

@router.put("", response_model=schemas.User)
def update_profile(
    profile: schemas.ProfileUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Update user profile name"""
    if profile.name is not None:
        current_user.name = profile.name
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Upload user profile photo to MinIO"""
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Generate unique filename
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    unique_filename = f"profiles/{current_user.id}/{uuid.uuid4()}.{file_ext}"
    
    try:
        # Delete old profile photo if exists
        if current_user.profile_photo:
            try:
                minio_client.remove_object("ai-drive", current_user.profile_photo)
            except:
                pass  # Ignore if old photo doesn't exist
        
        # Upload to MinIO
        file_content = await file.read()
        minio_client.put_object(
            "ai-drive",
            unique_filename,
            io.BytesIO(file_content),
            length=len(file_content),
            content_type=file.content_type
        )
        
        # Update user record
        current_user.profile_photo = unique_filename
        db.commit()
        
        return {"message": "Profile photo uploaded successfully", "photo_path": unique_filename}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.delete("/photo")
def delete_profile_photo(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Delete user profile photo"""
    if not current_user.profile_photo:
        raise HTTPException(status_code=404, detail="No profile photo to delete")
    
    try:
        # Delete from MinIO
        minio_client.remove_object("ai-drive", current_user.profile_photo)
        
        # Update user record
        current_user.profile_photo = None
        db.commit()
        
        return {"message": "Profile photo deleted successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@router.get("/photo/{user_id}")
def get_profile_photo(user_id: int, db: Session = Depends(database.get_db)):
    """Get profile photo URL for a user"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.profile_photo:
        raise HTTPException(status_code=404, detail="Profile photo not found")
    
    try:
        # Generate presigned URL (valid for 1 hour)
        url = minio_client.presigned_get_object("ai-drive", user.profile_photo, expires=3600)
        return {"photo_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get photo: {str(e)}")
