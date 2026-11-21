# Dostęp do modeli AI przez Eden AI (mail od organizatorów)

> Oryginalna treść maila od organizatorów zadania COI „Cyfryzacja formularzy”.
> Klucz API: `EDENAI_API_KEY` w `.env.local` (SECRET, tylko po stronie serwera, nigdy `NEXT_PUBLIC_`, nigdy w plikach `"use client"`).

---

Cześć,

dziękujemy za zgłoszenie do zadania COI „Cyfryzacja formularzy”! Na czas hackatonu udostępniamy Wam dostęp do modeli AI przez platformę Eden AI.

## Dane dostępowe

Endpoint dla LLM (zgodny z OpenAI Chat Completions):
https://api.edenai.run/v3/chat/completions

Endpoint dla wgrywania plików (docs: https://www.edenai.co/docs/v3/llms/file-upload):
https://api.edenai.run/v3/upload

Endpoint dla OCR (docs: https://www.edenai.co/docs/v3/expert-models/features/ocr/ocr):
https://api.edenai.run/v3/universal-ai

Klucz API Waszego zespołu:
`EDENAI_API_KEY` w `.env.local`

Klucz i zasoby może być wykorzystywany tylko w celu rozwiązania zadania Cyfryzacja formularzy. Jeśli Wasz zespół zrezygnuje z wykonywania tego zadania, należy to zgłosić niezwłocznie mentorom COI.

Dokumentację poszczególnych endpointów i inne funkcjonalności platformy znajdziecie na stronie:
https://www.edenai.co/docs

## Jak znaleźć model

Modele podaje się w formacie `dostawca/model` lub `usługa/dostawca/model`, np.:

- `google/gemma-4-31b-it`
- `mistral/mistral-small-2603`
- `deepinfra/meta-llama/Llama-3.3-70B-Instruct`
- `ocr/ocr/mistral/mistral-ocr-4-0`

Pełną listę modeli znajdziecie na dwa sposoby:

1. Katalog w przeglądarce: https://app.edenai.run/models – można filtrować po dostawcy i funkcji.
2. Przez API (bez klucza):
   ```sh
   curl -s https://api.edenai.run/v3/models | jq -r '.data[].id'
   ```
   Żeby zawęzić wyniki, dodajcie np. `| grep -i gemini`

Każdy model na liście ma pole „capabilities” – sprawdzicie tam m.in., czy przyjmuje obrazy/PDF-y (`input_modalities`) i czy obsługuje tool calling.

## Przykładowe zapytanie

```sh
curl -X POST https://api.edenai.run/v3/chat/completions \
  -H "Authorization: Bearer $EDENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-4-31b-it",
    "messages": [
      {"role": "system", "content": "Jesteś pomocnym asystentem."},
      {"role": "user", "content": "Podaj przepis na naleśniki."}
    ]
  }'
```
