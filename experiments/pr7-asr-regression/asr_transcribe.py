"""Amazon Transcribe streaming (th-TH): python asr_transcribe.py WAV_DIR OUT.json REGION"""
import asyncio, glob, json, os, sys, wave
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler

class H(TranscriptResultStreamHandler):
    def __init__(self, s):
        super().__init__(s); self.parts = []
    async def handle_transcript_event(self, ev):
        for r in ev.transcript.results:
            if not r.is_partial and r.alternatives:
                self.parts.append(r.alternatives[0].transcript)

async def attempt(client, pcm):
    s = await client.start_stream_transcription(language_code="th-TH", media_sample_rate_hz=16000, media_encoding="pcm")
    h = H(s.output_stream)
    async def feed():
        for i in range(0, len(pcm), 3200):
            await s.input_stream.send_audio_event(audio_chunk=pcm[i:i+3200])
        await s.input_stream.send_audio_event(audio_chunk=b"\0" * 32000)
        await s.input_stream.end_stream()
    await asyncio.gather(feed(), h.handle_events())
    return " ".join(h.parts)

async def one(client, path, sem):
    async with sem:
        for n in range(4):
            try:
                pcm = wave.open(path).readframes(10**9)
                return os.path.basename(path), await asyncio.wait_for(attempt(client, pcm), 30)
            except Exception as e:
                err = repr(e); await asyncio.sleep(2 ** n)
        return os.path.basename(path), f"ERROR {err}"

async def main():
    client = TranscribeStreamingClient(region=sys.argv[3])
    sem = asyncio.Semaphore(8)
    files = sorted(glob.glob(f"{sys.argv[1]}/*.wav"))
    import os
    done = {}
    if os.path.exists(sys.argv[2] + ".jsonl"):
        for l in open(sys.argv[2] + ".jsonl"):
            r = json.loads(l)
            if not r[1].startswith("ERROR"): done[r[0]] = r[1]
    log = open(sys.argv[2] + ".jsonl", "a")
    async def rec(f):
        r = await one(client, f, sem)
        log.write(json.dumps(r, ensure_ascii=False) + "\n"); log.flush()
        return r
    res = dict(done)
    res.update(dict(await asyncio.gather(*(rec(f) for f in files if os.path.basename(f) not in done))))
    json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(len(res), sum(v.startswith("ERROR") for v in res.values()), "errors", list(res.values())[:3])

asyncio.run(main())
