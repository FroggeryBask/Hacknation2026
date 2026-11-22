# Budżet Eden AI (wspólny klucz, 100 €)

Źródło prawdy: panel Eden AI (https://app.edenai.run). Ta tabela to szybki podgląd dla zespołu: **po każdej serii zapytań do Eden dopisz jedną linię** na dole.

- Koszt podaje sam Eden w każdej odpowiedzi (`cost`, USD). `api/src/autoformularz/llm.py` zapisuje go w `EDEN_USAGE`.
- Generator wyników (`uv run python -m autoformularz.results`) wypisuje na końcu gotową linię do tej tabeli (wstaw tylko imię), a koszt każdego formularza zapisuje w `wyniki/NN.report.json` (`edenUsage`).
- Model: `deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct`, 0,15 $ za 1M tokenów wejścia i 0,60 $ za 1M wyjścia. Jeden formularz ≈ 0,005 $. **Nie zmieniaj modelu bez uzgodnienia** (inne mogą być kilkadziesiąt razy droższe).
- Przed większą serią daj znać na kanale. Domyślnie pracujemy na Ollamie (`AUTOFORMULARZ_LLM_PROVIDER=ollama`) albo na zapisanych FormSpec (`--compile`, zero kosztu).

| Data | Kto | Co | Model | Zapytania | Koszt (USD) |
|---|---|---|---|---|---|
| 2026-11-21 | Ewelina | test: pole `cost` w odpowiedzi Eden | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0000 |
| 2026-11-21 | Ewelina | wyniki formularz 2: zapętlenie modelu, Eden przerwał po 400 s (504), koszt nieznany (do ~0,01) | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | ~0.0100 |
| 2026-11-21 | Ewelina | diagnoza zapętlenia (`max_tokens=6000`) | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0042 |
| 2026-11-21 | Ewelina | wyniki formularz 2 po poprawce zapętlenia | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0022 |
| 2026-11-21 | Ewelina | wyniki formularze 3,4,6,7 (ok) oraz 8,9 (ucięte na limicie 8000 tokenów) | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 6 | 0.0199 |
| 2026-11-21 | Ewelina | wyniki formularze 8 (znów ucięty: zapętlenie na objaśnieniach), 9 (ok) po poprawce odczytu DOCX | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 2 | 0.0117 |
| 2026-11-21 | Ewelina | wyniki formularze 8 (ok), 9 (gorszy niż poprzedni, zostaje spec z poprzedniej serii) po zakresach ról | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 2 | 0.0115 |
| 2026-11-21 | Ewelina | wyniki formularz 8 z regułami o polach nieobowiązkowych w prompcie: ucięty (role HEADING dla każdego bloku), zostaje poprzedni spec | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0066 |
| 2026-11-21 | Ewelina | wyniki formularz 8 ze schematem dla modelu (tylko dozwolone role, `required` obowiązkowe): ok | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0060 |
| 2026-11-21 | Ewelina | test Dockera z `docker-compose.eden.yml`: formularze 2 i 8 przez API w kontenerze (ok); wcześniej przerwany skrypt pomiaru mógł wysłać 1–2 zapytania (koszt nieznany, ≤ 0,01) | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 2 | 0.0080 |
| 2026-11-21 | Ewelina | wyniki formularze 8 (ok: prompt 9911 tok., odpowiedź 6302 tok., 0,0053 $) i 9 (ucięty: zapętlenie po „Podsumowaniu”, zostaje poprzedni spec) z presortem i skracaniem linii do wypełnienia | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 2 | 0.0115 |
| 2026-11-21 | Ewelina | wyniki formularz 9 bez presortu i bez skracania linii (porównanie): przeszedł na granicy limitu (7627 tok. odpowiedzi), ale gorszy od zapisanego (84 pola, zgody ×3), zostaje poprzedni spec | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0063 |
| 2026-11-21 | Ewelina | wyniki formularz 9 z presortem i zwijaniem powtórzonych wersji: prompt 8238 tok., znów ucięty (model opisuje warianty po kolei); na tej odpowiedzi zbudowany odzysk uciętych odpowiedzi, zostaje poprzedni spec | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0060 |
| 2026-11-21 | Ewelina | wyniki formularz 9 z limitem 12000: przeszedł (6559 tok., 2 min), ale model rozpisał sekcje na warianty; wykryty błąd kanonu (pusty formularz dla „nagrody”), poprawiony w kodzie; zostaje poprzedni spec (pełniejszy) | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 1 | 0.0052 |
| 2026-11-21 | Ewelina | diagnoza formularz 1 (.doc) z frontendu: 2 wysyłki z UI (zapętlenie w polach jednej sekcji, frontend przerwał po 5 min, koszt nieznany, do ~0,012) + test opóźnienia Eden (5 tok.) + odtworzenie ze strumieniem przerwane po 90 s (~1700 tok.) | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 4 | ~0.0140 |
| 2026-11-22 | Ewelina | formularz 1 zgodność ze wzorcem (presort: przypisy, nagłówek dwukolumnowy; kanon; prompt; zatrzymanie pętli na polach): PDF+DOCX (pętle do limitu, 433 s i 174 s), PDF/DOCX/ODS/JPG z nowym presortem, kontrolny PDF po poprawce pętli (20 s, wynik = wzorzec); + 3 wysyłki z UI przerwane (pętle na polach) | deepinfra/Qwen/Qwen3-VL-30B-A3B-Instruct | 7 (+3) | ~0.040 |
| 2026-11-22 | Ewelina | wyniki 2-9 dwie serie na Qwen3-VL (porównanie, nie przyjęte) + diagnoza pętli (formularz 2) + wybór modelu na formularzu 9: Qwen3.6-35B-A3B (2×, myśli, 0,042), Qwen3.5-122B (cały limit na myślenie, 0,118), Qwen3.5-397B (0,035), Mistral-Small-4-119B (zły JSON, 0,005), DeepSeek V4.1 Flash (0,004) + DeepSeek na formularzach 1-8 (0,009) i skan przez API (0,001); zapytania próbne o myślenie Qwen3.6 (~0,003) | różne (zob. opis) | ~30 | ~0.27 |
| 2026-11-22 | Ewelina | wyniki 2-9 na DeepSeek V4.1 Flash: dwie serie „najlepsza z 3” (0,0254 i 0,0274) + formularze 8 i 9 „najlepsza z 5” (0,0225) | deepinfra/deepseek-ai/DeepSeek-V4.1-Flash-1017 | 52 | 0.0753 |
| 2026-11-22 | Ewelina | wyniki formularz 9 na DeepSeek „najlepsza z 5” z uzupełnianiem z innych odpowiedzi; zapisany wynik = odpowiedź z warunkami uzupełniona o sekcje reprezentanta i pełnomocnika klubu | deepinfra/deepseek-ai/DeepSeek-V4.1-Flash-1017 | 5 | 0.0108 |
