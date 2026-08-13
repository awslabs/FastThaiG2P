"""Rewrite synthetic-dataset text as pure spoken Thai.

Numbers, Latin abbreviations, units, and symbols become their Thai
readout via fastthaig2p.normalize — e.g. "รอ 2 นาที" → "รอสองนาที",
"AA1234" → "เอเอหนึ่งสองสามสี่". IPA/phonemes are regenerated for every
changed row so they stay consistent with the new text. Anything still
not Thai/whitespace/punctuation after normalization is reported and
dropped (should be none).

Usage: python scripts/normalize_synthetic_text.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastthaig2p import G2P, ipa_to_kokoro, normalize

DATA_DIR = Path(__file__).parent.parent / "data" / "synthetic"
# Thai block, whitespace, and neutral punctuation that G2P ignores
ALLOWED = re.compile(r'^[ก-๏\s"\'().,!?\-–—]*$')


def main() -> None:
    g2p = G2P()
    for name in ("utterances.jsonl", "utterances_with_ipa.jsonl"):
        path = DATA_DIR / name
        rows, changed, dropped = [], 0, []
        for line in path.open(encoding="utf-8"):
            row = json.loads(line)
            norm = normalize(row["text"]).strip()
            if not ALLOWED.match(norm):
                dropped.append(norm)
                continue
            if norm != row["text"]:
                changed += 1
                row["text"] = norm
                if "ipa" in row:
                    row["ipa"] = g2p.convert(norm)
                    row["phonemes"] = " ".join(
                        p.strip("/") for p in row["ipa"].split()
                    )
            if "ipa" in row:
                # Kokoro training phonemes (5-tone v2 mapping) — the same
                # string format as kikiri-tts train_list.txt column 2
                row["kokoro"] = ipa_to_kokoro(row["ipa"])
            rows.append(row)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} kept, {changed} normalized, {len(dropped)} dropped")
        for d in dropped[:10]:
            print("  dropped:", d[:80])


if __name__ == "__main__":
    main()
