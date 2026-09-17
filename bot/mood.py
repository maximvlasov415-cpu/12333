"""Определяет по сообщению, уместна ли сейчас шутка.

Павлик, который шутит в каждой реплике, быстро надоедает: половина шуток
выходит натянутой. Режим сообщения решает, можно ли вообще въезжать с панчем.
"""

from __future__ import annotations

import re

SERIOUS = "serious"
INSULT = "insult"
QUESTION = "question"
BANTER = "banter"

# Насколько часто в этом режиме вообще разрешена шутка.
JOKE_CHANCE = {
    SERIOUS: 0.0,
    INSULT: 1.0,
    QUESTION: 0.25,
    BANTER: 0.7,
}

SERIOUS_RE = re.compile(
    r"умер|смерт|похорон|хорони|больниц|болезн|заболе|\bрак\b|онколог|инсульт|инфаркт"
    r"|скорая|реанимац|операци|авари|разбил.{0,10}маши|развод|развел|уволил|сократил"
    r"|депресс|суицид|повесит|не хочу жить|\bбед[аыуе]\b|\bгоре\b|помогите"
    r"|помоги.{0,15}пожалуйста|украли|обокрал|пожар|затопил|потерял работу",
    re.IGNORECASE,
)

INSULT_RE = re.compile(
    r"\bтуп(ой|ая|ица)|дурак|идиот|дебил|кретин|мудак|долбо|заткнис|завали|пошел нахуй"
    r"|иди нахуй|пшел|бесиш|достал|надоел|хуйню несеш|хуйня.{0,10}пишеш|бот сраный",
    re.IGNORECASE,
)

QUESTION_WORDS = frozenset(
    """
    как что чё че где когда почему зачем сколько кто какой какая какие куда откуда
    можно стоит посоветуй подскажи объясни расскажи напомни
    """.split()
)


def classify(text: str) -> str:
    stripped = text.strip()
    if SERIOUS_RE.search(stripped):
        return SERIOUS
    if INSULT_RE.search(stripped):
        return INSULT
    if _is_question(stripped):
        return QUESTION
    return BANTER


def _is_question(text: str) -> bool:
    words = [word.strip(".,!?«»\"'") for word in text.lower().split()]
    if len(words) < 2:
        return False
    # Вопросительное слово в начале: «как накачать пресс», «павлик, что такое ипотека».
    if any(word in QUESTION_WORDS for word in words[:3]):
        return True
    # Знак вопроса сам по себе ещё не вопрос: «вечером в пабг?» — это трёп.
    return "?" in text and len(words) >= 5
