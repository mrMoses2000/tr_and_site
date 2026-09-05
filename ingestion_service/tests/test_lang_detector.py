import pytest
from ingestion_service.lang_detector import detect_language, get_language_options

def test_detect_language_russian():
    ru_text = "Герменевтическая спираль: общее введение в библейское толкование. Грант Р. Осборн."
    assert detect_language(ru_text) == "ru"

def test_detect_language_english():
    en_text = "The Hermeneutical Spiral: A Comprehensive Introduction to Biblical Interpretation. Grant R. Osborne."
    assert detect_language(en_text) == "en"

def test_detect_language_kazakh():
    kk_text = "Жаңа Өсиет теологиясының негіздері мен қағидалары. Киелі Жазбаны дұрыс түсіну."
    assert detect_language(kk_text) == "kk"

def test_detect_language_empty():
    assert detect_language("") == "unknown"

def test_get_language_options_russian():
    options = get_language_options("ru")
    codes = [opt["code"] for opt in options]
    assert "kk" in codes
    assert "original" in codes
    # Must NOT offer 'ru' since it is already Russian!
    assert "ru" not in codes

def test_get_language_options_english():
    options = get_language_options("en")
    codes = [opt["code"] for opt in options]
    assert "kk" in codes
    assert "ru" in codes
    assert "original" in codes
