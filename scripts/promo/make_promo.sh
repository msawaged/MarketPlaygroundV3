#!/usr/bin/env bash
# Feature promo (v6 style): real footage of the live site in a phone frame on a branded stage, camera zooms,
# highlight rings, tap ripples, kinetic captions, original music + SFX, Kokoro voice, coming-soon end card.
#   bash scripts/promo/make_promo.sh <config.json> <out.mp4> [work_dir]
# Needs: node + Playwright/Chromium, ffmpeg, python with kokoro-onnx soundfile numpy scipy
#   (pip install --break-system-packages -q kokoro-onnx soundfile scipy). About 6-8 minutes; most of it is render.js.
# Steps: reel_voice.py (voice lines) -> capture.js (live footage + marks) -> edit.js (cut, camera, rings, cues)
#        -> render.js (stage.html frame by frame) -> mix.py (music, SFX, ducking, -14 LUFS) -> out.mp4
# The search in the config should be a story already made today (cached: free, no new idea). Never commit the MP4.
set -euo pipefail
cfg=$1; out=$2; work=${3:-$(mktemp -d)}
here=$(cd "$(dirname "$0")" && pwd)
export NODE_PATH=${NODE_PATH:-$(npm root -g)}
mkdir -p "$work/vo"
python3 -c "import json,sys; c=json.load(open(sys.argv[1])); json.dump([s['line'] for s in c['scenes']], open(sys.argv[2],'w'))" "$cfg" "$work/vo/lines.json"
voice=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('voice','af_heart'))" "$cfg")
search=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['search'])" "$cfg")
typed=$(python3 -c "import json,sys; c=json.load(open(sys.argv[1])); print(c.get('typed') or c['search'])" "$cfg")
python3 "$here/../reel_voice.py" "$work/vo/lines.json" "$work/vo" "$voice" > "$work/vo/lens.json"
rm -rf "$work/cap"; node "$here/capture.js" "$work/cap" "$search" "$typed"
node "$here/edit.js" "$cfg" "$work/cap" "$work/vo" "$work/ed"
node "$here/render.js" "$work/ed" "$work/silent.mp4"
python3 "$here/mix.py" "$work/ed/cues.json" "$work/vo" "$work/silent.mp4" "$out"
echo "done: $out (work files in $work)"
