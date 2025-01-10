from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptList, Transcript, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from app.core.auth import get_api_key
import asyncio
import logging
from youtube_transcript_api.formatters import WebVTTFormatter, SRTFormatter
import csv
import io

logger = logging.getLogger(__name__)
youtube_transcripts_router = APIRouter()

# Pydantic models
class TranslationLanguage(BaseModel):
    language: str
    language_code: str

class TranscriptItem(BaseModel):
    text: str
    start: float
    duration: float

class TranscriptResponse(BaseModel):
    video_id: str
    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool
    translation_languages: List[TranslationLanguage]
    transcript: List[TranscriptItem]

class TranscriptListResponse(BaseModel):
    transcripts: List[Dict[str, Any]]

# Helper function to fetch transcript
def fetch_transcript(video_id: str, languages: List[str] = ["en"]) -> Transcript:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        return transcript
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No transcript found for the given video ID.")
    except TranscriptsDisabled:
        raise HTTPException(status_code=403, detail="Transcripts are disabled for this video.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="The specified video is unavailable.")
    except Exception as e:
        logger.error(f"Error fetching transcript for video_id {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error while fetching transcript.")

# Endpoint to get transcript
@youtube_transcripts_router.get("/get-transcript", response_model=TranscriptResponse, summary="Get Transcript for a YouTube Video")
async def get_transcript(
    video_id: str = Query(..., description="YouTube video ID."),
    languages: Optional[List[str]] = Query(["en"], description="List of language codes in descending priority."),
    preserve_formatting: bool = Query(False, description="Preserve HTML formatting in transcripts."),
    api_key: str = Depends(get_api_key)
):
    """
    Retrieves the transcript for the specified YouTube video.
    """
    transcript_data = await asyncio.get_event_loop().run_in_executor(None, fetch_transcript, video_id, languages)
    
    # Optional formatting can be added here if needed
    transcript_items = [TranscriptItem(**item) for item in transcript_data]
    
    # Fetch transcript metadata
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    try:
        transcript_obj = transcript_list.find_transcript(languages)
    except Exception as e:
        logger.error(f"Error finding transcript for video_id {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error while processing transcript.")
    
    response = TranscriptResponse(
        video_id=transcript_obj.video_id,
        language=transcript_obj.language,
        language_code=transcript_obj.language_code,
        is_generated=transcript_obj.is_generated,
        is_translatable=transcript_obj.is_translatable,
        translation_languages=[TranslationLanguage(language=lang['language'], language_code=lang['language_code']) for lang in transcript_obj.translation_languages],
        transcript=transcript_items
    )
    
    return response

# Endpoint to list available transcripts
@youtube_transcripts_router.get("/list-transcripts", response_model=TranscriptListResponse, summary="List Available Transcripts for a YouTube Video")
async def list_transcripts(
    video_id: str = Query(..., description="YouTube video ID."),
    api_key: str = Depends(get_api_key)
):
    """
    Lists all available transcripts for the specified YouTube video.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcripts_info = []
        for transcript in transcript_list:
            transcripts_info.append({
                "video_id": transcript.video_id,
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": transcript.is_generated,
                "is_translatable": transcript.is_translatable,
                "translation_languages": transcript.translation_languages
            })
        return TranscriptListResponse(transcripts=transcripts_info)
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No transcripts found for the given video ID.")
    except TranscriptsDisabled:
        raise HTTPException(status_code=403, detail="Transcripts are disabled for this video.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="The specified video is unavailable.")
    except Exception as e:
        logger.error(f"Error listing transcripts for video_id {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error while listing transcripts.")

# Endpoint to translate transcript
@youtube_transcripts_router.get("/translate-transcript", response_model=TranscriptResponse, summary="Translate Transcript for a YouTube Video")
async def translate_transcript(
    video_id: str = Query(..., description="YouTube video ID."),
    target_language: str = Query(..., description="Target language code for translation."),
    source_languages: Optional[List[str]] = Query(["en"], description="List of source language codes."),
    api_key: str = Depends(get_api_key)
):
    """
    Translates the transcript of the specified YouTube video into the target language.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript_obj = transcript_list.find_transcript(source_languages)
        translated_transcript = transcript_obj.translate(target_language)
        transcript_data = translated_transcript.fetch()
        transcript_items = [TranscriptItem(**item) for item in transcript_data]
        
        response = TranscriptResponse(
            video_id=translated_transcript.video_id,
            language=translated_transcript.language,
            language_code=translated_transcript.language_code,
            is_generated=translated_transcript.is_generated,
            is_translatable=translated_transcript.is_translatable,
            translation_languages=[TranslationLanguage(language=lang['language'], language_code=lang['language_code']) for lang in translated_transcript.translation_languages],
            transcript=transcript_items
        )
        
        return response
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No transcript found for the given video ID.")
    except TranscriptsDisabled:
        raise HTTPException(status_code=403, detail="Transcripts are disabled for this video.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="The specified video is unavailable.")
    except Exception as e:
        logger.error(f"Error translating transcript for video_id {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error while translating transcript.")

# Endpoint to batch fetch transcripts
@youtube_transcripts_router.post("/batch-get-transcripts", response_model=List[TranscriptResponse], summary="Batch Fetch Transcripts for Multiple YouTube Videos")
async def batch_get_transcripts(
    video_ids: List[str] = Query(..., description="List of YouTube video IDs."),
    languages: Optional[List[str]] = Query(["en"], description="List of language codes in descending priority."),
    preserve_formatting: bool = Query(False, description="Preserve HTML formatting in transcripts."),
    api_key: str = Depends(get_api_key)
):
    """
    Retrieves transcripts for multiple YouTube videos.
    """
    tasks = []
    for video_id in video_ids:
        tasks.append(get_transcript(
            video_id=video_id,
            languages=languages,
            preserve_formatting=preserve_formatting,
            api_key=api_key
        ))
    
    transcripts = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions if any
    result = []
    for transcript in transcripts:
        if isinstance(transcript, Exception):
            result.append({"error": str(transcript)})
        else:
            result.append(transcript)
    
    return result

# Endpoint to format transcript
@youtube_transcripts_router.get("/format-transcript", summary="Format Transcript for a YouTube Video")
async def format_transcript(
    video_id: str = Query(..., description="YouTube video ID."),
    format_type: str = Query("json", description="Desired format type (json, txt, vtt, srt, csv)."),
    languages: Optional[List[str]] = Query(["en"], description="List of language codes in descending priority."),
    api_key: str = Depends(get_api_key)
):
    """
    Formats the transcript of the specified YouTube video into the desired format.
    """
    transcript = await get_transcript(
        video_id=video_id,
        languages=languages,
        preserve_formatting=False,
        api_key=api_key
    )
    
    formatter_response = ""
    
    if format_type == "json":
        formatter_response = TranscriptListResponse.parse_obj({"transcripts": [transcript.dict()]})
        return formatter_response
    elif format_type == "txt":
        transcript_text = "\n".join([item.text for item in transcript.transcript])
        return {"formatted_transcript": transcript_text}
    elif format_type == "vtt":
        formatter = WebVTTFormatter()
        formatted_transcript = formatter.format_transcript([item.dict() for item in transcript.transcript])
        return {"formatted_transcript": formatted_transcript}
    elif format_type == "srt":
        formatter = SRTFormatter()
        formatted_transcript = formatter.format_transcript([item.dict() for item in transcript.transcript])
        return {"formatted_transcript": formatted_transcript}
    elif format_type == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Start', 'Duration', 'Text'])
        for item in transcript.transcript:
            writer.writerow([item.start, item.duration, item.text])
        formatted_transcript = output.getvalue()
        return {"formatted_transcript": formatted_transcript}
    else:
        raise HTTPException(status_code=400, detail="Invalid format type specified.")