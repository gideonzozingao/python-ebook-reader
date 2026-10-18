"""Dictionary look-up for selected text (free dictionaryapi.dev service, no key needed)."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request


API = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def clean_term(text: str, limit: int = 60) -> str:
    """Selected text -> a short search term (whitespace and edge punctuation removed)."""
    term = " ".join((text or "").replace("\u2029", " ").split())
    return term.strip(" \t\"'“”‘’.,;:!?()[]{}—–-")[:limit]


def is_single_word(term: str) -> bool:
    return bool(re.fullmatch(r"[^\W\d_][\w'’-]*", term))


def lookup_word(term: str, timeout: float = 6.0) -> dict:
    """Returns dict(word, phonetic, meanings=[(part_of_speech, [(definition, example)])]).
    Raises LookupError with a readable message when nothing can be shown."""
    if not is_single_word(term):
        raise LookupError("Dictionary look-up works for single words. Use the web links below.")
    url = API + urllib.parse.quote(term.lower())
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise LookupError(f"No definition found for “{term}”.") from exc
        raise LookupError(f"The dictionary service returned an error ({exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LookupError("Could not reach the dictionary (are you offline?).") from exc
    except ValueError as exc:
        raise LookupError("The dictionary returned an unreadable answer.") from exc
    if not isinstance(data, list) or not data:
        raise LookupError(f"No definition found for “{term}”.")
    entry = data[0]
    phonetic = entry.get("phonetic") or next(
        (p.get("text") for p in entry.get("phonetics", []) if p.get("text")), "")
    meanings = []
    for m in entry.get("meanings", []):
        defs = [(d.get("definition", ""), d.get("example", "")) for d in m.get("definitions", [])[:3]]
        if defs:
            meanings.append((m.get("partOfSpeech", ""), defs))
    if not meanings:
        raise LookupError(f"No definition found for “{term}”.")
    return dict(word=entry.get("word", term), phonetic=phonetic, meanings=meanings)


def web_links(term: str) -> dict[str, str]:
    q = urllib.parse.quote(term)
    return {
        "Wikipedia": f"https://en.wikipedia.org/wiki/Special:Search?search={q}",
        "Web search": f"https://www.google.com/search?q={q}",
    }


def short_definition(info: dict) -> str:
    """First definition, for saving into a book note."""
    pos, defs = info["meanings"][0]
    return f"{info['word']} ({pos}) — {defs[0][0]}" if pos else f"{info['word']} — {defs[0][0]}"
