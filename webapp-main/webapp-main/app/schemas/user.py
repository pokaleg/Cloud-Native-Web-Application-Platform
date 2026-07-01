from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional
from datetime import datetime
import uuid as uuid_module

class UserCreate(BaseModel):
    username: EmailStr
    password: str
    first_name: str
    last_name: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password must not exceed 128 characters')
        return v
    
    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Name cannot be empty')
        if len(v) > 100:
            raise ValueError('Name must not exceed 100 characters')
        return v.strip()
    
    model_config = {"extra": "forbid"}

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if v is not None:
            if len(v) < 8:
                raise ValueError('Password must be at least 8 characters')
            if len(v) > 128:
                raise ValueError('Password must not exceed 128 characters')
        return v
    
    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Name cannot be empty')
            if len(v) > 100:
                raise ValueError('Name must not exceed 100 characters')
            return v.strip()
        return v
    
    @model_validator(mode='after')
    def check_at_least_one_field(self):
        if not any([self.first_name, self.last_name, self.password]):
            raise ValueError('At least one field must be provided for update')
        return self
    
    model_config = {"extra": "forbid"}

class UserResponse(BaseModel):
    id: uuid_module.UUID
    username: str
    first_name: str
    last_name: str
    account_created: datetime
    account_updated: datetime
    
    class Config:
        from_attributes = True
