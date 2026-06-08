import io
from minio import Minio
from src.core.config import get_settings

class StorageClient:
    def __init__(self):
        settings = get_settings()
        self.client = Minio(
            endpoint=settings.storage_endpoint,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            secure=settings.storage_use_ssl,
        )
        self.bucket = settings.storage_bucket_name
        
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_file(self, object_name: str, data, length: int, content_type: str = "application/octet-stream"):
        if isinstance(data, bytes):
            data = io.BytesIO(data)
            
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_name,
            data=data,
            length=length,
            content_type=content_type,
        )

    def get_presigned_url(self, object_name: str) -> str:
        return self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_name,
        )

storage_client = StorageClient()
