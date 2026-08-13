"""Generate IPA for words not covered by Wiktionary using Claude via Bedrock.

Features:
- Resumable: saves progress after each batch to generated_ipa.json
- Incremental: skips words already in generated_ipa.json
- Retries with exponential backoff on failures
- Validates phoneme inventory
- Uses Opus 4.6 for maximum quality
"""

import json
import re
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config

DATA_DIR = Path(__file__).parent.parent / "data"
PROMPT_PATH = Path(__file__).parent / "ipa_prompt.txt"
DICT_PATH = DATA_DIR / "dict.txt"
WIKTIONARY_PATH = DATA_DIR / "sources" / "wiktionary_ipa.json"
OUTPUT_PATH = DATA_DIR / "sources" / "generated_ipa.json"
INVALID_PATH = DATA_DIR / "sources" / "generated_ipa_invalid.json"

MODEL_ID = "us.anthropic.claude-opus-4-6-v1"
REGION = "us-west-2"
BATCH_SIZE = 100
MAX_RETRIES = 5

# Thai phoneme inventory for validation
VALID_CODEPOINTS = set(
    "abdefghijklmnoprstuvwŋɔɛɯɤʔɕ"  # consonants + vowels
    "ːʰ"  # length, aspiration
    "˥˦˧˨˩"  # tone letters
    "̯̚͡"  # combining: unreleased, non-syllabic, tie bar
    "./ "  # separators
)


def load_progress() -> dict[str, str]:
    if OUTPUT_PATH.exists():
        return json.loads(OUTPUT_PATH.read_text("utf-8"))
    return {}


def save_progress(data: dict[str, str]):
    OUTPUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def get_words_to_generate() -> list[str]:
    dict_words = set(DICT_PATH.read_text("utf-8").splitlines())
    dict_words.discard("")
    wiktionary = set(json.loads(WIKTIONARY_PATH.read_text("utf-8")).keys())
    already_done = set(load_progress().keys())

    remaining = dict_words - wiktionary - already_done
    return sorted(remaining)


def validate_ipa(word: str, ipa: str) -> str | None:
    """Return error message if IPA is invalid, None if OK."""
    if not ipa.startswith("/") or not ipa.endswith("/"):
        return f"not enclosed in slashes: {ipa}"
    inner = ipa[1:-1]
    for char in inner:
        if char not in VALID_CODEPOINTS:
            return f"invalid codepoint U+{ord(char):04X} '{char}' in: {ipa}"
    return None


def call_claude(client, prompt: str, words: list[str]) -> str:
    word_list = "\n".join(words)
    for attempt in range(MAX_RETRIES):
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
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                print(f"    Retry {attempt+1}/{MAX_RETRIES-1}: {e.__class__.__name__}. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def parse_response(text: str) -> dict[str, str]:
    results = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or "\t" not in line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            results[parts[0].strip()] = parts[1].strip()
    return results


def main():
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    words = get_words_to_generate()

    if not words:
        print("Nothing to generate — all words already covered.")
        return

    progress = load_progress()
    invalid = {}
    if INVALID_PATH.exists():
        invalid = json.loads(INVALID_PATH.read_text("utf-8"))

    total_batches = (len(words) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Words to generate: {len(words):,}")
    print(f"Batches: {total_batches} (batch size: {BATCH_SIZE})")
    print(f"Model: {MODEL_ID}")
    print(f"Already done: {len(progress):,}")
    print()

    client = boto3.client(
        "bedrock-runtime", region_name=REGION, config=Config(read_timeout=300)
    )

    generated_this_run = 0
    errors_this_run = 0

    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  [{batch_num}/{total_batches}] Generating {len(batch)} words...", end=" ", flush=True)

        try:
            response_text = call_claude(client, prompt, batch)
            parsed = parse_response(response_text)

            batch_ok = 0
            batch_invalid = 0
            for word in batch:
                if word in parsed:
                    ipa = parsed[word]
                    error = validate_ipa(word, ipa)
                    if error:
                        invalid[word] = {"ipa": ipa, "error": error}
                        batch_invalid += 1
                    else:
                        progress[word] = ipa
                        batch_ok += 1

            generated_this_run += batch_ok
            errors_this_run += batch_invalid
            missing = len(batch) - batch_ok - batch_invalid
            print(f"✓ {batch_ok} ok, {batch_invalid} invalid, {missing} missing")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            errors_this_run += len(batch)

        # Save after every batch (resumable)
        save_progress(progress)
        if invalid:
            INVALID_PATH.write_text(
                json.dumps(invalid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    print()
    print(f"=== DONE ===")
    print(f"Generated this run: {generated_this_run:,}")
    print(f"Invalid this run: {errors_this_run}")
    print(f"Total in generated_ipa.json: {len(progress):,}")
    print(f"Total invalid: {len(invalid)}")
    remaining = len(get_words_to_generate())
    print(f"Remaining: {remaining:,}")


if __name__ == "__main__":
    main()
