from __future__ import annotations

import unicodedata
from typing import Any


def normalize_ingredient_name(
    value: Any,
) -> str:
    text = str(value or "").strip().lower()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    return " ".join(text.split())
