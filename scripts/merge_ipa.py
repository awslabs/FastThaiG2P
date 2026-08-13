"""Merge Wiktionary IPA + generated IPA into final ipa.json and ipa_metadata.json.

Produces:
  data/ipa.json          — flat {word: ipa_string} for runtime lookup
  data/ipa_metadata.json — rich {word: {ipa, source, pos, etymology, ...}} for auditing
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DICT_PATH = DATA_DIR / "dict.txt"
MANUAL_PATH = DATA_DIR / "sources" / "manual_overrides.json"
WIKTIONARY_PATH = DATA_DIR / "sources" / "wiktionary_ipa.json"
GENERATED_PATH = DATA_DIR / "sources" / "generated_ipa.json"
KAIKKI_PATH = DATA_DIR / "sources" / "kaikki.org-dictionary-Thai.jsonl"
OUTPUT_PATH = DATA_DIR / "ipa.json"
METADATA_PATH = DATA_DIR / "ipa_metadata.json"


def load_kaikki_metadata() -> dict[str, dict]:
    """Extract pos and etymology from kaikki.org data."""
    metadata = {}
    if not KAIKKI_PATH.exists():
        return metadata
    with open(KAIKKI_PATH, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get("word", "")
            if word in metadata:
                continue
            pos = entry.get("pos", "")
            etym = entry.get("etymology_text", "") or ""
            # Extract origin language from etymology
            origin = ""
            if "Pali" in etym or "Sanskrit" in etym:
                origin = "pali-sanskrit"
            elif "Proto-Tai" in etym:
                origin = "proto-tai"
            elif "Khmer" in etym:
                origin = "khmer"
            elif "Chinese" in etym or "Hokkien" in etym or "Teochew" in etym:
                origin = "chinese"
            elif "English" in etym:
                origin = "english"
            elif "Malay" in etym:
                origin = "malay"
            metadata[word] = {"pos": pos, "origin": origin}
    return metadata


def main():
    dict_words = set(DICT_PATH.read_text("utf-8").splitlines())
    dict_words.discard("")

    manual = json.loads(MANUAL_PATH.read_text("utf-8")) if MANUAL_PATH.exists() else {}
    wiktionary = json.loads(WIKTIONARY_PATH.read_text("utf-8")) if WIKTIONARY_PATH.exists() else {}
    generated = json.loads(GENERATED_PATH.read_text("utf-8")) if GENERATED_PATH.exists() else {}

    print(f"Dict words: {len(dict_words):,}")
    print(f"Manual overrides: {len(manual):,}")
    print(f"Wiktionary entries: {len(wiktionary):,}")
    print(f"Generated entries: {len(generated):,}")
    print()

    # Load kaikki metadata
    print("Loading kaikki.org metadata...")
    kaikki_meta = load_kaikki_metadata()
    print(f"  Got metadata for {len(kaikki_meta):,} words")
    print()

    # Merge priority: manual > wiktionary > generated
    ipa_flat = {}
    ipa_metadata = {}

    # Generated first (lowest priority, gets overwritten)
    added_from_gen = 0
    for word, ipa in generated.items():
        ipa_flat[word] = ipa
        ipa_metadata[word] = {"ipa": ipa, "source": "generated", "model": "claude-opus-4.6"}
        added_from_gen += 1

    # Wiktionary (overrides generated)
    added_from_wikt = 0
    for word, ipa in wiktionary.items():
        ipa_flat[word] = ipa
        meta = {"ipa": ipa, "source": "wiktionary"}
        if word in kaikki_meta:
            meta["pos"] = kaikki_meta[word]["pos"]
            if kaikki_meta[word]["origin"]:
                meta["origin"] = kaikki_meta[word]["origin"]
        ipa_metadata[word] = meta
        added_from_wikt += 1

    # Manual overrides (highest priority)
    added_from_manual = 0
    for word, ipa in manual.items():
        ipa_flat[word] = ipa
        ipa_metadata[word] = {"ipa": ipa, "source": "manual"}
        added_from_manual += 1

    # Only keep entries that are in dict.txt
    ipa_flat = {w: ipa for w, ipa in ipa_flat.items() if w in dict_words}
    ipa_metadata = {w: m for w, m in ipa_metadata.items() if w in dict_words}

    print(f"Merged IPA entries: {len(ipa_flat):,}")
    print(f"  Manual overrides: {added_from_manual:,}")
    print(f"  From Wiktionary: {added_from_wikt:,}")
    print(f"  From generated: {added_from_gen:,}")
    print(f"  Missing (not in any source): {len(dict_words) - len(ipa_flat):,}")
    print()

    # Write outputs
    OUTPUT_PATH.write_text(
        json.dumps(ipa_flat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Written: {OUTPUT_PATH} ({len(ipa_flat):,} entries)")

    METADATA_PATH.write_text(
        json.dumps(ipa_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Written: {METADATA_PATH} ({len(ipa_metadata):,} entries)")

    # Coverage stats
    coverage = len(ipa_flat) / len(dict_words) * 100
    print(f"\nCoverage: {coverage:.1f}% of dict.txt")


if __name__ == "__main__":
    main()
