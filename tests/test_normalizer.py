"""Tests for the text normalizer."""

from fastthaig2p.normalizer import normalize


def test_plain_thai_unchanged():
    assert normalize("สวัสดีครับ") == "สวัสดีครับ"


def test_small_number_as_quantity():
    assert normalize("มี 42 คน") == "มี สี่สิบสอง คน"


def test_large_number_digit_by_digit():
    assert normalize("1234567890") == "หนึ่งสองสามสี่ห้าหกเจ็ดแปดเก้าศูนย์"


def test_comma_number():
    assert normalize("1,000,000") == "หนึ่งล้าน"


def test_decimal():
    assert normalize("3.14") == "สามจุดหนึ่งสี่"


def test_thai_numerals():
    assert "สองพันห้าร้อยหกสิบเก้า" in normalize("๒๕๖๙")


def test_phone_number():
    result = normalize("081-234-5678")
    assert "ศูนย์แปดหนึ่ง" in result
    assert "ห้าหกเจ็ดแปด" in result


def test_alphanum_id():
    result = normalize("ORD-001")
    assert "โอ" in result
    assert "ศูนย์ศูนย์หนึ่ง" in result


def test_month_abbreviation():
    assert "มกราคม" in normalize("ม.ค.")


def test_era_abbreviation():
    assert "พุทธศักราช" in normalize("พ.ศ.")


def test_title_abbreviation():
    assert "ด็อกเตอร์" in normalize("ดร.")


def test_mai_yamok():
    assert normalize("เด็กๆ") == "เด็กเด็ก"


def test_english_letter_in_id():
    result = normalize("A1")
    assert "เอ" in result
