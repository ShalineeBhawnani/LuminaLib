"""
Review service: submission gating, sentiment analysis, rolling consensus.
"""

import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.models import Book, BookBorrow, Review, User, UserPreference
from app.schemas.schemas import BookAnalysisResponse, ReviewRequest, ReviewResponse
from app.services.llm.base import BaseLLMService
from app.tasks.background_tasks import run_review_consensus_update


class ReviewService:
    def __init__(self, db: AsyncSession, llm: BaseLLMService) -> None:
        self._db = db
        self._llm = llm

    async def submit_review(
        self, book_id: uuid.UUID, user: User, payload: ReviewRequest
    ) -> Review:
        # Gate: user must have borrowed the book
        borrow_result = await self._db.execute(
            select(BookBorrow).where(
                BookBorrow.book_id == book_id,
                BookBorrow.user_id == user.id,
            )
        )
        if not borrow_result.scalar_one_or_none():
            raise ForbiddenError("You must borrow a book before reviewing it.")

        # Prevent duplicate reviews
        dup = await self._db.execute(
            select(Review).where(Review.book_id == book_id, Review.user_id == user.id)
        )
        if dup.scalar_one_or_none():
            raise ConflictError("You have already reviewed this book.")

        review = Review(
            user_id=user.id,
            book_id=book_id,
            rating=payload.rating,
            body=payload.body,
        )
        self._db.add(review)
        await self._db.flush()

        # Update user's average rating preference
        await self._update_avg_rating(user, payload.rating)

        # Fire async consensus update
        asyncio.create_task(
            run_review_consensus_update(book_id=book_id, llm=self._llm)
        )

        return review

    async def get_analysis(self, book_id: uuid.UUID) -> BookAnalysisResponse:
        result = await self._db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise NotFoundError("Book")

        stats = await self._db.execute(
            select(func.count(Review.id), func.avg(Review.rating)).where(Review.book_id == book_id)
        )
        total, avg = stats.one()

        return BookAnalysisResponse(
            book_id=book_id,
            ai_review_consensus=book.ai_review_consensus,
            total_reviews=total or 0,
            average_rating=round(float(avg), 2) if avg else None,
        )

    async def _update_avg_rating(self, user: User, new_rating: int) -> None:
        result = await self._db.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        pref = result.scalar_one_or_none()
        if not pref:
            pref = UserPreference(user_id=user.id)
            self._db.add(pref)

        reviews_result = await self._db.execute(
            select(func.avg(Review.rating)).where(Review.user_id == user.id)
        )
        avg = reviews_result.scalar_one()
        pref.avg_rating_given = round(float(avg), 2) if avg else None
        self._db.add(pref)
