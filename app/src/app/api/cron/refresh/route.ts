import { revalidatePath } from "next/cache";
import { sql } from "@/lib/db";

export const dynamic = "force-dynamic";

/**
 * Called once a day by Vercel Cron (vercel.json). Two jobs:
 *  1. A real query against the warehouse, which counts as activity and keeps
 *     a free-tier Supabase project from pausing after a quiet week.
 *  2. Marks every page stale so the next visit regenerates it from fresh data.
 * Vercel sends `Authorization: Bearer $CRON_SECRET` automatically.
 */
export async function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || request.headers.get("authorization") !== `Bearer ${secret}`) {
    return new Response("Unauthorized", { status: 401 });
  }
  const [row] = await sql()<{ articles: number; latest: string }[]>`
    SELECT total_articles::int AS articles, latest_article_date::text AS latest
    FROM bandcamp.vw_pipeline_health`;
  revalidatePath("/", "layout");
  return Response.json({ ok: true, ...row, revalidatedAt: new Date().toISOString() });
}
