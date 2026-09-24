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
 * Connect through Supabase's *session* pooler (port 5432). The transaction
 * pooler (6543) stalls under `next build`: postgres.js pipelines several
 * queries per connection, and with 10 build workers pages hit the 60s limit
 * or receive another query's rows. The site regenerates once a day, so a
 * session connection per worker is plenty.
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
