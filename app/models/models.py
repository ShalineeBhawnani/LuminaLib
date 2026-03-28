"""
ORM Models for LuminaLib.

Schema Design Decisions (see ARCHITECTURE.md for full rationale):
- UserPreference: hybrid model — explicit tags + implicit history.
- BookBorrow: tracks borrow/return lifecycle with timestamps.
- Review: gated by borrow history (enforced at service layer).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    borrows: Mapped[list["BookBorrow"]] = relationship("BookBorrow", back_populates="user")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user")
    preferences: Mapped["UserPreference | None"] = relationship("UserPreference", back_populates="user", uselist=False)


# ── Book ─────────────────────────────────────────────────────────────────────

class Book(Base):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    isbn: Mapped[str | None] = mapped_column(String(20), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    genre: Mapped[str | None] = mapped_column(String(100), index=True)
    published_year: Mapped[int | None] = mapped_column(Integer)

    # Storage: abstract key referencing the file in the configured backend
    file_storage_key: Mapped[str | None] = mapped_column(String(500))
    file_name: Mapped[str | None] = mapped_column(String(300))

    # GenAI outputs
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_review_consensus: Mapped[str | None] = mapped_column(Text)
    summary_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | processing | done | failed

    # ML feature vector (genre tags for content-based filtering)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Library mechanics
    total_copies: Mapped[int] = mapped_column(Integer, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    borrows: Mapped[list["BookBorrow"]] = relationship("BookBorrow", back_populates="book")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="book")


# ── BookBorrow ────────────────────────────────────────────────────────────────

class BookBorrow(Base):
    __tablename__ = "book_borrows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    borrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", back_populates="borrows")
    book: Mapped["Book"] = relationship("Book", back_populates="borrows")


# ── Review ────────────────────────────────────────────────────────────────────

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book_review"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(20))  # positive | neutral | negative
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    book: Mapped["Book"] = relationship("Book", back_populates="reviews")


# ── UserPreference ────────────────────────────────────────────────────────────
# Hybrid model: explicit tags the user sets + implicit data derived from borrow history.
# Stored as a single row per user; updated incrementally by background tasks.

class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Explicit: user-selected interests
    explicit_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Implicit: derived from borrow/review history
    implicit_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    avg_rating_given: Mapped[float | None] = mapped_column(Float)
    total_books_borrowed: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship("User", back_populates="preferences")
