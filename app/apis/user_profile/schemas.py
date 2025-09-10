from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.core.db.schemas.user_profile import Gender, EducationLevel, LearningStyle


class UserProfileBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    gender: Optional[Gender] = None
    age: Optional[int] = Field(None, ge=13, le=120)
    
    # Education-related fields
    education_level: Optional[EducationLevel] = None
    institution: Optional[str] = Field(None, max_length=200)
    field_of_study: Optional[str] = Field(None, max_length=200)
    graduation_year: Optional[int] = Field(None, ge=1950, le=2030)
    
    # Learning preferences
    learning_style: Optional[LearningStyle] = None
    subjects_of_interest: Optional[str] = Field(None, max_length=500)
    learning_goals: Optional[str] = Field(None, max_length=500)
    
    # Profile metadata
    bio: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=200)
    timezone: Optional[str] = Field(None, max_length=50)


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    gender: Optional[Gender] = None
    age: Optional[int] = Field(None, ge=13, le=120)
    
    # Education-related fields
    education_level: Optional[EducationLevel] = None
    institution: Optional[str] = Field(None, max_length=200)
    field_of_study: Optional[str] = Field(None, max_length=200)
    graduation_year: Optional[int] = Field(None, ge=1950, le=2030)
    
    # Learning preferences
    learning_style: Optional[LearningStyle] = None
    subjects_of_interest: Optional[str] = Field(None, max_length=500)
    learning_goals: Optional[str] = Field(None, max_length=500)
    
    # Profile metadata
    bio: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=200)
    timezone: Optional[str] = Field(None, max_length=50)


class UserProfileRead(UserProfileBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}