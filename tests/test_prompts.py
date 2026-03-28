"""
Tests for structured LLM prompt builders.
Ensures prompts contain all required context and no regressions.
"""

from app.services.llm.prompts import ReviewConsensusPrompt, SentimentPrompt, SummarizationPrompt


def test_summarization_prompt_contains_title_and_author():
    prompt = SummarizationPrompt.build(
        title="Dune",
        author="Frank Herbert",
        content_excerpt="A desert planet called Arrakis...",
    )
    assert "Dune" in prompt
    assert "Frank Herbert" in prompt
    assert "Arrakis" in prompt


def test_review_consensus_prompt_contains_all_reviews():
    reviews = [
        {"rating": 5, "body": "Absolutely brilliant."},
        {"rating": 2, "body": "Quite boring."},
    ]
    prompt = ReviewConsensusPrompt.build(title="1984", reviews=reviews)
    assert "1984" in prompt
    assert "brilliant" in prompt
    assert "boring" in prompt


def test_sentiment_prompt_contains_review_body():
    prompt = SentimentPrompt.build("This book changed my life.")
    assert "changed my life" in prompt


def test_system_prompts_are_non_empty():
    assert len(SummarizationPrompt.SYSTEM) > 10
    assert len(ReviewConsensusPrompt.SYSTEM) > 10
    assert len(SentimentPrompt.SYSTEM) > 10
