"""Typhoon ASR (scb10x/typhoon-asr-realtime, NeMo): python asr_typhoon.py MODEL.nemo WAV_DIR OUT.json"""
import glob, json, sys
import nemo.collections.asr as nemo_asr
model = nemo_asr.models.ASRModel.restore_from(sys.argv[1], map_location="cpu")
model.eval()
files = sorted(glob.glob(f"{sys.argv[2]}/*.wav"))
out = model.transcribe(files, batch_size=16)
texts = [o.text if hasattr(o, "text") else o for o in (out[0] if isinstance(out, tuple) else out)]
json.dump(dict(zip([f.rsplit('/', 1)[-1] for f in files], texts)), open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
print(len(texts), texts[:3])
