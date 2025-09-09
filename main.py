from fastapi import FastAPI
from app.core.config import settings
from app.apis.auth import router as auth_router

import uvicorn
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app.name, version=settings.app.version)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)

    @app.get("/")
    async def root():
        return {
            "status": "ok",
            "app": settings.app.name,
            "version": settings.app.version,
        }

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
