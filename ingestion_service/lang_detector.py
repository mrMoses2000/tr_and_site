import re
from typing import Dict, Literal, List

SupportedLanguage = Literal["ru", "kk", "en", "unknown"]

KAZAKH_SPECIFIC_CHARS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
CYRILLIC_PATTERN = re.compile(r'[а-яёА-ЯЁ]')
LATIN_PATTERN = re.compile(r'[a-zA-Z]')

def detect_language(text: str) -> SupportedLanguage:
    """
    Detects whether the primary language of the text is Kazakh ('kk'),
    Russian ('ru'), or English ('en').
    """
    if not text or len(text.strip()) == 0:
        return "unknown"

    kazakh_count = sum(1 for ch in text if ch in KAZAKH_SPECIFIC_CHARS)
    cyrillic_matches = CYRILLIC_PATTERN.findall(text)
    cyrillic_count = len(cyrillic_matches)
    latin_matches = LATIN_PATTERN.findall(text)
    latin_count = len(latin_matches)

    total_chars = cyrillic_count + latin_count + kazakh_count
    if total_chars < 10:
        return "unknown"

    # If Kazakh-specific characters appear in significant number or ratio
    if kazakh_count > 5 or (kazakh_count > 0 and kazakh_count / (cyrillic_count + 1) > 0.01):
        return "kk"

    # If mostly Cyrillic without Kazakh-specific characters -> Russian
    if cyrillic_count > latin_count * 1.5:
        return "ru"

    # If mostly Latin -> English
    if latin_count > cyrillic_count * 1.5:
        return "en"

    # Fallback to whichever has more characters
    if cyrillic_count >= latin_count:
        return "ru"
    return "en"

def get_language_options(detected_lang: SupportedLanguage) -> List[Dict[str, str]]:
    """
    Returns tailored options for the Telegram bot based on detected document language.
    Prevents offering 'Translate to Russian' when the document is already in Russian.
    """
    if detected_lang == "ru":
        return [
            {
                "code": "kk",
                "label": "🇰🇿 Қазақша аудару (Теологиялық аударма)",
                "description": "Параллельный казахско-русский текст"
            },
            {
                "code": "original",
                "label": "📖 Опубликовать в оригинале на русском (Без перевода)",
                "description": "Чистый академический текст на русском со сносками"
            },
            {
                "code": "en",
                "label": "🇬🇧 Translate to English (Academic translation)",
                "description": "Parallel English-Russian text"
            }
        ]
    elif detected_lang == "kk":
        return [
            {
                "code": "original",
                "label": "📖 Түпнұсқада қазақша жариялау (Аудармасыз)",
                "description": "Қазақ тіліндегі түпнұсқа мәтін"
            },
            {
                "code": "ru",
                "label": "🇷🇺 Орыс тіліне аудару (Перевод на русский)",
                "description": "Параллель орысша-қазақша мәтін"
            },
            {
                "code": "en",
                "label": "🇬🇧 Ағылшын тіліне аудару (Translate to English)",
                "description": "Parallel English-Kazakh text"
            }
        ]
    else: # English or unknown
        return [
            {
                "code": "kk",
                "label": "🇰🇿 Қазақша аудару (Богословский перевод на казахский)",
                "description": "Параллельный казахско-английский текст"
            },
            {
                "code": "ru",
                "label": "🇷🇺 Перевести на русский (Академический перевод)",
                "description": "Параллельный русско-английский текст"
            },
            {
                "code": "original",
                "label": "📖 Publish English original (Без перевода)",
                "description": "Publish original English text"
            }
        ]
