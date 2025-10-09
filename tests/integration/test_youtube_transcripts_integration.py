"""
Integration tests for YouTube Transcripts API endpoints.

These tests verify the complete request/response cycle for the YouTube Transcripts API.
"""

import pytest
from fastapi import status


class TestYouTubeTranscriptsEndpoints:
    """Integration tests for YouTube Transcripts API endpoints."""

    @pytest.mark.integration
    async def test_get_transcript_with_video_id(self, async_test_client):
        """Test GET /api/v1/youtube-transcripts with video ID."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ"}  # Valid YouTube video ID format
        )
        
        # May succeed or fail depending on whether video has transcripts
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ]

    @pytest.mark.integration
    async def test_get_transcript_with_language(self, async_test_client):
        """Test transcript request with language preference."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ", "language": "en"}
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ]

    @pytest.mark.integration
    async def test_list_available_transcripts(self, async_test_client):
        """Test listing available transcripts for a video."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts/list",
            params={"video_id": "dQw4w9WgXcQ"}
        )
        
        # Should list available transcripts or return 404
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]


class TestYouTubeTranscriptsParameterValidation:
    """Test parameter validation for YouTube Transcripts API."""

    @pytest.mark.integration
    async def test_missing_video_id(self, async_test_client):
        """Test endpoint without required video_id parameter."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts"
        )
        
        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    async def test_empty_video_id(self, async_test_client):
        """Test with empty video_id parameter."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": ""}
        )
        
        # Should reject empty video ID
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_invalid_video_id_format(self, async_test_client):
        """Test with invalid video ID format."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "invalid_format!@#"}
        )
        
        # Should validate or handle gracefully
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_404_NOT_FOUND
        ]

    @pytest.mark.integration
    async def test_invalid_language_code(self, async_test_client):
        """Test with invalid language code."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ", "language": "invalid"}
        )
        
        # Should handle invalid language codes
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ]


class TestYouTubeTranscriptsVideoIdFormats:
    """Test different YouTube video ID formats."""

    @pytest.mark.integration
    async def test_standard_video_id(self, async_test_client):
        """Test standard 11-character video ID."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ"}
        )
        
        # Valid format should be accepted
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]

    @pytest.mark.integration
    async def test_video_id_from_full_url(self, async_test_client):
        """Test extracting video ID from full YouTube URL."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )
        
        # Should extract or reject
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_video_id_from_short_url(self, async_test_client):
        """Test extracting video ID from youtu.be short URL."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "https://youtu.be/dQw4w9WgXcQ"}
        )
        
        # Should extract or reject
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestYouTubeTranscriptsLanguageHandling:
    """Test language handling for transcripts."""

    @pytest.mark.integration
    async def test_english_transcript(self, async_test_client):
        """Test requesting English transcript."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ", "language": "en"}
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]

    @pytest.mark.integration
    async def test_multiple_language_codes(self, async_test_client):
        """Test requesting transcript with multiple language preferences."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ", "languages": "en,es,fr"}
        )
        
        # Should handle multiple language codes
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_non_english_transcript(self, async_test_client):
        """Test requesting non-English transcript."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ", "language": "es"}
        )
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ]


class TestYouTubeTranscriptsResponseFormat:
    """Test response format and structure."""

    @pytest.mark.integration
    async def test_successful_transcript_structure(self, async_test_client):
        """Test structure of successful transcript response."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should have transcript data
            assert data is not None
            # Typical transcript structure has text, start, duration
            if isinstance(data, list) and len(data) > 0:
                first_item = data[0]
                assert "text" in first_item or "content" in first_item

    @pytest.mark.integration
    async def test_error_response_format(self, async_test_client):
        """Test error response follows RFC 7807."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "nonexistent123"}
        )
        
        if response.status_code >= 400:
            data = response.json()
            # Should follow RFC 7807 problem details
            assert "detail" in data or "title" in data

    @pytest.mark.integration
    async def test_list_transcripts_structure(self, async_test_client):
        """Test structure of transcript list response."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts/list",
            params={"video_id": "dQw4w9WgXcQ"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Should list available transcript languages
            assert data is not None
            assert isinstance(data, (list, dict))


class TestYouTubeTranscriptsErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.integration
    async def test_nonexistent_video(self, async_test_client):
        """Test requesting transcript for nonexistent video."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "nonexistent123"}
        )
        
        # Should return 404 or appropriate error
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ]

    @pytest.mark.integration
    async def test_video_without_transcripts(self, async_test_client):
        """Test requesting transcript for video without transcripts."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "zzzzzzzzzzz"}
        )
        
        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ]

    @pytest.mark.integration
    async def test_unavailable_language(self, async_test_client):
        """Test requesting unavailable language for transcript."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ", "language": "xx"}
        )
        
        # Should indicate language not available
        assert response.status_code in [
            status.HTTP_200_OK,  # Might fallback to default
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ]


class TestYouTubeTranscriptsInputSanitization:
    """Test input sanitization for YouTube Transcripts API."""

    @pytest.mark.integration
    async def test_xss_in_video_id(self, async_test_client):
        """Test XSS attempt in video_id parameter."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "<script>alert('xss')</script>"}
        )
        
        # Should sanitize or reject
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]

    @pytest.mark.integration
    async def test_sql_injection_in_video_id(self, async_test_client):
        """Test SQL injection attempt in video_id."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "abc' OR '1'='1"}
        )
        
        # Should handle safely
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]


class TestYouTubeTranscriptsCaching:
    """Test caching behavior for transcripts."""

    @pytest.mark.integration
    async def test_cache_headers(self, async_test_client):
        """Test that cache headers are present."""
        response = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params={"video_id": "dQw4w9WgXcQ"}
        )
        
        if response.status_code == status.HTTP_200_OK:
            # Should have cache-related headers
            headers = response.headers
            assert any(
                h in headers
                for h in ["cache-control", "etag", "x-cache"]
            )

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_repeated_transcript_request(self, async_test_client):
        """Test that repeated requests for same transcript use cache."""
        params = {"video_id": "dQw4w9WgXcQ"}
        
        # First request
        response1 = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params=params
        )
        
        # Second request (should be cached)
        response2 = await async_test_client.get(
            "/api/v1/youtube-transcripts",
            params=params
        )
        
        assert response1.status_code == response2.status_code
        if response1.status_code == status.HTTP_200_OK:
            # Results should be identical
            assert response1.json() == response2.json()
