from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.apis.auth import router as auth_router
from app.apis.user_profile.main import router as user_profile_router
from app.apis.flashcards.main import router as flashcards_router
from app.apis.video_generator.main import router as video_router

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from app.core.task_queue import queue as _bg_queue
from app.core.video_manager import video_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bg_queue.start()
    try:
        yield
    finally:
        await _bg_queue.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app.name, version=settings.app.version, lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://kuch-bhi-back.built.systems/",
            "https://kuch-bhi.built.systems/",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve generated videos as static files
    app.mount(
        "/videos",
        StaticFiles(directory=str(video_manager.base_dir), html=False),
        name="videos",
    )

    app.include_router(auth_router)
    app.include_router(user_profile_router)
    app.include_router(flashcards_router)
    app.include_router(video_router)

    @app.get("/")
    async def root():
        return {
            "status": "ok",
            "app": settings.app.name,
            "version": settings.app.version,
        }

    # Lifecycle handled via lifespan() above

    return app


app = create_app()


if __name__ == "__main__":
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=settings.app.port,
            reload=not settings.app.is_production,
        )
    except Exception as e:
        print(f"An error occurred when starting the server: {e}.")
