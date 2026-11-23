"""Promo step 4/4: original music + sound effects + voiceover, mixed under the rendered video.

    python scripts/promo/mix.py <cues.json> <voice_dir> <silent.mp4> <out.mp4>

Music is synthesized here (no samples, no licensing): 112 BPM, Am-F-C-G, kick/clap/hats, sub bass, pads and a
plucked arpeggio, filtered intro, a riser into the end card and a final hit. SFX: whoosh on cuts, tap clicks, a
soft ding when a highlight ring appears. The music ducks under the voice (sidechain), then the whole mix is
normalized to -14 LUFS (Instagram/TikTok loudness).
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

SR = 48000
BPM = 112
BEAT = 60 / BPM
rng = np.random.default_rng(7)


def env(n, a=0.005, d=0.2, curve=4.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) * np.exp(-curve * np.maximum(0, t - a) / d)
    return e


def lowpass(x, cutoff):
    # one-pole lowpass, cutoff may be an array (sweeps)
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def lp_fast(x, cutoff):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, cutoff, 'low', fs=SR, output='sos'), x)


def hp_fast(x, cutoff):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, cutoff, 'high', fs=SR, output='sos'), x)


def bp_fast(x, lo, hi):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x)


def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for d in (-detune, 0, detune):
        ph = (t * f * (1 + d) + rng.random()) % 1.0
        out += 2 * ph - 1
    return out / 3


def note(m):
    return 440 * 2 ** ((m - 69) / 12)


def add(buf, x, at):
    i = int(at * SR)
    if i >= len(buf) or i + len(x) <= 0:
        return
    x = x[max(0, -i):]
    i = max(0, i)
    j = min(len(buf), i + len(x))
    buf[i:j] += x[:j - i]


def music(dur, drop_at, end_at):
    n = int((dur + 1) * SR)
    drums = np.zeros(n); bass = np.zeros(n); pad = np.zeros(n); arp = np.zeros(n)
    chords = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]  # Am F C G
    bar = 4 * BEAT
    kick_n = int(0.35 * SR); tk = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-tk * 28)) / SR) * env(kick_n, 0.002, 0.22, 3)
    clap = bp_fast(rng.standard_normal(int(0.2 * SR)), 900, 3500) * env(int(0.2 * SR), 0.001, 0.09, 3) * 0.8
    hat = hp_fast(rng.standard_normal(int(0.06 * SR)), 7000) * env(int(0.06 * SR), 0.001, 0.025, 3) * 0.35
    b = 0
    t = 0.0
    while t < dur:
        root, ch = chords[b % 4]
        full = t >= drop_at - 0.01 and t < end_at
        # pad
        pn = int(bar * SR)
        p = sum(saw(note(m), pn, 0.004) for m in ch) / 3
        p = lp_fast(p, 1400 if full else 700) * np.minimum(1, np.arange(pn) / (0.25 * SR)) * 0.22
        add(pad, p, t)
        for beat in range(4):
            bt = t + beat * BEAT
            if bt >= dur:
                break
            if full:
                add(drums, kick, bt)
                if beat in (1, 3):
                    add(drums, clap, bt)
            for e8 in range(2):
                if full or beat >= 2:
                    add(drums, hat * (0.6 if e8 == 0 else 1.0), bt + e8 * BEAT / 2)
                if full:
                    bn = int(BEAT / 2 * SR * 0.9)
                    bs = lp_fast(saw(note(root - 24), bn) * 0.6 + np.sin(2 * np.pi * note(root - 24) * np.arange(bn) / SR), 260)
                    add(bass, bs * env(bn, 0.004, 0.18, 2) * 0.55, bt + e8 * BEAT / 2)
            # plucked arpeggio, 16ths
            for s16 in range(4):
                m = ch[(beat * 4 + s16) % 3] + 12 + (12 if (beat * 4 + s16) % 7 == 0 else 0)
                an = int(0.18 * SR)
                ta = np.arange(an) / SR
                x = (np.sign(np.sin(2 * np.pi * note(m) * ta)) * 0.5 + np.sin(2 * np.pi * note(m) * ta)) * env(an, 0.002, 0.07, 3)
                add(arp, lp_fast(x, 3200) * (0.13 if full else 0.09), bt + s16 * BEAT / 4)
        t += bar
        b += 1
    mix = drums * 0.9 + bass + pad + arp
    # final hit on the end card: big chord + low boom, then let it ring
    hn = int(3.2 * SR)
    hit = sum(saw(note(m), hn, 0.006) for m in (45, 57, 60, 64, 69)) / 5
    hit = lp_fast(hit, 1800) * env(hn, 0.004, 1.6, 2.5) * 0.45
    hit += np.sin(2 * np.pi * 50 * np.arange(hn) / SR) * env(hn, 0.003, 0.5, 3) * 0.7
    tail = np.ones(n)
    i = int(end_at * SR)
    tail[i:] = np.maximum(0, 1 - (np.arange(n - i) / SR) / 0.25)  # beat stops at the end card
    mix = mix * tail
    add(mix, hit, end_at)
    return mix[:int(dur * SR)]


def whoosh():
    n = int(0.55 * SR)
    x = rng.standard_normal(n)
    sweep = np.linspace(300, 6000, n) ** 1.0
    y = lowpass(x, sweep) - lowpass(x, sweep * 0.25)
    e = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return y * e * 0.9


def riser(length=1.2):
    n = int(length * SR)
    x = rng.standard_normal(n)
    y = lowpass(x, np.linspace(400, 9000, n)) * np.linspace(0, 1, n) ** 2 * 0.45
    tone = np.sin(2 * np.pi * np.cumsum(np.linspace(200, 900, n)) / SR) * np.linspace(0, 1, n) ** 3 * 0.12
    return y + tone


def tap():
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1900 * t) * 0.5 + hp_fast(rng.standard_normal(n), 3000) * 0.3) * env(n, 0.0005, 0.012, 3) * 0.7


def ding():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t) + 0.2 * np.sin(2 * np.pi * 2637 * t)) * env(n, 0.002, 0.35, 3) * 0.16


def main():
    cues_path, vo_dir, silent, out = sys.argv[1:5]
    cues = json.load(open(cues_path))
    dur = cues['duration']
    n = int(dur * SR)
    end_cue = next((c['t'] for c in cues['sfx'] if c['kind'] == 'impact'), dur - 3)
    voice = np.zeros(n)
    for v in cues['voice']:
        a, sr = sf.read(os.path.join(vo_dir, f"v{v['i']}.wav"))
        if a.ndim > 1:
            a = a.mean(axis=1)
        if sr != SR:
            a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a)
        add(voice, a, v['t'])
    sfx = np.zeros(n)
    for c in cues['sfx']:
        k = c['kind']
        if k == 'whoosh':
            add(sfx, whoosh() * 0.35, c['t'] - 0.3)
        elif k == 'riser':
            add(sfx, riser() * 0.5, c['t'])
        elif k == 'tap':
            add(sfx, tap(), c['t'])
        elif k == 'ding':
            add(sfx, ding() * 2, c['t'])
    mus = music(dur, drop_at=cues['voice'][1]['t'] - 0.25, end_at=end_cue)
    # levels: music sits ~11 dB under the voice before ducking
    rms = lambda x: float(np.sqrt(np.mean(x ** 2)) + 1e-9)
    talk = voice[np.abs(voice) > 0.02]
    v_rms = rms(talk) if len(talk) else 0.1
    mus *= (v_rms * 10 ** (-11 / 20)) / rms(mus)
    sfx *= np.max(np.abs(voice)) * 0.7  # fixed per-kind levels: taps ~-6 dB, dings ~-9 dB, whooshes ~-14 dB under voice peak
    tmp = tempfile.mkdtemp()
    for name, x in (('voice', voice), ('music', mus), ('sfx', sfx)):
        sf.write(os.path.join(tmp, f'{name}.wav'), np.clip(x, -1, 1).astype(np.float32), SR)
    fc = ('[0:a]asplit=2[v][vk];'
          '[1:a]anull[m];[m][vk]sidechaincompress=threshold=0.015:ratio=4:attack=20:release=400[md];'
          '[2:a]anull[s];'
          '[v][md][s]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(tmp, 'voice.wav'), '-i', os.path.join(tmp, 'music.wav'),
                    '-i', os.path.join(tmp, 'sfx.wav'), '-i', silent, '-filter_complex', fc, '-map', '3:v', '-map', '[a]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', out], check=True)
    print(out)


if __name__ == '__main__':
    main()
