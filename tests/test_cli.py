import io
import sys
import types
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
import unittest

# Ensure the package src is importable without installing
BASE_DIR = Path(__file__).resolve().parents[1]  # is-speech-cli/
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from is_speech_cli import cli as cli_module  # noqa: E402


class DummyTTSOut:
    def __init__(self, file_path: Path, text: str = "") -> None:
        self.file = str(file_path)
        self.text = text


def make_icespeak_stub(temp_audio_path: Path, normalized_text: str = "normalized") -> types.ModuleType:
    m = types.ModuleType("icespeak")

    class TTSOptions:
        def __init__(self, text_format: str, audio_format: str, voice: str) -> None:
            self.text_format = text_format
            self.audio_format = audio_format
            self.voice = voice

    def tts_to_file(text: str, opts: "TTSOptions", transcribe: bool = True) -> DummyTTSOut:
        return DummyTTSOut(temp_audio_path, normalized_text)

    m.TTSOptions = TTSOptions
    m.tts_to_file = tts_to_file
    return m


def make_mlx_stub(return_text: str = "Halló") -> types.ModuleType:
    m = types.ModuleType("mlx_whisper")

    def transcribe(audio_file: str, path_or_hf_repo: str):
        return {"text": return_text}

    m.transcribe = transcribe
    return m


class TestISCLITTS(unittest.TestCase):
    def test_tts_save_and_print(self):
        iscli = cli_module.ISCLI()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # create temp source audio file that stub will "return"
            src_audio = td_path / "tmp_src.mp3"
            src_audio.write_bytes(b"")

            # stub icespeak
            sys.modules["icespeak"] = make_icespeak_stub(src_audio, normalized_text="normaliserað")

            out = io.StringIO()
            with redirect_stdout(out):
                iscli.tts(
                    text="Halló",
                    voice="Dora",
                    audio_format="mp3",
                    output_dir=str(td_path),
                    filename="out",
                    mode="save",
                )
            stdout = out.getvalue()
            dest = td_path / "out.mp3"
            self.assertTrue(dest.exists(), "Output audio file not created")
            self.assertIn("Saved:", stdout)
            self.assertIn("normaliserað", stdout)

    def test_tts_both_mode_calls_play(self):
        iscli = cli_module.ISCLI()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src_audio = td_path / "tmp_src.mp3"
            src_audio.write_bytes(b"")

            sys.modules["icespeak"] = make_icespeak_stub(src_audio)

            calls = []
            original_play = cli_module._play_audio
            try:
                def fake_play(p):
                    calls.append(str(p))
                cli_module._play_audio = fake_play

                iscli.tts(
                    text="Halló",
                    voice="Karl",
                    audio_format="mp3",
                    output_dir=str(td_path),
                    filename="x",
                    mode="both",
                )
            finally:
                cli_module._play_audio = original_play

            self.assertEqual(len(calls), 1, "Expected _play_audio to be called exactly once")

    def test_tts_invalid_voice_raises(self):
        iscli = cli_module.ISCLI()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src_audio = td_path / "tmp_src.mp3"
            src_audio.write_bytes(b"")
            sys.modules["icespeak"] = make_icespeak_stub(src_audio)
            with self.assertRaises(ValueError):
                iscli.tts(text="Halló", voice="Bogus", output_dir=str(td_path))


