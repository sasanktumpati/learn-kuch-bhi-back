# Import models so Alembic and Base metadata are aware of them
from .auth import User  # noqa: F401
from .flashcards import FlashcardSet, Flashcard, MultiFlashcardsResult, Topic, Subtopic  # noqa: F401
from .videos import Videos, VideoCodes, ManimConfig, ManimRenderRequest  # noqa: F401
from .user_profile import UserProfile  # noqa: F401
