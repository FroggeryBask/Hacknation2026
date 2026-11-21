"""Presort (between extract and the model): the code recognises obvious blocks before the model sees them.

Three kinds of blocks never need the model, and on big forms they are most of the prompt and of the answer
(form 8: a 60-line GDPR clause; every form: signature and "fill in with capitals" lines):
- GDPR information clause -> role GDPR (the design standard links the clause, it is never on the form),
- paper-only lines: signature, stamp, "miejscowość i data", "wypełnia urząd", "write in capitals",
  page footers -> role SKIP,
- the applicant's / proxy's / contact data, which the compiler adds from the design-standard template
  -> role FIELD_LABEL (section headings: HEADING).

The blocks keep their IDs and stay in the Document (source view, coverage); they are only left out of the
prompt and their roles are added to the FormSpec after the model (`apply`). Rules work on normalised text
(lowercase, no Polish diacritics: OCR often drops them, no numbering), so wording may vary between forms.
When a rule is not sure, the block goes to the model: a block with a place to fill in is never removed,
except signature/date lines and the template's own fields.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from autoformularz.document import Block, Document
from autoformularz.spec import BlockRole, FormSpec, Role


def fold(text: str) -> str:
    """Lowercase ASCII without diacritics (OCR often drops them), spaces collapsed; digits kept."""
    text = text.replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(text.split())


def norm(text: str) -> str:
    """`fold` with numbering ("2.1.", "B.4", "12)", "76.") removed: for labels and headings."""
    text = fold(text)
    text = re.sub(r"(?<![\w])(?:[a-z]\.)?\d+(?:\.\d+)*[.)]?(?![\w])", " ", text)  # 2.1. | b.4 | 12) | 76.
    text = re.sub(r"(?<![\w])[a-h]\.(?=\s)", " ", text)  # section letters "B. DANE ..."
    return " ".join(text.split())


def words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", norm(text))


PLACEHOLDER = re.compile(r"^[\s._…\-–—/|:()\[\]]*$")


def is_placeholder(text: str) -> bool:
    """Only dots, underscores, dashes or brackets: a place to write by hand, or a separator ("-")."""
    return bool(PLACEHOLDER.match(text))


def has_fill_in(text: str) -> bool:
    return bool(re.search(r"_{3,}|\.{4,}|…{2,}|[☐□❑❒▢◻⬜]", text))


# ---------------------------------------------------------------- GDPR clause

GDPR_START = re.compile(
    r"2016/679|\brodo\b|ogolne rozporzadzenie o ochronie danych|klauzul\w* informacyjn|"
    r"(informacj\w*|obowiazek informacyjny) (o|na temat|dotyczac\w*) (przetwarzani\w*|ochron\w*) (\w+ )?danych|"
    r"inspektor\w* ochrony danych|administrator\w* (pani|pana|panstwa|twoich|pani/pana|danych)|"
    r"urzed\w* ochrony danych|\buodo\b"
)
GDPR_WORDS = re.compile(
    r"dan\w* osobow|przetwarz|administrator|inspektor|ochron\w* danych|rodo|2016/679|"
    r"prawo (do )?(dostepu|sprostowania|usuniecia|ograniczenia|przenoszenia|wniesienia|cofniecia|sprzeciwu)|"
    r"sprostowani|ograniczeni\w* przetwarzania|"
    r"sprzeciw|skarg\w* do prezesa|organ\w* nadzorcz|odbiorc|profilowan|zautomatyzowan|"
    r"okres\w* przechowywania|przechowywane|archiwizac|panstwa trzeciego|organizacji miedzynarodowej|"
    r"podanie (danych|przez)|art\w* \d+ (ust|lit)|lit\w* [a-f] rodo|iod@|cel\w* przetwarzania|"
    r"kategori\w* danych|zrodl\w* pozyskania|dane (identyfikacyjne|adresowe|kontaktowe)"
)
# A consent or statement the applicant gives is not part of the information clause: the model handles it.
GDPR_STOP = re.compile(r"\b(wyrazam zgode|oswiadczam|zgoda na|ja nizej podpisan)")
GDPR_GAP = 4  # lines of a broken sentence ("Piłsudskiego 52/54, 81-382 Gdynia.") between clause lines


def gdpr_blocks(blocks: list[Block]) -> set[str]:
    out: set[str] = set()
    i = 0
    while i < len(blocks):
        t = fold(blocks[i].text)
        if not GDPR_START.search(t) or GDPR_STOP.search(t) or has_fill_in(blocks[i].text):
            i += 1
            continue
        run, j = [blocks[i].id], i + 1
        while j < len(blocks):
            nxt = fold(blocks[j].text)
            if GDPR_STOP.search(nxt) or has_fill_in(blocks[j].text):
                break
            if GDPR_WORDS.search(nxt):
                run.append(blocks[j].id)
                j += 1
                continue
            # Not clause vocabulary: keep it only if clause text follows within a few lines.
            ahead = blocks[j + 1 : j + 1 + GDPR_GAP]
            k = next(
                (
                    n
                    for n, b in enumerate(ahead)
                    if GDPR_WORDS.search(fold(b.text)) and not GDPR_STOP.search(fold(b.text))
                ),
                None,
            )
            if k is None or any(
                GDPR_STOP.search(fold(b.text)) or has_fill_in(b.text) for b in ahead[: k + 1]
            ):
                break
            run += [b.id for b in blocks[j : j + 1 + k + 1]]
            j += k + 2
        out.update(run)
        i = j
    return out


# ---------------------------------------------------------------- paper-only lines

PAPER = re.compile(
    r"(wypelni\w*|pisac|prosimy|nalezy).{0,40}(drukowanymi|wielkimi|duzymi|czytelnie|literami)|"
    r"(kolorem|dlugopisem|tuszem|atramentem) (czarnym|niebieskim)|"
    r"pola wyboru (nalezy )?(oznacz|zaznacz)|instrukcj\w* wypelni|"
    r"(wypelnia|wypelniaja|wypelnic przez) (urzad|organ|pracownik|przyjmujac)|"
    r"adnotacj\w* (urzedu|organu)|data wplywu|potwierdzenie (wplywu|przyjecia|zlozenia)|"
    r"(pieczec|pieczatk|stempel)\w* (urzedu|organu|przyjmujac|wplywu)"
)
# A signature or date line: only these words (and placeholders) remain once numbering is removed.
SIGNATURE_WORDS = {
    "podpis",
    "podpisy",
    "czytelny",
    "czytelnie",
    "wlasnoreczny",
    "data",
    "dnia",
    "dn",
    "miejscowosc",
    "miejsce",
    "i",
    "oraz",
    "lub",
    "pieczec",
    "pieczatka",
    "pieczeci",
    "pieczatki",
    "imienna",
    "imienne",
    "wnioskodawcy",
    "wnioskodawca",
    "wnioskujacego",
    "skladajacego",
    "skladajacej",
    "skladajacych",
    "deklaracje",
    "wniosek",
    "wniosku",
    "osoby",
    "osob",
    "reprezentujacej",
    "reprezentujacych",
    "upowaznionej",
    "uprawnionej",
    "pelnomocnika",
    "wspolmalzonka",
    "kandydata",
    "kandydatki",
    "rodzica",
    "opiekuna",
    "prawnego",
    "przyjmujacego",
    "przyjmujacej",
    "wypelnienia",
    "sporzadzenia",
    "zlozenia",
    "wplywu",
    "do",
    "organu",
    "urzedu",
    "pracownika",
    "r",
    "rok",
    "roku",
}
SIGNATURE_KEY = {"podpis", "podpisy", "pieczec", "pieczatka", "pieczeci", "pieczatki", "wplywu"}
PLACE_DATE = re.compile(
    r"miejscowosc,? i data|data i miejscowosc|miejsce i data|data i podpis|, dnia\b|^dnia\b"
)


PAGE_FOOTER = re.compile(r"^\s*(strona\s*)?\d+\s*(/|z|of)\s*\d+\s*$", re.IGNORECASE)


def is_paper_only(text: str) -> bool:
    if PAGE_FOOTER.match(text):  # "strona 1/2", "1/6"
        return True
    t = norm(text)
    if not t:
        return False
    if PAPER.search(t):
        return True
    # "(wypełnić tylko …)" after a signature does not count; a label that is all in brackets does.
    # The bracket may be left open: numbering removal takes "1.1.2)" with its ")".
    w = set(re.findall(r"[a-z]+", re.sub(r"\([^)]*(\)|$)", " ", t))) or set(re.findall(r"[a-z]+", t))
    if w and w <= SIGNATURE_WORDS and (w & SIGNATURE_KEY or PLACE_DATE.search(t)):
        return True
    if w and w <= SIGNATURE_WORDS and w & {"data", "dnia", "dn"} and has_fill_in(text):  # "……… dnia ………"
        return True
    # "Młynary, dnia ………" / "……… (miejscowość i data)": a town and a date to write by hand.
    return bool(PLACE_DATE.search(t)) and has_fill_in(text) and len(w - SIGNATURE_WORDS) <= 2


def is_tiny(text: str) -> bool:
    """A fragment of a split line: "1.", "lub", "." (no meaning on its own)."""
    w = words(text)
    return len(text.strip()) <= 3 or (len(w) <= 1 and len(text.strip()) <= 6)


# ---------------------------------------------------------------- applicant / proxy / contact data

APPLICANT_HEADING = re.compile(r"\b(wnioskodawc\w*|pelnomocni\w*|skladajac\w*|wnioskujac\w*)\b")
NOT_APPLICANT = re.compile(
    r"oswiadcz|podpis|zgod|wniosek o|zalacznik|pouczeni|objasnieni|klauzul|wspolmalzon|dzieck|kandydat|"
    r"podopieczn|sportowc|ucznia|zmarl|nieruchomosc|pojazd|psa|zwierz|budyn|dzialk|lokal"
)
STANDARD_PART = re.compile(
    r"^(imie|imiona|drugie imie|nazwisko|imie i nazwisko|nazwisko i imie|nazwisko imie|nazwa|nazwa firmy|"
    r"pelna nazwa|nazwa pelna|pesel|numer pesel|nip|regon|krs|numer krs|seria i numer dowodu( osobistego)?|"
    r"numer dowodu( osobistego)?|obywatelstwo|adres|adres zamieszkania|adres siedziby|adres do korespondencji|"
    r"miejsce zamieszkania|miejsca zamieszkania|siedziba firmy|siedziba|siedziby|zamieszkania|kraj|wojewodztwo|powiat|gmina|miejscowosc|ulica|"
    r"nr domu|numer domu|nr budynku|numer budynku|nr lokalu|numer lokalu|nr mieszkania|kod pocztowy|kod|poczta|"
    r"telefon|nr telefonu|numer telefonu|telefon kontaktowy|nr tel|tel|e-mail|email|adres e-mail|"
    r"adres poczty elektronicznej|poczty elektronicznej|adres skrzynki epuap|faks|fax|nr faksu)$"
)
ROLE_WORDS = re.compile(
    r"\b(wnioskodawcy|wnioskodawca|skladajacego|pelnomocnika|wnioskujacego|identyfikacyjne)\b"
)


def is_standard_label(text: str) -> bool:
    """Every label in the line is template data: numbered labels ("3. PESEL 4. NIP/REGON") and table
    cells ("| Ulica: | Nr domu: | Nr lokalu: |") are checked one by one."""
    cells = [c for c in text.split("|") if c.strip()] if "|" in text else [text]
    parts = [
        p
        for c in cells
        for p in re.split(r"(?:^|\s)(?:[A-Za-z]\.)?\d+(?:\.\d+)*[.)]\s|:\s+(?=\S)", c)
        if p.strip()
    ]
    return bool(parts) and all(_standard_label(p) for p in parts)


def _standard_label(text: str) -> bool:
    """Every part of the label is personal, address or contact data of the template:
    "Nazwa /Imię i nazwisko", "(imię i nazwisko wnioskodawcy)", "3. PESEL 4. NIP/REGON", "nr telefonu i e-mail"."""
    t = re.sub(r"[_…]{2,}|\.{3,}", " ", text)  # "Imię ………": the label with its hand-written line
    t = re.sub(r"\([^)]*(dot\.|dotyczy|opcjonaln|nieobowiazk)[^)]*\)", " ", t)  # "(dot. tylko osób prawnych)"
    t = ROLE_WORDS.sub(" ", norm(t))
    t = re.sub(r"[()\[\]:;*|]|\.(?=\s|$)", " ", t)
    parts = [p.strip(" ,.-") for p in re.split(r"/|,| i (?=[a-z])| lub | albo | oraz ", t)]
    parts = [p for p in parts if p]
    if not parts:
        return False
    whole = " ".join(t.split())
    if STANDARD_PART.match(whole):
        return True
    return all(STANDARD_PART.match(p) for p in parts)


def numbering(text: str) -> str | None:
    m = re.match(r"\s*((?:[A-Za-z]\.)?\d+(?:\.\d+)*)[.)]?\s", text)
    return m.group(1).lower() if m else None


def is_heading(block: Block) -> bool:
    t = block.text.strip()
    w = words(t)
    if not w or len(w) > 14 or has_fill_in(t):
        return False
    return bool(numbering(t)) or t.isupper() or block.kind == "heading"


def applicant_blocks(blocks: list[Block]) -> tuple[dict[str, Role], set[str]]:
    """Roles for the template's applicant/proxy/contact data and the labels that were dropped (to set
    `applicant.entity` when NIP/REGON/KRS is asked). Two shapes on the materials:
    - a section headed "Dane wnioskodawcy" / "Dane pełnomocnika" (its sub-sections "2.1." stay in it),
    - a letter-style header before the title: "……" lines with "(imię i nazwisko wnioskodawcy)" under them."""
    roles: dict[str, Role] = {}
    labels: set[str] = set()

    def applicant_heading(b: Block) -> bool:
        t = norm(b.text)
        return is_heading(b) and bool(APPLICANT_HEADING.search(t)) and not NOT_APPLICANT.search(t)

    i = 0
    while i < len(blocks):
        b = blocks[i]
        if not applicant_heading(b):
            i += 1
            continue
        # The section lasts only while its blocks are template data: labels, their hand-written lines,
        # sub-sections ("2.1." under "2."), applicant headings and the rest of a heading split over two
        # lines. The first other block ends it: what follows (e.g. "Dane sportowca") goes to the model.
        head_no = numbering(b.text)
        headings, content, j = [b], [], i + 1
        while j < len(blocks):
            nb, prev = blocks[j], blocks[j - 1]
            no = numbering(nb.text)
            open_paren = prev.text.count("(") > prev.text.count(")")
            if is_standard_label(nb.text) or is_placeholder(nb.text):
                content.append(nb)
            elif open_paren and prev in headings and ")" in nb.text:
                headings.append(nb)  # "2.3. Dane kontaktowe (… nie są obowiązkowe," + "ale ułatwią …)"
            elif is_heading(nb) and (
                applicant_heading(nb) or (head_no and no and no.startswith(head_no + "."))
            ):
                if NOT_APPLICANT.search(norm(nb.text)):
                    break
                headings.append(nb)
            else:
                break
            j += 1
        if content:
            for c in content:
                roles[c.id] = Role.FIELD_LABEL
            labels.update(norm(c.text) for c in content if not is_placeholder(c.text))
            for h in headings:
                roles[h.id] = Role.HEADING
        i = j

    # Letter-style header: blocks before the title ("Wniosek …", "Deklaracja …").
    title = next(
        (
            n
            for n, b in enumerate(blocks)
            if re.match(r"^(wniosek|deklaracja|zgloszenie|podanie|oswiadczenie)\b", norm(b.text))
        ),
        None,
    )
    if title:
        head = blocks[:title]
        pairs = [b for b in head if is_standard_label(b.text) and re.search(r"[(/]", b.text)]
        if pairs:  # "(imię i nazwisko)", "/ adres /": labels under hand-written lines
            for b in head:
                if b.id in roles:
                    continue
                if b in pairs or is_standard_label(b.text):  # also "PESEL *………" (label with its line)
                    roles[b.id] = Role.FIELD_LABEL
                    labels.add(norm(b.text))
                elif is_placeholder(b.text):  # the hand-written lines of the header
                    roles[b.id] = Role.FIELD_LABEL
                elif re.match(r"^(dane )?wnioskodawc\w*$", " ".join(words(b.text))):
                    roles[b.id] = Role.HEADING
    return roles, labels


# ---------------------------------------------------------------- the step


@dataclass
class Presorted:
    model_doc: Document  # what the model sees (same block IDs, fewer blocks)
    roles: list[BlockRole]  # roles set by code, as ranges of consecutive blocks
    entity: bool = False  # the applicant may be a company (NIP/REGON/KRS/name of firm among dropped labels)
    nip_only: bool = False
    counts: dict[str, int] = field(default_factory=dict)  # dropped blocks per role (prompt note, report)


def presort(doc: Document) -> Presorted:
    blocks = doc.blocks
    roles: dict[str, Role] = {}
    for bid in gdpr_blocks(blocks):
        roles[bid] = Role.GDPR
    for b in blocks:
        if b.id not in roles and is_paper_only(b.text):
            roles[b.id] = Role.SKIP
    app_roles, labels = applicant_blocks([b for b in blocks if b.id not in roles])
    roles.update(app_roles)
    # Fragments of a split line between two removed blocks of the same role ("1.", "lub", "."): same role.
    for n, b in enumerate(blocks):
        if b.id in roles or not is_tiny(b.text):
            continue
        before = next((blocks[k] for k in range(n - 1, -1, -1) if not is_tiny(blocks[k].text)), None)
        after = next((blocks[k] for k in range(n + 1, len(blocks)) if not is_tiny(blocks[k].text)), None)
        if before and after and roles.get(before.id) and roles.get(before.id) == roles.get(after.id):
            roles[b.id] = roles[before.id]
    kept = [b for b in blocks if b.id not in roles]
    kept_ids = {b.id for b in kept}
    model_doc = Document(
        blocks=kept,
        candidates=[c for c in doc.candidates if c.block in kept_ids],
        images=doc.images,
        notes=doc.notes,
    )
    ids = " ".join(labels)
    found = set(re.findall(r"\b(nip|regon|krs)\b", ids))
    entity = bool(found) or bool(re.search(r"\bnazwa\b", ids))  # "Nazwa firmy", "Nazwa /Imię i nazwisko"
    counts: dict[str, int] = {}
    for role in roles.values():
        counts[role.value] = counts.get(role.value, 0) + 1
    out = Presorted(
        model_doc=model_doc,
        roles=ranges(blocks, roles),
        entity=entity,
        nip_only=found == {"nip"},
        counts=counts,
    )
    model_doc.hint = prompt_note(out)
    return out


def ranges(blocks: list[Block], roles: dict[str, Role]) -> list[BlockRole]:
    """Consecutive blocks with the same role -> one entry `block`..`to` (short spec, within MAX_ROLES)."""
    out: list[BlockRole] = []
    for n, b in enumerate(blocks):
        role = roles.get(b.id)
        if role is None:
            continue
        last = out[-1] if out else None
        prev = blocks[n - 1].id if n else None
        if last and last.role is role and (last.to or last.block) == prev:
            last.to = b.id
        else:
            out.append(BlockRole(block=b.id, role=role))
    return out


def prompt_note(p: Presorted) -> str:
    """One line for the model: what was left out, so it does not look for it or invent it."""
    labels = {
        "GDPR": "klauzula RODO",
        "SKIP": "podpisy, daty, adnotacje urzędu i instrukcje wypełniania druku",
        "FIELD_LABEL": "dane wnioskodawcy, pełnomocnika i kontaktowe (część standardowa)",
        "HEADING": None,
    }
    parts = [labels[k] for k in ("FIELD_LABEL", "GDPR", "SKIP") if p.counts.get(k)]
    if not parts:
        return ""
    note = "Kod już rozpoznał i pominął na liście bloków: " + "; ".join(parts) + "."
    if p.entity:
        note += " Formularz pyta o dane firmy (NIP/REGON/KRS lub nazwa): wnioskodawcą może być firma."
    return note


def apply(spec: FormSpec, p: Presorted) -> FormSpec:
    """Add the code's roles to the model's FormSpec (code wins for blocks it recognised) and the entity hint."""
    code = {bid for r in p.roles for bid in r.ids()}
    model_roles = [r for r in spec.block_roles if not set(r.ids()) & code]
    update: dict = {"block_roles": [*p.roles, *model_roles]}
    if p.entity and not spec.applicant.entity:
        update["applicant"] = spec.applicant.model_copy(
            update={"entity": True, "entity_nip_only": p.nip_only}
        )
    return spec.model_copy(update=update)
