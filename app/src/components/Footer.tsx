import { getHealth } from "@/lib/queries";
import { fmtDate } from "@/lib/format";
import { AUTHOR, PORTFOLIO_URL, REPO_URL, TABLEAU_URL } from "@/lib/links";

export default async function Footer() {
  const h = await getHealth();
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-muted sm:px-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-md space-y-2">
          <p className="text-ink-2">
            Data as of <span className="text-ink">{fmtDate(h.latestArticleDate)}</span> · warehouse last loaded{" "}
            {fmtDate(h.lastLoadAt)}
          </p>
          <p>
            An independent analysis. Not affiliated with Bandcamp or Spotify. Cover art is served by Spotify and
            links back to each album.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          <a className="hover:text-ink" href={PORTFOLIO_URL} target="_blank" rel="noreferrer">
            Built by {AUTHOR}
          </a>
          <a className="hover:text-ink" href={REPO_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
          <a className="hover:text-ink" href={TABLEAU_URL} target="_blank" rel="noreferrer">
            Tableau dashboard
          </a>
        </div>
      </div>
    </footer>
  );
}
