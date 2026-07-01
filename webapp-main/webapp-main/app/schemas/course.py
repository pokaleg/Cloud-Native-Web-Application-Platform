import uuid
import re
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime
from app.models.course import ClassificationEnum

DEPT_CODE_REGEX = re.compile(r'^[A-Z]{2,6}$')

IMMUTABLE_FIELDS = {"id", "department_code", "number", "has_syllabus", "date_created", "date_updated"}


class CourseCreateRequest(BaseModel):
    department_code: str
    number: str
    title: str
    credit_hours: int
    classification: ClassificationEnum
    description: Optional[str] = None
    prerequisites: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator('department_code')
    @classmethod
    def validate_dept_code(cls, v):
        if not DEPT_CODE_REGEX.match(v):
            raise ValueError('department_code must be 2-6 uppercase letters only')
        return v

    @field_validator('number')
    @classmethod
    def validate_number(cls, v):
        if not (1 <= len(v) <= 6):
            raise ValueError('number must be 1-6 characters')
        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if not (1 <= len(v) <= 255):
            raise ValueError('title must be 1-255 characters')
        return v

    @field_validator('credit_hours')
    @classmethod
    def validate_credit_hours(cls, v):
        if not (1 <= v <= 8):
            raise ValueError('credit_hours must be between 1 and 8 inclusive')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v is not None and len(v) > 2000:
            raise ValueError('description must not exceed 2000 characters')
        return v

    @field_validator('prerequisites')
    @classmethod
    def validate_prerequisites(cls, v):
        if v is not None and len(v) > 512:
            raise ValueError('prerequisites must not exceed 512 characters')
        return v


class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    credit_hours: Optional[int] = None
    classification: Optional[ClassificationEnum] = None
    description: Optional[str] = None
    prerequisites: Optional[str] = None

    model_config = {"extra": "forbid"}

    @model_validator(mode='before')
    @classmethod
    def reject_immutable_fields(cls, data):
        """Return 400 if client tries to set any immutable field."""
        if isinstance(data, dict):
            for field in IMMUTABLE_FIELDS:
                if field in data:
                    raise ValueError(f"Field '{field}' is immutable and cannot be updated")
        return data

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if v is not None and not (1 <= len(v) <= 255):
            raise ValueError('title must be 1-255 characters')
        return v

    @field_validator('credit_hours')
    @classmethod
    def validate_credit_hours(cls, v):
        if v is not None and not (1 <= v <= 8):
            raise ValueError('credit_hours must be between 1 and 8 inclusive')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v is not None and len(v) > 2000:
            raise ValueError('description must not exceed 2000 characters')
        return v

    @field_validator('prerequisites')
    @classmethod
    def validate_prerequisites(cls, v):
        if v is not None and len(v) > 512:
            raise ValueError('prerequisites must not exceed 512 characters')
        return v


class CourseResponse(BaseModel):
    id: uuid.UUID
    department_code: str
    number: str
    title: str
    credit_hours: int
    classification: ClassificationEnum
    description: Optional[str]
    prerequisites: Optional[str]
    has_syllabus: bool
    date_created: datetime
    date_updated: datetime

    model_config = {"from_attributes": True}


class SyllabusResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    file_name: str
    s3_bucket_name: str
    s3_object_key: str
    content_type: str
    file_size: int
    url: str
    date_created: datetime
    date_updated: datetime

    model_config = {"from_attributes": True}
