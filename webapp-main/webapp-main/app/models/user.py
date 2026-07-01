from sqlalchemy import Column, String, DateTime, BigInteger, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base
from app.core.security import verify_password


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)  # NEW in A08
    account_created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    account_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def check_password(self, password: str) -> bool:
        return verify_password(password, self.password)


class HealthCheck(Base):
    __tablename__ = "health_checks"

    check_id = Column(BigInteger, primary_key=True, autoincrement=True)
    check_datetime = Column(DateTime(timezone=True), server_default=func.now())


class EmailVerificationToken(Base):
    """Stores short-lived tokens for email verification (1 minute TTL)."""
    __tablename__ = "email_verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    token = Column(String(36), unique=True, nullable=False, index=True)  # UUID string
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)
