"""Flashcards module exports."""

from .models.flashcards import Flashcard, FlashcardSet
from .generator import generate_flashcards, generate_flashcards_sync
from .main import FlashcardsGenerator

__all__ = [
    "Flashcard",
    "FlashcardSet",
    "generate_flashcards",
    "generate_flashcards_sync",
    "FlashcardsGenerator",
]
