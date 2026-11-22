---
marp: true
lang: pl
size: 16:9
paginate: true
title: autoformularz
description: Cyfryzacja formularzy urzędowych, HackNation 2026, zadanie COI
style: |
  /* Motyw na wzór identyfikacji COI (Behance 223311653, coi.gov.pl):
     Inter Light w nagłówkach, granat #0b1a4f, królewski błękit #1f3ea6,
     magenta #8e1a6c→#e3125a, lawenda. Grafiki jak na tablicy COI: płaskie
     koło, prostokąt magenty, lawendowy kwadrat z jasnym pasem, mały
     magentowy kwadrat na krawędzi. Bez logo COI. */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700&display=swap');
  :root {
    --ink: #0b1a4f;
    --muted: #4a5068;
    --line: #d1d4dd;
    --paper: #ffffff;
    --soft: #eceff8;
    --navy: #0b1a4f;
    --navy-2: #13286e;
    --blue: #1f3ea6;
    --blue-2: #4f79b5;
    --blue-pale: #b4cdf5;
    --plum: #871c6c;
    --crimson: #ca0049;
    --crimson-2: #e3125a;
    --magenta: linear-gradient(90deg, #8e1a6c, #e3125a);
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
  section.dark::before { background: linear-gradient(90deg, #2c3d7a calc(100% - 88px), var(--crimson-2) calc(100% - 88px)); }

  /* Grafiki z tablicy COI (Behance): płaskie formy z liniowym gradientem, nakładane na siebie */
  .deco, .deco div { position: absolute; }
  .deco { inset: 0; pointer-events: none; z-index: 0; }
  section > :not(.deco, footer, header) { position: relative; z-index: 1; }
  .deco .round { border-radius: 50%; }
  .deco .mag { background: linear-gradient(90deg, #8e1a6c, #e3125a); }
  .deco .pix { background: linear-gradient(135deg, #e3125a, #8e1a6c); }
  .deco .royal { background: linear-gradient(100deg, #2a4cc0, #1c379a 70%); }
  .deco .lav { background: linear-gradient(180deg, #eef1fb, #a9b7e8); }
  .deco .lav-strip { background: linear-gradient(90deg, rgba(255,255,255,.85), rgba(255,255,255,0)); }
  .deco .deep { background: linear-gradient(180deg, #1c379a, #0b1a4f); }
  section:has(.deco)::before { display: none; }

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
  section.dark em { color: #ff6fa6; }
  section.dark a { color: #ff6fa6; }
  .sep { height: 1px; background: var(--line); margin: 36px 0 24px; }
  section.dark .sep { background: #3a4c8c; }
  section.dark li::marker { color: #ff6fa6; }
  section.dark code { background: var(--navy-2); color: #fff; }
  section.dark footer, section.dark::after { color: #9aa6cf; }
  section.dark .card { background: var(--navy-2); }
  section.dark .card p { color: #c3cbe6; }

  /* Tytuł */
  section.title { justify-content: center; }
  section.title::before { display: none; }
  section.title h1 { font-size: 80px; max-width: 620px; }
  /* „Papierowy wniosek” w dwóch liniach, strzałka na środku tego bloku, „e-formularz” bez dzielenia */
  section.title h1.hero-title { display: flex; align-items: center; gap: 28px; max-width: none; }
  .hero-title .arrow { line-height: 1; transform: translateY(-0.06em); }
  .hero-title .to { white-space: nowrap; }
  section.title p { font-size: 26px; color: #d3d9ef; max-width: 540px; }
  section.title::after, section.title footer { display: none; }

  /* Tytuł: billboard „Ludzie. Innowacje. Technologie.” (magenta u góry, koło, lawendowy kwadrat) */
  .hero .mag { left: 610px; top: 0; width: 440px; height: 118px; }
  .hero .royal { left: 1000px; top: 170px; width: 720px; height: 720px; }
  .hero .deep { left: 1050px; top: 0; width: 230px; height: 150px; }
  .hero .lav { left: 1040px; top: 390px; width: 240px; height: 330px; }
  .hero .lav-strip { left: 1040px; top: 390px; width: 80px; height: 330px; }
  .hero .pix { left: 1010px; top: 420px; width: 30px; height: 30px; }

  /* Ciemne plansze: wycinek koła i pas magenty przy prawej krawędzi */
  .dark-deco .royal { left: 1010px; top: -250px; width: 520px; height: 520px; }
  .dark-deco .mag { left: 760px; top: 0; width: 250px; height: 54px; }
  .dark-deco .lav { left: 1214px; top: 110px; width: 66px; height: 110px; }
  .dark-deco .pix { left: 1194px; top: 110px; width: 20px; height: 20px; }

  /* Jasne plansze: mały układ w prawym górnym rogu (lawendowe koło, granatowy kwadrat, magenta) */
  .corner .lavc { left: 1110px; top: -110px; width: 280px; height: 280px;
    background: linear-gradient(200deg, #eef1fb, #9fb0e6); }
  .corner .deep { left: 1190px; top: 0; width: 90px; height: 100px; }
  .corner .pix { left: 1166px; top: 100px; width: 24px; height: 24px; }

  /* Plansza z liczbami: ekran „Tworzymy nowoczesne rozwiązania” (lawendowy panel z kołem po prawej) */
  section.stage { background: var(--soft); padding-right: 360px; }
  .stage-deco .panel { left: 950px; top: 0; width: 330px; height: 720px;
    background: linear-gradient(180deg, #d9e0f7, #b9c5ef); }
  .stage-deco .disc { left: 1000px; top: 120px; width: 470px; height: 470px;
    background: linear-gradient(90deg, #7f93d6, #c9d3f3 70%, #e9edfa); }
  .stage-deco .deep { left: 1170px; top: 355px; width: 110px; height: 115px;
    background: linear-gradient(135deg, #e9edfa, #2f458f); }
  .stage-deco .white { left: 1170px; top: 470px; width: 110px; height: 120px; background: linear-gradient(180deg, #f5f7fd, #dfe5f8); }
  .stage-deco .pix { left: 950px; top: 300px; width: 52px; height: 52px; }

  .eq { display: flex; align-items: center; gap: 18px; font-size: 32px; font-weight: 300; margin: 0 0 18px; }
  .eq .op { color: #ff6fa6; font-size: 40px; }
  .eq .stack { display: flex; flex-direction: column; gap: 4px; padding-left: 18px; border-left: 3px solid #e3125a; font-size: 22px; color: #d3d9ef; }
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
  section.dark .lead { color: #d3d9ef; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
  .cols3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 28px; }
  .card { background: var(--soft); padding: 24px 28px; border-top: 4px solid var(--blue); }
  .card.hl { border-image: var(--magenta) 1; border-top-width: 4px; border-top-style: solid; }
  .card p { margin: 0; font-size: 21px; color: var(--muted); }
  .big { font-size: 68px; font-weight: 300; color: var(--crimson); line-height: 1; margin-bottom: 10px; letter-spacing: -0.02em; }
  .big.word { font-size: 40px; line-height: 1.1; }
  section.stage .cols3 .big { height: 90px; display: flex; align-items: flex-end; }
  section.stage .cols3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  section.dark .big { color: #ff6fa6; }
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

<div class="deco hero"><div class="round royal"></div><div class="deep"></div><div class="mag"></div><div class="lav"></div><div class="lav-strip"></div><div class="pix"></div></div>

<h1 class="hero-title"><span>Papierowy<br>wniosek</span><span class="arrow">→</span><span class="to">e-formularz</span></h1>

Z papierowego wniosku do e-formularza gotowego do importu w kilka minut, na otwartym modelu.

<!--
Mówca: jedno zdanie o tym, co robimy. Zespół przedstawiamy na końcu.
-->

---

<!-- _class: dark -->

<div class="deco dark-deco"><div class="round royal"></div><div class="mag"></div><div class="lav"></div><div class="pix"></div></div>

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

<div class="deco corner"><div class="round lavc"></div><div class="deep"></div><div class="pix"></div></div>

<div class="one"><span class="n">1</span><div><span>Plik</span><span>Wywołanie REST</span><span>Gotowy JSON</span></div></div>

<div class="steps">
<div><b>Plik</b><small>PDF · DOC · DOCX · ODS<br>XLSX · JPG · PNG</small></div><span>→</span>
<div><b>Wywołanie API</b><small><code>POST /api/v1/forms</code></small></div><span>→</span>
<div><b>JSON</b><small>W formacie COI</small></div><span>→</span>
<div><b>E-formularz</b><small>Gotowy. Po prostu.</small></div>
</div>

<div class="flow">
<div>odczyt<br>bloki z ID</div><span>→</span>
<div>presort<br>kod odsiewa</div><span>→</span>
<div class="ai">model<br>FormSpec</div><span>→</span>
<div>sprawdzenie<br>pokrycia</div><span>→</span>
<div>kompilator<br>COI JSON</div><span>→</span>
<div>linter<br>reguły techniczne</div>
</div>

Model tylko klasyfikuje bloki i wypełnia mały FormSpec, a <em>JSON COI buduje kod</em>.

---

<div class="deco corner"><div class="round lavc"></div><div class="deep"></div><div class="pix"></div></div>

## Mniej dla modelu, mniej błędów

<div class="cols">
<div class="card">
<h3>Zanim pójdzie do modelu</h3>
<p>Kod sam rozpoznaje klauzulę RODO, elementy tylko na papier (podpis, data, „wypełnia urząd”, stopki), dane wnioskodawcy z szablonu, przypisy i powtórzone wersje wniosku. Nie wysyła ich do modelu.</p>
<div class="big" style="margin-top:20px">−30–80%</div>
<p>krótszy prompt, niższy koszt</p>
</div>
<div class="card hl">
<h3>Po modelu</h3>
<p>Przypis „dane nieobowiązkowe” decyduje o polach opcjonalnych.</p><br>
<p>Pola zmyślone, czyli bez miejsca na papierze, są usuwane.</p><br>
<p>Zgody i oświadczenia model pisze przed stronami, więc nie giną, gdy odpowiedź zostanie ucięta.</p>
</div>
</div>

---

<!-- _class: dense -->

<div class="deco corner"><div class="round lavc"></div><div class="deep"></div><div class="pix"></div></div>

## Budowanie JSON dla COI: kompilator, bez modelu

<div class="cols">
<div>

- **Część standardowa z szablonów:** urząd, wnioskodawca, adres, pełnomocnik, opłata skarbowa, kontakt i zgody
- **Warunki** pokazywania pól w JSONata (`states`), także dla sekcji powtarzalnych i kilku wersji jednego wniosku
- **Walidacja:** pola wymagane oraz PESEL, NIP, REGON, kod pocztowy i e-mail, rozpoznawane także po etykietach

</div>
<div>

- **Kanon:** usuwa duplikaty sekcji, sekcje szablonu, wybory z jedną opcją i pola powtarzające tytuł
- **Stabilne identyfikatory:** stabilniejszy determinizm
- **Format pilnowany testami**

</div>
</div>

---

<div class="deco corner"><div class="round lavc"></div><div class="deep"></div><div class="pix"></div></div>

## Kontrola jakości

<div class="cols">
<div class="card">
<h3>Pokrycie</h3>
<p>Porównanie, które bloki dokumentu trafiły do formularza.</p>
</div>
<div class="card hl">
<h3>Skan bezpieczeństwa formularza</h3>
<p>Prośby o hasła, PIN, kody SMS i dane karty</p>
<p>Linki spoza gov.pl albo bez HTTPS</p>
<p>Tekst skierowany do modelu (prompt injection, PL i EN)</p>
<p>Ukryte znaki, HTML i skrypty</p>
<p>Bardzo długie etykiety</p><br>
<p>Tylko ostrzega, nigdy nie zmienia JSON-a.</p>
</div>
</div>

---

<div class="deco corner"><div class="round lavc"></div><div class="deep"></div><div class="pix"></div></div>

## Interfejs dla urzędnika

<div class="cols">
<div class="shot">ZRZUT: postęp na żywo<br>i formularz z sekcją warunkową<br>oraz błędem walidacji</div>
<div>

- Dynamiczne, warunkowe formularze z walidacją
- Postęp na żywo
- Anulowanie, które zatrzymuje model i oszczędza tokeny
- Prosty interfejs, który chroni przed utratą postępów
- Link do klauzuli informacyjnej przy zgodzie
- Dostępność (a11y)
- Wiele plików naraz (batch)

</div>
</div>

<!--
Renderer czyta wyłącznie COI JSON i ewaluuje states, więc podgląd i plik importu nie mogą się rozjechać.
-->

---

<!-- _class: stage -->

<div class="deco stage-deco"><div class="panel"></div><div class="round disc"></div><div class="deep"></div><div class="white"></div><div class="pix"></div></div>

## Zamknięty system

<div class="cols3">
<div class="card hl"><div class="big word">Docker</div></div>
<div class="card"><div class="big word">Oficjalne AI: Eden</div></div>
<div class="card"><div class="big">0</div><p>zależności copyleft, baz danych i zapisanych plików. Plik tylko w pamięci.</p></div>
</div>

<br>

Czas przetworzenia formularza: <em>średnio 7,4 s</em>

---

<div class="deco corner"><div class="round lavc"></div><div class="deep"></div><div class="pix"></div></div>

## Kompletność

| Zakres | Stan |
|---|---|
| Formaty wejścia: PDF, DOC, DOCX, ODS, XLSX, JPG, PNG | ✓ wszystkie |
| Błędy lintera w naszych JSON-ach | 0 |
| I. Słowniki i dane inicjalne | ✓ kraje, TERYT, dane z logowania |
| II. Propozycja nowego słownika | ✓ rasy psów, dyscypliny sportowe |
| III. Zależności i przepływy | ✓ warunki JSONata między polami, sekcjami i stronami |
| IV. Frontend z uploadem i JSON | ✓ upload, postęp, podgląd JSON |
| V. Wizualizacja formularza | ✓ e-formularz renderowany z JSON-a |
| VI. Walidacje i batch | ✓ PESEL, NIP, REGON, kod pocztowy, e-mail, długość pól; wiele plików naraz |

---

<!-- _class: dark -->

<div class="deco dark-deco"><div class="round royal"></div><div class="mag"></div><div class="lav"></div><div class="pix"></div></div>

<div class="cols">
<div>

## Jakość kodu

- <em>273</em> testy API, w tym porównanie z wzorcowymi JSON-ami COI
- `npm run check`: biome, tsc, ruff, pytest

</div>
<div>

## Co dalej

- Ręczna korekta FormSpec bez ponownego wywołania modelu
- Gotowe pod agentów: ten sam JSON dla ludzi i automatów

</div>
</div>

<div class="sep"></div>

Ewelina Musińska · Konrad Piekarz · Gabriela Rusek

Repozytorium: <a href="https://github.com/FroggeryBask/Hacknation2026">github.com/FroggeryBask/Hacknation2026</a> · Film: <a href="https://drive.google.com/file/d/1R41hzPY-2XGb4rstmdMXj6w0sqbB5rDl/view?usp=sharing">Google Drive</a>
