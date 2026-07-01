import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from app.core.database import Base
import enum

class ClassificationEnum(str, enum.Enum):
    core = "core"
    elective = "elective"

class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_code = Column(String(6), nullable=False)
    number = Column(String(6), nullable=False)
    title = Column(String(255), nullable=False)
    credit_hours = Column(Integer, nullable=False)
    classification = Column(SAEnum(ClassificationEnum), nullable=False)
    description = Column(String(2000), nullable=True)
    prerequisites = Column(String(512), nullable=True)
    has_syllabus = Column(Boolean, nullable=False, default=False)
    date_created = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    date_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Unique constraint on department_code + number
        __import__('sqlalchemy').UniqueConstraint('department_code', 'number', name='uq_course_dept_number'),
    )
