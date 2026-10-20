"""Daily review inbox: old notes come back after growing intervals (no Qt)."""
import time

from book_reader.services.notes_index import all_entries


INTERVALS = [1, 3, 7, 14, 30, 60, 120]  # days until a note resurfaces again, by box
ACTIONS = {"again": 0, "good": 1, "easy": 2}


def key_of(e: dict) -> str:
    return f"{e['kind']}:{e['id']}"


def _due_list(library, now: float) -> list[tuple[float, dict]]:
    states = library.review_states()
    items = []
    for e in all_entries(library):
        if not (e["text"] or e["quote"]).strip():
            continue
        state = states.get(key_of(e))
        if state and state[0] < 0:  # archived
            continue
        due = state[1] if state else e["created"] + 86400  # new notes wait a day
        if due <= now:
            items.append((due, e))
    items.sort(key=lambda t: t[0])
    return items


def due_items(library, limit: int = 10, now: float | None = None) -> list[dict]:
    return [e for _, e in _due_list(library, now or time.time())[:limit]]


def count_due(library, now: float | None = None) -> int:
    return len(_due_list(library, now or time.time()))


def answer(library, e: dict, action: str, now: float | None = None):
    """again / good / easy move the note through the intervals; archive removes it."""
    now = now or time.time()
    key = key_of(e)
    if action == "archive":
        library.set_review(key, e["book_id"], -1, 0)
        return
    box = library.review_states().get(key, (0, 0))[0]
    box = 0 if action == "again" else min(max(box, 0) + ACTIONS[action], len(INTERVALS) - 1)
    library.set_review(key, e["book_id"], box, now + INTERVALS[box] * 86400)
