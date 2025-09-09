"""Pydantic models for flashcard generation and validation.

Note: To keep the Google Generative AI structured output schema simple and
compatible, we avoid complex constraints (min/max lengths, formats, etc.).
Validation can be applied post-generation if needed.
"""

from pydantic import BaseModel, Field


class Flashcard(BaseModel):
    """Simple question/answer flashcard."""

    question: str
    answer: str


class FlashcardSet(BaseModel):
    """A titled set of flashcards with metadata."""

    title: str
    description: str
    flashcards: list[Flashcard]
    tags: list[str] = Field(default_factory=list)
