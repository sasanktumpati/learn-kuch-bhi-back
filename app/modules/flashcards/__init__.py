"""Flashcards module exports (multi-generation focused)."""

from .models.flashcards import Flashcard, FlashcardSet
from .main import MultiFlashcardsGenerator

__all__ = [
    "Flashcard",
    "FlashcardSet",
    "MultiFlashcardsGenerator",
]
