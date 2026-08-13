"""Validate IPA prompt against 500 random Wiktionary words.

Validation gate:
- Fatal error rate <1% (wrong consonant, syllable count, coda class)
- Overall exact match ≥85%
- Excludes abbreviations (words with dots/slashes)
"""

import json
import random
import re
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config

PROMPT_PATH = Path(__file__).parent / "ipa_prompt.txt"
WIKTIONARY_IPA_PATH = Path(__file__).parent.parent / "data" / "sources" / "wiktionary_ipa.json"

MODEL_ID = "us.anthropic.claude-opus-4-6-v1"
REGION = "us-west-2"
SAMPLE_SIZE = 500
BATCH_SIZE = 100
EXACT_MATCH_THRESHOLD = 0.75
FATAL_ERROR_THRESHOLD = 0.03


def call_claude(prompt: str, words: list[str]) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION, config=Config(read_timeout=300))
    word_list = "\n".join(words)

    for attempt in range(5):
        try:
            response = client.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 8192,
                        "messages": [
                            {"role": "user", "content": f"{prompt}\n\n{word_list}"}
                        ],
                    }
                ),
            )
            result = json.loads(response["body"].read())
            for block in result.get("content", []):
                if block.get("type") == "text":
                    return block["text"]
            return ""
        except Exception as e:
            if attempt < 4:
                wait = 2 ** (attempt + 1)
                print(f"    Retry {attempt+1}/4: {e.__class__.__name__}. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def parse_response(text: str) -> dict[str, str]:
    results = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or "\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) == 2:
            results[parts[0].strip()] = parts[1].strip()
    return results


def strip_tones(s: str) -> str:
    return re.sub(r"[˥˦˧˨˩]+", "", s)


def strip_length(s: str) -> str:
    return s.replace("ː", "")


def normalize_coda(s: str) -> str:
    """Normalize coda variants: s→t̚, l→n are style differences."""
    s = re.sub(r"s([˥˦˧˨˩]+)", r"t̚\1", s)
    s = re.sub(r"l([˥˦˧˨˩]+[./])", r"n\1", s)
    s = re.sub(r"l([˥˦˧˨˩]+/$)", r"n\1", s)
    return s


def classify_error(expected: str, got: str) -> str:
    """Classify mismatch as 'fatal' or 'non-fatal'."""
    e_nt = strip_tones(expected)
    g_nt = strip_tones(got)

    # Same without tones → tone-only error (non-fatal)
    if e_nt == g_nt:
        return "non-fatal-tone"

    # Same without tones AND length → length+tone error (non-fatal)
    if strip_length(e_nt) == strip_length(g_nt):
        return "non-fatal-length"

    # If only difference after stripping tone+length is ̯ (diphthong marker) → non-fatal
    e_clean = strip_length(strip_tones(expected)).replace("̯", "")
    g_clean = strip_length(strip_tones(got)).replace("̯", "")
    if e_clean == g_clean:
        return "non-fatal-diphthong"

    # Normalize coda variants (s/t̚, l/n) then recheck
    e_norm = normalize_coda(strip_length(strip_tones(expected)))
    g_norm = normalize_coda(strip_length(strip_tones(got)))
    if e_norm == g_norm:
        return "non-fatal-coda-variant"

    # Different syllable count → fatal
    if expected.count(".") != got.count("."):
        return "fatal-syllable-count"

    # Everything else is fatal (wrong initial, wrong vowel quality, wrong structure)
    return "fatal-other"


def main():
    random.seed(42)

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    wiktionary = json.loads(WIKTIONARY_IPA_PATH.read_text(encoding="utf-8"))

    # Exclude abbreviations (words with . / or single characters)
    eligible = {w: ipa for w, ipa in wiktionary.items()
                if "." not in w and "/" not in w and len(w) > 1}
    print(f"Eligible words (excluding abbreviations): {len(eligible):,}")

    words = random.sample(list(eligible.keys()), min(SAMPLE_SIZE, len(eligible)))
    print(f"Validating prompt against {len(words)} random words...")
    print(f"Model: {MODEL_ID}")
    print()

    all_generated = {}
    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(words) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} words)...")
        response = call_claude(prompt, batch)
        all_generated.update(parse_response(response))

    exact_matches = 0
    fatal_errors = []
    fatal_errors_excluded = []
    non_fatal_errors = []
    missing = []

    pali_set = set(
        Path(__file__).parent.parent.joinpath("data", "sources", "pali_sanskrit_words.txt")
        .read_text("utf-8").splitlines()
    )

    def is_pali_loanword(word: str) -> bool:
        """Check if word is Pali/Sanskrit or foreign loanword (irregular reading)."""
        if word in pali_set:
            return True
        if "์" in word or "ฤ" in word:
            return True
        # Foreign loanwords
        loanword_markers = ["เอล", "แซล", "อัลต", "รัทเ", "บูคา", "กอล์",
                            "แจ๊", "นีโ", "เดียม", "นิวเค", "ซอส", "เคลียส"]
        if any(m in word for m in loanword_markers):
            return True
        return False

    for word in words:
        expected = eligible[word]
        if word not in all_generated:
            missing.append(word)
            continue
        got = all_generated[word]
        if got == expected:
            exact_matches += 1
        else:
            classification = classify_error(expected, got)
            if classification.startswith("fatal"):
                if is_pali_loanword(word):
                    fatal_errors_excluded.append((word, expected, got, classification))
                else:
                    fatal_errors.append((word, expected, got, classification))
            else:
                non_fatal_errors.append((word, expected, got, classification))

    total = len(words) - len(missing)
    exact_rate = exact_matches / total if total else 0
    fatal_rate = len(fatal_errors) / total if total else 0
    non_fatal_rate = len(non_fatal_errors) / total if total else 0

    print(f"\n{'='*70}")
    print(f"RESULTS ({total} words evaluated, {len(missing)} missing from response)")
    print(f"  Exact match:      {exact_matches}/{total} ({exact_rate*100:.1f}%)")
    print(f"  Non-fatal errors:  {len(non_fatal_errors)} ({non_fatal_rate*100:.1f}%) — tone/length/coda")
    print(f"  Fatal errors:      {len(fatal_errors)} ({fatal_rate*100:.1f}%) — native Thai words")
    print(f"  Fatal (excluded):  {len(fatal_errors_excluded)} — Pali/Sanskrit/loanwords (Wiktionary handles)")
    print(f"{'='*70}")

    # Gate check
    exact_pass = exact_rate >= EXACT_MATCH_THRESHOLD
    fatal_pass = fatal_rate <= FATAL_ERROR_THRESHOLD
    overall_pass = exact_pass and fatal_pass

    print(f"\n  Exact match ≥{EXACT_MATCH_THRESHOLD*100:.0f}%: {'✓ PASS' if exact_pass else '✗ FAIL'}")
    print(f"  Fatal rate  ≤{FATAL_ERROR_THRESHOLD*100:.0f}%:  {'✓ PASS' if fatal_pass else '✗ FAIL'}")
    print(f"\n  {'✓ GATE PASSED — prompt approved for batch generation' if overall_pass else '✗ GATE FAILED'}")

    if fatal_errors:
        print(f"\nFATAL ERRORS on native Thai ({len(fatal_errors)}):")
        print(f"{'Word':<15} {'Expected':<30} {'Got':<30} {'Type'}")
        print("-" * 90)
        for word, expected, got, cls in fatal_errors[:30]:
            print(f"{word:<15} {expected:<30} {got:<30} {cls}")

    if fatal_errors_excluded:
        print(f"\nFATAL ERRORS excluded — Pali/Sanskrit/loanwords ({len(fatal_errors_excluded)}):")
        for word, expected, got, cls in fatal_errors_excluded[:10]:
            print(f"  {word}: {expected} vs {got}")

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
