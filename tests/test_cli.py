import io
import sys
import types
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import os
import json
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


def make_mlx_stub(return_text: str = "Halló", capture_list: list[str] | None = None) -> types.ModuleType:
    m = types.ModuleType("mlx_whisper")

    def transcribe(audio_file: str, path_or_hf_repo: str):
        if capture_list is not None:
            capture_list.append(audio_file)
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
    def _load_ifa_entries(self):
        data_dir = BASE_DIR / "data" / "ifa_b1"
        json_path = data_dir / "ifa_b1.json"
        if not json_path.exists():
            self.skipTest("ifa_b1.json not present")
        entries = json.loads(json_path.read_text(encoding="utf-8"))
        return data_dir, entries

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

    def test_stt_m4a_uses_ffmpeg_and_cleans_up(self):
        """
        If ffmpeg is available and an .m4a sample is present under data/ifa_b1,
        verify conversion happens (mlx receives a .wav) and the temp file is removed.
        """
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg not available on PATH")
        data_dir = BASE_DIR / "data" / "ifa_b1"
        if not data_dir.exists():
            self.skipTest("No sample data directory present")
        m4a_files = sorted([p for p in data_dir.rglob("*.m4a")])
        if not m4a_files:
            self.skipTest("No .m4a sample files found")
        audio_m4a = m4a_files[0]

        iscli = cli_module.ISCLI()
        captured = []
        sys.modules["mlx_whisper"] = make_mlx_stub("transcript", capture_list=captured)

        out = io.StringIO()
        with redirect_stdout(out):
            iscli.stt(audio_file=str(audio_m4a), model_path=str(data_dir / "model"))
        self.assertIn("transcript", out.getvalue())
        self.assertTrue(captured, "mlx_whisper.transcribe was not called")
        used_path = Path(captured[0])
        self.assertEqual(used_path.suffix.lower(), ".wav", "Expected conversion to WAV via ffmpeg")
        # temp converted file should be deleted by CLI after transcribe
        self.assertFalse(used_path.exists(), "Temporary converted WAV was not cleaned up")

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

        for audio in sample_files:
            if audio.suffix.lower() == ".m4a" and shutil.which("ffmpeg") is None:
                continue
            out = io.StringIO()
            with redirect_stdout(out):
                iscli.stt(audio_file=str(audio), model_path=str(data_dir / "model"))
            self.assertIn("SAMPLE_TRANSCRIPT", out.getvalue())

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

        chosen = None
        for f in sample_files:
            if f.suffix.lower() != ".m4a" or shutil.which("ffmpeg") is not None:
                chosen = f
                break
        if chosen is None:
            self.skipTest("No suitable sample file to write transcript (requires ffmpeg for m4a)")

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_txt = td_path / "out.txt"
            iscli.stt(
                audio_file=str(chosen),
                model_path=str(data_dir / "model"),
                output_file=str(out_txt),
            )
            self.assertTrue(out_txt.exists(), "Transcript file not written")
            self.assertEqual(out_txt.read_text(encoding="utf-8"), "SAMPLE_FILE\n")

    def test_stt_integration_matches_ground_truth_real_model(self):
        """
        Integration: run real mlx_whisper on available audio and compare to JSON ground truth.
        Skips if mlx_whisper not importable, model path missing, or no suitable audio exists.
        """
        try:
            import mlx_whisper  # noqa: F401
        except Exception:
            self.skipTest("mlx_whisper not importable")

        from is_speech_cli.consts import DEFAULT_IS_MODEL_PATH

        model_path = os.getenv("IS_SPEECH_CLI_IS_MODEL_PATH", DEFAULT_IS_MODEL_PATH)
        model_path = str(Path(model_path).expanduser())
        if not Path(model_path).exists():
            self.skipTest("Whisper model path not found; set IS_SPEECH_CLI_IS_MODEL_PATH to enable")

        data_dir, entries = self._load_ifa_entries()

        expected_by_filename = {}
        for item in entries:
            if "Q_MP3" in item and "Q_IS" in item:
                expected_by_filename[item["Q_MP3"]] = item["Q_IS"]
            if "A_MP3" in item and "A_IS" in item:
                expected_by_filename[item["A_MP3"]] = item["A_IS"]
        pairs = []
        for fname, exp in expected_by_filename.items():
            fpath = data_dir / fname
            if fpath.exists():
                pairs.append((fpath, exp))
        if not pairs:
            self.skipTest("No matching audio files present on disk for JSON entries")

        runnable = [
            (p, exp) for (p, exp) in pairs
            if p.suffix.lower() != ".m4a" or shutil.which("ffmpeg") is not None
        ]
        if not runnable:
            self.skipTest("No suitable audio files to run (ffmpeg required for m4a)")

        def normalize(s: str) -> str:
            s = s.lower()
            s = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in s)
            return " ".join(s.split())

        iscli = cli_module.ISCLI()
        for audio_path, expected_text in runnable[:1]:
            out = io.StringIO()
            with redirect_stdout(out):
                iscli.stt(
                    audio_file=str(audio_path),
                    model_path=model_path,
                )
            detected = out.getvalue().strip()
            self.assertTrue(detected, "No transcript produced")
            self.assertEqual(normalize(detected), normalize(expected_text), f"Mismatch for {audio_path.name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)


