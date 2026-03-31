import io
from supabase import create_client, Client
from app.core.config import settings

# Initialize Supabase Client
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

class StorageService:
    def __init__(self, bucket_name: str = "event-assets"):
        self.bucket = bucket_name

    def upload_file(self, file_path: str, file_bytes: bytes, content_type: str = "image/png") -> str:
        """
        Uploads a file to Supabase storage and returns the public URL.
        """
        try:
            # Check if bucket exists, if not we rely on it being there or Supabase failing gracefully
            res = supabase.storage.from_(self.bucket).upload(
                file_path,
                file_bytes,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            # Get public url
            public_url = supabase.storage.from_(self.bucket).get_public_url(file_path)
            return public_url
        except Exception as e:
            raise Exception(f"Failed to upload to Supabase storage: {e}")

    def get_public_url(self, file_path: str) -> str:
        return supabase.storage.from_(self.bucket).get_public_url(file_path)
