"""
Recommendation Engine supporting two algorithms:
  - content_based: cosine similarity on book tags vs user preference tags
  - collaborative: item-based collaborative filtering via borrow history co-occurrence

Switch algorithms via RECOMMENDATION_ALGORITHM in .env.
"""

import uuid
from collections import Counter, defaultdict
from typing import Literal

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Book, BookBorrow, User, UserPreference
from app.schemas.schemas import BookResponse, RecommendationResponse


class RecommendationEngine:
    def __init__(
        self,
        db: AsyncSession,
        algorithm: Literal["content_based", "collaborative"] = "content_based",
    ) -> None:
        self._db = db
        self._algorithm = algorithm

    async def recommend(self, user: User, top_n: int = 10) -> RecommendationResponse:
        if self._algorithm == "collaborative":
            books, basis = await self._collaborative(user, top_n)
        else:
            books, basis = await self._content_based(user, top_n)

        return RecommendationResponse(
            books=books,
            algorithm=self._algorithm,
            based_on=basis,
        )

    # ── Content-Based Filtering ──────────────────────────────────────────

    async def _content_based(self, user: User, top_n: int) -> tuple[list[BookResponse], str]:
        """
        Strategy:
        1. Merge user's explicit + implicit preference tags into a preference vector.
        2. Represent each book as a binary tag vector over the global tag vocabulary.
        3. Compute cosine similarity between user vector and each book vector.
        4. Exclude already-borrowed books. Return top-N by score.
        """
        pref_result = await self._db.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        pref = pref_result.scalar_one_or_none()

        user_tags: set[str] = set()
        if pref:
            user_tags.update(pref.explicit_tags or [])
            user_tags.update(pref.implicit_tags or [])

        if not user_tags:
            # Cold-start: return newest books
            return await self._cold_start(top_n), "newest books (cold start)"

        # Fetch borrowed book IDs to exclude
        borrowed_ids = await self._get_borrowed_ids(user.id)

        books_result = await self._db.execute(select(Book))
        all_books = books_result.scalars().all()

        # Build vocabulary
        vocab = sorted({tag for b in all_books if b.tags for tag in b.tags})
        if not vocab:
            return await self._cold_start(top_n), "newest books (no tags)"

        vocab_index = {tag: i for i, tag in enumerate(vocab)}
        user_vec = self._tags_to_vector(user_tags, vocab_index)

        scored: list[tuple[float, Book]] = []
        for book in all_books:
            if book.id in borrowed_ids:
                continue
            book_vec = self._tags_to_vector(set(book.tags or []), vocab_index)
            score = self._cosine_similarity(user_vec, book_vec)
            if score > 0:
                scored.append((score, book))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_books = [b for _, b in scored[:top_n]]
        basis = f"your interests: {', '.join(sorted(user_tags)[:5])}"
        return top_books, basis

    # ── Collaborative Filtering ──────────────────────────────────────────

    async def _collaborative(self, user: User, top_n: int) -> tuple[list[BookResponse], str]:
        """
        Item-based collaborative filtering via borrow co-occurrence.

        Strategy:
        1. Build user→books borrow map from full history.
        2. Find all users who borrowed at least one book in common with target user.
        3. Score candidate books by number of co-borrowers (popularity among similar users).
        4. Exclude already-borrowed books. Return top-N.
        """
        borrows_result = await self._db.execute(select(BookBorrow))
        all_borrows = borrows_result.scalars().all()

        user_books: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for b in all_borrows:
            user_books[b.user_id].add(b.book_id)

        my_books = user_books.get(user.id, set())
        if not my_books:
            return await self._cold_start(top_n), "newest books (no history)"

        # Find similar users
        similar_users = {
            uid for uid, books in user_books.items()
            if uid != user.id and books & my_books
        }

        if not similar_users:
            return await self._cold_start(top_n), "newest books (no similar users)"

        # Score candidate books
        candidate_scores: Counter = Counter()
        for uid in similar_users:
            for book_id in user_books[uid] - my_books:
                candidate_scores[book_id] += 1

        top_book_ids = [book_id for book_id, _ in candidate_scores.most_common(top_n)]

        books_result = await self._db.execute(
            select(Book).where(Book.id.in_(top_book_ids))
        )
        books = books_result.scalars().all()
        # Preserve ranking order
        book_map = {b.id: b for b in books}
        ordered = [book_map[bid] for bid in top_book_ids if bid in book_map]
        return ordered, "readers with similar tastes"

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _cold_start(self, top_n: int) -> list[Book]:
        result = await self._db.execute(
            select(Book).order_by(Book.created_at.desc()).limit(top_n)
        )
        return result.scalars().all()

    async def _get_borrowed_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        result = await self._db.execute(
            select(BookBorrow.book_id).where(BookBorrow.user_id == user_id)
        )
        return {row[0] for row in result.all()}

    @staticmethod
    def _tags_to_vector(tags: set[str], vocab_index: dict[str, int]) -> np.ndarray:
        vec = np.zeros(len(vocab_index))
        for tag in tags:
            if tag in vocab_index:
                vec[vocab_index[tag]] = 1.0
        return vec

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)
