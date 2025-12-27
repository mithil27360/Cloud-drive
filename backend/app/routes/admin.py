
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from .. import database, models, schemas, auth
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_admin_user)]
)

# Admin Schemas (Internal use for now)
class AdminUserStats(schemas.User):
    files_count: int
    queries_total: int
    queries_24h: int
    storage_used: int
    failed_queries: int
    last_login: datetime | None
    created_at: datetime | None
    can_upload: bool
    is_verified: bool

    class Config:
        from_attributes = True

class AuditLogView(BaseModel):
    id: int
    timestamp: datetime
    actor_email: str
    action: str
    target_id: int | None
    target_type: str | None
    metadata_json: str | None

    class Config:
        from_attributes = True

class AdminFileView(BaseModel):
    id: int
    filename: str
    size: int
    upload_date: datetime
    content_type: str | None
    owner_email: str

    class Config:
        from_attributes = True

class AdminChatView(BaseModel):
    id: int
    query: str
    answer: str | None
    timestamp: datetime
    user_email: str

    class Config:
        from_attributes = True

# --- Helpers ---
def log_audit(db: Session, actor_id: int, action: str, target_id: int = None, target_type: str = None, meta: dict = None):
    import json
    log = models.AuditLog(
        actor_id=actor_id,
        action=action,
        target_id=target_id,
        target_type=target_type,
        metadata_json=json.dumps(meta) if meta else None
    )
    db.add(log)
    db.commit()

# --- Endpoints ---

@router.get("/users", response_model=List[AdminUserStats])
def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_admin_user)
):
    users = db.query(models.User).order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()
    
    # Enrichment
    results = []
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)

    for u in users:
        u_dict = u.__dict__
        u_dict['files_count'] = len(u.files)
        u_dict['storage_used'] = sum(f.size for f in u.files)
        u_dict['queries_total'] = len(u.chats)
        # Inefficient loop for 24h, but ok for small scale. 
        # For production, use optimized SQL query.
        u_dict['queries_24h'] = sum(1 for c in u.chats if c.timestamp > day_ago)
        u_dict['failed_queries'] = sum(1 for c in u.chats if c.answer and c.answer.startswith("Error"))
        results.append(u_dict)
        
    return results

@router.get("/files", response_model=List[AdminFileView])
def get_all_files(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(database.get_db)
):
    files = db.query(models.File).order_by(models.File.upload_date.desc()).offset(skip).limit(limit).all()
    
    results = []
    for f in files:
        results.append({
            "id": f.id,
            "filename": f.filename,
            "size": f.size,
            "upload_date": f.upload_date,
            "content_type": f.content_type,
            "owner_email": f.owner.email if f.owner else "Unknown"
        })
    return results

@router.get("/chats", response_model=List[AdminChatView])
def get_all_chats(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(database.get_db)
):
    chats = db.query(models.ChatHistory).order_by(models.ChatHistory.timestamp.desc()).offset(skip).limit(limit).all()
    
    results = []
    for c in chats:
        results.append({
            "id": c.id,
            "query": c.query,
            "answer": c.answer,
            "timestamp": c.timestamp,
            "user_email": c.user.email if c.user else "Unknown"
        })
    return results

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(auth.get_admin_user)):
    from ..storage.minio_client import minio_client
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_email = user.email  # Save for audit log
    deleted_files_count = 0
    
    try:
        # 1. Delete user's files from MinIO and database
        user_files = db.query(models.File).filter(models.File.owner_id == user_id).all()
        for file in user_files:
            try:
                # Delete from MinIO storage
                if file.file_path:
                    minio_client.delete_file(file.file_path)
            except Exception as e:
                print(f"Warning: Could not delete file from MinIO: {file.file_path} - {e}")
            # Delete file record from DB
            db.delete(file)
            deleted_files_count += 1
        
        # 2. Delete user's chat history
        db.query(models.ChatHistory).filter(models.ChatHistory.user_id == user_id).delete()
        
        # 3. Delete the user
        db.delete(user)
        db.commit()
        
        # Log the action
        log_audit(db, admin.id, "delete_user", user_id, "user", {
            "email": user_email, 
            "files_deleted": deleted_files_count
        })
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Cannot delete user: {str(e)}")
        
    return {"message": f"User deleted along with {deleted_files_count} files"}

@router.post("/users/{user_id}/verify")
def verify_user_manually(user_id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_verified = True
    user.verification_token = None
    db.commit()
    log_audit(db, None, "verify_user", user.id, "user", {"email": user.email}) # Actor ID None (or fetch current user)
    return {"message": f"User {user.email} manually verified"}

@router.post("/users/{user_id}/suspend")
def suspend_user(user_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(auth.get_admin_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    user.is_active = False
    db.commit()
    log_audit(db, admin.id, "suspend_user", user.id, "user", {"email": user.email})
    return {"message": "User suspended"}

@router.post("/users/{user_id}/unsuspend")
def unsuspend_user(user_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(auth.get_admin_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    user.is_active = True
    db.commit()
    log_audit(db, admin.id, "unsuspend_user", user.id, "user", {"email": user.email})
    return {"message": "User unsuspended"}

@router.post("/users/{user_id}/disable-upload")
def disable_upload(user_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(auth.get_admin_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    user.can_upload = False
    db.commit()
    log_audit(db, admin.id, "disable_upload", user.id, "user", {"email": user.email})
    return {"message": "Uploads disabled for user"}

@router.post("/users/{user_id}/enable-upload")
def enable_upload(user_id: int, db: Session = Depends(database.get_db), admin: models.User = Depends(auth.get_admin_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    user.can_upload = True
    db.commit()
    log_audit(db, admin.id, "enable_upload", user.id, "user", {"email": user.email})
    return {"message": "Uploads enabled for user"}

@router.get("/audit-logs", response_model=List[AuditLogView])
def get_audit_logs(skip: int = 0, limit: int = 50, db: Session = Depends(database.get_db)):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    results = []
    for log in logs:
        results.append({
            "id": log.id,
            "timestamp": log.timestamp,
            "actor_email": log.actor.email if log.actor else "System",
            "action": log.action,
            "target_id": log.target_id,
            "target_type": log.target_type,
            "metadata_json": log.metadata_json
        })
    return results
