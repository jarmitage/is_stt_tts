from __future__ import annotations

# Supported values
SUPPORTED_VOICES = {"Dora", "Karl"}
SUPPORTED_AUDIO_FORMATS = {"mp3", "wav"}
SUPPORTED_MODES = {"save", "play", "both"}

# Defaults
DEFAULT_TTS_VOICE = "Dora"
DEFAULT_AUDIO_FORMAT = "mp3"
DEFAULT_MODE = "save"
DEFAULT_OUTPUT_DIR = "."
DEFAULT_FILENAME = "output"

# Platform specifics / tools
MACOS_PLAYBACK_CMD = "afplay"
FFMPEG_CMD = "ffmpeg"

__all__ = [
    "SUPPORTED_VOICES",
    "SUPPORTED_AUDIO_FORMATS",
    "SUPPORTED_MODES",
    "DEFAULT_TTS_VOICE",
    "DEFAULT_AUDIO_FORMAT",
    "DEFAULT_MODE",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_FILENAME",
    "DEFAULT_IS_MODEL_PATH",
    "MACOS_PLAYBACK_CMD",
    "FFMPEG_CMD",
]


