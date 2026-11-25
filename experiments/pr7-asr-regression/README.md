# PR #7 ASR regression test

This test checks whether the IPA cleanup in PR #7 changes what the shipped Kokoro model (`kokoro_thai.onnx`, release v0.3.0) says, and whether any change is for the worse.

## Result

The PR is safe to merge. Of the 1,009 changed entries, 838 produce byte-identical Kokoro phoneme input, so their audio cannot change. For the other 171, two independent ASR systems show no consistent regression, and Amazon Transcribe shows a net improvement.

| Set | n | Transcribe hit, before → after | Typhoon hit, before → after |
|---|---|---|---|
| Changed entries | 171 | 53.8% → 63.2% (23 better, 7 worse) | 42.1% → 41.5% (18 better, 14 worse) |
| Repeated / multi-word entries | 14 | 0% → 92.9% | 0% → 7.1% (CER 0.097 → 0.062) |
| Diphthong length | 91 | 65.9% → 67.0% (6 better, 2 worse) | 59.3% → 52.7% (3 better, 9 worse) |
| Unchanged control | 170 | 60.0% → 60.0% | 52.4% → 52.4% |
| Sensitivity (all tones rotated) | 40 | 57.5% → 22.5% | 52.5% → 15.0% |

A "hit" means the ASR transcribed the target word exactly. CER is the character error rate over the whole sentence. The full per-category table and every flipped word are in `results.txt`.

The two ASR systems disagree on the direction of the diphthong change, and neither result is significant. We treat it as noise.

The repeated and multi-word row overstates the real-world gain. This test feeds dictionary values straight to Kokoro. `G2P.convert` expands ๆ before the dictionary lookup, so 12 of those 14 entries are never used in practice. Only the 2 multi-word names are reachable: ศิลป์ พีระศรี and อินเตอร์ มิลาน. Before the PR, they had a space inside one `/.../` group, and `ipa_to_kokoro` dropped everything after the first word.

On the 156 changed entries that don't contain ๆ:

| ASR | Hit, before → after | CER, before → after | Better / worse |
|---|---|---|---|
| Transcribe | 57.7% → 60.9% | 0.035 → 0.032 | 12 / 6 |
| Typhoon | 46.2% → 45.5% | 0.048 → 0.044 | 15 / 12 |

## Method

1. For every entry whose `ipa_to_kokoro` output differs between `main` and the PR, synthesize the sentence ฉันพูดคำว่า ___ อีกครั้งหนึ่ง twice, once with each phoneme string. The carrier words have the same IPA on both sides, so only the target word varies. The carrier gives no context, so the ASR language model cannot guess the target.
2. Control: 170 random unchanged words (seed 7) synthesized the same way. This measures the ASR's baseline accuracy and confirms that identical input gives identical transcripts.
3. Sensitivity: 40 of the control words with every tone rotated. This proves the test detects a bad pronunciation.
4. Transcribe each clip with Amazon Transcribe streaming (`th-TH`, us-west-2) and with Typhoon ASR (`scb10x/typhoon-asr-realtime`, local NeMo).
5. Score target-word exact match and sentence CER, paired per word.

Limits: one voice (`thai_som`), one carrier sentence, one transcription per clip.

## Reproduce

The WAV files (592 clips, 38 MB) are not committed. Kokoro inference is deterministic, so `synth.py` regenerates them exactly.

```bash
git show 4e82a29:data/ipa.json > before.json
git show adcd3f3:data/ipa.json > after.json
uv run --extra tts --with scipy python synth.py wavs before.json after.json   # run from the repo root
python asr_transcribe.py wavs transcripts_transcribe.json us-west-2           # needs amazon-transcribe
python asr_typhoon.py typhoon-asr-realtime.nemo wavs transcripts_typhoon.json # needs nemo_toolkit[asr]
python score.py items.json transcripts_transcribe.json transcripts_typhoon.json
```

## Files

- `items.json` lists every stimulus: set, word, both phoneme strings, both IPA strings, and the WAV names.
- `transcripts_transcribe.json` and `transcripts_typhoon.json` map each WAV name to its transcript.
- `results.txt` is the output of `score.py`.
- `synth.py`, `asr_transcribe.py`, `asr_typhoon.py` and `score.py` are the scripts that produced them.
