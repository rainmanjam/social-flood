"""
YouTube Transcripts Service.

This module handles all business logic for fetching and processing
YouTube video transcripts, keeping the API router thin.

Updated for youtube-transcript-api v1.x API compatibility.
"""
import logging
import asyncio
import csv
import io
from typing import List, Optional, Dict, Any

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable
)
from youtube_transcript_api.formatters import WebVTTFormatter, SRTFormatter
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Module-level API instance for reuse (v1.x uses instance methods)
_youtube_api = YouTubeTranscriptApi()


class YouTubeTranscriptsService:
    """Service class for YouTube transcript operations."""

    @staticmethod
    def fetch_transcript(video_id: str, languages: List[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            languages: List of language codes in descending priority

        Returns:
            List of transcript items with text, start, and duration

        Raises:
            HTTPException: If transcript cannot be fetched
        """
        if languages is None:
            languages = ["en"]

        try:
            # v1.x API: use instance method fetch() instead of class method get_transcript()
            fetched = _youtube_api.fetch(video_id, languages=tuple(languages))
            # Return raw data format for compatibility
            return fetched.to_raw_data()
        except NoTranscriptFound:
            raise HTTPException(
                status_code=404,
                detail="No transcript found for the given video ID."
            )
        except TranscriptsDisabled:
            raise HTTPException(
                status_code=403,
                detail="Transcripts are disabled for this video."
            )
        except VideoUnavailable:
            raise HTTPException(
                status_code=404,
                detail="The specified video is unavailable."
            )
        except Exception as e:
            logger.error(f"Error fetching transcript for video_id {video_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error while fetching transcript."
            )

    @staticmethod
    async def fetch_transcript_async(
        video_id: str,
        languages: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Asynchronously fetch transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            languages: List of language codes in descending priority

        Returns:
            List of transcript items
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            YouTubeTranscriptsService.fetch_transcript,
            video_id,
            languages
        )

    @staticmethod
    def list_available_transcripts(video_id: str) -> List[Dict[str, Any]]:
        """
        List all available transcripts for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            List of transcript metadata dictionaries

        Raises:
            HTTPException: If transcripts cannot be listed
        """
        try:
            # v1.x API: use instance method list() instead of class method list_transcripts()
            transcript_list = _youtube_api.list(video_id)
            transcripts_info = []
            for transcript in transcript_list:
                # v1.x API: translation_languages contains objects with attributes
                translation_langs = [
                    {"language": lang.language, "language_code": lang.language_code}
                    for lang in transcript.translation_languages
                ]
                transcripts_info.append({
                    "video_id": transcript.video_id,
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "is_translatable": transcript.is_translatable,
                    "translation_languages": translation_langs
                })
            return transcripts_info
        except NoTranscriptFound:
            raise HTTPException(
                status_code=404,
                detail="No transcripts found for the given video ID."
            )
        except TranscriptsDisabled:
            raise HTTPException(
                status_code=403,
                detail="Transcripts are disabled for this video."
            )
        except VideoUnavailable:
            raise HTTPException(
                status_code=404,
                detail="The specified video is unavailable."
            )
        except Exception as e:
            logger.error(f"Error listing transcripts for video_id {video_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error while listing transcripts."
            )

    @staticmethod
    def get_transcript_metadata(video_id: str, languages: List[str] = None):
        """
        Get transcript metadata for a video.

        Args:
            video_id: YouTube video ID
            languages: List of language codes to find

        Returns:
            Transcript object with metadata

        Raises:
            HTTPException: If metadata cannot be retrieved
        """
        if languages is None:
            languages = ["en"]

        try:
            # v1.x API: use instance method list()
            transcript_list = _youtube_api.list(video_id)
            return transcript_list.find_transcript(languages)
        except Exception as e:
            logger.error(f"Error finding transcript for video_id {video_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error while processing transcript."
            )

    @staticmethod
    def translate_transcript(
        video_id: str,
        target_language: str,
        source_languages: List[str] = None
    ) -> Dict[str, Any]:
        """
        Translate a transcript to the target language.

        Args:
            video_id: YouTube video ID
            target_language: Target language code
            source_languages: List of source language codes

        Returns:
            Dictionary with translated transcript data and metadata

        Raises:
            HTTPException: If translation fails
        """
        if source_languages is None:
            source_languages = ["en"]

        try:
            # v1.x API: use instance method list()
            transcript_list = _youtube_api.list(video_id)
            transcript_obj = transcript_list.find_transcript(source_languages)
            translated_transcript = transcript_obj.translate(target_language)
            # v1.x API: fetch() returns FetchedTranscript, use to_raw_data() for dict format
            fetched = translated_transcript.fetch()
            transcript_data = fetched.to_raw_data()

            # v1.x API: translation_languages contains objects with attributes
            translation_langs = [
                {"language": lang.language, "language_code": lang.language_code}
                for lang in translated_transcript.translation_languages
            ]

            return {
                "video_id": fetched.video_id,
                "language": fetched.language,
                "language_code": fetched.language_code,
                "is_generated": fetched.is_generated,
                "is_translatable": translated_transcript.is_translatable,
                "translation_languages": translation_langs,
                "transcript_data": transcript_data
            }
        except NoTranscriptFound:
            raise HTTPException(
                status_code=404,
                detail="No transcript found for the given video ID."
            )
        except TranscriptsDisabled:
            raise HTTPException(
                status_code=403,
                detail="Transcripts are disabled for this video."
            )
        except VideoUnavailable:
            raise HTTPException(
                status_code=404,
                detail="The specified video is unavailable."
            )
        except Exception as e:
            logger.error(f"Error translating transcript for video_id {video_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error while translating transcript."
            )

    @staticmethod
    def format_transcript_from_raw(
        transcript_items: List[Dict[str, Any]],
        format_type: str
    ) -> str:
        """
        Format transcript items from raw data into the specified format.

        Note: This method works with raw dict data. For better formatting
        with v1.x API, use format_transcript_from_fetched() with
        FetchedTranscript objects.

        Args:
            transcript_items: List of transcript items (text, start, duration)
            format_type: Desired format (txt, csv)

        Returns:
            Formatted transcript string

        Raises:
            HTTPException: If format type is invalid or unsupported
        """
        if format_type == "txt":
            return "\n".join([item["text"] for item in transcript_items])

        elif format_type == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Start', 'Duration', 'Text'])
            for item in transcript_items:
                writer.writerow([item["start"], item["duration"], item["text"]])
            return output.getvalue()

        elif format_type in ("vtt", "srt"):
            # For vtt/srt, we recommend using format_transcript_from_video()
            # which fetches the transcript in the proper format for formatters
            raise HTTPException(
                status_code=400,
                detail=f"Use format_transcript_from_video() for {format_type} format"
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid format type specified. Use: txt, csv, vtt, or srt"
            )

    @staticmethod
    def format_transcript_from_video(
        video_id: str,
        format_type: str,
        languages: List[str] = None
    ) -> str:
        """
        Fetch and format transcript directly from a video.

        This method is preferred for vtt/srt formats as it uses the
        v1.x FetchedTranscript objects that formatters expect.

        Args:
            video_id: YouTube video ID
            format_type: Desired format (txt, vtt, srt, csv)
            languages: List of language codes in descending priority

        Returns:
            Formatted transcript string

        Raises:
            HTTPException: If format type is invalid or transcript cannot be fetched
        """
        if languages is None:
            languages = ["en"]

        try:
            # v1.x API: fetch returns FetchedTranscript
            fetched = _youtube_api.fetch(video_id, languages=tuple(languages))

            if format_type == "txt":
                return "\n".join([snippet.text for snippet in fetched.snippets])

            elif format_type == "vtt":
                formatter = WebVTTFormatter()
                # v1.x formatters work with FetchedTranscript directly
                return formatter.format_transcript(fetched)

            elif format_type == "srt":
                formatter = SRTFormatter()
                # v1.x formatters work with FetchedTranscript directly
                return formatter.format_transcript(fetched)

            elif format_type == "csv":
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Start', 'Duration', 'Text'])
                for snippet in fetched.snippets:
                    writer.writerow([snippet.start, snippet.duration, snippet.text])
                return output.getvalue()

            else:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid format type specified. Use: txt, vtt, srt, or csv"
                )

        except NoTranscriptFound:
            raise HTTPException(
                status_code=404,
                detail="No transcript found for the given video ID."
            )
        except TranscriptsDisabled:
            raise HTTPException(
                status_code=403,
                detail="Transcripts are disabled for this video."
            )
        except VideoUnavailable:
            raise HTTPException(
                status_code=404,
                detail="The specified video is unavailable."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error formatting transcript for video_id {video_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error while formatting transcript."
            )


# Singleton instance for convenience
youtube_transcripts_service = YouTubeTranscriptsService()
