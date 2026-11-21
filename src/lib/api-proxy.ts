import "server-only";
import { createHmac } from "node:crypto";

// Server-side calls to the API, so the JWT secret and the API address stay on the server.
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

export const fail = (status: number, message: string) =>
  Response.json({ error: { code: "WEB_PROXY", message } }, { status });

/** Forwards to the API and passes its answer through; 502 when the API cannot be reached. */
export async function forward(
  path: string,
  init: RequestInit & { signal: AbortSignal },
): Promise<Response> {
  const jwt = token();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: jwt ? { Authorization: `Bearer ${jwt}` } : undefined,
    });
  } catch {
    if (init.signal.aborted) return fail(499, "Anulowano.");
    return fail(
      502,
      "Nie można połączyć się z usługą konwersji. Sprawdź, czy API działa, i spróbuj ponownie.",
    );
  }
  return new Response(res.status === 204 ? null : res.body, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/json",
    },
  });
}
