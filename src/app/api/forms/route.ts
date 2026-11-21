import { fail, forward } from "@/lib/api-proxy";

// Starts a conversion job; the page polls /api/forms/[id] for its steps and result
// (one long request would hit fetch's 5-minute header timeout while the model writes).
export async function POST(req: Request) {
  let file: FormDataEntryValue | null;
  try {
    file = (await req.formData()).get("file");
  } catch {
    return fail(400, "Nie udało się odczytać przesłanego pliku.");
  }
  if (!(file instanceof File)) return fail(400, "Nie wybrano pliku.");

  const out = new FormData();
  out.append("file", file, file.name);
  return forward("/api/v1/jobs?details=true", {
    method: "POST",
    body: out,
    signal: req.signal,
  });
}
