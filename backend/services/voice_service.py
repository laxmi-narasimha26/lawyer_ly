"""
Voice Input/Output Service with Legal Terminology Recognition
Supports Whisper (OpenAI) for transcription and ElevenLabs for TTS
"""
import asyncio
import aiohttp
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog
from config import settings

logger = structlog.get_logger(__name__)


class VoiceService:
    """
    Voice input/output service for legal AI

    Features:
    - Speech-to-text with Whisper API
    - Text-to-speech with ElevenLabs
    - Legal terminology recognition and correction
    - Multi-language support
    """

    def __init__(self):
        self.whisper_endpoint = "https://api.openai.com/v1/audio/transcriptions"
        self.elevenlabs_endpoint = "https://api.elevenlabs.io/v1/text-to-speech"

        # Legal terminology dictionary for post-processing
        self.legal_terms = {
            "eye PC": "IPC",
            "eye P C": "IPC",
            "cr PC": "CrPC",
            "see PC": "CPC",
            "section tree sixty": "Section 360",
            "article tree seventy": "Article 370",
            "habeas corpus": "habeas corpus",
            "mandamus": "mandamus",
            "certiorari": "certiorari",
            "quo warranto": "quo warranto",
            "prohibition": "prohibition"
        }

    async def transcribe_audio(
        self,
        audio_data: bytes,
        audio_format: str = "wav",
        language: str = "en",
        legal_context: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text using Whisper API

        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (wav, mp3, m4a, etc.)
            language: Language code (en, hi, etc.)
            legal_context: Apply legal terminology correction

        Returns:
            Transcription result with text and confidence
        """
        try:
            # Get API key
            api_key = getattr(settings, 'OPENAI_API_KEY', None)

            if not api_key:
                raise ValueError("OpenAI API key not configured")

            # Prepare form data
            form_data = aiohttp.FormData()
            form_data.add_field('file',
                              audio_data,
                              filename=f'audio.{audio_format}',
                              content_type=f'audio/{audio_format}')
            form_data.add_field('model', 'whisper-1')
            form_data.add_field('language', language)
            form_data.add_field('response_format', 'verbose_json')

            # Make request
            headers = {
                "Authorization": f"Bearer {api_key}"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.whisper_endpoint,
                    headers=headers,
                    data=form_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        text = result.get('text', '')

                        # Apply legal terminology correction
                        if legal_context:
                            text = self._correct_legal_terms(text)

                        logger.info(f"Audio transcribed successfully: {len(text)} characters")

                        return {
                            "text": text,
                            "language": result.get('language', language),
                            "duration": result.get('duration', 0),
                            "segments": result.get('segments', []),
                            "confidence": self._calculate_confidence(result)
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Whisper API error: {response.status} - {error_text}")
                        raise Exception(f"Transcription failed: {response.status}")

        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            raise

    def _correct_legal_terms(self, text: str) -> str:
        """Apply legal terminology corrections to transcribed text"""

        corrected = text

        for incorrect, correct in self.legal_terms.items():
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(incorrect), re.IGNORECASE)
            corrected = pattern.sub(correct, corrected)

        return corrected

    def _calculate_confidence(self, whisper_result: Dict[str, Any]) -> float:
        """Calculate overall confidence score from Whisper result"""

        segments = whisper_result.get('segments', [])

        if not segments:
            return 0.9  # Default confidence

        # Average confidence from segments if available
        confidences = []
        for segment in segments:
            if 'confidence' in segment:
                confidences.append(segment['confidence'])

        if confidences:
            return sum(confidences) / len(confidences)
        else:
            return 0.9

    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "default",
        model: str = "eleven_monolingual_v1",
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ) -> bytes:
        """
        Convert text to speech using ElevenLabs API

        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            model: TTS model to use
            stability: Voice stability (0-1)
            similarity_boost: Voice similarity boost (0-1)

        Returns:
            Audio data as bytes (MP3)
        """
        try:
            # Get API key
            api_key = getattr(settings, 'ELEVENLABS_API_KEY', None)

            if not api_key:
                logger.warning("ElevenLabs API key not configured, TTS unavailable")
                raise ValueError("ElevenLabs API key not configured")

            # Use default professional voice if none specified
            if voice_id == "default":
                voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel (professional female voice)

            endpoint = f"{self.elevenlabs_endpoint}/{voice_id}"

            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }

            payload = {
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        logger.info(f"Speech synthesized: {len(audio_data)} bytes")
                        return audio_data
                    else:
                        error_text = await response.text()
                        logger.error(f"ElevenLabs API error: {response.status} - {error_text}")
                        raise Exception(f"TTS failed: {response.status}")

        except Exception as e:
            logger.error(f"Speech synthesis error: {str(e)}")
            raise

    async def transcribe_with_speaker_diarization(
        self,
        audio_data: bytes,
        audio_format: str = "wav"
    ) -> Dict[str, Any]:
        """
        Advanced transcription with speaker diarization
        Useful for court proceedings, depositions, etc.
        """
        # This would require additional processing or services like AssemblyAI
        logger.info("Speaker diarization requested - using Whisper + post-processing")

        # Get basic transcription
        result = await self.transcribe_audio(audio_data, audio_format)

        # Add speaker diarization (placeholder - would need specialized service)
        result['speakers'] = [
            {
                "speaker": "Speaker 1",
                "segments": []
            }
        ]

        return result

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages for voice recognition"""

        return [
            {"code": "en", "name": "English"},
            {"code": "hi", "name": "Hindi"},
            {"code": "ta", "name": "Tamil"},
            {"code": "te", "name": "Telugu"},
            {"code": "mr", "name": "Marathi"},
            {"code": "bn", "name": "Bengali"},
            {"code": "gu", "name": "Gujarati"},
            {"code": "kn", "name": "Kannada"},
            {"code": "ml", "name": "Malayalam"},
            {"code": "pa", "name": "Punjabi"}
        ]

    def get_available_voices(self) -> List[Dict[str, str]]:
        """Get list of available TTS voices"""

        return [
            {
                "id": "21m00Tcm4TlvDq8ikWAM",
                "name": "Rachel (Professional Female)",
                "gender": "female",
                "accent": "American"
            },
            {
                "id": "AZnzlk1XvdvUeBnXmlld",
                "name": "Domi (Confident Female)",
                "gender": "female",
                "accent": "American"
            },
            {
                "id": "ErXwobaYiN019PkySvjV",
                "name": "Antoni (Well-rounded Male)",
                "gender": "male",
                "accent": "American"
            },
            {
                "id": "VR6AewLTigWG4xSOukaG",
                "name": "Arnold (Crisp Male)",
                "gender": "male",
                "accent": "American"
            }
        ]


# Global instance
voice_service = VoiceService()
