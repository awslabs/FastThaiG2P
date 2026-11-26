"""Synthesize carrier-sentence clips: python synth.py OUT_DIR before_ipa.json after_ipa.json"""
import json, os, random, re, sys, wave
import numpy as np
from scipy.signal import resample_poly
from fastthaig2p import G2P, ipa_to_kokoro
from fastthaig2p.tts import TTS

OUT, BEFORE, AFTER = sys.argv[1:4]
a = json.load(open(BEFORE))
b = json.load(open(AFTER))
g = G2P()
pre = ipa_to_kokoro(g.convert("ฉันพูดคำว่า"))
post = ipa_to_kokoro(g.convert("อีกครั้งหนึ่ง"))

items = []
for w in a:
    ka, kb = ipa_to_kokoro(a[w]), ipa_to_kokoro(b[w])
    if ka != kb:
        items.append({"set": "changed", "word": w, "main": ka, "pr": kb, "ipa_main": a[w], "ipa_pr": b[w]})

random.seed(7)
pool = [w for w in a if a[w] == b[w] and re.fullmatch(r"[ก-๎]{2,12}", w) and "ๆ" not in w]
control = random.sample(pool, 170)
for w in control:
    k = ipa_to_kokoro(a[w])
    items.append({"set": "control", "word": w, "main": k, "pr": k})

ROT = {"→": "↗", "↗": "↓", "↓": "↑", "↑": "↘", "↘": "→"}
for w in control[:40]:
    k = ipa_to_kokoro(a[w])
    bad = "".join(ROT.get(c, c) for c in k)
    items.append({"set": "sensitivity", "word": w, "main": k, "pr": bad})

tts = TTS()
tts._text_to_phonemes = lambda s: s
def write(path, phon):
    audio = tts.generate(f"{pre} {phon} {post}")
    audio = resample_poly(audio, 2, 3)
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000); f.writeframes(pcm.tobytes())

for i, it in enumerate(items):
    it["id"] = i
    for side in ("main", "pr"):
        p = f"{OUT}/{i:04d}_{side}.wav"
        if side == "pr" and it["pr"] == it["main"]:
            it["wav_pr"] = it["wav_main"]; continue
        write(p, it[side]); it[f"wav_{side}"] = os.path.basename(p)
json.dump({"pre": pre, "post": post, "items": items}, open(f"{OUT}/items.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(i["set"] for i in items), "pre:", pre, "post:", post)
