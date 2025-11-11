"""
Minimal Icelandic TTS/STT CLI using Fire.

Subcommands:
- tts: Icelandic TTS via Icespeak (voices: Dora, Karl)
- stt: Icelandic STT via mlx_whisper (local IS model)

Usage examples:
- TTS (Dora):
  is-speech tts --text 'Halló heimur' --voice Dora --mode save

 - TTS (Karl):
  is-speech tts --input_file note.txt --voice Karl --output_dir out --filename greeting

 - TTS (play and save using comma-list):
  is-speech tts --text 'Halló' --voice Dora --mode 'play,save'

 - STT (print transcript):
  is-speech stt --audio_file sample.mp3

 - STT (save transcript):
  is-speech stt --audio_file sample.mp3 --output_file sample.txt
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Any, Iterable
import tempfile
from uuid import uuid4

from .consts import (
    SUPPORTED_VOICES,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_MODES,
    DEFAULT_TTS_VOICE,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_MODE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_FILENAME,
    DEFAULT_IS_MODEL_PATH,
    MACOS_PLAYBACK_CMD,
    FFMPEG_CMD,
)

def _validate_voice(voice: str) -> str:
    normalized = (voice or DEFAULT_TTS_VOICE).strip()
    lowered = normalized.lower()
    if lowered in {v.lower() for v in SUPPORTED_VOICES}:
        # Return canonical casing from SUPPORTED_VOICES
        return next(v for v in SUPPORTED_VOICES if v.lower() == lowered)
    raise ValueError(f"voice must be one of: {', '.join(sorted(SUPPORTED_VOICES))}")


def _validate_mode(mode: str) -> str:
    normalized = (mode or DEFAULT_MODE).strip().lower()
    if normalized not in {m.lower() for m in SUPPORTED_MODES}:
        raise ValueError(f"mode must be one of: {', '.join(sorted(SUPPORTED_MODES))}")
    return normalized


def _parse_modes(mode_arg: Any) -> set[str]:
    """
    Parse mode argument which may be:
    - a string: "save", "play", "both", or comma-separated like "play,save"
    - an iterable of strings (e.g., tuple/list from Fire): ("play","save")
    Returns a normalized set of modes containing any of {"save","play"}.
    Accepts "both" as an alias for {"save","play"} for backward compatibility.
    """
    def normalize_item(item: str) -> set[str]:
        val = (item or "").strip().lower()
        if not val:
            return set()
        if val == "both":
            return {"save", "play"}
        if val in {"save", "play"}:
            return {val}
        if val in {m.lower() for m in SUPPORTED_MODES}:
            return {val}
        raise ValueError(f"mode must be one or more of: {', '.join(sorted(SUPPORTED_MODES))}")

    if mode_arg is None:
        return {DEFAULT_MODE}

    if isinstance(mode_arg, str):
        parts = [p for p in (mode_arg.split(",") if "," in mode_arg else [mode_arg])]
        result: set[str] = set()
        for p in parts:
            result |= normalize_item(p)
        return (result or {DEFAULT_MODE}) if result else {DEFAULT_MODE}

    if isinstance(mode_arg, Iterable):
        result: set[str] = set()
        for item in mode_arg:
            if isinstance(item, str):
                result |= normalize_item(item)
            else:
                raise ValueError("mode iterable must contain strings")
        if not result:
            return {DEFAULT_MODE}
        canonical = set()
        for v in result:
            if v == "both":
                canonical |= {"save", "play"}
            elif v in {"save", "play"}:
                canonical.add(v)
        if not canonical:
            raise ValueError("mode must include at least one of: save, play")
        return canonical

    raise ValueError("Invalid mode value; expected string or iterable of strings")


def _validate_audio_format(audio_format: str) -> str:
    normalized = (audio_format or DEFAULT_AUDIO_FORMAT).strip().lower()
    if normalized not in {f.lower() for f in SUPPORTED_AUDIO_FORMATS}:
        raise ValueError(
            f"audio_format must be one of: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
        )
    return normalized


def _read_text_input(text: Optional[str], input_file: Optional[str]) -> str:
    if text:
        return text
    if input_file:
        return Path(input_file).expanduser().read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    raise ValueError("No text provided. Use --text, --input_file, or pipe via stdin.")


def _play_audio(filepath: Path) -> None:
    try:
        if sys.platform == "darwin" and shutil.which(MACOS_PLAYBACK_CMD):
            subprocess.run([MACOS_PLAYBACK_CMD, str(filepath)], check=False)
        else:
            print("Playback not supported (requires macOS 'afplay'). Skipping play.")
    except Exception as exc:
        print(f"Playback failed: {exc}")


def _extract_transcript_text(result: Any) -> str:
    if isinstance(result, dict):
        if "text" in result and isinstance(result["text"], str):
            return result["text"]
        return json.dumps(result, ensure_ascii=False, indent=2)
    if hasattr(result, "text") and isinstance(getattr(result, "text"), str):
        return getattr(result, "text")
    if isinstance(result, (list, tuple)):
        try:
            return " ".join(str(x) for x in result)
        except Exception:
            return json.dumps(result, ensure_ascii=False)
    if isinstance(result, str):
        return result
    return str(result)


class ISCLI:
    def tts(
        self,
        text: Optional[str] = None,
        input_file: Optional[str] = None,
        voice: str = DEFAULT_TTS_VOICE,
        audio_format: str = DEFAULT_AUDIO_FORMAT,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        filename: str = DEFAULT_FILENAME,
        mode: Any = DEFAULT_MODE,
    ) -> None:
        """
        Icelandic TTS using Icespeak.

        Args:
            text: Direct text input. Mutually exclusive with input_file; stdin supported.
            input_file: Path to a text/markdown file.
            voice: 'Dora' or 'Karl'. Default: 'Dora'.
            audio_format: 'mp3' or 'wav'. Default: 'mp3'.
            output_dir: Directory to write the audio file. Default: current directory.
            filename: Base filename without extension. Default: 'output'.
            mode: One or more of 'save', 'play'. You can pass:
                  - a single value: 'save' or 'play'
                  - 'both' (back-compat alias for 'play'+'save')
                  - a comma-list: 'play,save'
                  - an iterable (e.g., --mode play,save parsed by Fire as tuple)
                  Default: 'save'.
        """
        from icespeak import TTSOptions, tts_to_file

        selected_voice = _validate_voice(voice)
        selected_modes = _parse_modes(mode)
        selected_format = _validate_audio_format(audio_format)

        text_content = _read_text_input(text, input_file)

        tts_out = tts_to_file(
            text_content,
            TTSOptions(
                text_format="text",
                audio_format=selected_format,
                voice=selected_voice,
            ),
            transcribe=True,
        )

        src_path = Path(getattr(tts_out, "file", ""))
        if not src_path:
            raise RuntimeError("Icespeak did not return an output file path.")

        do_save = "save" in selected_modes
        do_play = "play" in selected_modes

        dest_path: Optional[Path] = None
        if do_save:
            dest_dir = Path(output_dir).expanduser()
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{filename}.{selected_format}"
            try:
                if src_path.resolve() != dest_path.resolve():
                    if dest_path.exists():
                        dest_path.unlink()
                    shutil.move(str(src_path), str(dest_path))
            finally:
                pass

        normalized_text = getattr(tts_out, "text", "")
        if do_save and dest_path is not None:
            print(f"Saved: {dest_path}")
        if normalized_text:
            print(f"Text (normalized by Icespeak): {normalized_text}")

        if do_play:
            path_to_play = dest_path if (do_save and dest_path is not None) else src_path
            try:
                _play_audio(path_to_play)
            finally:
                if not do_save:
                    try:
                        if src_path.exists():
                            src_path.unlink()
                    except Exception:
                        pass

    def stt(
        self,
        audio_file: str,
        model_path: str = DEFAULT_IS_MODEL_PATH,
        output_file: Optional[str] = None,
    ) -> None:
        """
        Icelandic STT using mlx_whisper.

        Args:
            audio_file: Path to audio file (e.g. .mp3, .wav).
            model_path: Path or HF repo to mlx whisper IS model.
            output_file: If set, write transcript to this file; otherwise print to stdout.
        """
        import mlx_whisper

        audio_path = Path(audio_file).expanduser()
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        prepared_path, tmp_to_cleanup = self._maybe_convert_m4a_to_wav_ffmpeg(audio_path)
        try:
            result = mlx_whisper.transcribe(
                str(prepared_path),
                path_or_hf_repo=str(Path(model_path).expanduser()),
            )
        finally:
            if tmp_to_cleanup and tmp_to_cleanup.exists():
                try:
                    tmp_to_cleanup.unlink()
                except Exception:
                    pass
        transcript = _extract_transcript_text(result).strip()

        if output_file:
            out_path = Path(output_file).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(transcript + "\n", encoding="utf-8")
            print(f"Wrote transcript: {out_path}")
        else:
            print(transcript)

    def _maybe_convert_m4a_to_wav_ffmpeg(self, audio_path: Path) -> tuple[Path, Optional[Path]]:
        """
        If input is .m4a and ffmpeg is available, convert to a temporary .wav
        and return (converted_path, temp_path_to_cleanup).
        Otherwise return (audio_path, None).
        """
        if audio_path.suffix.lower() != ".m4a":
            return audio_path, None

        if shutil.which(FFMPEG_CMD):
            tmp_dir = Path(tempfile.gettempdir())
            tmp_wav = tmp_dir / f"is_speech_cli_{uuid4().hex}.wav"
            try:
                tmp_wav.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            # Convert to mono, 16kHz, PCM 16-bit WAV for robust STT
            subprocess.run(
                [
                    FFMPEG_CMD, "-y",
                    "-i", str(audio_path),
                    "-ac", "1",
                    "-ar", "16000",
                    "-c:a", "pcm_s16le",
                    str(tmp_wav),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return tmp_wav, tmp_wav

        print("Input is .m4a but 'ffmpeg' not available; attempting direct decode with mlx_whisper.")
        return audio_path, None


def main():
    import fire

    fire.Fire(ISCLI)


if __name__ == "__main__":
    main()


