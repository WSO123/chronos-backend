import boto3
from botocore.client import Config
from app.core.config import settings

class StorageService:
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1' # MinIO ignores this but boto3 requires it
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except:
            # Create bucket if it doesn't exist
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
            except Exception as e:
                print(f"Warning: Could not create bucket {self.bucket_name}: {e}")

    def upload_file(self, file_path: str, object_name: str = None) -> str:
        if object_name is None:
            object_name = file_path.split("/")[-1]
        
        try:
            self.client.upload_file(file_path, self.bucket_name, object_name)
            # Return pre-signed URL or public URL depending on policy. 
            # For now, let's return a simple URL assuming public read or internal usage
            return f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{object_name}"
        except Exception as e:
            print(f"Failed to upload file: {e}")
            raise e

storage_service = StorageService()
