from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.flashcards.models.outline import TopicOutline


class OutlineRequest(BaseModel):
    base_prompt: str = Field(..., description="Subject or instructions for outline")


class OutlineResponse(BaseModel):
    outline: TopicOutline


class GeneratePersistRequest(BaseModel):
    base_prompt: str = Field(..., description="Base subject for multi flashcards")


class MultiRunSummary(BaseModel):
    id: int
    status: str
    outline: dict
    created_at: str | None = None
    completed_at: str | None = None
    sets_created: int = 0


class GeneratePersistResponse(BaseModel):
    run: MultiRunSummary
    status_url: str
    sets_url: str


class FlashcardRead(BaseModel):
    id: int
    question: str
    answer: str
    order_index: int


class FlashcardSetSummary(BaseModel):
    id: int
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    status: str
    created_at: str


class FlashcardSetRead(FlashcardSetSummary):
    flashcards: list[FlashcardRead] = Field(default_factory=list)


class AggregatedFlashcardsResponse(BaseModel):
    prompt: str
    total_sets: int
    total_flashcards: int
    sets: list[FlashcardSetRead] = Field(default_factory=list)
