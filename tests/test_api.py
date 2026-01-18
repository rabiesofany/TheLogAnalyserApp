"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from src.api.main import app
from src.models import (
    ErrorLog,
    ErrorClassification,
    FixSuggestion,
    Severity,
    Stage,
    Complexity,
    ParsedError
)


client = TestClient(app)


class TestAPI:
    """Test cases for API endpoints."""

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        assert "message" in response.json()
        assert "PLC Error Classification API" in response.json()["message"]

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @patch("src.api.main.parse_error_log")
    @patch("src.api.main.classify_error_log")
    @patch("src.api.main.generate_fix_suggestions")
    def test_classify_endpoint_success(
        self,
        mock_suggestions,
        mock_classify,
        mock_parse
    ):
        """Test successful classification."""
        # Mock returns
        mock_parse.return_value = ErrorLog(
            raw_log="test log",
            errors=[
                ParsedError(
                    error_type="TestError",
                    message="Test message",
                    stage=Stage.IEC_COMPILATION
                )
            ],
            has_cascading_errors=False
        )

        mock_classify.return_value = ErrorClassification(
            severity=Severity.BLOCKING,
            stage=Stage.IEC_COMPILATION,
            complexity=Complexity.TRIVIAL,
            reasoning="Test reasoning"
        )

        mock_suggestions.return_value = [
            FixSuggestion(
                title="Test Fix",
                description="Test description",
                root_cause="Test cause",
                code_before="before",
                code_after="after",
                confidence=0.9
            )
        ]

        # Make request
        response = client.post(
            "/classify",
            json={"error_log": "test error log"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "classification" in data
        assert "suggestions" in data
        assert "parsed_errors" in data
        assert data["classification"]["severity"] == "blocking"
        assert len(data["suggestions"]) == 1

    @patch("src.api.main.parse_error_log")
    def test_classify_endpoint_no_errors(self, mock_parse):
        """Test classification with no errors found."""
        mock_parse.return_value = ErrorLog(
            raw_log="test log",
            errors=[],
            has_cascading_errors=False
        )

        response = client.post(
            "/classify",
            json={"error_log": "test error log"}
        )

        assert response.status_code == 400
        assert "No errors found" in response.json()["detail"]

    def test_classify_endpoint_invalid_request(self):
        """Test classification with invalid request."""
        response = client.post("/classify", json={})

        assert response.status_code == 422  # Validation error
