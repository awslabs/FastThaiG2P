from fastthaig2p.g2p import G2P
from fastthaig2p.kokoro import ipa_to_kokoro
from fastthaig2p.normalizer import normalize
from fastthaig2p.tokenizer import Tokenizer

__all__ = ["G2P", "Tokenizer", "normalize", "ipa_to_kokoro", "TTS"]


def __getattr__(name):
    # TTS pulls in kokoro → torch/spacy (~6s); load only when asked for
    if name == "TTS":
        from fastthaig2p.tts import TTS

        return TTS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
