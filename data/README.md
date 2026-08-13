# Data Directory

## Core Files (runtime)

| File | Description | Used by |
|------|-------------|---------|
| `dict.txt` | Word list (62k), one per line. Drives both tokenization and IPA lookup keys. | `Tokenizer`, `G2P` |
| `ipa.json` | Flat `{word: "/ipa/"}` for runtime lookup. Merged from Wiktionary + generated. | `G2P` |
| `ipa_metadata.json` | Rich `{word: {ipa, source, pos, origin, ...}}` for auditing. | analysis only |

## Fallback G2P Data (vendored from tltk)

| File | Size | Description |
|------|------|-------------|
| `fallback/sylrule.lts` | 4 KB | Syllable pattern regex rules |
| `fallback/thaisyl.dict` | 31 KB | Exception syllable pronunciations |
| `fallback/sylseg.3g` | 15 MB | Syllable trigram statistics |
| `fallback/PhSTrigram.sts` | 1.3 MB | Pronunciation selection trigrams |
| `fallback/thdict` | 2.3 MB | Thai word dictionary (for syllable segmentation) |
| `fallback/sylform_var.pkl` | 244 KB | Syllable form variants |

## Source Files (for rebuild/audit)

| File | Description | Git? |
|------|-------------|------|
| `sources/manual_overrides.json` | User corrections (highest merge priority) | ✓ |
| `sources/wiktionary_ipa.json` | 13k IPA entries from kaikki.org (Wiktionary) | ✓ |
| `sources/generated_ipa.json` | ~49k IPA entries from Claude Opus 4.6 | ✗ (gitignored) |
| `sources/generated_ipa_invalid.json` | Entries that failed validation | ✗ (gitignored) |
| `sources/kaikki.org-dictionary-Thai.jsonl` | Raw Wiktionary dump (44 MB) | ✗ (gitignored) |
| `sources/pali_sanskrit_words.txt` | Pali/Sanskrit word list for validation exclusion | ✓ |

## Test Files (prompt validation)

| File | Description |
|------|-------------|
| `tests/ground_truth_ipa.json` | 34 manually verified IPA (initial test set) |
| `tests/blind_test_ipa.json` | 17 blind test words |

---

## Updating the Dictionary

### Adding new words to dict.txt

1. Add word(s) to `data/dict.txt`
2. Generate IPA: run `scripts/generate_ipa.py` (only generates for missing words)
3. Re-merge: run `scripts/merge_ipa.py`
4. Result: `ipa.json` updated with new entries

### Correcting wrong IPA

1. Add correction to `data/sources/manual_overrides.json`: `{"word": "/correct_ipa/"}`
2. Re-merge: run `scripts/merge_ipa.py`
3. Result: `ipa.json` updated — manual overrides have highest priority

Merge priority: **manual_overrides.json > wiktionary_ipa.json > generated_ipa.json**

### Full rebuild from scratch

```bash
# 1. Make sure data/dict.txt exists

# 2. Download kaikki.org data
curl -L -o data/sources/kaikki.org-dictionary-Thai.jsonl \
  "https://kaikki.org/dictionary/Thai/kaikki.org-dictionary-Thai.jsonl"

# 3. Extract Wiktionary IPA
uv run python3 scripts/extract_wiktionary_ipa.py

# 4. Generate IPA for remaining words (requires AWS Bedrock access)
uv run python3 scripts/generate_ipa.py

# 5. Merge everything
uv run python3 scripts/merge_ipa.py
```
