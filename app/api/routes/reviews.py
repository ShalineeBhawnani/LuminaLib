"""Review submission and GenAI analysis routes."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import BookAnalysisResponse, ReviewRequest, ReviewResponse
from app.services.llm.factory import get_llm_service
from app.services.review_service import ReviewService

router = APIRouter()


def _get_review_service(db: AsyncSession = Depends(get_db)) -> ReviewService:
    llm = get_llm_service(settings.LLM_BACKEND)
    return ReviewService(db, llm)


@router.post("/{book_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    book_id: uuid.UUID,
    payload: ReviewRequest,
    current_user: User = Depends(get_current_user),
    svc: ReviewService = Depends(_get_review_service),
):
    """Submit a review. Triggers background sentiment + consensus update."""
    return await svc.submit_review(book_id, current_user, payload)


@router.get("/{book_id}/analysis", response_model=BookAnalysisResponse)
async def get_analysis(
    book_id: uuid.UUID,
    _: User = Depends(get_current_user),
    svc: ReviewService = Depends(_get_review_service),
):
    return await svc.get_analysis(book_id)
