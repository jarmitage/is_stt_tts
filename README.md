# is-speech-cli

Minimal Icelandic TTS/STT CLI using Icespeak (Dora/Karl) and MLX Whisper.

## Install (with uv)

Create/activate a virtual environment (optional):

```bash
uv venv
source .venv/bin/activate  # zsh/bash on macOS/Linux
```

If Icespeak is not available on PyPI in your environment, install it locally first (adjust the path as needed):

```bash
uv pip install -e /Users/jarm/Documents/work/code/learn/Icespeak
```

Then install this package:

```bash
uv pip install -e .
```

This will provide a console command `is-speech`.

## Usage

### TTS (Dora)
```bash
is-speech tts --text 'Halló heimur' --voice Dora --mode save
```

### TTS (Karl)
```bash
is-speech tts --input_file note.txt --voice Karl --output_dir out --filename greeting
```

### STT (print transcript)
```bash
is-speech stt --audio_file sample.mp3
```

### STT (save transcript)
```bash
is-speech stt --audio_file sample.mp3 --output_file sample.txt
```

## Notes
- Playback uses `afplay` on macOS if available.
- Default STT model path points to your local MLX Whisper IS model:
  `/Users/jarm/Documents/work/code/learn/mlx-examples/whisper/mlx_models/is_large_is`.
  Override with `--model_path` as needed.


