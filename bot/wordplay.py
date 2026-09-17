"""Шутка «Я пошел обедать» -> «Ты обедин чтоли»: основа слова + «ин»."""

from __future__ import annotations

import re

WORD_RE = re.compile(r"[а-яё]{3,}", re.IGNORECASE)

# Порядок важен: сначала длинные окончания.
SUFFIXES = (
    "ться", "тся", "ались", "ался", "алась", "ились", "ился", "илась",
    "аете", "ляет", "ываю", "иваю", "ает", "яет", "ует", "уют", "ают", "яют",
    "аем", "ием", "ишь", "ешь", "ать", "ять", "еть", "ить", "ыть", "уть", "оть",
    "ала", "яла", "ила", "ыла", "ели", "или", "ала", "ыми", "ому", "ого",
    "аю", "яю", "ую", "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие",
    "ла", "ли", "ло", "ет", "ут", "ют", "ит", "ат", "ят",
    "л", "ю", "у", "а", "я", "о", "е", "ы", "и", "ь",
)

VERB_MARKERS = (
    "ться", "тся", "ать", "ять", "еть", "ить", "ыть", "уть",
    "аю", "яю", "ую", "ешь", "ишь", "ает", "яет", "ает", "ал", "ял", "ил", "ел", "ул",
)

STOPWORDS = frozenset(
    """
    что чтоли как так там тут это этот эта эти тот той они она оно мне меня тебе тебя
    себе себя нас вам вас них ним нее его ему ее наш ваш мой твой еще уже или либо
    если чтобы потому когда пока где куда откуда почему зачем ничего никто никогда
    очень просто вроде типа блядь бля нахуй хуй пизда ебать сука нахер нихуя
    сейчас сегодня завтра вчера потом снова опять всегда короче вообще может надо
    нибудь либо кто-то что-то кого кому чего чему всех всем весь вся все
    """.split()
)


def _stem(word: str) -> str | None:
    stem = word.lower().replace("ё", "е")
    for suffix in SUFFIXES:
        if stem.endswith(suffix) and len(stem) - len(suffix) >= 3:
            stem = stem[: -len(suffix)]
            break
    while len(stem) > 3 and stem[-1] in "аеиоуыэюяьъй":
        stem = stem[:-1]
    return stem if len(stem) >= 3 else None


def inify(word: str) -> str | None:
    """«обедать» -> «обедин», «пошел» -> «пошин», «пиво» -> «пивин»."""
    stem = _stem(word)
    return f"{stem}ин" if stem else None


def _looks_like_verb(word: str) -> bool:
    return word.endswith(VERB_MARKERS)


def pick_joke(text: str) -> str | None:
    """Достаёт из сообщения самое сочное слово и лепит из него «-ин»."""
    words = [w.lower() for w in WORD_RE.findall(text) if w.lower() not in STOPWORDS and len(w) >= 4]
    if not words:
        return None

    verbs = [w for w in words if _looks_like_verb(w)]
    for candidate in sorted(verbs, key=len, reverse=True) + sorted(words, key=len, reverse=True):
        joke = inify(candidate)
        if joke:
            return joke
    return None
