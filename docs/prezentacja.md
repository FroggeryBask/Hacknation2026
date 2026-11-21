---
marp: true
lang: pl
size: 16:9
paginate: true
title: autoformularz
description: Cyfryzacja formularzy urzędowych, HackNation 2026, zadanie COI
style: |
  /* Motyw na wzór identyfikacji COI (Behance 223311653, coi.gov.pl):
     Inter Light w nagłówkach, granat #04122f, magenta→karmazyn, błękit.
     Grafiki jak na stronie COI: koła i kwadraty z gradientem stożkowym,
     nakładane półprzezroczyście, małe kwadraty na narożnikach. Bez logo COI. */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700&display=swap');
  :root {
    --ink: #04122f;
    --muted: #4a5068;
    --line: #d1d4dd;
    --paper: #ffffff;
    --soft: #e8ebf2;
    --navy: #04122f;
    --navy-2: #061a3f;
    --blue: #133692;
    --blue-2: #4f79b5;
    --blue-pale: #b4cdf5;
    --plum: #871c6c;
    --crimson: #ca0049;
    --crimson-2: #e10a58;
    --magenta: linear-gradient(90deg, #871c6c, #e10a58);
    --yellow: #ffdd00;
  }
  section {
    font-family: Inter, system-ui, sans-serif;
    color: var(--ink);
    background: var(--paper);
    font-size: 25px;
    line-height: 1.45;
    padding: 72px 80px 60px;
    justify-content: flex-start;
  }
  section { position: relative; overflow: hidden; }
  /* linia jak na kafelkach Strefy Wiedzy COI: szara kreska z magentowym końcem */
  section::before {
    content: "";
    position: absolute; left: 80px; width: 1120px; top: 44px; height: 2px;
    background: linear-gradient(90deg, var(--line) calc(100% - 88px), var(--crimson-2) calc(100% - 88px));
  }
  section.dark::before { background: linear-gradient(90deg, #26314f calc(100% - 88px), var(--crimson-2) calc(100% - 88px)); }

  /* Grafiki COI: koła i kwadraty z gradientem stożkowym (conic), półprzezroczyste, nakładane */
  .deco, .deco div { position: absolute; }
  .deco { inset: 0; pointer-events: none; z-index: 0; }
  section > :not(.deco, footer, header) { position: relative; z-index: 1; }
  .deco .round { border-radius: 50%; }
  h1 { font-size: 64px; font-weight: 300; line-height: 1.08; margin: 0 0 24px; letter-spacing: -0.02em; }
  h2 { font-size: 42px; font-weight: 300; line-height: 1.15; margin: 0 0 32px; letter-spacing: -0.015em; }
  h3 { font-size: 24px; font-weight: 500; margin: 0 0 8px; }
  strong { font-weight: 700; }
  em { font-style: normal; color: var(--crimson); }
  a { color: var(--blue); }
  code { font-size: 0.85em; background: var(--soft); color: var(--ink); padding: 2px 8px; border-radius: 2px; }
  ul { padding-left: 1.1em; } li { margin: 6px 0; }
  li::marker { color: var(--crimson); }
  table { border-collapse: collapse; font-size: 21px; width: 100%; }
  th { text-align: left; font-weight: 500; border-bottom: 2px solid var(--ink); padding: 7px 12px; background: none; }
  td { border-bottom: 1px solid var(--line); padding: 7px 12px; background: none; }
  tr { background: none !important; }
  section::after { font-size: 15px; color: var(--muted); right: 80px; bottom: 28px; }
  footer { font-size: 15px; color: var(--muted); left: 80px; bottom: 28px; }

  /* Ciemne plansze: granat, biały tekst Light */
  section.dark, section.title { background-color: var(--navy); color: #fff; }
  section.dark h2, section.title h1 { color: #fff; }
  section.dark em { color: #ff83b7; }
  section.dark li::marker { color: #ff83b7; }
  section.dark code { background: var(--navy-2); color: #fff; }
  section.dark footer, section.dark::after { color: #8a93b0; }
  section.dark .card { background: var(--navy-2); }
  section.dark .card p { color: #b9c0d6; }

  /* Tytuł: kompozycja z hero coi.gov.pl (koło, pionowy pas, magenta, mały kwadrat biel→błękit) */
  section.title { justify-content: center; }
  section.title::before { display: none; }
  section.title h1 { font-size: 80px; max-width: 620px; }
  /* „Papierowy wniosek” w dwóch liniach, strzałka na środku tego bloku, „e-formularz” bez dzielenia */
  section.title h1.hero-title { display: flex; align-items: center; gap: 28px; max-width: none; }
  .hero-title .arrow { line-height: 1; transform: translateY(-0.06em); }
  .hero-title .to { white-space: nowrap; }
  section.title p { font-size: 26px; color: #c9cfe0; max-width: 540px; }
  section.title::after, section.title footer { display: none; }
  .hero .circle { left: 664px; top: -353px; width: 920px; height: 920px;
    background: conic-gradient(from 200deg, #12367d, #133a88 40%, #0f2f6e 75%, #12367d); }
  .hero .bar { left: 1126px; top: 107px; width: 154px; height: 569px;
    background: conic-gradient(from 90deg at 0 0, #061535, #0a1f4f 90deg, transparent 90deg); }
  .hero .mag { left: 878px; top: 427px; width: 124px; height: 249px;
    background: linear-gradient(180deg, rgba(150,40,130,.55) 0%, rgba(150,40,130,.55) 50%, #8e1a6c 50%, #e10a58 100%); }
  .hero .mag2 { left: 1002px; top: 427px; width: 124px; height: 124px;
    background: conic-gradient(from 180deg at 0 100%, rgba(150,40,130,.5), rgba(80,50,150,.35)); }
  .hero .shade { left: 1002px; top: 551px; width: 124px; height: 125px;
    background: linear-gradient(180deg, #0b1d46, #061535); }
  .hero .tiny { left: 1126px; top: 373px; width: 55px; height: 55px;
    background: conic-gradient(from 90deg at 50% 50%, #ffffff, #c9d6ef 25%, #3d4fa0 50%, #6f7fc0 75%, #ffffff); }

  /* Jasne plansze z liczbami: kompozycja z „O nas” coi.gov.pl (szare koło, duży niebieski kwadrat) */
  section.stage { background: var(--paper); padding-right: 340px; }
  .stage-deco .grey { left: 948px; top: 120px; width: 290px; height: 290px;
    background: conic-gradient(from 90deg, #fafafa, #ececec 35%, #d6d6d6 70%, #ababab); }
  .stage-deco .blue { left: 1093px; top: 265px; width: 325px; height: 325px; mix-blend-mode: multiply;
    background: conic-gradient(from 90deg at 40% 62%, #1f57b2, #4f7cc4 25%, #a9c0e6 55%, #e4ecf8 80%, #ffffff); }
  .stage-deco .tiny { left: 1215px; top: 242px; width: 44px; height: 44px; mix-blend-mode: multiply;
    background: conic-gradient(from 90deg at 50% 50%, #1f57b2, #6a8fcd 40%, #c7d5ee 75%, #ffffff); }
  .stage-deco .mag { left: 1007px; top: 506px; width: 84px; height: 84px;
    background: conic-gradient(from 180deg at 80% 80%, #e10a58, #c0367f 30%, #ecc6dc 65%, #ffffff 80%, #ffffff); }

  /* Ciemne plansze: magentowe koło stożkowe na krawędzi, jak na kafelkach COI */
  section.dark:has(.dark-deco)::before { width: 900px; }
  .dark-deco .disc { right: -110px; top: -110px; width: 300px; height: 300px; opacity: .9;
    background: conic-gradient(from 0deg, #871c6c, #4a1752 25%, rgba(225,10,88,.15) 50%, #e10a58 75%, #c4176a); }
  .dark-deco .tiny { right: 174px; top: 40px; width: 34px; height: 34px;
    background: conic-gradient(from 90deg at 50% 50%, #ffffff, #9fb6e6 50%, #3d63b4); }

  .eq { display: flex; align-items: center; gap: 18px; font-size: 32px; font-weight: 300; margin: 0 0 18px; }
  .eq .op { color: #ff83b7; font-size: 40px; }
  .eq .stack { display: flex; flex-direction: column; gap: 4px; padding-left: 18px; border-left: 3px solid #e10a58; font-size: 22px; color: #c9cfe0; }
  .one { display: flex; align-items: center; gap: 28px; margin: 0 0 28px; }
  .one .n { font-size: 168px; font-weight: 300; line-height: .8; color: var(--crimson); letter-spacing: -0.04em; }
  .one div { display: flex; flex-direction: column; font-size: 34px; font-weight: 300; line-height: 1.2; }
  .steps { display: flex; align-items: stretch; gap: 12px; margin: 0 0 24px; }
  .steps div { flex: 1; background: var(--navy); color: #fff; padding: 18px 16px; display: flex; flex-direction: column; gap: 6px; }
  .steps b { font-size: 22px; font-weight: 500; text-transform: uppercase; letter-spacing: .06em; }
  .steps small { font-size: 17px; color: #b9c0d6; line-height: 1.35; }
  .steps code { background: var(--navy-2); color: #fff; font-size: 15px; }
  .steps > span { align-self: center; color: var(--crimson); font-size: 26px; }
  .lead { font-size: 29px; font-weight: 300; color: var(--muted); max-width: 1000px; margin-bottom: 28px; }
  section.dark .lead { color: #c9cfe0; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
  .cols3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 28px; }
  .card { background: var(--soft); padding: 24px 28px; border-top: 4px solid var(--blue); }
  .card.hl { border-image: var(--magenta) 1; border-top-width: 4px; border-top-style: solid; }
  .card p { margin: 0; font-size: 21px; color: var(--muted); }
  .big { font-size: 68px; font-weight: 300; color: var(--crimson); line-height: 1; margin-bottom: 10px; letter-spacing: -0.02em; }
  section.dark .big { color: #ff83b7; }
  .flow { display: flex; align-items: stretch; gap: 10px; margin: 8px 0 28px; }
  .flow div { flex: 1; background: var(--soft); padding: 14px 12px; font-size: 19px; text-align: center; border-top: 4px solid var(--blue); }
  .flow div.ai { border-image: var(--magenta) 1; border-top-width: 4px; border-top-style: solid; }
  section.dark .flow div { background: var(--navy-2); }
  .flow span { align-self: center; color: var(--blue-2); }
  .shot { background: var(--soft); border: 2px dashed var(--line); color: var(--muted); display: flex; align-items: center; justify-content: center; text-align: center; font-size: 21px; height: 420px; }
  .shot img { max-width: 100%; max-height: 100%; }
  section.dense table { font-size: 17px; }
  section.dense th, section.dense td { padding: 4px 10px; }
  section.dense .card { align-self: start; }
  .todo { background: var(--yellow); color: #0d0e0e; padding: 0 6px; font-weight: 500; }
footer: autoformularz · HackNation 2026 · zadanie COI
---

<!-- _class: title -->
<!-- _paginate: false -->

<div class="deco hero"><div class="round circle"></div><div class="bar"></div><div class="mag2"></div><div class="mag"></div><div class="shade"></div><div class="tiny"></div></div>

<h1 class="hero-title"><span>Papierowy<br>wniosek</span><span class="arrow">→</span><span class="to">e-formularz</span></h1>

Z papierowego wniosku do e-formularza gotowego do importu w kilka minut, na lokalnym modelu.

<!--
Mówca: jedno zdanie o tym, co robimy. Zespół przedstawiamy na końcu.
-->

---

<!-- _class: dark -->

<div class="deco dark-deco"><div class="round disc"></div><div class="tiny"></div></div>

## Urzędnik podaje plik. Buduje e-usługę

<div class="eq">
<span>Znany wniosek</span><span class="op">×</span><span>inny urząd</span><span class="op">=</span><span>nowe</span>
<div class="stack"><span>wniosek</span><span>struktura danych</span><span>JSON</span><span>…</span></div>
</div>

<p class="lead">Wszystko trzeba przepisać ręcznie.</p>

<div class="cols3">
<div class="card"><h3>Ręczna praca</h3><p>Znajomość pól, walidacji, warunków, aplikacji…</p></div>
<div class="card"><h3>Brak standardu</h3><p>Urząd A nie wie, w jaki sposób Urząd B stworzył podobny formularz.</p></div>
<div class="card hl"><h3>Cel</h3><p>Plik na wejściu, JSON zgodny z formatem importu COI na wyjściu.</p></div>
</div>

---

<div class="one"><span class="n">1</span><div><span>Plik</span><span>Wywołanie REST</span><span>Gotowy JSON</span></div></div>

<div class="steps">
<div><b>Plik</b><small>PDF · DOC · DOCX · ODS<br>XLSX · JPG · PNG</small></div><span>→</span>
<div><b>Wywołanie API</b><small><code>POST /api/v1/forms</code></small></div><span>→</span>
<div><b>JSON</b><small>W formacie COI</small></div><span>→</span>
<div><b>E-formularz</b><small>Gotowy. Po prostu.</small></div>
</div>

- Walidacja pliku: nazwa, rozmiar z konfiguracji, MIME z zawartości
- Plik tylko w pamięci lub katalogu tymczasowym, bez bazy i bez zapisu
- JWT, dokumentacja OpenAPI pod `/docs`
- Frontend dla urzędnika: upload, podgląd JSON i wyrenderowany formularz

---

## Model tylko wskazuje, kod buduje JSON

<div class="flow">
<div>odczyt<br>bloki z ID</div><span>→</span>
<div class="ai">lokalny model<br>FormSpec</div><span>→</span>
<div>sprawdzenie<br>kotwic i pokrycia</div><span>→</span>
<div>kompilator<br>COI JSON</div><span>→</span>
<div>linter<br>reguły techniczne</div>
</div>

<div class="cols">
<div>

### Model (Qwen3-VL)
Klasyfikuje bloki źródła, typy pól i warunki. Odpowiedź wymuszona schematem JSON. Nie przepisuje tekstu i nie pisze JSON-a COI.

</div>
<div>

### Kod
Sekcje standardowe z szablonów, tekst prawny dosłownie ze źródła, warunki jsonata, UUID deterministyczne: *ten sam plik daje ten sam JSON*.

</div>
</div>

---

## Demo: plik na wejściu

<div class="cols">
<div class="shot">ZRZUT: ekran uploadu z wybranym plikiem<br>(formularz spoza wzorców, np. nr 7)</div>
<div class="shot">ZRZUT: wynik, zakładki JSON i raport lintera</div>
</div>

---

## Demo: e-formularz z JSON-a

<div class="cols">
<div class="shot">ZRZUT: wyrenderowany formularz,<br>sekcja pokazana po wyborze opcji</div>
<div class="shot">ZRZUT: błąd walidacji PESEL<br>lub kodu pocztowego</div>
</div>

<!--
Renderer czyta wyłącznie COI JSON i ewaluuje states, więc podgląd i plik importu nie mogą się rozjechać.
-->

---

<!-- _class: dense -->

## Kompletność

<div class="cols">
<div>

| Zakres | Stan |
|---|---|
| Formaty wejścia (8 rozszerzeń) | <span class="todo">✓ / do potwierdzenia</span> |
| JSON-y dla formularzy 2, 3, 4, 6, 7, 8, 9 | <span class="todo">x / 7</span> |
| Błędy lintera w naszych JSON-ach | <span class="todo">0</span> |
| I. Słowniki i dane inicjalne | <span class="todo">?</span> |
| II. Propozycja nowego słownika | <span class="todo">?</span> |
| III. Zależności i przepływy | <span class="todo">?</span> |
| IV. Frontend z uploadem i JSON | <span class="todo">?</span> |
| V. Wizualizacja formularza | <span class="todo">?</span> |
| VI. Walidacje i batch | <span class="todo">?</span> |

</div>
<div class="card hl">
<div class="big"><span class="todo">7/7</span></div>
<p>formularzy do oceny przetworzonych na Dockerze z lokalnym modelem. Wyniki w <code>wyniki/</code>.</p>
</div>
</div>

---

## Zgodnie ze standardem projektowania formularzy

<div class="cols3">
<div class="card"><h3>Strony tematyczne</h3><p>Urząd, wnioskodawca, adres, pełnomocnik, opłata skarbowa, kontakt, zgoda, podgląd z szablonów standardu.</p></div>
<div class="card"><h3>Walidacje</h3><p>PESEL, NIP, REGON, kod pocztowy, e-mail i wymagalność, także wykrywane z etykiet pól.</p></div>
<div class="card"><h3>Dane i słowniki</h3><p>Adres i kontakt z danych inicjalnych, słowniki (np. kraje, TERYT) podpięte do pól.</p></div>
</div>

<br>

Nic nie znika po cichu: każdy blok źródła ma pole, tekst albo jawne „pomiń”, a nieprzypisane bloki widać w raporcie.

---

<!-- _class: stage -->

<div class="deco stage-deco"><div class="round grey"></div><div class="blue"></div><div class="tiny"></div><div class="mag"></div></div>

## Wdrożenie: działa u urzędu, bez chmury

<div class="cols3">
<div class="card hl"><div class="big">8B</div><p>parametrów: Qwen3-VL na Apache-2.0, czyta tekst i skany, działa przez Ollama na CPU i GPU.</p></div>
<div class="card"><div class="big">1</div><p>polecenie: <code>docker compose up --build</code>. Oficjalne obrazy, przypięte wersje, użytkownik bez roota.</p></div>
<div class="card"><div class="big">0</div><p>zewnętrznych API i zapisanych plików. Zależności open source bez copyleftu.</p></div>
</div>

<br>

Czas przetworzenia formularza: <span class="todo">~x min na CPU, ~y s na GPU</span>

---

<!-- _class: dark -->

<div class="deco dark-deco"><div class="round disc"></div><div class="tiny"></div></div>

## Jakość kodu i co dalej

<div class="cols">
<div>

- <em>67+</em> testów, w tym porównanie z wzorcowymi JSON-ami COI
- `npm run check`: biome, tsc, ruff, pytest
- Dokumentacja architektury i decyzji w repo

</div>
<div>

- Ręczna korekta FormSpec bez ponownego wywołania modelu
- Batch wielu formularzy
- Gotowe pod agentów: ten sam JSON dla ludzi i automatów

</div>
</div>

<br>

<span class="todo">Ewelina · Konrad · Gabrysia</span>

Repozytorium: <span class="todo">link</span> · Film: <span class="todo">link</span>
