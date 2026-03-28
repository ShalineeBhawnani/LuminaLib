"""
Book service: CRUD, borrow/return mechanics, file ingestion.
Background tasks for async AI summarization are dispatched here.
"""

import asyncio
import math
import uuid
from typing import Any

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.models import Book, BookBorrow, User, UserPreference
from app.schemas.schemas import (
    BookMetadataRequest,
    BookResponse,
    BookUpdateRequest,
    PaginatedBooksResponse,
)
from app.services.llm.base import BaseLLMService
from app.services.storage.base import BaseStorageService
from app.tasks.background_tasks import run_book_summarization


class BookService:
    def __init__(
        self,
        db: AsyncSession,
        storage: BaseStorageService,
        llm: BaseLLMService,
    ) -> None:
        self._db = db
        self._storage = storage
        self._llm = llm

    # ── Create ────────────────────────────────────────────────────────────

    async def create_book(self, metadata: BookMetadataRequest, file: UploadFile) -> Book:
        self._validate_file(file)

        content = await file.read()
        storage_key = f"books/{uuid.uuid4()}/{file.filename}"
        await self._storage.upload(key=storage_key, data=content, content_type=file.content_type)

        book = Book(
            title=metadata.title,
            author=metadata.author,
            isbn=metadata.isbn,
            description=metadata.description,
            genre=metadata.genre,
            published_year=metadata.published_year,
            tags=metadata.tags,
            total_copies=metadata.total_copies,
            available_copies=metadata.total_copies,
            file_storage_key=storage_key,
            file_name=file.filename,
            summary_status="pending",
        )
        self._db.add(book)
        await self._db.flush()

        # Fire-and-forget background summarization
        book_id = book.id
        asyncio.create_task(
            run_book_summarization(book_id=book_id, storage=self._storage, llm=self._llm)
        )

        return book

    # ── Read ──────────────────────────────────────────────────────────────

    async def get_book(self, book_id: uuid.UUID) -> Book:
        result = await self._db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise NotFoundError("Book")
        return book

    async def list_books(
        self, *, page: int, page_size: int, genre: str | None, author: str | None
    ) -> PaginatedBooksResponse:
        query = select(Book)
        if genre:
            query = query.where(Book.genre.ilike(f"%{genre}%"))
        if author:
            query = query.where(Book.author.ilike(f"%{author}%"))

        total_result = await self._db.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar_one()

        query = query.offset((page - 1) * page_size).limit(page_size).order_by(Book.created_at.desc())
        result = await self._db.execute(query)
        books = result.scalars().all()

        return PaginatedBooksResponse(
            items=books,
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )

    # ── Update ────────────────────────────────────────────────────────────

    async def update_book(self, book_id: uuid.UUID, payload: BookUpdateRequest) -> Book:
        book = await self.get_book(book_id)
        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(book, field, value)
        self._db.add(book)
        await self._db.flush()
        return book

    # ── Delete ────────────────────────────────────────────────────────────

    async def delete_book(self, book_id: uuid.UUID) -> None:
        book = await self.get_book(book_id)
        if book.file_storage_key:
            await self._storage.delete(book.file_storage_key)
        await self._db.delete(book)

    # ── Borrow / Return ───────────────────────────────────────────────────

    async def borrow_book(self, book_id: uuid.UUID, user: User) -> Book:
        book = await self.get_book(book_id)

        if book.available_copies < 1:
            raise ConflictError("No copies available for borrowing.")

        # Check user doesn't already have an active borrow
        existing = await self._db.execute(
            select(BookBorrow).where(
                BookBorrow.book_id == book_id,
                BookBorrow.user_id == user.id,
                BookBorrow.is_active == True,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("You already have this book borrowed.")

        borrow = BookBorrow(user_id=user.id, book_id=book_id)
        self._db.add(borrow)

        book.available_copies -= 1
        self._db.add(book)

        # Update implicit preferences
        await self._update_implicit_preferences(user, book)

        await self._db.flush()
        return book

    async def return_book(self, book_id: uuid.UUID, user: User) -> Book:
        book = await self.get_book(book_id)

        result = await self._db.execute(
            select(BookBorrow).where(
                BookBorrow.book_id == book_id,
                BookBorrow.user_id == user.id,
                BookBorrow.is_active == True,
            )
        )
        borrow = result.scalar_one_or_none()
        if not borrow:
            raise NotFoundError("Active borrow record")

        from datetime import datetime, timezone
        borrow.is_active = False
        borrow.returned_at = datetime.now(timezone.utc)
        self._db.add(borrow)

        book.available_copies = min(book.available_copies + 1, book.total_copies)
        self._db.add(book)

        await self._db.flush()
        return book

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _validate_file(file: UploadFile) -> None:
        allowed = {"application/pdf", "text/plain"}
        if file.content_type not in allowed:
            raise ValidationError("Only PDF and TXT files are supported.")

    async def _update_implicit_preferences(self, user: User, book: Book) -> None:
        """Increment implicit tag counts when a user borrows a book."""
        result = await self._db.execute(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        pref = result.scalar_one_or_none()
        if not pref:
            pref = UserPreference(user_id=user.id, implicit_tags=[], total_books_borrowed=0)
            self._db.add(pref)

        pref.total_books_borrowed = (pref.total_books_borrowed or 0) + 1

        if book.tags:
            existing = set(pref.implicit_tags or [])
            existing.update(book.tags)
            pref.implicit_tags = list(existing)

        self._db.add(pref)
