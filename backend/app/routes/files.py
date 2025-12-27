from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, models, database, auth
from ..storage.minio_client import minio_client
from ..tasks.celery_app import process_file_task
import mimetypes

router = APIRouter(
    prefix="/api",
    tags=["files"]
)

@router.post("/upload", response_model=schemas.File)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Permissions Check
    if not current_user.can_upload:
        raise HTTPException(status_code=403, detail="Uploads are disabled for your account")

    # Rate Limit: File Count
    MAX_FILES_COUNT = 50
    current_file_count = db.query(models.File).filter(models.File.owner_id == current_user.id).count()
    if current_file_count >= MAX_FILES_COUNT:
        raise HTTPException(status_code=400, detail=f"File limit reached ({MAX_FILES_COUNT} files). Please delete some files.")

    # Constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_TYPES = ["application/pdf", "text/plain", "text/markdown", "text/x-markdown"]
    ALLOWED_EXTENSIONS = [".pdf", ".txt", ".md"]
    
    # Validate file extension
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size: 50MB")
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Cannot upload empty file")

    # Upload to MinIO
    try:
        object_name = minio_client.upload_file(
            file_data=file_content,
            file_name=file.filename,
            content_type=file.content_type,
            user_id=current_user.id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload to storage: {str(e)}")

    # Save metadata to DB
    db_file = models.File(
        filename=file.filename,
        file_path=object_name,
        content_type=file.content_type,
        size=file_size,
        owner_id=current_user.id,
        is_indexed=False 
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # Trigger Async Task (Phase 5)
    process_file_task.delay(db_file.id, object_name, file.content_type, current_user.id)

    return db_file

@router.get("/files", response_model=List[schemas.File])
def get_files(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    files = db.query(models.File).filter(models.File.owner_id == current_user.id).all()
    return files

@router.get("/download/{file_id}")
def download_file(
    file_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Admin can download any file, regular users can only download their own
    file = db.query(models.File).filter(models.File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if user is admin or file owner
    # Admin users have email format "admin:username"
    from ..config import settings
    is_admin = (
        current_user.email == settings.ADMIN_USERNAME or
        current_user.email == f"admin:{settings.ADMIN_USERNAME}" or
        current_user.email.startswith("admin:")
    )
    
    if not is_admin and file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to download this file")


    try:
        response = minio_client.get_file_content(file.file_path)
        
        # Determine media type using standard library or fallback to application/octet-stream
        media_type = file.content_type or "application/octet-stream"
        
        return StreamingResponse(
            response, 
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{file.filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@router.delete("/delete/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    file = db.query(models.File).filter(models.File.id == file_id, models.File.owner_id == current_user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from MinIO
    try:
        minio_client.delete_file(file.file_path)
    except Exception as e:
        print(f"Warning: Failed to delete from MinIO: {e}")
        # Continue to delete from DB even if MinIO fails (orphaned check later?)
    
    # Delete from DB
    db.delete(file)
    db.commit()
    
    return {"message": "File deleted successfully"}
