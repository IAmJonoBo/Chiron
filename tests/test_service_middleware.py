"""Tests for chiron.service.middleware module."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import Request, Response
from starlette.datastructures import Headers

from chiron.service.middleware import LoggingMiddleware, SecurityMiddleware


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware class."""

    @pytest.mark.asyncio
    async def test_logging_middleware_request_id(self) -> None:
        """Test that logging middleware adds request ID to response headers."""
        middleware = LoggingMiddleware(app=Mock())

        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.query_params = {}
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"

        # Create mock response
        mock_response = Response(content="test", status_code=200)

        # Create async call_next that returns the response
        async def call_next(request: Request) -> Response:
            return mock_response

        with patch("chiron.service.middleware.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)

            # Check that request ID was added to headers
            assert "X-Request-ID" in response.headers
            assert len(response.headers["X-Request-ID"]) == 36  # UUID format

            # Check that logging occurred
            assert mock_logger.info.call_count == 2  # Started + completed

    @pytest.mark.asyncio
    async def test_logging_middleware_logs_request_details(self) -> None:
        """Test that logging middleware logs request details."""
        middleware = LoggingMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/api/data"
        mock_request.query_params = {"filter": "active"}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"

        mock_response = Response(content="test", status_code=201)

        async def call_next(request: Request) -> Response:
            return mock_response

        with patch("chiron.service.middleware.logger") as mock_logger:
            await middleware.dispatch(mock_request, call_next)

            # Check request started log
            first_call = mock_logger.info.call_args_list[0]
            assert "Request started" in str(first_call)
            assert "method=POST" in str(first_call) or first_call[1].get("method") == "POST"

    @pytest.mark.asyncio
    async def test_logging_middleware_no_client(self) -> None:
        """Test logging middleware when client is None."""
        middleware = LoggingMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.query_params = {}
        mock_request.client = None

        mock_response = Response(content="test", status_code=200)

        async def call_next(request: Request) -> Response:
            return mock_response

        with patch("chiron.service.middleware.logger") as mock_logger:
            response = await middleware.dispatch(mock_request, call_next)
            assert response is not None
            assert mock_logger.info.called

    @pytest.mark.asyncio
    async def test_logging_middleware_logs_duration(self) -> None:
        """Test that logging middleware logs request duration."""
        middleware = LoggingMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/slow"
        mock_request.query_params = {}
        mock_request.client = None

        mock_response = Response(content="test", status_code=200)

        async def call_next(request: Request) -> Response:
            return mock_response

        with patch("chiron.service.middleware.logger") as mock_logger:
            await middleware.dispatch(mock_request, call_next)

            # Check completed log has duration
            completed_call = mock_logger.info.call_args_list[1]
            assert "duration_ms" in str(completed_call) or "duration_ms" in completed_call[1]

    @pytest.mark.asyncio
    async def test_logging_middleware_error_handling(self) -> None:
        """Test that logging middleware logs errors."""
        middleware = LoggingMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/error"
        mock_request.query_params = {}
        mock_request.client = None

        async def call_next(request: Request) -> Response:
            raise ValueError("Test error")

        with patch("chiron.service.middleware.logger") as mock_logger:
            with pytest.raises(ValueError, match="Test error"):
                await middleware.dispatch(mock_request, call_next)

            # Check that error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert "Request failed" in str(error_call)


class TestSecurityMiddleware:
    """Tests for SecurityMiddleware class."""

    @pytest.mark.asyncio
    async def test_security_middleware_adds_headers(self) -> None:
        """Test that security middleware adds security headers."""
        middleware = SecurityMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_response = Response(content="test", status_code=200)

        async def call_next(request: Request) -> Response:
            return mock_response

        response = await middleware.dispatch(mock_request, call_next)

        # Check all security headers are present
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
        assert response.headers["Content-Security-Policy"] == "default-src 'self'"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_security_middleware_removes_server_header(self) -> None:
        """Test that security middleware removes Server header."""
        middleware = SecurityMiddleware(app=Mock())

        mock_request = Mock(spec=Request)

        # Create response with Server header
        mock_response = Response(content="test", status_code=200)
        mock_response.headers["Server"] = "uvicorn"

        async def call_next(request: Request) -> Response:
            return mock_response

        response = await middleware.dispatch(mock_request, call_next)

        # Check that Server header was removed
        assert "Server" not in response.headers

    @pytest.mark.asyncio
    async def test_security_middleware_no_server_header(self) -> None:
        """Test security middleware when Server header is not present."""
        middleware = SecurityMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_response = Response(content="test", status_code=200)

        async def call_next(request: Request) -> Response:
            return mock_response

        response = await middleware.dispatch(mock_request, call_next)

        # Should not raise error if Server header is not present
        assert "Server" not in response.headers

    @pytest.mark.asyncio
    async def test_security_middleware_preserves_status_code(self) -> None:
        """Test that security middleware preserves response status code."""
        middleware = SecurityMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_response = Response(content="error", status_code=500)

        async def call_next(request: Request) -> Response:
            return mock_response

        response = await middleware.dispatch(mock_request, call_next)

        # Status code should be preserved
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_security_middleware_preserves_content(self) -> None:
        """Test that security middleware preserves response content."""
        middleware = SecurityMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        content = b"test content"
        mock_response = Response(content=content, status_code=200)

        async def call_next(request: Request) -> Response:
            return mock_response

        response = await middleware.dispatch(mock_request, call_next)

        # Content should be preserved
        assert response.body == content
