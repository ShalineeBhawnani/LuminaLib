"""Book management routes: CRUD, borrow, return."""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import (
    BookMetadataRequest,
    BookResponse,
    BookUpdateRequest,
    PaginatedBooksResponse,
)
from app.services.book_service import BookService
from app.services.llm.factory import get_llm_service
from app.services.storage.factory import get_storage_service

router = APIRouter()


def _get_book_service(db: AsyncSession = Depends(get_db)) -> BookService:
    storage = get_storage_service(settings.STORAGE_BACKEND)
    llm = get_llm_service(settings.LLM_BACKEND)
    return BookService(db, storage, llm)


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    metadata: str = Form(..., description="JSON string of BookMetadataRequest"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    svc: BookService = Depends(_get_book_service),
):
    """Upload a book file (PDF/TXT) with metadata. Triggers async AI summarization."""
    parsed = BookMetadataRequest(**json.loads(metadata))
    return await svc.create_book(parsed, file)


@router.get("", response_model=PaginatedBooksResponse)
async def list_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    genre: str | None = Query(None),
    author: str | None = Query(None),
    _: User = Depends(get_current_user),
    svc: BookService = Depends(_get_book_service),
):
    return await svc.list_books(page=page, page_size=page_size, genre=genre, author=author)


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: uuid.UUID,
    _: User = Depends(get_current_user),
    svc: BookService = Depends(_get_book_service),
):
    return await svc.get_book(book_id)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: uuid.UUID,
    payload: BookUpdateRequest,
    _: User = Depends(get_current_user),
    svc: BookService = Depends(_get_book_service),
):
    return await svc.update_book(book_id, payload)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: uuid.UUID,
    _: User = Depends(get_current_user),
    svc: BookService = Depends(_get_book_service),
):
    await svc.delete_book(book_id)


@router.post("/{book_id}/borrow", response_model=BookResponse)
async def borrow_book(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: BookService = Depends(_get_book_service),
):
    return await svc.borrow_book(book_id, current_user)


@router.post("/{book_id}/return", response_model=BookResponse)
async def return_book(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: BookService = Depends(_get_book_service),
):
    return await svc.return_book(book_id, current_user)
