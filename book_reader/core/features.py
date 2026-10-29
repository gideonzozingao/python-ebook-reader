"""Optional features that can be switched on or off in Settings.

One list is the single source of truth: the Settings page draws its switches from it, the
preferences get their defaults from it, and every page asks `enabled()` before showing or
starting a feature. Turning a feature off only hides it and blocks it; your data is untouched.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    name: str
    title: str
    description: str
    shortcut: str = ""


FEATURES = (
    Feature("roadmap", "Book roadmap",
            "An outline of the open book with page ranges and a link to every section.", "Ctrl+R"),
    Feature("mindmap", "Mind maps",
            "Draw mind maps for a book, or turn your notes into one.", "Ctrl+M"),
    Feature("journal", "Book journal",
            "Write notes filed under the section you are reading, with summary and export.", "Ctrl+J"),
    Feature("flashcards", "Review and flashcards",
            "Quiz yourself with flashcards made from your notes and highlights."),
    Feature("stats", "Reading statistics and daily goal",
            "The Reading Stats window and the goal line in the library. Reading time is still "
            "recorded while this is off, so nothing is lost."),
    Feature("lookup", "Dictionary lookup",
            "Look up a selected word (Ctrl+K or right-click). Sends that word to an online dictionary.",
            "Ctrl+K"),
)

BY_NAME = {f.name: f for f in FEATURES}
DEFAULTS = {f"feature_{f.name}": True for f in FEATURES}


def enabled(prefs, name: str) -> bool:
    """True if the feature is on (a missing preference counts as on)."""
    if prefs is None:
        return True
    return bool(prefs.v.get(f"feature_{name}", True))


def off_message(name: str) -> str:
    return f"{BY_NAME[name].title} is turned off. You can switch it on in Settings (Ctrl+,)"
