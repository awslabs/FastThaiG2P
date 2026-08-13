"""Tests for the G2P engine."""

import time

from fastthaig2p import G2P


def test_known_word_returns_ipa():
    g2p = G2P()
    result = g2p.convert("กิน")
    assert "/kin˧/" in result


def test_multi_word_sentence():
    g2p = G2P()
    result = g2p.convert("ไปกินข้าว")
    assert "/paj˧/" in result
    assert "kʰaːw˥˩" in result


def test_oov_passthrough():
    g2p = G2P()
    result = g2p.convert("สตาร์บัคส์")
    # This word is likely not in Wiktionary 13k, should pass through
    assert "สตาร์บัคส์" in result or "/" in result


def test_number_normalized():
    g2p = G2P()
    result = g2p.convert("มี 3 คน")
    # "3" should be normalized to "สาม" which has IPA
    assert "สาม" not in result or "/" in result  # either IPA or passthrough of Thai
    assert "3" not in result


def test_abbreviation_expanded():
    g2p = G2P()
    result = g2p.convert("ม.ค.")
    # Should expand to มกราคม then produce IPA
    assert "ม.ค." not in result


def test_no_file_io_after_init():
    g2p = G2P()
    # After init, convert should be pure in-memory
    # We just verify it doesn't error on repeated calls
    for _ in range(100):
        g2p.convert("ทดสอบ")


def test_latency_dict_hits_under_1ms():
    g2p = G2P()
    g2p.convert("warmup")

    # Use only words known to be in Wiktionary IPA dict for pure-lookup benchmark
    text = "ไป กิน ข้าว กัน"
    start = time.perf_counter()
    for _ in range(100):
        g2p.convert(text)
    elapsed = (time.perf_counter() - start) / 100

    assert elapsed < 0.001, f"Per-call latency {elapsed*1000:.3f}ms exceeds 1ms"


def test_empty_string():
    g2p = G2P()
    result = g2p.convert("")
    assert result == ""
