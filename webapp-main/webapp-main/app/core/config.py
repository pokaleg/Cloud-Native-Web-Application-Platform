import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load .env from the deployed path if it exists AND is readable (EC2 instance),
# otherwise fall back to local .env file (local dev / CI)
_deployed_env = "/opt/csye6225/.env"
if os.path.exists(_deployed_env) and os.access(_deployed_env, os.R_OK):
    load_dotenv(_deployed_env)
else:
    load_dotenv()


class Settings:
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "webapp")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    SNS_TOPIC_ARN: str = os.getenv("SNS_TOPIC_ARN", "")      # NEW in A08
    DOMAIN: str = os.getenv("DOMAIN", "demo.techwithhk.me")  # NEW in A08

    @property
    def DATABASE_URL(self) -> str:
        pwd = quote_plus(self.DB_PASSWORD)
        base = (
            f"postgresql://{self.DB_USER}:{pwd}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
        if self.DB_HOST and self.DB_HOST != "localhost":
            return base + "?sslmode=require&sslcert=&sslkey=&sslrootcert="
        return base


settings = Settings()
