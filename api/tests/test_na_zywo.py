"""Test na żywo: dowolny plik formularza przez całą usługę z prawdziwym modelem (Eden AI albo Ollama, jak
w `.env`). Tak jak na obronie (pkt 6 zadania: „uruchomienie rozwiązania na podstawie nowych plików”): plik,
którego kod nie widział, ma dać formularz gotowy do importu. Jedno wywołanie modelu, na Eden AI ok. 0,001 USD.

    npm run proof:live                              # materiał 1 (PDF)
    npm run proof:live -- --plik "ścieżka/do/wniosku.docx"

Bez `--na-zywo` (albo `--plik`) test jest pomijany, więc `npm run check` nic nie kosztuje.
"""

import json
import tempfile
import time
from pathlib import Path

import pytest
from conftest import MATERIALS, reference
from test_wymagania import fields

from autoformularz import pipeline, safety
from autoformularz.config import Settings


@pytest.fixture
def plik(request) -> Path:
    given = request.config.getoption("--plik")
    if not (given or request.config.getoption("--na-zywo")):
        pytest.skip("test na żywo: uruchom z --na-zywo albo --plik <ścieżka> (płatne wywołanie modelu)")
    path = Path(given) if given else next(MATERIALS.glob("1. */*porządkowego nieruchomości.pdf"))
    assert path.is_file(), f"nie ma pliku {path}"
    return path


def test_nowy_plik_daje_formularz_gotowy_do_importu(plik):
    settings = Settings()
    if settings.llm_provider == "eden" and not settings.eden_api_key:
        pytest.skip("brak EDENAI_API_KEY w .env")

    start = time.monotonic()
    result = pipeline.from_file(plik.name, plik.read_bytes(), settings)
    seconds = time.monotonic() - start
    form, m = result.form, result.metrics.as_dict()

    out = Path(tempfile.gettempdir()) / f"autoformularz-na-zywo-{plik.stem}.json"
    out.write_text(json.dumps(form, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = [i for i in result.issues if i.level == "error"]
    cov = result.coverage
    own = [
        t["title"] for t in form["tabs"][1:-1] if t["title"] not in ("Kontakt i zgody", "Kontakt z urzędem")
    ]
    print(
        f"\n\n  Plik:     {plik.name} ({result.source_format})"
        f"\n  Czas:     {seconds:.1f} s, koszt: {m.get('costUsd') or 0:.4f} USD"
        f"\n  Tytuł:    {form['title']}"
        f"\n  Strony:   {', '.join(t['title'] for t in form['tabs'])}"
        f"\n  Pola:     {sum(1 for f in fields(form) if f['type'] != 'SECTION')}"
        f", warunki: {sum(len(f.get('states') or []) for f in fields(form))}"
        f"\n  Miejsca do wypełnienia bez pola: {len(cov.candidates_without_field)} z {cov.candidates}"
        f"\n  Błędy reguł: {len(errors)}, uwagi bezpieczeństwa: {len(safety.scan(form))}"
        f"\n  JSON:     {out}\n"
    )

    # Gotowy do importu: klucze jak w plikach referencyjnych COI, 0 błędów reguł technicznych.
    assert set(form) == set(reference(1)) == {"title", "tabs", "flow"}
    assert errors == [], [f"{i.code}: {i.message}" for i in errors]
    assert form["tabs"][0]["title"] == "Dane" and form["tabs"][-1]["type"] == "FINISH"
    # Treść z pliku: co najmniej jedna strona o sprawie, pola wskazują tylko istniejące fragmenty dokumentu.
    assert own, "brak strony o sprawie z wniosku"
    assert cov.unknown_refs == []
    # Bezpieczny: skaner nie znalazł próśb o hasła, obcych linków, poleceń dla modelu ani HTML.
    assert safety.scan(form) == []
