"""
Audio processing using ffmpeg subprocess.
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_transition_sound(output_path: str, duration: float = 3.0) -> str:
    """
    Generate a soft two-tone transition chime using ffmpeg sine waves.
    Returns the path to the generated mp3.
    """
    # Two gentle sine tones: 440Hz (A4) for 0.4s, then 523Hz (C5) for 0.6s, with fade in/out
    # Creates a pleasant "ding-ding" transition sound
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration=0.4,afade=t=in:d=0.05,afade=t=out:d=0.1",
        "-f", "lavfi",
        "-i", f"sine=frequency=523:duration=0.6,afade=t=in:d=0.05,afade=t=out:d=0.15",
        "-filter_complex",
        "[0:a][1:a]concat=n=2:v=0:a=1,apad=pad_dur=1.5",
        "-b:a", "128k", output_path,
    ], check=True, capture_output=True)
    logger.info("Transition sound generated: %s", output_path)
    return output_path


def compose_segments(
    segments: list[str],
    output_path: str,
    transition_path: str = "",
    include_transition_before_first: bool = False,
    include_transition_after_last: bool = False,
) -> str:
    """
    Concatenate audio segments with optional transition sounds between them.

    segments: list of audio file paths in order
    transition_path: path to a transition sound mp3 (inserted between segments)
    """
    if not segments:
        raise ValueError("No segments to compose")

    ref_info = _probe_audio(segments[0])
    sample_rate = ref_info["sample_rate"]
    channels = ref_info["channels"]

    # Build ordered input list
    inputs_ordered: list[str] = []
    for i, seg in enumerate(segments):
        if i > 0 and transition_path and Path(transition_path).exists():
            inputs_ordered.append(str(Path(transition_path).absolute()))
        elif i == 0 and include_transition_before_first and transition_path and Path(transition_path).exists():
            inputs_ordered.append(str(Path(transition_path).absolute()))
        inputs_ordered.append(str(Path(seg).absolute()))

    if include_transition_after_last and transition_path and Path(transition_path).exists():
        inputs_ordered.append(str(Path(transition_path).absolute()))

    # Write concat file with absolute paths
    concat_file = str(Path(output_path).with_suffix(".concat.txt"))
    with open(concat_file, "w") as f:
        for p in inputs_ordered:
            f.write(f"file '{p}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-ac", str(channels),
        "-ar", sample_rate,
        "-b:a", "128k",
        output_path,
    ], check=True, capture_output=True)

    Path(concat_file).unlink(missing_ok=True)

    duration = get_audio_duration_seconds(output_path)
    logger.info("Composed podcast: %s (duration: %.1fs, %d segments)", output_path, duration, len(segments))
    return output_path


def get_audio_duration_seconds(file_path: str) -> float:
    info = _probe_audio(file_path)
    return float(info.get("duration", 0))


def _probe_audio(file_path: str) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", file_path,
    ], check=True, capture_output=True, text=True)
    info = json.loads(result.stdout)

    fmt = info.get("format", {})
    streams = info.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    return {
        "duration": float(fmt.get("duration", 0)),
        "channels": audio.get("channels", 2),
        "sample_rate": audio.get("sample_rate", "44100"),
        "codec": audio.get("codec_name", "mp3"),
    }
