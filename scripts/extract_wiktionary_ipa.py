"""Extract Thai IPA from kaikki.org JSONL dump, intersect with dict.txt."""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
KAIKKI_PATH = DATA_DIR / "sources" / "kaikki.org-dictionary-Thai.jsonl"
DICT_PATH = DATA_DIR / "dict.txt"
OUTPUT_PATH = DATA_DIR / "sources" / "wiktionary_ipa.json"


def clean_ipa(ipa: str) -> str:
    ipa = re.sub(r"\.\s*/", "/", ipa)
    ipa = re.sub(r"\s+/", "/", ipa)
    return ipa.strip()


def main():
    dict_words = set(DICT_PATH.read_text("utf-8").splitlines())
    dict_words.discard("")

    entries = {}
    total = 0
    skipped_no_ipa = 0
    skipped_not_in_dict = 0
    skipped_bad_format = 0

    with open(KAIKKI_PATH, encoding="utf-8") as f:
        for line in f:
            total += 1
            entry = json.loads(line)
            word = entry.get("word", "")

            ipa = None
            for s in entry.get("sounds", []):
                if "ipa" in s:
                    ipa = s["ipa"]
                    break

            if not ipa:
                skipped_no_ipa += 1
                continue

            if word not in dict_words:
                skipped_not_in_dict += 1
                continue

            ipa = clean_ipa(ipa)
            if not (ipa.startswith("/") and ipa.endswith("/")):
                skipped_bad_format += 1
                continue

            entries[word] = ipa

    OUTPUT_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Parsed {total:,} kaikki entries")
    print(f"Skipped: {skipped_no_ipa} no IPA, {skipped_not_in_dict} not in dict, {skipped_bad_format} bad format")
    print(f"Output: {len(entries):,} entries → {OUTPUT_PATH}")

    all_valid = all(v.startswith("/") and v.endswith("/") for v in entries.values())
    all_in_dict = all(k in dict_words for k in entries)
    print(f"\nValidation: all start/end with /: {all_valid}, all keys in dict.txt: {all_in_dict}")


if __name__ == "__main__":
    main()
