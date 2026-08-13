"""Export a Thai-finetuned Kokoro checkpoint to ONNX.

Wraps kokoro.model.KModelForONNX (token IDs in, waveform out) with
disable_complex=True so the iSTFT head uses real arithmetic that ONNX
can represent. Dynamic axes handle variable phoneme counts and the
data-dependent audio length from the duration predictor.

Usage:
    python scripts/export_onnx.py \
        --model kokoro_thai.pth --config config.json \
        --output kokoro_thai.onnx [--voicepack thai_som.pt --validate]

The exported graph takes (input_ids[1,T], ref_s[1,256], speed[1]) and
returns (waveform[N], duration[T]). Pair it with fastthaig2p.TTS by
passing the .onnx path as model_path.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help=".pth in KModel inference format")
    parser.add_argument("--config", required=True, help="config.json with Thai vocab")
    parser.add_argument("--output", required=True, help="output .onnx path")
    parser.add_argument("--voicepack", help="voicepack for --validate")
    parser.add_argument(
        "--validate", action="store_true",
        help="compare ONNX vs PyTorch audio on Thai test sentences",
    )
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()

    import torch
    from kokoro.model import KModel, KModelForONNX

    kmodel = KModel(
        repo_id="hexgrad/Kokoro-82M",
        config=args.config,
        model=args.model,
        disable_complex=True,
    ).eval()
    wrapper = KModelForONNX(kmodel).eval()

    dummy_ids = torch.LongTensor([[0, *range(10, 60), 0]])
    dummy_ref = torch.randn(1, 256)
    dummy_speed = torch.ones(1)

    print(f"Exporting to {args.output} (opset {args.opset})...")
    torch.onnx.export(
        wrapper,
        (dummy_ids, dummy_ref, dummy_speed),
        args.output,
        input_names=["input_ids", "ref_s", "speed"],
        output_names=["waveform", "duration"],
        dynamic_axes={
            "input_ids": {1: "n_tokens"},
            "waveform": {0: "n_samples"},
            "duration": {0: "n_tokens"},
        },
        opset_version=args.opset,
        do_constant_folding=True,
    )

    import onnx

    onnx.checker.check_model(onnx.load(args.output))
    size_mb = Path(args.output).stat().st_size / 1e6
    print(f"Export OK: {args.output} ({size_mb:.0f} MB)")

    if args.validate:
        if not args.voicepack:
            parser.error("--validate requires --voicepack")
        validate(kmodel, args.output, args.voicepack)


def validate(kmodel, onnx_path: str, voicepack_path: str) -> None:
    import numpy as np
    import onnxruntime as ort
    import torch

    from fastthaig2p import G2P, ipa_to_kokoro

    sentences = [
        "สวัสดีค่ะ ยินดีต้อนรับสู่บริการของเรา",
        "ยอดเงินคงเหลือสามพันห้าร้อยบาท",
        "ใครขายไข่ไก่ ใกล้ๆ บ้านเรา",
        "กรุณากดหมายเลขหนึ่งเพื่อติดต่อพนักงาน",
        "วันนี้อากาศเป็นอย่างไรบ้าง",
    ]
    g2p = G2P()
    voice = torch.load(voicepack_path, map_location="cpu", weights_only=True)
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

    import time

    print("\nValidating ONNX vs PyTorch:")
    torch_total = onnx_total = 0.0
    for text in sentences:
        phonemes = ipa_to_kokoro(g2p.convert(text))
        ids = [kmodel.vocab[c] for c in phonemes if c in kmodel.vocab]
        input_ids = torch.LongTensor([[0, *ids, 0]])
        ref_s = voice[len(phonemes) - 1]

        t0 = time.perf_counter()
        with torch.no_grad():
            pt_audio, _ = kmodel.forward_with_tokens(input_ids, ref_s)
        torch_total += time.perf_counter() - t0
        pt_audio = pt_audio.squeeze().numpy()

        t0 = time.perf_counter()
        onnx_audio, _ = sess.run(
            None,
            {
                "input_ids": input_ids.numpy(),
                "ref_s": ref_s.numpy(),
                "speed": np.ones(1, dtype=np.float32),
            },
        )
        onnx_total += time.perf_counter() - t0

        n = min(len(pt_audio), len(onnx_audio))
        # duration rounding can differ at the boundary; compare overlap
        diff = np.abs(pt_audio[:n] - onnx_audio[:n]).max()
        corr = np.corrcoef(pt_audio[:n], onnx_audio[:n])[0, 1]
        secs = len(onnx_audio) / 24000
        print(
            f"  {text[:30]:<32} {secs:4.1f}s  len Δ{abs(len(pt_audio)-len(onnx_audio)):>4}  "
            f"max|Δ| {diff:.2e}  corr {corr:.6f}"
        )

    print(f"\nPyTorch total: {torch_total:.2f}s | ONNX total: {onnx_total:.2f}s "
          f"| speedup {torch_total/onnx_total:.2f}x")


if __name__ == "__main__":
    main()
