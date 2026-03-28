"""
Pydantic v2 schemas for request validation and API responses.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    username: str | None = Field(default=None, min_length=3, max_length=100)


# ── Books ─────────────────────────────────────────────────────────────────────

class BookMetadataRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field(..., min_length=1, max_length=300)
    isbn: str | None = None
    description: str | None = None
    genre: str | None = None
    published_year: int | None = Field(default=None, ge=1000, le=2100)
    tags: list[str] | None = None
    total_copies: int = Field(default=1, ge=1)


class BookUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    author: str | None = None
    description: str | None = None
    genre: str | None = None
    published_year: int | None = None
    tags: list[str] | None = None
    total_copies: int | None = Field(default=None, ge=1)


class BookResponse(BaseModel):
    id: uuid.UUID
    title: str
    author: str
    isbn: str | None
    description: str | None
    genre: str | None
    published_year: int | None
    tags: list[str] | None
    ai_summary: str | None
    ai_review_consensus: str | None
    summary_status: str
    total_copies: int
    available_copies: int
    file_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedBooksResponse(BaseModel):
    items: list[BookResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    body: str = Field(..., min_length=10)


class ReviewResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    book_id: uuid.UUID
    rating: int
    body: str
    sentiment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Analysis ──────────────────────────────────────────────────────────────────

class BookAnalysisResponse(BaseModel):
    book_id: uuid.UUID
    ai_review_consensus: str | None
    total_reviews: int
    average_rating: float | None


# ── Recommendations ──────────────────────────────────────────────────────────

class RecommendationResponse(BaseModel):
    books: list[BookResponse]
    algorithm: str
    based_on: str


# ── User Preferences ─────────────────────────────────────────────────────────

class UserPreferenceRequest(BaseModel):
    explicit_tags: list[str] = Field(..., min_length=1)


class UserPreferenceResponse(BaseModel):
    user_id: uuid.UUID
    explicit_tags: list[str] | None
    implicit_tags: list[str] | None
    avg_rating_given: float | None
    total_books_borrowed: int

    model_config = {"from_attributes": True}
