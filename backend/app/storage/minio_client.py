from minio import Minio
from minio.error import S3Error
from ..config import settings
import io

class MinioClient:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False  # Set to True for HTTPS
        )
        self.bucket_name = "ai-cloud-drive"
        self._create_bucket_if_not_exists()

    def _create_bucket_if_not_exists(self):
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_file(self, file_data, file_name, content_type, user_id):
        object_name = f"user_{user_id}/{file_name}"
        try:
            # Check if file_data is bytes or file-like
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
                content_type=content_type
            )
            return object_name
        except S3Error as e:
            print(f"MinIO Upload Error: {e}")
            raise e

    def get_file_url(self, object_name):
        return self.client.presigned_get_object(self.bucket_name, object_name)

    def get_file_content(self, object_name):
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            return response
        except S3Error as e:
             print(f"MinIO Download Error: {e}")
             raise e

    def delete_file(self, object_name):
        self.client.remove_object(self.bucket_name, object_name)

minio_client = MinioClient()
