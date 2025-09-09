"""Models for topic outlines used by the multi-agent flashcards generator."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Subtopic(BaseModel):
    name: str
    description: str | None = None


class Topic(BaseModel):
    name: str
    subtopics: list[Subtopic] = Field(default_factory=list)


class TopicOutline(BaseModel):
    title: str
    topics: list[Topic] = Field(default_factory=list)


class SubtopicFlashcards(BaseModel):
    topic: str
    subtopic: str
    flashcard_set: "FlashcardSet"  # forward ref to avoid import cycle


class MultiFlashcardsResult(BaseModel):
    outline: TopicOutline
    sets: list[SubtopicFlashcards] = Field(default_factory=list)


# Late import to resolve forward refs
from app.modules.flashcards.models.flashcards import FlashcardSet  # noqa: E402

SubtopicFlashcards.model_rebuild()
MultiFlashcardsResult.model_rebuild()
