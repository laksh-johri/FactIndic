"""Light, script-aware text normalisation shared by retrieval and rule checks.

normalize() makes surface variants comparable WITHOUT changing meaning:
  * Unicode NFC (one canonical code-point sequence per character)
  * Devanagari digits -> ASCII digits   (२०२५ -> 2025)
  * nukta removed                        (ज़ -> ज, फ़ -> फ)
  * chandrabindu -> anusvara             (हँ -> हं)
  * lowercase Latin, collapse whitespace
"""
from __future__ import annotations

import re
import unicodedata

DEV_TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")
NUKTA = "़"
CHANDRABINDU, ANUSVARA = "ँ", "ं"
_WS = re.compile(r"\s+")


def normalize_digits(text: str) -> str:
    return text.translate(DEV_TO_ASCII)


def strip_nukta(text: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFD", text).replace(NUKTA, ""))


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    t = normalize_digits(t)
    t = strip_nukta(t)
    t = t.replace(CHANDRABINDU, ANUSVARA)
    return _WS.sub(" ", t.lower()).strip()
