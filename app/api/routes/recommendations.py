"""ML-based recommendation endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import RecommendationResponse
from app.services.ml.recommendation_engine import RecommendationEngine

router = APIRouter()


def _get_engine(db: AsyncSession = Depends(get_db)) -> RecommendationEngine:
    return RecommendationEngine(db, algorithm=settings.RECOMMENDATION_ALGORITHM)


@router.get("", response_model=RecommendationResponse)
async def get_recommendations(
    current_user: User = Depends(get_current_user),
    engine: RecommendationEngine = Depends(_get_engine),
):
    """Return ML-powered book recommendations for the authenticated user."""
    return await engine.recommend(current_user, top_n=settings.RECOMMENDATION_TOP_N)
