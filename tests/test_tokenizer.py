"""Tests for the Tokenizer class."""

import tempfile
from pathlib import Path

from fastthaig2p.tokenizer import Tokenizer, DEFAULT_DICT_PATH


def test_vocab_size_matches_dict_file():
    lines = [l for l in DEFAULT_DICT_PATH.read_text("utf-8").splitlines() if l]
    tok = Tokenizer()
    assert len(tok.vocab) == len(lines)


def test_custom_word_segments_as_single_token():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("สวัสดี\nครับ\nแบรนด์ใหม่\n")
        tmp_path = f.name

    tok = Tokenizer(dict_path=tmp_path)
    result = tok.tokenize("แบรนด์ใหม่ครับ")
    assert "แบรนด์ใหม่" in result

    Path(tmp_path).unlink()


def test_basic_segmentation():
    tok = Tokenizer()
    result = tok.tokenize("สวัสดีครับ")
    assert result == ["สวัสดี", "ครับ"]
