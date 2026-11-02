import { revalidateTag } from "next/cache";

import { CACHE_TAGS } from "@/lib/cache-tags";
import { isAuthorized } from "@/lib/revalidate-auth";

// Called by the GitHub Actions workflow after each daily run:
//   curl -X POST -H "Authorization: Bearer $REVALIDATE_SECRET" <dashboard>/api/revalidate
export async function POST(request: Request): Promise<Response> {
  if (!isAuthorized(request.headers.get("authorization"), process.env.REVALIDATE_SECRET)) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  for (const tag of CACHE_TAGS) {
    // Stale-while-revalidate: next visitor triggers the refresh. Data changes once a day.
    revalidateTag(tag, "max");
  }
  return Response.json({ ok: true, revalidated: CACHE_TAGS });
}
