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
        
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception as e:
            print(f"Warning: Could not verify or create bucket (normal for restricted R2 tokens): {e}")

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

    def list_objects(self, prefix: str):
        return self.client.list_objects(self.bucket, prefix=prefix, recursive=True)

storage_client = StorageClient()
