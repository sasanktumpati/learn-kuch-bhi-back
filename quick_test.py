"""
Quick test script for video generation - minimal setup.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.modules.video_generator.main import VideoGenerator
from app.modules.flashcards.main import MultiFlashcardsGenerator


async def quick_test():
    """Quick test of video generation with database."""

    engine = create_async_engine(str(settings.postgres.connection_string))
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    session = async_session()

    try:
        generator = VideoGenerator()

        print("🎬 Generating video for user 1...")

        result, video_id = await generator.generate_with_db(
            session=session,
            user_id=2,
            prompt="Show a simple animation of a circle to triangle to square to rectangle to pentagon to hexagon to heptagon to octagon to nonagon to decagon, each in different colors",
            title="Shapes",
            description="Test animation showing shapes",
        )

        if result.ok:
            print(f"✅ Success! Video ID in database: {video_id}")
            print(f"📁 Video path: {result.video_path}")
        else:
            print("❌ Generation failed")
            if result.runtime_errors:
                print(f"Errors: {result.runtime_errors}")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        await session.close()
        await engine.dispose()


async def test_flashcards():
    """Quick test of flashcard generation with database."""

    try:
        engine = create_async_engine(str(settings.postgres.connection_string))
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        session = async_session()
        try:
            print("\n📝 Generating multi-flashcards with outline...")
            multi_generator = MultiFlashcardsGenerator(concurrency=6)
            multi_result = await multi_generator.generate_with_db(
                session=session,
                user_id=1,
                base_prompt="Introduction to Computer Programming",
            )
            print(f"✅ Multi-flashcards generated! Result ID: {multi_result.id}")
            topics = (
                (multi_result.outline or {}).get("topics", [])
                if hasattr(multi_result, "outline")
                else []
            )
            print(f"📋 Outline topics: {len(topics)}")
            sets = getattr(multi_result, "flashcard_sets", [])
            print(f"📚 Total subtopic sets: {len(sets)}")
        finally:
            await session.close()
            await engine.dispose()

    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all quick tests."""
    await test_flashcards()


if __name__ == "__main__":
    asyncio.run(main())
