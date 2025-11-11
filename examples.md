## Examples

### TTS examples

1) Basic TTS (Dora, save as MP3 to current directory)

```bash
is-speech tts --text 'Halló heimur' --voice Dora --mode save
```

2) TTS using Karl and play immediately (no file saved unless you choose mode=both)

```bash
is-speech tts --text 'Góða nótt' --voice Karl --mode play
```

3) TTS save and then play (both), custom filename

```bash
is-speech tts --text 'Hvernig hefur þú það?' --voice Dora --mode both --filename greeting_is
```

4) TTS from a text file, custom output directory

```bash
is-speech tts --input_file ./notes/lesson1.txt --voice Karl --output_dir ./out --filename lesson1_karl
```

5) TTS from stdin (pipe), default voice (Dora) and MP3

```bash
echo 'Velkomin!' | is-speech tts --mode save --filename velkomin
```

6) TTS save as WAV instead of MP3

```bash
is-speech tts --text 'Þetta er próf' --audio_format wav --filename prova_wav
```

7) TTS with absolute output directory (e.g., Downloads)

```bash
is-speech tts --text 'Skál!' --output_dir ~/Downloads --filename skal
```

8) TTS with timestamped filename

```bash
is-speech tts --text 'Frábært!' --filename "$(date +%Y%m%d_%H%M%S)" --mode save
```

9) TTS from a multiline here-doc

```bash
is-speech tts --voice Dora --mode save --filename multiline <<'TXT'
Halló!
Þetta er dæmi um marglínan texta.
TXT
```

10) TTS Karl to WAV and play

```bash
is-speech tts --text 'Gleðileg jól' --voice Karl --audio_format wav --mode play
```

### STT examples

11) STT: print transcript to stdout (MP3)

```bash
is-speech stt --audio_file ./audio/sample.mp3
```

12) STT: save transcript to a file

```bash
is-speech stt --audio_file ./audio/meeting.mp3 --output_file ./transcripts/meeting.txt
```

13) STT: specify explicit model path

```bash
is-speech stt --audio_file ./audio/answer.wav --model_path ~/models/is-whisper-mlx
```

14) STT: use env var for model path (no --model_path needed)

```bash
IS_SPEECH_CLI_IS_MODEL_PATH=~/models/is-whisper-mlx is-speech stt --audio_file ./audio/clip.mp3
```

15) STT: WAV input, print transcript

```bash
is-speech stt --audio_file ./audio/prompt.wav
```

16) STT: M4A input (auto-converts to WAV if ffmpeg available)

```bash
is-speech stt --audio_file ./audio/sample.m4a --output_file ./transcripts/sample.txt
```

17) STT: batch transcribe a folder of MP3s

```bash
mkdir -p transcripts
for f in ./data/ifa_b1/*.mp3; do
  base="$(basename "$f" .mp3)"
  is-speech stt --audio_file "$f" --output_file "transcripts/${base}.txt"
done
```

18) STT: find all .wav under a tree and transcribe

```bash
find ./recordings -type f -name '*.wav' | while read -r f; do
  base="$(basename "$f" .wav)"
  out="./transcripts/${base}.txt"
  mkdir -p "$(dirname "$out")"
  is-speech stt --audio_file "$f" --output_file "$out"
done
```

19) STT: redirect stdout to a file (alternative to --output_file)

```bash
is-speech stt --audio_file ./audio/clip.mp3 > ./transcripts/clip.txt
```

20) Generate with TTS then transcribe with STT

```bash
# 1) Generate speech
is-speech tts --text 'Halló, þetta er prófun.' --output_dir ./out --filename combo --mode save
# 2) Transcribe what we just generated
is-speech stt --audio_file ./out/combo.mp3 --output_file ./transcripts/combo.txt
```


