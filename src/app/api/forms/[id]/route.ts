import { forward } from "@/lib/api-proxy";

type Ctx = { params: Promise<{ id: string }> };

const path = async (ctx: Ctx) =>
  `/api/v1/jobs/${encodeURIComponent((await ctx.params).id)}`;

/** Steps of the job so far and, when done, its result. */
export async function GET(req: Request, ctx: Ctx) {
  return forward(await path(ctx), { signal: req.signal, cache: "no-store" });
}

/** Cancels the job: the model stops writing (no more tokens are paid for). */
export async function DELETE(req: Request, ctx: Ctx) {
  return forward(await path(ctx), { method: "DELETE", signal: req.signal });
}
