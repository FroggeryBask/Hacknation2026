# Tła prezentacji

Tła slajdów 1280×720 (pliki 2560×1440 JPG), generowane przez `generuj.py`:

```sh
uv run --with numpy --with pillow python docs/tla/generuj.py
```

Wzory: tablica identyfikacji COI na Behance (`materialy/inspo_prezentacja`), przede wszystkim strona „Pracuj z nami”. Podstawą jest jej znak: koło z gradientem stożkowym (szew pionowo w dół od środka), pod nim jasny prostokąt od lewej krawędzi koła do jego środka, mały kwadrat magenta → lawenda przy lewej krawędzi prostokąta i mała szara kulka z wcięciem. Poza tym: ogromne koło magenty na granacie (stopka strony), duże blade koła na białym (oferta pracy), raster kropek (ekran „Tworzymy nowoczesne rozwiązania”), nadruk z koszulki i giloszowanie z mObywatela. Bez logo COI i godła. Kolory jak w motywie `docs/prezentacja.md`.

| Plik | Do czego | Miejsce na tekst |
|---|---|---|
| `01-tytul.jpg` | slajd tytułowy: granat, znak COI po prawej | do x ≈ 680 px |
| `02-sekcja.jpg` | przerywnik, np. „Demo”: ogromne koło magenty | lewa połowa |
| `03-tresc-jasna.jpg` | zwykła treść: biel, blade koło w rogu | cały slajd poza prawym górnym rogiem |
| `04-tresc-jasna-bok.jpg` | liczby, wnioski: raster kropek, jasny znak COI po prawej | do x ≈ 820 px |
| `05-tresc-ciemna.jpg` | treść na granacie, dwa duże ciemne koła | cały slajd poza prawym górnym rogiem |
| `06-mobywatel.jpg` | demo, zrzuty ekranu (jasne jak mObywatel) | cały slajd |
| `07-kola.jpg` | treść z akcentem: blade koła i niebieskie koło po prawej | do x ≈ 900 px |
| `08-koniec.jpg` | podziękowania, kontakt (nadruk z koszulki COI) | lewa połowa |

Na tłach `02`, `03`, `05` i `07` jest już kreska u góry (na `03` i `07` szara z magentowym końcem jak w obecnym motywie, ale krótsza: kończy się przed formami w rogu), więc przy tych tłach wyłącz `section::before`, żeby nie było jej dwa razy.

Użycie w Marp (ścieżka względem `docs/prezentacja.md`):

```md
<!-- _class: dark -->
![bg](tla/01-tytul.jpg)
```
