import "server-only";
import postgres from "postgres";

/**
 * One Postgres client for the whole app, created lazily so importing this
 * module never opens a connection by itself.
 *
 * The app only ever reads the views in db/views.sql - the same semantic layer
 * Tableau and the notebooks use - so a metric is defined once for every
 * surface. Point DATABASE_URL at a read-only role (see db/app_role.sql).
 *
 * `prepare: false` keeps it compatible with Supabase's transaction pooler
 * (port 6543) as well as the session pooler (5432).
 */
let client: postgres.Sql | undefined;

export function sql() {
  if (!client) {
    const url = process.env.DATABASE_URL;
    if (!url) {
      throw new Error(
        "DATABASE_URL is not set. Copy app/.env.example to app/.env.local and add the Supabase connection string.",
      );
    }
    client = postgres(url, {
      max: 2,
      prepare: false,
      idle_timeout: 20,
      connect_timeout: 15,
    });
  }
  return client;
}