class TestISCLISTT(unittest.TestCase):
    def test_stt_prints_transcript(self):
        iscli = cli_module.ISCLI()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            audio = td_path / "audio.mp3"
            audio.write_bytes(b"")
            sys.modules["mlx_whisper"] = make_mlx_stub("Halló heimur")
            out = io.StringIO()
            with redirect_stdout(out):
                iscli.stt(audio_file=str(audio), model_path=str(td_path / "model"))
            stdout = out.getvalue().strip()
            self.assertIn("Halló heimur", stdout)

    def test_stt_writes_transcript_file(self):
        iscli = cli_module.ISCLI()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            audio = td_path / "audio.mp3"
            audio.write_bytes(b"")
            out_txt = td_path / "transcript.txt"
            sys.modules["mlx_whisper"] = make_mlx_stub("Halló")
            iscli.stt(audio_file=str(audio), model_path=str(td_path / "model"), output_file=str(out_txt))
            self.assertTrue(out_txt.exists(), "Transcript file not written")
            self.assertEqual(out_txt.read_text(encoding="utf-8"), "Halló\n")

    def test_stt_m4a_converts_via_helper_and_cleans_up(self):
        iscli = cli_module.ISCLI()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            audio_m4a = td_path / "audio.m4a"
            audio_m4a.write_bytes(b"")
            tmp_wav = td_path / "converted.wav"
            tmp_wav.write_bytes(b"")  # simulate ffmpeg output

            # Monkeypatch helper to avoid calling real ffmpeg
            original_helper = cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg
            try:
                def fake_helper(_self, p):
                    return tmp_wav, tmp_wav
                cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg = fake_helper
                sys.modules["mlx_whisper"] = make_mlx_stub("transcript")
                out = io.StringIO()
                with redirect_stdout(out):
                    iscli.stt(audio_file=str(audio_m4a), model_path=str(td_path / "model"))
                self.assertFalse(tmp_wav.exists(), "Temporary converted file was not cleaned up")
                self.assertIn("transcript", out.getvalue())
            finally:
                cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg = original_helper

    def test_stt_on_sample_data_files_prints(self):
        """
        Use any sample audio under data/ifa_b1/*.{mp3,wav,m4a} and ensure STT prints stub text.
        Skips if no sample files are present.
        """
        data_dir = BASE_DIR / "data" / "ifa_b1"
        if not data_dir.exists():
            self.skipTest("No sample data directory present")
        sample_files = sorted(
            [p for p in data_dir.rglob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a"}]
        )
        if not sample_files:
            self.skipTest("No sample audio files found in data/ifa_b1")

        iscli = cli_module.ISCLI()
        sys.modules["mlx_whisper"] = make_mlx_stub("SAMPLE_TRANSCRIPT")

        # Monkeypatch helper so .m4a won't invoke real ffmpeg
        original_helper = cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg
        try:
            def fake_helper(_self, p: Path):
                if p.suffix.lower() == ".m4a":
                    # create temp "converted" wav in a temp dir
                    with tempfile.TemporaryDirectory() as td:
                        tmp_wav = Path(td) / "tmp.wav"
                        tmp_wav.write_bytes(b"")
                        # return a persistent path by copying to a real tmp file we manage
                    # We cannot use context tmp here because cleanup happens after transcribe,
                    # so create a NamedTemporaryFile-like persistent path:
                    tmp_wav2 = Path(tempfile.gettempdir()) / f"converted_{p.stem}.wav"
                    tmp_wav2.write_bytes(b"")
                    return tmp_wav2, tmp_wav2
                return p, None

            cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg = fake_helper
            for audio in sample_files:
                out = io.StringIO()
                with redirect_stdout(out):
                    iscli.stt(audio_file=str(audio), model_path=str(data_dir / "model"))
                self.assertIn("SAMPLE_TRANSCRIPT", out.getvalue())
        finally:
            cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg = original_helper

    def test_stt_on_sample_data_writes_file(self):
        """
        Use the first sample audio and ensure STT writes transcript to a file.
        Skips if no sample files are present.
        """
        data_dir = BASE_DIR / "data" / "ifa_b1"
        if not data_dir.exists():
            self.skipTest("No sample data directory present")
        sample_files = sorted(
            [p for p in data_dir.rglob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a"}]
        )
        if not sample_files:
            self.skipTest("No sample audio files found in data/ifa_b1")

        iscli = cli_module.ISCLI()
        sys.modules["mlx_whisper"] = make_mlx_stub("SAMPLE_FILE")

        # Monkeypatch helper for .m4a
        original_helper = cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg
        try:
            def fake_helper(_self, p: Path):
                if p.suffix.lower() == ".m4a":
                    tmp_wav = Path(tempfile.gettempdir()) / f"converted_{p.stem}.wav"
                    tmp_wav.write_bytes(b"")
                    return tmp_wav, tmp_wav
                return p, None
            cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg = fake_helper

            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                out_txt = td_path / "out.txt"
                iscli.stt(
                    audio_file=str(sample_files[0]),
                    model_path=str(data_dir / "model"),
                    output_file=str(out_txt),
                )
                self.assertTrue(out_txt.exists(), "Transcript file not written")
                self.assertEqual(out_txt.read_text(encoding="utf-8"), "SAMPLE_FILE\n")
        finally:
            cli_module.ISCLI._maybe_convert_m4a_to_wav_ffmpeg = original_helper


if __name__ == "__main__":
    unittest.main(verbosity=2)


