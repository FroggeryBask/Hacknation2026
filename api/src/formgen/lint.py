"""Rule checker for a form JSON (like KSeF's schema + business-rule validation).

Rules come from "Reguły techniczne konfiguracji formularzy i pól na formularzu" and "Dane inicjalne".
Errors break the rules; warnings flag places where the reference JSON files themselves differ from
the written rules (so the reference files pass with warnings only)."""

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

Json = dict[str, Any]

FIELD_TYPES = {
    "TEXT_FIELD",
    "CHECKBOX",
    "NUMBER",
    "CONSENT_SECTION",
    "SELECT",
    "TEXTAREA",
    "FILE_UPLOADER",
    "RADIO",
    "DATEPICKER",
    "TEXT_BLOCK",
    "INFO_SECTION",
}
SECTION_TYPES = {"SECTION", "REPEATING_SECTION"}
INPUT_TYPES = FIELD_TYPES - {"TEXT_BLOCK", "INFO_SECTION"}
CHOICE_TYPES = {"SELECT", "RADIO", "CHECKBOX"}
VALIDATORS = {
    "REQUIRED",
    "EMAIL",
    "PESEL",
    "NIP",
    "REGON",
    "ZIP_CODE",
    "EPUAP",
    "ADE",
    "SERIAL_NUMBER_ID_CARD",
}
SOURCES = {"PESEL", "PESEL_ADDRESS", "MLPZ"}
SELECT_ONLY_DICTS = {
    "Kraje",
    "TERYT_4G_DOWODOWY",
    "TERYT_DOWODOWY",
    "Województwo",
    "Powiat",
    "Gmina",
    "Miejscowość",
}

TECH_REF = re.compile(r"'([^']+)' in (?:field\.techName|fieldTechName)")
TAB_REF = re.compile(r"tabs\['((?:[^'\\]|\\.)+)' in title\]")


@dataclass
class Issue:
    level: Literal["error", "warning"]
    code: str
    message: str
    path: str = ""


