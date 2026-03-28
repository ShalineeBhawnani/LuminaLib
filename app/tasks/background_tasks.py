"""
Async background tasks for AI processing.
Dispatched via asyncio.create_task() so they don't block HTTP responses.

For production scale, replace with Celery + Redis or ARQ task queue.
The interface is identical — only the dispatch mechanism changes.
"""

import logging
import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionFactory
from app.services.llm.base import BaseLLMService
from app.services.llm.prompts import ReviewConsensusPrompt, SentimentPrompt, SummarizationPrompt
from app.services.storage.base import BaseStorageService

logger = logging.getLogger(__name__)

MAX_CONTENT_CHARS = 8_000  # Trim book content to fit LLM context window


async def run_book_summarization(
    book_id: uuid.UUID,
    storage: BaseStorageService,
    llm: BaseLLMService,
) -> None:
    """
    Background task: fetch book file → generate AI summary → persist.
    Runs outside the request lifecycle; uses its own DB session.
    """
    from app.models.models import Book

    async with AsyncSessionFactory() as db:
        try:
            result = await db.execute(select(Book).where(Book.id == book_id))
            book = result.scalar_one_or_none()
            if not book or not book.file_storage_key:
                return

            book.summary_status = "processing"
            db.add(book)
            await db.commit()

            # Fetch and decode file content
            raw = await storage.download(book.file_storage_key)
            content = _extract_text(raw, book.file_name or "")

            prompt = SummarizationPrompt.build(
                title=book.title,
                author=book.author,
                content_excerpt=content[:MAX_CONTENT_CHARS],
            )
            summary = await llm.generate(prompt, system=SummarizationPrompt.SYSTEM)

            book.ai_summary = summary
            book.summary_status = "done"
            db.add(book)
            await db.commit()

            logger.info("Summarization complete for book %s", book_id)

        except Exception:
            logger.exception("Summarization failed for book %s", book_id)
            async with AsyncSessionFactory() as db2:
                result = await db2.execute(select(Book).where(Book.id == book_id))
                book = result.scalar_one_or_none()
                if book:
                    book.summary_status = "failed"
                    db2.add(book)
                    await db2.commit()


async def run_review_consensus_update(
    book_id: uuid.UUID,
    llm: BaseLLMService,
) -> None:
    """
    Background task: collect all reviews → update sentiment labels
    → regenerate rolling consensus → persist.
    """
    from app.models.models import Book, Review

    async with AsyncSessionFactory() as db:
        try:
            result = await db.execute(select(Book).where(Book.id == book_id))
            book = result.scalar_one_or_none()
            if not book:
                return

            reviews_result = await db.execute(
                select(Review).where(Review.book_id == book_id)
            )
            reviews = reviews_result.scalars().all()
            if not reviews:
                return

            # Update individual sentiment labels
            for review in reviews:
                if review.sentiment is None:
                    sentiment_prompt = SentimentPrompt.build(review.body)
                    raw = await llm.generate(sentiment_prompt, system=SentimentPrompt.SYSTEM)
                    sentiment = raw.strip().lower()
                    if sentiment not in {"positive", "neutral", "negative"}:
                        sentiment = "neutral"
                    review.sentiment = sentiment
                    db.add(review)

            await db.flush()

            # Regenerate rolling consensus
            review_dicts = [{"rating": r.rating, "body": r.body} for r in reviews]
            consensus_prompt = ReviewConsensusPrompt.build(
                title=book.title, reviews=review_dicts
            )
            consensus = await llm.generate(consensus_prompt, system=ReviewConsensusPrompt.SYSTEM)

            book.ai_review_consensus = consensus
            db.add(book)
            await db.commit()

            logger.info("Consensus updated for book %s", book_id)

        except Exception:
            logger.exception("Consensus update failed for book %s", book_id)


def _extract_text(data: bytes, filename: str) -> str:
    """Best-effort text extraction from PDF or plain text bytes."""
    if filename.lower().endswith(".pdf"):
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return data.decode("utf-8", errors="ignore")
    return data.decode("utf-8", errors="ignore")
