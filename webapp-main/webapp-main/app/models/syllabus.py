import uuid
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from app.core.database import Base

class Syllabus(Base):
    __tablename__ = "syllabi"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, unique=True)
    file_name = Column(String, nullable=False)
    s3_bucket_name = Column(String, nullable=False)
    s3_object_key = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    url = Column(String, nullable=False)
    date_created = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    date_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
