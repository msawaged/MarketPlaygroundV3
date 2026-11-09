"""Voiceover for scripts/make_reel.js: speaks each card's line with Kokoro (free, runs locally, no API key).

    python scripts/reel_voice.py lines.json out_dir [voice=am_michael]

Writes out_dir/v0.wav, v1.wav, ... and prints a JSON list of their lengths in seconds.
Needs: pip install kokoro-onnx soundfile. The model (~350 MB) is downloaded once to ~/.cache/kokoro.
"""
import json
import os
import sys
import urllib.request

import soundfile as sf
from kokoro_onnx import Kokoro

REL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
CACHE = os.path.expanduser("~/.cache/kokoro")
SPEED = 1.12


def model():
    os.makedirs(CACHE, exist_ok=True)
    paths = []
    for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        p = os.path.join(CACHE, name)
        if not os.path.exists(p) or os.path.getsize(p) < 1_000_000:
            print(f"downloading {name}...", file=sys.stderr)
            urllib.request.urlretrieve(REL + name, p + ".part")
            os.replace(p + ".part", p)
        paths.append(p)
    return Kokoro(*paths)


def main():
    lines = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "am_michael"
    k = model()
    lens = []
    for i, line in enumerate(lines):
        audio, sr = k.create(line, voice=voice, speed=SPEED, lang="en-us")
        if len(audio) < sr * 0.5:
            raise SystemExit(f"line {i} came out empty: {line!r}")
        sf.write(os.path.join(out, f"v{i}.wav"), audio, sr)
        lens.append(round(len(audio) / sr, 2))
    print(json.dumps(lens))


if __name__ == "__main__":
    main()
