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

## Environment and API keys

Icespeak expects API credentials to live in a keys directory, configured via the environment variable `ICESPEAK_KEYS_DIR`. In this repo:

- `.env` contains only one variable: `ICESPEAK_KEYS_DIR`
- `keys/` is where your provider key files live (e.g., AWS Polly)
- Both `.env` and `keys/` are gitignored

Example `.env`:

```bash
# point to your absolute keys directory
ICESPEAK_KEYS_DIR=/absolute/path/to/keys
```

Example layout:

```bash
keys/
  AWSPollyServerKey.json
  # ...other provider files required by Icespeak...
```

Note: Icespeak will read credentials from `ICESPEAK_KEYS_DIR`; this project does not check your keys into version control.

## Usage

See [examples.md](examples.md) for more.

### TTS (Dora)
```bash
is-speech tts --text 'Halló heimur' --voice Dora --mode save
```

### TTS (play and save in one go)
```bash
is-speech tts --text 'Halló' --voice Dora --mode 'play,save'
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
- Default STT model path points to your local MLX Whisper IS model: `IS_SPEECH_CLI_IS_MODEL_PATH`. Override with `--model_path` as needed.
- `--mode` accepts a single value (`save` or `play`), a comma-list like `'play,save'`, or the legacy alias `both`.


