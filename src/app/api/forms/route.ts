import "server-only";
import { createHmac } from "node:crypto";

// Proxies the upload to the API so the JWT secret and the API address stay on the server.
const API_URL = process.env.AUTOFORMULARZ_API_URL ?? "http://localhost:8000";

const b64url = (s: string) => Buffer.from(s).toString("base64url");

/** Short-lived HS256 token signed with AUTOFORMULARZ_JWT_SECRET (none if auth is off). */
function token(): string | undefined {
  const secret = process.env.AUTOFORMULARZ_JWT_SECRET;
  if (!secret) return undefined;
  const aud = process.env.AUTOFORMULARZ_JWT_AUDIENCE;
  const claims = {
    sub: "web",
    exp: Math.floor(Date.now() / 1000) + 15 * 60,
    ...(aud ? { aud } : {}),
  };
  const body = `${b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }))}.${b64url(JSON.stringify(claims))}`;
  const sig = createHmac("sha256", secret).update(body).digest("base64url");
  return `${body}.${sig}`;
}

const fail = (status: number, message: string) =>
  Response.json({ error: { code: "WEB_PROXY", message } }, { status });

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
  const jwt = token();
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/forms?details=true`, {
      method: "POST",
      body: out,
      headers: jwt ? { Authorization: `Bearer ${jwt}` } : undefined,
    });
  } catch {
    return fail(
      502,
      "Usługa konwersji nie odpowiada. Sprawdź, czy API działa, i spróbuj ponownie.",
    );
  }
  return new Response(res.body, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/json",
    },
  });
}
