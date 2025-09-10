from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Enum,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.db.base import Base

if TYPE_CHECKING:
    from .auth import User


class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class EducationLevel(enum.Enum):
    HIGH_SCHOOL = "high_school"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"
    OTHER = "other"


class LearningStyle(enum.Enum):
    VISUAL = "visual"
    AUDITORY = "auditory"
    KINESTHETIC = "kinesthetic"
    READING_WRITING = "reading_writing"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender), nullable=True
    )
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Education-related fields
    education_level: Mapped[EducationLevel] = mapped_column(
        Enum(EducationLevel), nullable=True
    )
    institution: Mapped[str] = mapped_column(String, nullable=True)
    field_of_study: Mapped[str] = mapped_column(String, nullable=True)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Learning preferences
    learning_style: Mapped[LearningStyle] = mapped_column(
        Enum(LearningStyle), nullable=True
    )
    subjects_of_interest: Mapped[str] = mapped_column(String, nullable=True)  # Comma-separated
    learning_goals: Mapped[str] = mapped_column(String, nullable=True)
    
    # Profile metadata
    bio: Mapped[str] = mapped_column(String, nullable=True)
    location: Mapped[str] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="profile")


__all__ = [
    "Gender",
    "EducationLevel", 
    "LearningStyle",
    "UserProfile",
]