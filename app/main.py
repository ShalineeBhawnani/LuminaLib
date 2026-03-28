"""
LuminaLib - Intelligent Library System
Main application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, books, recommendations, reviews
from app.core.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    await init_db()
    yield


def create_application() -> FastAPI:
    """Factory function to create and configure the FastAPI app."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Next-generation intelligent library system with GenAI capabilities.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    application.include_router(books.router, prefix="/books", tags=["Books"])
    application.include_router(reviews.router, prefix="/books", tags=["Reviews"])
    application.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])

    return application


app = create_application()
