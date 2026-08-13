"""Profile g2p.convert() on utterances.jsonl"""
import json, time, cProfile, pstats, sys
from pathlib import Path
from io import StringIO

from fastthaig2p.g2p import G2P
from fastthaig2p.normalizer import normalize
from fastthaig2p.fallback import fallback_g2p

from tqdm.auto import tqdm

DATA = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "utterances.jsonl"
utts = [json.loads(l)["text"] for l in DATA.read_text().splitlines() if l.strip()]
print(f"Loaded {len(utts)} utterances", flush=True)

g2p = G2P()
tokenizer = g2p._tokenizer
ipa_dict = g2p._ipa

# --- Full run timing ---
t0 = time.perf_counter()
for u in tqdm(utts):
    g2p.convert(u)
elapsed = time.perf_counter() - t0
print(f"Total: {elapsed:.3f}s | Avg: {1000*elapsed/len(utts):.3f}ms/utt | {len(utts)/elapsed:.0f} utt/s", flush=True)

# --- Stage breakdown ---
N = len(utts)
nt = tt = ft = 0.0
fc = tc = 0
for text in tqdm(utts[:N]):
    t = time.perf_counter()
    n = normalize(text)
    nt += time.perf_counter() - t

    t = time.perf_counter()
    toks = tokenizer.tokenize(n)
    tt += time.perf_counter() - t

    for tok in toks:
        if not tok.strip():
            continue
        tc += 1
        if ipa_dict.get(tok) is None:
            t = time.perf_counter()
            fallback_g2p(tok)
            ft += time.perf_counter() - t
            fc += 1

total_sub = nt + tt + ft
print(f"\nStage breakdown (first {N} utts, {total_sub:.3f}s):", flush=True)
print(f"  normalize:  {nt:.3f}s ({100*nt/total_sub:.1f}%)")
print(f"  tokenize:   {tt:.3f}s ({100*tt/total_sub:.1f}%)")
print(f"  fallback:   {ft:.3f}s ({100*ft/total_sub:.1f}%) [{fc}/{tc} tokens = {100*fc/max(tc,1):.1f}% OOV]")

# --- cProfile (first 2000) ---
print(f"\ncProfile top-25 (cumulative):", flush=True)
pr = cProfile.Profile()
pr.enable()
for u in tqdm(utts[:N]):
    g2p.convert(u)
pr.disable()
s = StringIO()
pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(25)
print(s.getvalue(), flush=True)
