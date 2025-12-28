from minio import Minio
from minio.error import S3Error
from ..config import settings
import io
import time
import logging
import functools
from typing import Union, Optional, BinaryIO
import urllib3

logger = logging.getLogger(__name__)

def retry_operation(max_retries=3, delay=1.0, backoff=2.0):
    """
    Decorator for robust retry logic with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            last_exception = None
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (S3Error, urllib3.exceptions.HTTPError) as e:
                    retries += 1
                    last_exception = e
                    if retries == max_retries:
                        break
                    
                    logger.warning(
                        f"MinIO Op Failed ({func.__name__}): {e}. "
                        f"Retrying {retries}/{max_retries} in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            logger.error(f"MinIO Op Permanently Failed ({func.__name__}): {last_exception}")
            raise last_exception
        return wrapper
    return decorator

class MinioClient:
    """
    Production-Grade Object Storage Client.
    Wrapper around MinIO S3 SDK with robust error handling and retries.
    """
    
    def __init__(self):
        try:
            # Custom HTTP client for connection pooling
            http_client = urllib3.PoolManager(
                timeout=settings.MINIO_TIMEOUT if hasattr(settings, 'MINIO_TIMEOUT') else 5.0,
                retries=urllib3.Retry(
                    total=3,
                    backoff_factor=0.2,
                    status_forcelist=[500, 502, 503, 504]
                )
            )
            
            self.client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False,  # Set to True in Prod with SSL
                http_client=http_client
            )
            self.bucket_name = "ai-cloud-drive"
            self._ensure_bucket_exists()
            logger.info(f"MinIO Client initialized for bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.critical(f"MinIO Initialization Failed: {e}")
            raise

    @retry_operation(max_retries=3)
    def _ensure_bucket_exists(self):
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    @retry_operation(max_retries=3)
    def upload_file(self, 
                   file_data: Union[bytes, BinaryIO], 
                   file_name: str, 
                   content_type: str, 
                   user_id: int) -> str:
        """
        Securely upload file to user-scoped path.
        Returns: object_name
        """
        object_name = f"user_{user_id}/{file_name}"
        
        # Prepare stream
        if isinstance(file_data, bytes):
            data = io.BytesIO(file_data)
            length = len(file_data)
        else:
            data = file_data
            file_data.seek(0, 2)
            length = file_data.tell()
            file_data.seek(0)
            
        self.client.put_object(
            self.bucket_name,
            object_name,
            data,
            length,
            content_type=content_type,
            metadata={
                "user_id": str(user_id),
                "original_name": file_name
            }
        )
        logger.info(f"Uploaded {length} bytes to {object_name}")
        return object_name

    @retry_operation(max_retries=2)
    def get_file_url(self, object_name: str, expiry_hours: int = 1) -> str:
        """Generate presigned URL for secure frontend access."""
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket_name, 
            object_name,
            expires=timedelta(hours=expiry_hours)
        )

    @retry_operation(max_retries=3)
    def get_file_content(self, object_name: str):
        """Stream file content for processing."""
        return self.client.get_object(self.bucket_name, object_name)

    @retry_operation(max_retries=3)
    def delete_file(self, object_name: str):
        """Remove file permanently."""
        self.client.remove_object(self.bucket_name, object_name)
        logger.info(f"Deleted object: {object_name}")

# Singleton
minio_client = MinioClient()
