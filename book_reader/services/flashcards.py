"""Flashcards and quizzes built from a book's notes and highlights (no Qt)."""
import random
import re
import time

from dataclasses import dataclass

from book_reader.services.journal import ref_text


LEITNER_DAYS = [0, 1, 3, 7, 21]  # days until a card is due again, by box
_STOP = set("""about above after again against because before being below between could does doing
during each from further have having here itself just more most other over same should some such than
that their them then there these they this those through under until very were what when where which
while with would your""".split())


@dataclass
class Card:
    key: str          # 'note:12' / 'highlight:3' (progress is stored per key)
    topic: str
    chapter: str
    ref: str
    text: str         # the note or highlighted passage
    front: str        # flashcard prompt
    back: str         # flashcard answer
    cloze: str = ""   # text with one key word blanked
    answer: str = ""  # the blanked word


def make_cloze(text: str) -> tuple[str, str] | None:
    """Blank the longest non-trivial word. Returns (masked text, answer) or None."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]{3,}", text) if w.lower() not in _STOP]
    if not words:
        return None
    answer = max(words, key=len)
    return re.sub(rf"(?<![\w]){re.escape(answer)}(?![\w])", "_____", text, count=1), answer


def build_cards(entries: list[dict], fmt: str) -> list[Card]:
    """One card per note or highlight (see SummaryBuilder.entries)."""
    cards = []
    for e in entries:
        text = (e["text"] or e["quote"]).strip()
        if not text:
            continue
        ref = ref_text(e["chapter"], e["page"], e["total"], fmt)
        cloze = make_cloze(text)
        if e["kind"] == "note":
            front, back = f"{e['topic']}  ·  {ref}\n\nWhat did you note here?", e["text"]
        elif e["text"]:  # highlight with a note
            front, back = f"“{e['quote']}”\n\nWhat was your note?", e["text"]
        elif cloze:      # plain highlight: recall the missing word
            front, back = f"Fill in the blank:\n\n“{cloze[0]}”", e["quote"]
        else:
            front, back = f"Recall this passage from {ref}", e["quote"]
        cards.append(Card(f"{e['kind']}:{e['id']}", e["topic"], e["chapter"], ref, text, front,
                          back, cloze[0] if cloze else "", cloze[1] if cloze else ""))
    return cards


def section_choices(card: Card, sections: list[str], n: int = 4, rng=random) -> list[str]:
    """Multiple-choice options for 'Which section is this from?' (includes the answer)."""
    others = [s for s in dict.fromkeys(sections) if s != card.chapter]
    rng.shuffle(others)
    options = [card.chapter] + others[:n - 1]
    rng.shuffle(options)
    return options


def schedule(box: int, correct: bool, now: float | None = None) -> tuple[int, float]:
    """Leitner step: right answers move up a box (longer wait), wrong ones restart."""
    box = min(box + 1, len(LEITNER_DAYS) - 1) if correct else 0
    return box, (now or time.time()) + LEITNER_DAYS[box] * 86400


def is_due(state: tuple[int, float] | None, now: float | None = None) -> bool:
    return state is None or state[1] <= (now or time.time())
