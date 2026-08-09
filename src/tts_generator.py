"""
Text-to-speech: Fish Audio (voice cloning) via Python SDK.
"""

import logging
import random
import time

logger = logging.getLogger(__name__)

JOHNNY_VOICE_ID = "da7cfccf419840dfb273c9cb7734996c"


def generate_speech(
    text: str,
    output_path: str,
    voice: str = "zh-CN-YunyangNeural",
    speed: str = "+5%",
    openai_api_key: str = "",
    fish_audio_key: str = "",
) -> None:
    """Generate MP3 using Fish Audio Python SDK (Johnny's cloned voice)."""

    if not fish_audio_key:
        raise RuntimeError("Fish Audio API key is required")

    max_retries = 6
    for attempt in range(1, max_retries + 1):
        try:
            _fish_audio_sdk(text, output_path, fish_audio_key)
            return
        except Exception as e:
            if attempt < max_retries:
                wait = 4 * (2 ** (attempt - 1)) + random.uniform(0, 3)
                logger.warning(
                    "Fish Audio attempt %d/%d: %s, retry in %.0fs...",
                    attempt, max_retries, str(e)[:80], wait,
                )
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Fish Audio failed after {max_retries} attempts"
                ) from e


def _fish_audio_sdk(text: str, output_path: str, api_key: str) -> None:
    """Call Fish Audio via Python SDK (routes through VPN)."""
    from fishaudio import FishAudio

    client = FishAudio(api_key=api_key)
    with open(output_path, "wb") as f:
        for chunk in client.tts.stream(
            text=text,
            reference_id=JOHNNY_VOICE_ID,
            format="mp3",
            latency="balanced",
        ):
            f.write(chunk if isinstance(chunk, bytes) else chunk.data)

    import os
    size = os.path.getsize(output_path)
    logger.info("TTS generated (Fish Audio - Johnny): %s (%s bytes)", output_path, size)
