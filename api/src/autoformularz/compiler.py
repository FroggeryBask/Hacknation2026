"""Deterministic compiler: FormSpec -> e-form JSON in the COI import format.

Predefined sections (office, applicant, address, proxy, stamp duty, contact, consent, preview) follow
"HackNation - Standardy i dobre praktyki projektowania formularzy" and mirror the reference JSON files
in materialy/ (same techNames and jsonata query shape). Only the case-specific pages come from the spec.

IDs are UUIDv5 derived from the form title and element path, so the same input gives the same output."""

import html as html_lib
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any

from autoformularz.document import Block, Document
from autoformularz.spec import Condition, FieldSpec, FormSpec, Kind, Role, SectionSpec

Json = dict[str, Any]

DATA_TAB = "Dane"
CONTACT_TAB = "Kontakt i zgody"
FINISH_TAB = "Strona końcowa"

SELF = "Swoim"
OTHER = "Innej osoby"
ENTITY = "Osoby prawnej lub jednostki organizacyjnej"
PROXY = "Pełnomocnik"
REPRESENTATIVE = "Reprezentant"
POLAND = "Polska"

PROXY_FORMATS = "jpg, pdf, xml, PAdES, png, jpeg, CAdES, XAdES"

AUTO_VALIDATORS: list[tuple[str, str]] = [
    (r"\bpesel\b", "PESEL"),
    (r"\bnip\b", "NIP"),
    (r"\bregon\b", "REGON"),
    (r"kod pocztowy", "ZIP_CODE"),
    (r"e-?mail", "EMAIL"),
    (r"epuap|skrytk", "EPUAP"),
    (r"e-?dorę?cze|\bade\b", "ADE"),
    (r"seri\w* i numer dowodu", "SERIAL_NUMBER_ID_CARD"),
]
COUNTRY_LABEL = re.compile(r"^(kraj|państwo|obywatelstwo)\b", re.IGNORECASE)


def slug(text: str, max_len: int = 60) -> str:
    text = text.replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (text[:max_len].rstrip("_")) or "pole"


