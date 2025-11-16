import os
import base64
import io
import wave
import asyncio
from typing import Optional
from openai import AsyncOpenAI
from src.log import logger


class AudioProvider:
    """
    Provider for OpenAI audio processing using gpt-audio model with v1/completions API.
    
    Note: This is a flexible implementation based on the expected API format.
    The exact format for gpt-audio with v1/completions may need adjustments
    when the full API specification is available.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_KEY")
        
        if not self.api_key:
            logger.warning("No OpenAI API key provided for audio processing")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)
            logger.info("Audio provider initialized with OpenAI client")
    
    async def process_audio(self, audio_data: bytes) -> Optional[bytes]:
        """
        Process audio through OpenAI's gpt-audio model using completions API.
        
        Args:
            audio_data: Audio data in WAV format
            
        Returns:
            Audio response in WAV format, or None if processing fails
        """
        if not self.client:
            logger.error("AudioProvider not initialized - no API key")
            return None
        
        try:
            # Convert audio to base64 for API transmission
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            logger.info(f"Sending {len(audio_data)} bytes of audio to OpenAI gpt-audio model")
            
            # Call OpenAI completions API with gpt-audio model
            try:
                response = await self._call_completions_api(audio_base64)
                return response
            except Exception as e:
                logger.debug(f"Approach 1 failed: {e}")
                return None
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return None

    async def _call_completions_api(self, audio_base64: str) -> Optional[bytes]:
        response = await self.client.chat.completions.create(
            model="gpt-audio-mini",
            modalities=["text","audio"],
            audio={"voice": "shimmer","format": "wav"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_base64,
                                "format": "wav"
                            }
                        }
                    ]
                },
            ]
        )

        return base64.b64decode(response.choices[0].message.audio.data)
        
    
    def _extract_audio_from_response(self, response: dict) -> Optional[bytes]:
        """
        Extract audio data from API response.
        Tries multiple possible response formats.
        """
        # Format 1: Direct audio field
        if 'audio' in response:
            try:
                return base64.b64decode(response['audio'])
            except Exception:
                pass
        
        # Format 2: Nested in output
        if 'output' in response:
            output = response['output']
            if isinstance(output, dict) and 'audio' in output:
                try:
                    return base64.b64decode(output['audio'])
                except Exception:
                    pass
        
        # Format 3: In choices array
        if 'choices' in response and len(response['choices']) > 0:
            choice = response['choices'][0]
            
            # Check various fields
            for field in ['audio', 'audio_output', 'data']:
                if field in choice:
                    try:
                        return base64.b64decode(choice[field])
                    except Exception:
                        pass
            
            # Check if text contains audio encoding
            if 'text' in choice:
                text = choice['text']
                if text.startswith("[AUDIO:") and text.endswith("]"):
                    try:
                        return base64.b64decode(text[7:-1])
                    except Exception:
                        pass
        
        return None


# Create singleton instance
_audio_provider_instance = None


def get_audio_provider(api_key: Optional[str] = None) -> AudioProvider:
    """Get or create the audio provider singleton"""
    global _audio_provider_instance
    
    if _audio_provider_instance is None:
        _audio_provider_instance = AudioProvider(api_key)
    
    return _audio_provider_instance

