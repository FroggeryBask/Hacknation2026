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
