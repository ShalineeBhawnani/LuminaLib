"""
Unit tests for the ML Recommendation Engine.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.services.ml.recommendation_engine import RecommendationEngine


def test_cosine_similarity_identical_vectors():
    a = np.array([1.0, 1.0, 0.0])
    b = np.array([1.0, 1.0, 0.0])
    assert RecommendationEngine._cosine_similarity(a, b) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert RecommendationEngine._cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    a = np.zeros(3)
    b = np.array([1.0, 0.0, 1.0])
    assert RecommendationEngine._cosine_similarity(a, b) == 0.0


def test_tags_to_vector():
    vocab = {"fiction": 0, "thriller": 1, "romance": 2}
    vec = RecommendationEngine._tags_to_vector({"fiction", "romance"}, vocab)
    assert vec[0] == 1.0
    assert vec[1] == 0.0
    assert vec[2] == 1.0


def test_tags_to_vector_unknown_tags():
    vocab = {"fiction": 0}
    vec = RecommendationEngine._tags_to_vector({"unknown_tag"}, vocab)
    assert vec[0] == 0.0
