"""Versioned, deterministic highlight-phrase lexicon; no ML or network I/O.

Built-in terms are curated in code. User additions live separately in the
installation's data/settings/highlight_words.json, never overwritten by releases.
Terms are always treated as literal text, not user-supplied regexes.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable, Sequence

CATEGORIES = {
    "surprise": "Überraschung", "reaction": "Starke Reaktion",
    "laughter": "Lachen", "danger": "Gefahr",
    "accident": "Unfall / Schaden", "combat": "Kampf",
    "success": "Erfolg", "pursuit": "Verfolgung",
}
PRIORITY = {"high": 0.73, "context": 0.34, "low": 0.22}
MAX_CUSTOM_TERMS = 150
MAX_FILE_SIZE = 131072


@dataclass(frozen=True)
class PhraseRule:
    phrase: str
    category: str
    priority: str
    source: str = "default"  # default or user

    @property
    def strength(self) -> float:
        return PRIORITY[self.priority]

    @property
    def requires_context(self) -> bool:
        return self.priority != "high"


def _rule(phrase: str, category: str, priority: str = "high") -> PhraseRule:
    return PhraseRule(phrase, category, priority)


# English and German reaction cues, tested against routine narration. New
# slang goes here with tests: do not turn every game noun into a highlight.
DEFAULT_RULES: tuple[PhraseRule, ...] = (
    _rule("oh mein gott", "surprise"), _rule("ach du scheiße", "surprise"),
    _rule("was zum teufel", "surprise"), _rule("was zur hölle", "surprise"),
    _rule("wtf", "surprise"), _rule("no way", "surprise"),
    _rule("holy shit", "surprise"), _rule("oh my god", "surprise"),
    _rule("das gibt's doch nicht", "surprise"),
    _rule("nicht dein ernst", "surprise"),
    _rule("ich glaub es nicht", "surprise"),
    _rule("oh nein", "surprise"),
    _rule("alter", "reaction"), _rule("krass", "reaction"),
    _rule("unfassbar", "reaction"), _rule("wahnsinn", "reaction"),
    _rule("scheiße", "reaction"), _rule("scheisse", "reaction"),
    _rule("shit", "reaction"), _rule("fuck", "reaction"),
    _rule("wow", "reaction"), _rule("aua", "reaction"),
    _rule("heftig", "reaction"), _rule("unglaublich", "reaction"),
    _rule("haha", "laughter"), _rule("hahaha", "laughter"),
    _rule("lol", "laughter"), _rule("lmao", "laughter"),
    _rule("lache", "laughter"), _rule("lachen", "laughter"),
    _rule("lacht", "laughter"),
    _rule("vorsicht", "danger", "context"),
    _rule("pass auf", "danger", "context"),
    _rule("hilfe", "danger", "context"),
    _rule("unfall", "accident", "context"),
    _rule("crash", "accident", "context"),
    _rule("gerammt", "accident", "context"),
    _rule("was war das", "surprise", "context"),
    _rule("überschlagen", "accident", "context"),
    _rule("headshot", "combat", "context"),
    _rule("treffer", "combat", "context"),
    _rule("erwischt", "combat", "context"),
    _rule("gewonnen", "success", "context"),
    _rule("geschafft", "success", "context"),
    _rule("endlich", "success", "context"),
    _rule("jawoll", "success", "context"),
    _rule("polizei", "pursuit", "context"),
    _rule("cops", "pursuit", "context"),
    _rule("fahndung", "pursuit", "context"),
    _rule("verfolgung", "pursuit", "context"),
)


def settings_path() -> Path:
    from .portable import installation_directory
    return installation_directory() / "data" / "settings" / "highlight_words.json"


def _normalize_phrase(text: str) -> str:
    return " ".join(text.split()).lower()


def validate_custom_rules(rules: Sequence[PhraseRule]) -> list[PhraseRule]:
    if len(rules) > MAX_CUSTOM_TERMS:
        raise ValueError(f"Maximal {MAX_CUSTOM_TERMS} eigene Highlight-Ausdrücke")
    seen: set[str] = set()
    checked = []
    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, PhraseRule) or not isinstance(rule.phrase, str):
            raise ValueError(f"Ungültiger Ausdruck in Zeile {index}")
        phrase = " ".join(rule.phrase.split())
        if not (2 <= len(phrase) <= 80) or any(ord(c) < 32 for c in phrase):
            raise ValueError(f"Ausdruck {index}: bitte 2 bis 80 lesbare Zeichen eingeben")
        if rule.category not in CATEGORIES or rule.priority not in PRIORITY:
            raise ValueError(f"Ausdruck {index}: unbekannte Kategorie oder Priorität")
        key = _normalize_phrase(phrase)
        if key in seen:
            raise ValueError(f"Doppelter Ausdruck: {phrase}")
        seen.add(key)
        checked.append(PhraseRule(phrase, rule.category, rule.priority, source="user"))
    return checked


def load_custom_rules(path: str | Path | None = None) -> list[PhraseRule]:
    filename = Path(path) if path is not None else settings_path()
    if not filename.exists():
        return []
    if filename.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("Eigene Highlight-Wortliste ist ungewöhnlich groß")
    try:
        data = json.loads(filename.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("version") != 1
                or not isinstance(data.get("rules"), list)):
            raise ValueError("Unbekanntes Format der Highlight-Wortliste")
        rules = []
        for entry in data["rules"]:
            if not isinstance(entry, dict):
                raise ValueError("Ungültiger Highlight-Eintrag")
            rules.append(PhraseRule(entry["phrase"], entry["category"], entry["priority"], "user"))
        return validate_custom_rules(rules)
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Highlight-Wortliste kann nicht geladen werden: {exc}") from exc


def save_custom_rules(rules: Sequence[PhraseRule], path: str | Path | None = None) -> Path:
    filename = Path(path) if path is not None else settings_path()
    checked = validate_custom_rules(rules)
    payload = json.dumps({"version": 1, "rules": [
        {"phrase": rule.phrase, "category": rule.category, "priority": rule.priority}
        for rule in checked]}, indent=2, ensure_ascii=False)
    filename.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                         dir=filename.parent, prefix=".highlight_words-",
                                         suffix=".tmp", delete=False) as stream:
            pending = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, filename)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    return filename


def merged_rules(custom_rules: Sequence[PhraseRule] = ()) -> tuple[PhraseRule, ...]:
    # An identical personal expression overrides the shipped priority/category.
    custom = validate_custom_rules(custom_rules)
    by_key = {_normalize_phrase(rule.phrase): rule for rule in DEFAULT_RULES}
    for rule in custom:
        by_key[_normalize_phrase(rule.phrase)] = rule
    return tuple(by_key.values())


def match_rules(text: str, rules: Iterable[PhraseRule]) -> list[PhraseRule]:
    """Literal Unicode-aware whole-phrase matching; never execute user regex."""
    normalized = " ".join(text.split())
    hits = []
    for rule in rules:
        # Spaces inside a multiword phrase may vary in the recognized text.
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(piece) for piece in rule.phrase.split()) + r"(?!\w)"
        if re.search(pattern, normalized, re.IGNORECASE):
            hits.append(rule)
    return hits
