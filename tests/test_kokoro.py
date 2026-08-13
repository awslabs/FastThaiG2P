"""Tests for the IPA-to-Kokoro phoneme mapping."""

from fastthaig2p.kokoro import ipa_to_kokoro


def test_basic_sentence():
    assert (
        ipa_to_kokoro("/sa˨˩.wat̚˨˩.diː˧/ /kʰrap̚˦˥/")
        == "sa↓.wat↓.diː→ kʰrap↑"
    )


def test_five_tones_distinct():
    """All five Thai tones must map to distinct symbols (no mergers)."""
    tones = {
        "˧": "→",    # mid
        "˨˩": "↓",   # low
        "˥˩": "↘",   # falling
        "˦˥": "↑",   # high
        "˩˩˦": "↗",  # rising
    }
    outputs = {ipa_to_kokoro(f"/maː{chao}/") for chao in tones}
    assert len(outputs) == 5
    for chao, arrow in tones.items():
        assert ipa_to_kokoro(f"/maː{chao}/") == f"maː{arrow}"


def test_high_vs_rising_minimal_pair():
    """ม้า (horse, high) and หมา (dog, rising) must not collapse."""
    assert ipa_to_kokoro("/maː˦˥/") != ipa_to_kokoro("/maː˩˩˦/")


def test_affricates():
    assert ipa_to_kokoro("/t͡ɕʰan˩˩˦/") == "ʨʰan↗"
    assert ipa_to_kokoro("/t͡ɕaːn˧/") == "ʨaːn→"


def test_strips_unsupported_diacritics():
    # unreleased stop t̚ and non-syllabic a̯
    assert ipa_to_kokoro("/wat̚˨˩/") == "wat↓"
    assert ipa_to_kokoro("/dia̯w˩˩˦/") == "diaw↗"


def test_no_slash_input():
    """metadata.csv-style input without slashes still converts."""
    assert ipa_to_kokoro("maː˦˥ maː˩˩˦") == "maː↑ maː↗"
