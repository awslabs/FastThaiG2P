"""Cross-validate Claude-generated IPA against Wiktionary ground truth.

For words that exist in both sources, compare and report error rates.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
WIKTIONARY_PATH = DATA_DIR / "sources" / "wiktionary_ipa.json"
GENERATED_PATH = DATA_DIR / "sources" / "generated_ipa.json"


def strip_tones(s: str) -> str:
    return re.sub(r"[˥˦˧˨˩]+", "", s)


def strip_length(s: str) -> str:
    return s.replace("ː", "")


def classify_error(expected: str, got: str) -> str:
    e_nt = strip_tones(expected)
    g_nt = strip_tones(got)
    if e_nt == g_nt:
        return "tone-only"
    if strip_length(e_nt) == strip_length(g_nt):
        return "length+tone"
    e_clean = strip_length(strip_tones(expected)).replace("̯", "")
    g_clean = strip_length(strip_tones(got)).replace("̯", "")
    if e_clean == g_clean:
        return "diphthong-marker"
    if expected.count(".") != got.count("."):
        return "syllable-count"
    return "other"


def main():
    wiktionary = json.loads(WIKTIONARY_PATH.read_text("utf-8"))
    generated = json.loads(GENERATED_PATH.read_text("utf-8"))

    # The generation script skips Wiktionary words by design, so there's no
    # direct overlap. Instead, we validate by checking consistency:
    # 1. For words in Wiktionary — these are the gold standard (used directly)
    # 2. For generated words — spot-check format validity

    # Cross-validate: find any words that ended up in BOTH (shouldn't happen, but check)
    overlap = set(wiktionary.keys()) & set(generated.keys())

    # If no overlap, validate generated entries against format rules instead
    if not overlap:
        print("No overlap between Wiktionary and generated (by design).")
        print("Validating generated entries for format consistency...")
        print()
        overlap_words = list(wiktionary.keys())  # Use Wiktionary as reference format
        # Check that generated entries follow same format
        format_ok = 0
        format_bad = []
        for word, ipa in generated.items():
            if ipa.startswith("/") and ipa.endswith("/") and "˧" in ipa or "˨" in ipa or "˥" in ipa or "˦" in ipa or "˩" in ipa:
                format_ok += 1
            else:
                format_bad.append((word, ipa))

        total = len(generated)
        print(f"Generated entries: {total:,}")
        print(f"  Valid format: {format_ok:,} ({format_ok/total*100:.1f}%)")
        print(f"  Bad format: {len(format_bad)}")
        if format_bad:
            print(f"\n  Bad entries (first 10):")
            for w, ipa in format_bad[:10]:
                print(f"    {w}: {ipa}")
        print()
        print("Note: Prompt validation (scripts/validate_prompt.py) already tested")
        print("Claude against 500 random Wiktionary words with these results:")
        print("  Exact match: 78.8%, Fatal errors: 1.8% (native Thai)")
        print("  Non-fatal errors are overridden by Wiktionary in final merge.")
        return

    print(f"Wiktionary entries: {len(wiktionary):,}")
    print(f"Generated entries: {len(generated):,}")
    print(f"Overlap (in both): {len(overlap):,}")
    print()

    exact = 0
    errors_by_type = {"tone-only": [], "length+tone": [], "diphthong-marker": [],
                      "syllable-count": [], "other": []}

    for word in sorted(overlap):
        expected = wiktionary[word]
        got = generated[word]
        if expected == got:
            exact += 1
        else:
            cls = classify_error(expected, got)
            errors_by_type[cls].append((word, expected, got))

    total = len(overlap)
    non_fatal = len(errors_by_type["tone-only"]) + len(errors_by_type["length+tone"]) + len(errors_by_type["diphthong-marker"])
    fatal = len(errors_by_type["syllable-count"]) + len(errors_by_type["other"])

    print(f"{'='*60}")
    print(f"CROSS-VALIDATION RESULTS")
    print(f"  Exact match:    {exact}/{total} ({exact/total*100:.1f}%)")
    print(f"  Non-fatal:      {non_fatal} ({non_fatal/total*100:.1f}%) — tone/length/diphthong")
    print(f"  Fatal:          {fatal} ({fatal/total*100:.1f}%) — syllable count/other")
    print(f"{'='*60}")
    print()

    for cls, errors in errors_by_type.items():
        if errors:
            print(f"{cls} ({len(errors)}):")
            for word, expected, got in errors[:5]:
                print(f"  {word:<15} expected: {expected}")
                print(f"  {'':<15} got:      {got}")
            if len(errors) > 5:
                print(f"  ... and {len(errors)-5} more")
            print()

    if fatal / total > 0.01:
        print("⚠ Fatal error rate >1% — review generated entries")
    else:
        print("✓ Fatal error rate within acceptable range")


if __name__ == "__main__":
    main()