def lint(form: Json) -> list[Issue]:
    issues: list[Issue] = []

    def err(code: str, msg: str, path: str = "") -> None:
        issues.append(Issue("error", code, msg, path))

    def warn(code: str, msg: str, path: str = "") -> None:
        issues.append(Issue("warning", code, msg, path))

    title = form.get("title")
    if not isinstance(title, str) or not title.strip():
        err("TITLE_MISSING", "Formularz musi mieć tytuł.")
    elif len(title) > 255:
        err("TITLE_TOO_LONG", "Tytuł formularza może mieć najwyżej 255 znaków.")

    tabs = form.get("tabs") or []
    if len(tabs) < 2:
        err("TABS_MIN", "Formularz musi mieć co najmniej dwie strony.")
    finish = [t for t in tabs if t.get("type") == "FINISH"]
    if len(finish) != 1:
        err("FINISH_COUNT", "Formularz musi mieć dokładnie jedną stronę końcową (FINISH).")
    elif tabs and tabs[-1].get("type") != "FINISH":
        err("FINISH_NOT_LAST", "Strona końcowa (FINISH) musi być ostatnia.")
    for t in tabs:
        if t.get("type") not in ("MAIN", "FINISH"):
            err("TAB_TYPE", f"Nieznany typ strony: {t.get('type')}.", t.get("title", ""))

    ids: set[str] = set()
    tech_names: dict[str, int] = {}
    tab_titles = {t.get("title") for t in tabs}
    queries: list[tuple[str, str]] = []

    def check_field(f: Json, path: str, tab_type: str) -> None:
        fid = f.get("id")
        if not fid:
            err("ID_MISSING", "Element nie ma identyfikatora.", path)
        elif fid in ids:
            err("ID_DUPLICATE", f"Powtórzony identyfikator {fid}.", path)
        ids.add(fid or "")
        tech = f.get("techName")
        if not tech:
            err("TECHNAME_MISSING", "Element nie ma nazwy technicznej (techName).", path)
        else:
            tech_names[tech] = tech_names.get(tech, 0) + 1
        typ = f.get("type")
        validation = f.get("validation")
        if typ in FIELD_TYPES:
            if not isinstance(validation, list):
                warn("VALIDATION_NOT_LIST", "Atrybut validation powinien być tablicą.", path)
            else:
                for v in validation:
                    if v not in VALIDATORS:
                        err("VALIDATOR_UNKNOWN", f"Nieznany walidator: {v}.", path)
        if tab_type == "FINISH" and typ in INPUT_TYPES:
            err("FINISH_HAS_INPUT", "Na stronie końcowej nie może być pól do wprowadzania danych.", path)
        if tab_type == "FINISH" and typ == "TEXT_BLOCK":
            warn("FINISH_TEXT_BLOCK", "Reguły dopuszczają na stronie końcowej tylko INFO_SECTION.", path)
        if typ == "INFO_SECTION" and not f.get("description"):
            err("INFO_NO_DESCRIPTION", "Sekcja informacyjna musi mieć opis.", path)
        dictionary = f.get("dictionaryName")
        if dictionary and typ not in CHOICE_TYPES:
            err("DICT_WRONG_TYPE", "Słownik można podpiąć tylko do listy, radiobuttona lub checkboxa.", path)
        if dictionary in SELECT_ONLY_DICTS and typ != "SELECT":
            err("DICT_SELECT_ONLY", f"Słownik {dictionary} można podpiąć tylko do listy rozwijanej.", path)
        if typ in CHOICE_TYPES and not dictionary and not f.get("options"):
            err("OPTIONS_MISSING", "Pole wyboru musi mieć opcje albo słownik.", path)
        if f.get("defaultValueType") == "EXTERNAL_SYSTEM":
            dv = f.get("defaultValue")
            source = dv.split(".", 1)[0] if isinstance(dv, str) and "." in dv else None
            if source not in SOURCES:
                err("PREFILL_SOURCE", f"Nieznane źródło danych inicjalnych: {dv}.", path)
            if not f.get("readOnly"):
                warn("PREFILL_EDITABLE", "Pole zasilane z rejestru powinno być tylko do odczytu.", path)
        for s in f.get("states") or []:
            if s.get("type") not in ("SHOW", "READ_ONLY"):
                err("STATE_TYPE", f"Nieznany stan: {s.get('type')}.", path)
            if not s.get("query"):
                err("STATE_QUERY", "Stan musi mieć warunek (query).", path)
            else:
                queries.append((path, s["query"]))

    for t in tabs:
        ttype = t.get("type", "")
        tpath = t.get("title", "")
        ids.add(t.get("id", ""))
        fields_on_tab = 0
        for qn in t.get("questions") or []:
            sec = qn.get("field") or {}
            spath = f"{tpath} › {sec.get('title') or sec.get('techName')}"
            if sec.get("type") not in SECTION_TYPES:
                err(
                    "FIELD_OUTSIDE_SECTION",
                    "Każde pole musi być w sekcji lub sekcji powtarzającej się.",
                    spath,
                )
                continue
            check_field(sec, spath, ttype)
            for child in sec.get("repeatingSectionGrid") or []:
                f = child.get("field") or {}
                fpath = f"{spath} › {f.get('title') or f.get('techName')}"
                if f.get("type") in SECTION_TYPES:
                    err("NESTED_SECTION", "Nie można zagnieżdżać sekcji w sekcji.", fpath)
                    continue
                if f.get("type") not in FIELD_TYPES:
                    err("FIELD_TYPE", f"Nieznany typ pola: {f.get('type')}.", fpath)
                check_field(f, fpath, ttype)
                fields_on_tab += 1
        if fields_on_tab == 0:
            err("TAB_EMPTY", "Każda strona musi mieć co najmniej jedno pole.", tpath)

    for name, n in tech_names.items():
        if n > 1:
            warn("TECHNAME_DUPLICATE", f"Nazwa techniczna {name} występuje {n} razy.")

    for path, query in queries:
        for tech in TECH_REF.findall(query):
            if tech not in tech_names:
                err("STATE_UNKNOWN_FIELD", f"Warunek odwołuje się do nieistniejącego pola {tech}.", path)
        for tab in TAB_REF.findall(query):
            if tab.replace("\\'", "'") not in tab_titles:
                err("STATE_UNKNOWN_TAB", f"Warunek odwołuje się do nieistniejącej strony {tab}.", path)
        if query.count("(") != query.count(")"):
            err("STATE_PARENS", "Niezbalansowane nawiasy w warunku.", path)

    tab_ids = [t.get("id") for t in tabs]
    links = (form.get("flow") or {}).get("links") or []
    pairs = {(lnk.get("source"), lnk.get("target")) for lnk in links}
    for lnk in links:
        if lnk.get("source") not in tab_ids or lnk.get("target") not in tab_ids:
            err("FLOW_UNKNOWN_TAB", "Przejście odwołuje się do nieistniejącej strony.")
    for a, b in zip(tab_ids, tab_ids[1:], strict=False):
        if not any(src == a for src, _ in pairs):
            err("FLOW_DEAD_END", "Strona nie ma przejścia do kolejnej strony.", str(a))
        if (a, b) not in pairs and not any(tgt == b for _, tgt in pairs):
            err("FLOW_UNREACHABLE", "Do strony nie prowadzi żadne przejście.", str(b))
    return issues


def as_dicts(issues: list[Issue]) -> list[Json]:
    return [asdict(i) for i in issues]
