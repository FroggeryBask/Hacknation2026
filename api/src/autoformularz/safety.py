"""Checks a generated COI form for content a hostile document may have smuggled in (prompt injection).

The model reads text from an uploaded file. A document can carry text written for the model ("zignoruj
poprzednie instrukcje…") or a fake form asking for passwords or card data, and the model may copy it into
labels, hints, options and links. The JSON schema and the compiler fix the structure, not the words. This
scan runs on every result (lint warnings with a SAFETY_ prefix), so API clients see the same findings as the
web preview (`src/lib/form/safety.ts`, same rules). It warns; it never changes the JSON.
"""

import html
import re
from collections.abc import Iterator
from urllib.parse import urlparse

from autoformularz.lint import Issue

# Data a public form never asks for. Bank account numbers are fine (refunds).
SENSITIVE = re.compile(
    r"\bhas(ł|l)\w*|\bpin\b|\bkod\w* (sms|weryfikacyjn\w*|autoryzacyjn\w*|jednorazow\w*|blik)|\bblik\b|\bcvv\b"
    r"|\bcvc\b|kart\w* (płatnicz|kredytow|debetow|bankow)\w*|data ważności karty|\blogin\b(?!\.gov)"
    r"|nazw\w* użytkownika|\bpassword\b|\btoken\w*|klucz\w* prywatn\w*|fraz\w* (odzyskiwania|seed)|\bseed\b",
    re.IGNORECASE,
)
# Text addressed to a language model, not to a citizen.
INSTRUCTION = re.compile(
    r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|above|prior|earlier|all)\b.{0,20}\b(instructions?|prompts?"
    r"|rules)\b|\bzignoruj\w*\b.{0,40}\b(instrukcj\w*|polece\w*|zasad\w*|reguł\w*)|\bsystem prompt\b|\bprompt\b"
    r"|\byou are (now )?(an? )?(ai|assistant|language model|chatgpt)\b|\bjesteś (teraz )?(asystent\w*|model\w*|ai)\b"
    r"|\bact as\b|\bjako model (językowy|ai)\b|<\|?(im_start|im_end|system)\|?>|\[/?(inst|system)\]"
    r"|^\s*(system|assistant)\s*:",
    re.IGNORECASE | re.MULTILINE,
)
# Zero-width and bidirectional control characters: hide or reorder text.
HIDDEN = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿]")
# HTML the renderer drops anyway, but it should never come from a paper form.
MARKUP = re.compile(
    r"<\s*(script|iframe|object|embed|form|input|style)\b|\bon[a-z]+\s*=|javascript:|data:text/html",
    re.IGNORECASE,
)
URL = re.compile(r"\b(?:https?://|www\.)[^\s\"'<>)]+", re.IGNORECASE)

RULES = [
    (
        "SAFETY_SENSITIVE_DATA",
        SENSITIVE,
        "Formularz pyta o dane, o które urząd nie prosi (hasło, PIN, karta płatnicza).",
    ),
    (
        "SAFETY_INSTRUCTION",
        INSTRUCTION,
        "Tekst wygląda na polecenie dla modelu AI (możliwa próba prompt injection).",
    ),
    (
        "SAFETY_HIDDEN_CHARS",
        HIDDEN,
        "Tekst zawiera niewidoczne znaki sterujące, które ukrywają lub odwracają treść.",
    ),
    ("SAFETY_MARKUP", MARKUP, "Tekst zawiera kod HTML lub skrypt."),
]


def trusted(url: str) -> bool:
    """Public administration domains: gov.pl and its subdomains (BIP, urzędy)."""
    host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
    return host == "gov.pl" or host.endswith(".gov.pl")


def texts(form: dict) -> Iterator[tuple[str, str]]:
    """(where, text) of every title, description and option, descriptions without HTML entities."""

    def walk(node, where: str) -> Iterator[tuple[str, str]]:
        if isinstance(node, dict):
            name = node.get("title") or node.get("techName") or ""
            here = f"{where} › {name}" if name and where else name or where
            for key in ("title", "description", "name", "tooltipMessage", "placeholder"):
                value = node.get(key)
                if isinstance(value, str) and value:
                    yield here, html.unescape(value)
            for value in node.values():
                yield from walk(value, here)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item, where)

    yield from walk(form, "")


def scan(form: dict) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()

    def add(code: str, message: str, where: str) -> None:
        if (code, where) not in seen:
            seen.add((code, where))
            issues.append(Issue("warning", code, message, where))

    for where, text in texts(form):
        for code, pattern, message in RULES:
            if pattern.search(text):
                add(code, message, where)
        for url in URL.findall(text):
            if url.lower().startswith("javascript:"):
                continue
            if not trusted(url):
                add("SAFETY_EXTERNAL_LINK", f"Link poza domeną gov.pl: {url[:80]}", where)
    return issues