def html(text: str | None) -> str:
    if not text:
        return ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = "".join(f"<p>{html_lib.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return f"<html><head></head><body>{body}</body></html>"


def q(s: str) -> str:
    """Quote for a jsonata single-quoted string literal."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


@dataclass
class FieldRef:
    tab: str
    section: str
    tech: str
    repeating: bool
    options: list[str]


def answer_path(ref: FieldRef) -> str:
    base = f"tabs['{q(ref.tab)}' in title].questions['{ref.section}' in field.techName].field"
    return f"{base}.repeatingSectionGrid['{ref.tech}' in field.techName].field.__userAnswer"


def selected(value: str, ref: FieldRef, *, same_repeating_section: bool = False) -> str:
    v = value.replace('"', '\\"')
    if same_repeating_section:
        base = f"tabs['{q(ref.tab)}' in title].questions['{ref.section}' in field.techName].field"
        return (
            f"(\"{v}\" in {base}.__userAnswer[$repeatingSectionIndex]['{ref.tech}' in fieldTechName].answers)"
        )
    return f'("{v}" in {answer_path(ref)})'


def not_(expr: str) -> str:
    atom = expr.startswith("(") and expr.endswith(")") and " and " not in expr and " or " not in expr
    return f"$not{expr}" if atom else f"$not({expr})"


def and_(*exprs: str) -> str:
    return " and ".join(exprs)


def or_(*exprs: str) -> str:
    """Operands that are themselves `and` chains get parentheses (same shape as the reference JSON)."""
    return " or ".join(f"({e})" if " and " in e else e for e in exprs)


def show(query: str | None) -> list[Json]:
    return [{"type": "SHOW", "query": query}] if query else []


@dataclass
class Builder:
    title: str
    used_tech: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def id(self, path: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autoformularz:{self.title}:{path}"))

    def tech(self, base: str) -> str:
        name, n = base, 2
        while name in self.used_tech:
            name = f"{base}_{n}"
            n += 1
        self.used_tech.add(name)
        return name

    def field(
        self,
        type_: str,
        tech: str,
        title: str = "",
        *,
        description: str | None = None,
        options: list[str] | None = None,
        validation: list[str] | None = None,
        read_only: bool = False,
        default: Any = None,
        external: bool = False,
        dictionary: str | None = None,
        states: list[Json] | None = None,
        extra: Json | None = None,
    ) -> Json:
        tech = self.tech(tech)
        f: Json = {
            "id": self.id(tech),
            "type": type_,
            "techName": tech,
            "title": title,
            "description": html(description),
            "options": [{"id": o, "name": o, "techName": slug(o)} for o in options or []],
            "validation": validation or [],
            "readOnly": read_only,
            "repeatingSectionGrid": [],
        }
        if dictionary:
            f["dictionaryName"] = dictionary
        if default is not None:
            f["defaultValue"] = default
        if external:
            f["defaultValueType"] = "EXTERNAL_SYSTEM"
        if extra:
            f.update(extra)
        f["states"] = states or []
        f["questionOrder"] = 0
        f["tooltipMessage"] = ""
        return f

    def section(
        self,
        tech: str,
        title: str,
        children: list[Json],
        *,
        description: str | None = None,
        states: list[Json] | None = None,
        repeating: bool = False,
    ) -> Json:
        s = self.field(
            "REPEATING_SECTION" if repeating else "SECTION",
            tech,
            title,
            description=description,
            states=states,
        )
        s["description"] = html(description) or "<html><head></head><body></body></html>"
        s["repeatingSectionGrid"] = [_place(c, i) for i, c in enumerate(children)]
        return s

    def tab(self, title: str, type_: str, sections: list[Json]) -> Json:
        questions, y = [], 0
        for i, s in enumerate(sections):
            rows = len(s["repeatingSectionGrid"]) + 1
            s["questionOrder"] = i
            questions.append({"x": 0, "y": y, "rows": rows, "cols": 3, "field": s})
            y += rows
        return {"id": self.id(f"tab:{title}"), "title": title, "type": type_, "questions": questions}


def _place(f: Json, i: int) -> Json:
    f["questionOrder"] = i
    return {"x": 0, "y": i, "rows": 1, "cols": 3, "field": f}


def req(required: bool, *extra: str) -> list[str]:
    return (["REQUIRED"] if required else []) + list(extra)


# ---------------------------------------------------------------- predefined sections (Standardy)


class Standard:
    def __init__(self, b: Builder, spec: FormSpec, source: dict[Role, list[str]] | None = None):
        self.b, self.spec = b, spec
        self.source = source or {}  # verbatim source text by role (see source_texts)
        a = spec.applicant
        self.has_subject = a.other_person or a.entity
        subject = FieldRef(DATA_TAB, "podmiot_wniosku", "wybierz_w_czyim_imieniu_wnioskujesz", False, [])
        role = FieldRef(DATA_TAB, "podmiot_wniosku", "wybierz_jako_kto_wnioskujesz", False, [])
        self.c_other = selected(OTHER, subject)
        self.c_entity = selected(ENTITY, subject)
        self.c_proxy = selected(PROXY, role)
        self.c_rep = selected(REPRESENTATIVE, role)

    def authority(self) -> Json:
        organ = self.spec.authority_kind == "organ"
        b = self.b
        name = b.field(
            "TEXT_FIELD",
            "nazwa_organu" if organ else "nazwa_urzedu",
            "Nazwa organu" if organ else "Nazwa urzędu",
            validation=req(True),
            read_only=True,
            default=self.spec.authority_name,
        )
        if organ:
            return b.section(
                "organ_do_ktorego_jest_skladany_wniosek", "Organ, do którego jest składany wniosek", [name]
            )
        return b.section(
            "urzad_do_ktorego_jest_skladany_wniosek", "Urząd, do którego jest składany wniosek", [name]
        )

    def subject(self) -> Json:
        a, b = self.spec.applicant, self.b
        options = [SELF] + ([OTHER] if a.other_person else []) + ([ENTITY] if a.entity else [])
        children = [
            b.field(
                "RADIO",
                "wybierz_w_czyim_imieniu_wnioskujesz",
                "Wybierz, w czyim imieniu wnioskujesz",
                options=options,
                validation=req(True),
            )
        ]
        if a.entity:
            children.append(
                b.field(
                    "RADIO",
                    "wybierz_jako_kto_wnioskujesz",
                    "Wybierz, jako kto wnioskujesz",
                    options=[PROXY, REPRESENTATIVE],
                    validation=req(True),
                    states=show(self.c_entity),
                )
            )
        return b.section("podmiot_wniosku", "Podmiot wniosku", children)

    def your_data(self) -> Json:
        b = self.b
        return b.section(
            "twoje_dane",
            "Twoje dane",
            [
                b.field(
                    "TEXT_FIELD",
                    "imie",
                    "Imię",
                    validation=req(True),
                    read_only=True,
                    default="MLPZ.name",
                    external=True,
                ),
                b.field(
                    "TEXT_FIELD",
                    "nazwisko",
                    "Nazwisko",
                    validation=req(True),
                    read_only=True,
                    default="MLPZ.surname",
                    external=True,
                ),
                b.field(
                    "TEXT_FIELD",
                    "numer_pesel",
                    "Numer PESEL",
                    validation=req(True, "PESEL"),
                    read_only=True,
                    default="MLPZ.pesel",
                    external=True,
                ),
            ],
        )

    def address(self, tech: str, title: str, suffix: str, *, prefill: bool, states: list[Json] | None = None):
        b = self.b
        country = FieldRef(DATA_TAB, tech, f"kraj{suffix}", False, [])
        pl = selected(POLAND, country)
        abroad = not_(pl)

        def pre(attr: str) -> Json:
            return {"default": f"MLPZ.{attr}", "external": True} if prefill else {}

        children = [
            b.field(
                "SELECT",
                f"kraj{suffix}",
                "Kraj",
                dictionary="Kraje",
                validation=req(True),
                default=[POLAND],
                extra={"searchEnabled": True},
            ),
            b.field(
                "TEXT_FIELD",
                f"miejscowosc{suffix}_zagranica",
                "Miejscowość",
                validation=req(True),
                states=show(abroad),
            ),
            b.field(
                "TEXT_FIELD",
                f"kod_pocztowy{suffix}_zagranica",
                "Kod pocztowy",
                validation=req(True),
                states=show(abroad),
            ),
            b.field(
                "TEXT_FIELD", f"ulica{suffix}_zagranica", "Ulica", validation=req(True), states=show(abroad)
            ),
            b.field(
                "SELECT",
                f"wojewodztwo{suffix}",
                "Województwo, powiat, gmina i miejscowość",
                dictionary="TERYT_4G_DOWODOWY",
                validation=req(True),
                default=[],
                extra={"searchEnabled": True, "multiLevelTree": True},
                states=show(pl),
            ),
            b.field(
                "TEXT_FIELD",
                f"kod_pocztowy{suffix}",
                "Kod pocztowy",
                validation=req(True, "ZIP_CODE"),
                states=show(pl),
                **pre("postCode"),
            ),
            b.field(
                "TEXT_FIELD",
                f"ulica{suffix}",
                "Ulica",
                validation=req(True),
                states=show(pl),
                description="Np. Polna, Aleja Leśna, Plac Lipowy, Skwer Słoneczny",
                **pre("street"),
            ),
            b.field(
                "TEXT_FIELD",
                f"numer_budynku{suffix}",
                "Numer budynku",
                validation=req(True),
                **pre("building"),
            ),
            b.field(
                "TEXT_FIELD",
                f"numer_lokalu{suffix}",
                "Numer lokalu",
                validation=req(False),
                **pre("apartment"),
            ),
        ]
        return b.section(tech, title, children, states=states)

    def entity(self) -> list[Json]:
        b, a = self.b, self.spec.applicant
        fields = [
            b.field("TEXT_FIELD", "nazwa", "Nazwa", validation=req(True)),
            b.field("TEXT_FIELD", "nip", "NIP", validation=req(True, "NIP")),
        ]
        if not a.entity_nip_only:
            fields += [
                b.field("TEXT_FIELD", "regon", "REGON", validation=req(True, "REGON")),
                b.field(
                    "TEXT_FIELD",
                    "numer_krs",
                    "Numer KRS",
                    validation=req(False),
                    description="Wpisz 10 cyfr.",
                    extra={"pattern": "^\\d{10}$"},
                ),
            ]
        return [
            b.section("dane_podmiotu", "Dane podmiotu", fields, states=show(self.c_entity)),
            self.address(
                "adres_siedziby", "Adres siedziby", "_siedziba", prefill=False, states=show(self.c_entity)
            ),
            b.section(
                "potwierdzenie_ze_jestes_reprezentantem",
                "Potwierdzenie, że jesteś reprezentantem",
                [
                    b.field(
                        "FILE_UPLOADER",
                        "plik_z_odpisem_danych",
                        "Plik z odpisem danych",
                        validation=req(True),
                    )
                ],
                states=show(and_(self.c_entity, self.c_rep)),
            ),
        ]

    def other_person(self) -> list[Json]:
        b = self.b
        return [
            b.section(
                "dane_innej_osoby",
                "Dane innej osoby",
                [
                    b.field("TEXT_FIELD", "imie_inna_osoba", "Imię", validation=req(True)),
                    b.field("TEXT_FIELD", "nazwisko_inna_osoba", "Nazwisko", validation=req(True)),
                    b.field(
                        "TEXT_FIELD", "numer_pesel_inna_osoba", "Numer PESEL", validation=req(True, "PESEL")
                    ),
                ],
                states=show(self.c_other),
            ),
            self.address(
                "adres_zamieszkania_osoby_ktorej_jestes_pelnomocnikiem",
                "Adres zamieszkania innej osoby",
                "_inna_osoba",
                prefill=False,
                states=show(self.c_other),
            ),
        ]

    def proxy(self) -> list[Json]:
        b, a = self.b, self.spec.applicant
        when = []
        if a.other_person:
            when.append(self.c_other)
        if a.entity:
            when.append(and_(self.c_entity, self.c_proxy))
        upload = f"Dopuszczalne formaty: {PROXY_FORMATS}. Maksymalny rozmiar pliku: 10 MB. Maksymalna liczba plików: 1."
        out = [
            b.section(
                "pelnomocnictwo",
                "Pełnomocnictwo",
                [
                    b.field(
                        "FILE_UPLOADER",
                        "plik_dokumentu_z_pelnomocnictwem",
                        "Plik dokumentu z pełnomocnictwem",
                        validation=req(True),
                        description=upload,
                    )
                ],
                description="Dodaj dokument potwierdzający, że jesteś pełnomocnikiem.",
                states=show(or_(*when)),
            )
        ]
        fee = (
            "Opłata skarbowa wynosi 17 zł.\n\n"
            "Przelej ją na konto urzędu miasta lub gminy właściwego dla adresu zamieszkania osoby, która udzieliła "
            "pełnomocnictwa. Jeśli adres nie jest w Polsce, opłatę przelej na konto Urzędu Miasta Stołecznego "
            "Warszawy – Centrum Obsługi Podatnika.\n\n"
            f"W tytule przelewu wpisz „{self.spec.title} – opłata skarbowa za pełnomocnictwo”.\n\n"
            "Dodaj plik z potwierdzeniem przelewu. Znajdziesz go na stronie lub w aplikacji swojego banku."
        )
        receipt = "Dopuszczalny format: pdf. Maksymalny rozmiar pliku: 10 MB. Maksymalna liczba plików: 1."
        if a.other_person:
            radio = FieldRef(
                DATA_TAB,
                "oplata_skarbowa_pelnomocnictwo_1",
                "czy_zlozenie_pelnomocnictwa_wymaga_oplaty_skarbowej",
                False,
                [],
            )
            yes = show(selected("Tak", radio))
            out.append(
                b.section(
                    "oplata_skarbowa_pelnomocnictwo_1",
                    "Opłata skarbowa",
                    [
                        b.field(
                            "RADIO",
                            "czy_zlozenie_pelnomocnictwa_wymaga_oplaty_skarbowej",
                            "Czy złożenie pełnomocnictwa wymaga opłaty skarbowej?",
                            options=["Tak", "Nie"],
                            validation=req(True),
                        ),
                        b.field("TEXT_BLOCK", "oplata_info_1", description=fee, states=yes),
                        b.field(
                            "FILE_UPLOADER",
                            "plik_z_potwierdzeniem_przelewu",
                            "Plik z potwierdzeniem przelewu",
                            validation=req(True),
                            description=receipt,
                            states=yes,
                        ),
                    ],
                    description="Nie musisz płacić za złożenie pełnomocnictwa wystawionego przez najbliższą "
                    "rodzinę: małżonka, dzieci, rodziców, dziadków, wnuków, rodzeństwo. Więcej informacji "
                    "na stronie biznes.gov.pl",
                    states=show(self.c_other),
                )
            )
        if a.entity:
            out.append(
                b.section(
                    "oplata_skarbowa_pelnomocnictwo_2",
                    "Opłata skarbowa",
                    [
                        b.field("TEXT_BLOCK", "oplata_info", description=fee),
                        b.field(
                            "FILE_UPLOADER",
                            "plik_z_potwierdzeniem_przelewu_2",
                            "Plik z potwierdzeniem przelewu",
                            validation=req(True),
                            description=receipt,
                        ),
                    ],
                    states=show(and_(self.c_entity, self.c_proxy)),
                )
            )
        return out

    def data_tab_sections(self) -> list[Json]:
        out = [self.authority()]
        if self.has_subject:
            out.append(self.subject())
        out += [self.your_data(), self.address("adres_zamieszkania", "Adres zamieszkania", "", prefill=True)]
        if self.spec.applicant.entity:
            out += self.entity()
        if self.spec.applicant.other_person:
            out += self.other_person()
        if self.has_subject:
            out += self.proxy()
        return out

    def contact_tab_sections(self) -> list[Json]:
        b = self.b
        contact = b.section(
            "dane_do_kontaktu",
            "Dane do kontaktu",
            [
                b.field(
                    "TEXT_FIELD",
                    "numer_telefonu",
                    "Numer telefonu",
                    validation=req(False),
                    default="MLPZ.phoneNumber",
                    external=True,
                ),
                b.field(
                    "TEXT_FIELD",
                    "adres_e_mail",
                    "Adres e-mail",
                    validation=req(False, "EMAIL"),
                    default="MLPZ.email",
                    external=True,
                ),
            ],
            description="Wpisanie danych do kontaktu może przyspieszyć załatwienie sprawy. Urzędnik będzie mógł "
            "skontaktować się z Tobą w przypadku pytań lub wątpliwości.\n\n"
            "Jeśli widzisz uzupełnione dane, sprawdź, czy są poprawne. Możesz je zmienić lub usunąć.",
        )
        consents = [{"description": html(text), "required": True} for text in self.spec.consents]
        consents.append(
            {
                "description": "<html><head></head><body><p>Wyrażam zgodę na przetwarzanie moich danych osobowych "
                'zgodnie z <a href="#klauzula-informacyjna" target="_blank" rel="noopener noreferrer" '
                'aria-label="Link otwiera się w nowej karcie">klauzulą informacyjną</a></p></body></html>',
                "required": True,
            }
        )
        consent = b.field(
            "CONSENT_SECTION",
            "zgoda",
            validation=req(True),
            extra={
                "selectAllEnabled": len(consents) > 1,
                "consentSectionConfig": {"consents": consents, "files": []},
            },
        )
        title = "Zgody i oświadczenia" if self.spec.consents else "Zgoda"
        return [contact, b.section("zgoda_wyrazenie", title, [consent])]

    def finish_tab_sections(self) -> list[Json]:
        b = self.b
        out = []
        if self.spec.summary:
            out.append(
                b.section(
                    "podsumowanie",
                    "Podsumowanie",
                    [b.field("INFO_SECTION", "podsumowanie_info", description=self.spec.summary)],
                )
            )
        for role, tech, title in SOURCE_SECTIONS:
            if texts := self.source.get(role):
                text = "\n\n".join(texts)
                out.append(b.section(tech, title, [b.field("TEXT_BLOCK", f"{tech}_tekst", description=text)]))
        preview = (
            "Zanim przejdziesz do wyboru sposobu podpisu, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, "
            "wróć do edycji."
            if self.spec.signed
            else "Zanim wyślesz formularz, sprawdź dane na podglądzie. Jeśli zobaczysz błędy, wróć do edycji."
        )
        out.append(
            b.section(
                "podglad_uzupelnionego_wniosku",
                "Podgląd uzupełnionego wniosku",
                [b.field("INFO_SECTION", "podglad", description=preview)],
            )
        )
        return out


# ---------------------------------------------------------------- case-specific pages (from the spec)


def _validators(f: FieldSpec) -> list[str]:
    found = list(f.validators)
    if f.kind in (Kind.TEXT,) and not f.prefill:
        label = f.label.lower()
        for pattern, name in AUTO_VALIDATORS:
            if name not in found and re.search(pattern, label):
                found.append(name)
    return found


class SpecPages:
    def __init__(self, b: Builder, spec: FormSpec):
        self.b, self.spec = b, spec
        self.refs: dict[str, FieldRef] = {}  # normalized label -> ref
        self.section_of: dict[int, str] = {}  # id(SectionSpec) -> techName
        self._tech_for: dict[int, str] = {}  # id(FieldSpec) -> techName

    def plan(self) -> None:
        """First pass: assign techNames so conditions can point forward or backward."""
        for page in self.spec.pages:
            for section in page.sections:
                s_tech = self.b.tech(slug(section.title))
                self.section_of[id(section)] = s_tech
                for f in section.fields:
                    t = self.b.tech(slug(f.label))
                    ref = FieldRef(page.title, s_tech, t, section.repeating, f.options)
                    self.refs.setdefault(_norm(f.label), ref)
                    self._tech_for[id(f)] = t

    def condition(self, c: Condition | None, section: SectionSpec | None = None) -> list[Json]:
        if c is None:
            return []
        ref = self.refs.get(_norm(c.field))
        if ref is None:
            self.b.warnings.append(f"Warunek odwołuje się do nieznanego pola „{c.field}” i został pominięty.")
            return []
        value = c.equals
        if ref.options and value not in ref.options:
            # The model may write the option slightly differently ("TAK" vs "Tak"); an option that does not
            # exist at all would hide the element forever, so the condition is dropped with a warning.
            match = [o for o in ref.options if _norm(o) == _norm(value)]
            if not match:
                self.b.warnings.append(
                    f"Warunek sprawdza opcję „{value}”, której nie ma w polu „{c.field}”; pominięty."
                )
                return []
            value = match[0]
        same = section is not None and section.repeating and ref.section == self.section_of.get(id(section))
        expr = selected(value, ref, same_repeating_section=same)
        return show(not_(expr) if c.negate else expr)

    def field(self, f: FieldSpec, section: SectionSpec) -> Json:
        tech = self._tech_for[id(f)]
        self.b.used_tech.discard(tech)  # reserved in plan(); Builder.field re-adds it
        states = self.condition(f.show_if, section)
        common: Json = {"description": f.description, "states": states}
        if f.prefill:
            common |= {"read_only": True, "default": f.prefill, "external": True}
        validation = req(f.required, *_validators(f))
        kind = f.kind
        dictionary = f.dictionary
        if kind in (Kind.TEXT, Kind.SELECT) and COUNTRY_LABEL.match(f.label) and not dictionary:
            kind, dictionary = Kind.SELECT, "Kraje"
        if kind == Kind.SINGLE_CHOICE and (len(f.options) > 5 or dictionary):
            kind = Kind.SELECT
        if kind == Kind.SELECT:
            extra = {"searchEnabled": bool(dictionary) or len(f.options) > 15}
            if dictionary == "Kraje":
                common["default"] = [POLAND]
            return self.b.field(
                "SELECT",
                tech,
                f.label,
                options=[] if dictionary else f.options,
                dictionary=dictionary,
                validation=validation,
                extra=extra,
                **common,
            )
        if kind in (Kind.SINGLE_CHOICE, Kind.MULTI_CHOICE):
            type_ = "RADIO" if kind == Kind.SINGLE_CHOICE else "CHECKBOX"
            return self.b.field(
                type_,
                tech,
                f.label,
                options=f.options,
                dictionary=dictionary,
                validation=validation,
                **common,
            )
        if kind == Kind.FILE:
            parts = [f.description] if f.description else []
            if f.allowed_formats:
                parts.append(f"Dopuszczalne formaty: {', '.join(f.allowed_formats)}.")
            if f.max_files:
                parts.append(f"Maksymalna liczba plików: {f.max_files}.")
            common["description"] = " ".join(parts) or None
            return self.b.field("FILE_UPLOADER", tech, f.label, validation=validation, **common)
        if kind == Kind.INFO:
            return self.b.field(
                "TEXT_BLOCK", tech, f.label, description=f.description or f.label, states=states
            )
        type_ = {
            Kind.TEXT: "TEXT_FIELD",
            Kind.LONG_TEXT: "TEXTAREA",
            Kind.NUMBER: "NUMBER",
            Kind.DATE: "DATEPICKER",
        }[kind]
        return self.b.field(type_, tech, f.label, validation=validation, **common)

    def tabs(self) -> list[Json]:
        out = []
        for page in self.spec.pages:
            sections = []
            for section in page.sections:
                s_tech = self.section_of[id(section)]
                self.b.used_tech.discard(s_tech)
                children = [self.field(f, section) for f in section.fields]
                sections.append(
                    self.b.section(
                        s_tech,
                        section.title,
                        children,
                        description=section.description,
                        states=self.condition(section.show_if),
                        repeating=section.repeating,
                    )
                )
            out.append(self.b.tab(page.title, "MAIN", sections))
        return out


def _norm(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip().lower()


# Source text copied verbatim to the finish page (standard: "Podsumowanie i podgląd" holds text blocks).
# Not copied: STATEMENT (standard wants short, gender-neutral statements: the model writes `consents`),
# GDPR (standard: the information clause is linked, never placed on the form), SKIP (paper only).
SOURCE_SECTIONS: list[tuple[Role, str, str]] = [
    (Role.INSTRUCTION, "pouczenie", "Pouczenie"),
    (Role.LEGAL_BASIS, "podstawa_prawna", "Podstawa prawna"),
]


def _plain(block: Block) -> str:
    """Block text without table markup: '| a | b |' -> 'a b'."""
    if block.kind == "table_row":
        return " ".join(c.strip() for c in block.text.strip("|").split("|") if c.strip())
    return block.text


def source_texts(spec: FormSpec, doc: Document | None) -> dict[Role, list[str]]:
    """Verbatim text of blocks with a copied role, in document order (the model only points to them)."""
    if doc is None:
        return {}
    copied = {role for role, _, _ in SOURCE_SECTIONS}
    wanted = {block: role for block, role in spec.roles().items() if role in copied}
    out: dict[Role, list[str]] = {}
    for block in doc.blocks:
        if role := wanted.get(block.id):
            out.setdefault(role, []).append(_plain(block))
    return out


def compile_form(spec: FormSpec, doc: Document | None = None) -> tuple[Json, list[str]]:
    """Returns (form JSON, warnings). `doc` (the source) adds verbatim legal text; None keeps the spec only."""
    b = Builder(spec.title)
    std = Standard(b, spec, source_texts(spec, doc))
    pages = SpecPages(b, spec)
    data_sections = std.data_tab_sections()  # reserves predefined techNames first
    pages.plan()
    tabs = [b.tab(DATA_TAB, "MAIN", data_sections)]
    tabs += pages.tabs()
    tabs.append(b.tab(CONTACT_TAB, "MAIN", std.contact_tab_sections()))
    tabs.append(b.tab(FINISH_TAB, "FINISH", std.finish_tab_sections()))
    links = [
        {"id": b.id(f"link:{i}")[:8], "source": a["id"], "target": c["id"]}
        for i, (a, c) in enumerate(zip(tabs, tabs[1:], strict=False))
    ]
    form = {"title": spec.title[:255], "tabs": tabs, "flow": {"links": links}}
    return form, b.warnings
