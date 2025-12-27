from celery import Celery
from ..config import settings
from ..storage.minio_client import minio_client
from ..rag import indexer
from ..database import SessionLocal
from .. import models

celery = Celery(
    "tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

@celery.task
def process_file_task(file_id: int, object_name: str, content_type: str, user_id: int):
    print(f"Starting background processing for file {file_id}")
    
    # 1. Download file content from MinIO
    try:
        response = minio_client.get_file_content(object_name)
        file_content = response.read()
        response.close()
        response.release_conn()
    except Exception as e:
        print(f"Error downloading file from MinIO: {e}")
        return

    # 2. Process and Index
    try:
        indexer.process_and_index_file(file_id, file_content, content_type, user_id)
        
        # 3. Update DB status
        db = SessionLocal()
        try:
            db_file = db.query(models.File).filter(models.File.id == file_id).first()
            if db_file:
                db_file.is_indexed = True
                db.commit()
                print(f"Successfully indexed file {file_id}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error processing file {file_id}: {e}")
