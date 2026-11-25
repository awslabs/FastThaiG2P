"""Score: python score.py items.json transcripts_*.json"""
import json, re, sys, unicodedata
from collections import Counter, defaultdict

items = json.load(open(sys.argv[1]))["items"]
PRE, POST = "ฉันพูดคำว่า", "อีกครั้งหนึ่ง"

def norm(s):
    s = unicodedata.normalize("NFC", s).replace("ํา", "ำ")
    return re.sub(r"[\s\.\,\?\!\-\"'ฯ]", "", s)

def variants(word):
    toks, out = word.split(), []
    for t in toks:
        if t == "ๆ" and out: out.append(out[-1])
        elif t.endswith("ๆ"): out += [t[:-1], t[:-1]]
        else: out.append(t)
    return {norm(word), norm("".join(out))}

def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def category(m, p):
    if " " in m and m.replace(" ", ".") == p: return "space->dot (repeats/multiword)"
    if re.search(r"[iuɯ]ː?aː?(?!̯)", m) or re.search(r"[iuɯ]ːa", m): return "diphthong length"
    if "iu" in m: return "iu->iw"
    if re.search(r"[ptk]h", m): return "aspiration typo"
    if p.count("ʔ") > m.count("ʔ"): return "glottal insert"
    return "other typo"

def score(hyp, word):
    h = norm(hyp)
    best = None
    for v in variants(word):
        ref = PRE + v + POST
        cer = lev(h, ref) / len(ref)
        hit = v in h
        if best is None or (hit, -cer) > (best[0], -best[1]): best = (hit, cer)
    return best

for asr_path in sys.argv[2:]:
    hyp = json.load(open(asr_path))
    errs = sum(v.startswith("ERROR") for v in hyp.values())
    print(f"\n===== {asr_path}  (ASR errors: {errs})")
    agg = defaultdict(lambda: Counter())
    rows = []
    for it in items:
        sm = score(hyp[it["wav_main"]], it["word"]); sp = score(hyp[it["wav_pr"]], it["word"])
        key = it["set"] if it["set"] != "changed" else "changed"
        c = agg[key]
        c["n"] += 1; c["hit_main"] += sm[0]; c["hit_pr"] += sp[0]
        c["cer_main"] += sm[1]; c["cer_pr"] += sp[1]
        c["pr_better"] += sp[1] < sm[1] - 1e-9; c["pr_worse"] += sp[1] > sm[1] + 1e-9
        if it["set"] == "changed":
            cat = category(it["ipa_main"], it["ipa_pr"])
            k = agg["  cat: " + cat]
            k["n"] += 1; k["hit_main"] += sm[0]; k["hit_pr"] += sp[0]
            k["cer_main"] += sm[1]; k["cer_pr"] += sp[1]
            k["pr_better"] += sp[1] < sm[1] - 1e-9; k["pr_worse"] += sp[1] > sm[1] + 1e-9
            if sm[0] != sp[0]:
                rows.append((("WORSE" if sm[0] else "better"), it["word"], it["main"], it["pr"], hyp[it["wav_main"]], hyp[it["wav_pr"]]))
    print(f"{'set':38} {'n':>4} {'hit main':>9} {'hit pr':>7} {'CER main':>9} {'CER pr':>7} {'pr better':>10} {'pr worse':>9}")
    for k in sorted(agg, key=lambda x: (x.startswith("  "), x)):
        c = agg[k]; n = c["n"]
        print(f"{k:38} {n:4} {c['hit_main']/n:9.1%} {c['hit_pr']/n:7.1%} {c['cer_main']/n:9.3f} {c['cer_pr']/n:7.3f} {c['pr_better']:10} {c['pr_worse']:9}")
    print("target-word hit flips (main -> pr):")
    for r in sorted(rows): print("  ", *r, sep=" | ")
