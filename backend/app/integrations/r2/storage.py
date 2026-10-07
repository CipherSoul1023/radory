import boto3

from app.core.config import get_settings


class R2NotConfigured(RuntimeError):
    pass


class R2Storage:
    def __init__(self):
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return all(
            [
                self.settings.r2_account_id or self.settings.r2_endpoint,
                self.settings.r2_access_key_id,
                self.settings.r2_secret_access_key,
                self.settings.r2_bucket_name,
            ]
        )

    def client(self):
        if not self.configured:
            raise R2NotConfigured("R2 credentials and bucket are not configured")
        endpoint = self.settings.r2_endpoint or (
            f"https://{self.settings.r2_account_id}.r2.cloudflarestorage.com"
        )
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name="auto",
        )
