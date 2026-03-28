"""
Centralized, reusable prompt templates for all LLM interactions.
Structured as dataclasses so prompts are composable, testable, and version-controlled.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SummarizationPrompt:
    """Prompt for generating a book summary from its content."""

    SYSTEM = (
        "You are a literary analyst. Your task is to produce concise, accurate, "
        "and spoiler-aware summaries of books. Respond with only the summary — "
        "no preamble, no formatting markers."
    )

    @staticmethod
    def build(title: str, author: str, content_excerpt: str) -> str:
        return (
            f"Book Title: {title}\n"
            f"Author: {author}\n\n"
            f"Content (excerpt):\n{content_excerpt}\n\n"
            "Write a concise summary (3–5 paragraphs) covering the main themes, "
            "plot, and significance of this book."
        )


@dataclass(frozen=True)
class ReviewConsensusPrompt:
    """Prompt for synthesizing a rolling consensus from reader reviews."""

    SYSTEM = (
        "You are a literary critic aggregating reader sentiment. "
        "Produce a balanced, neutral consensus summary. "
        "Respond with only the consensus text — no bullet points, no labels."
    )

    @staticmethod
    def build(title: str, reviews: list[dict]) -> str:
        formatted = "\n".join(
            f"- Rating {r['rating']}/5: {r['body']}" for r in reviews
        )
        return (
            f"Book: {title}\n\n"
            f"Reader Reviews:\n{formatted}\n\n"
            "Synthesize these reviews into a single, balanced consensus paragraph "
            "describing overall reader sentiment, common praise, and common criticism."
        )


@dataclass(frozen=True)
class SentimentPrompt:
    """Prompt for classifying a single review's sentiment."""

    SYSTEM = (
        "You are a sentiment classifier. Respond with exactly one word: "
        "'positive', 'neutral', or 'negative'. No other output."
    )

    @staticmethod
    def build(review_body: str) -> str:
        return f"Classify the sentiment of this book review:\n\n{review_body}"
