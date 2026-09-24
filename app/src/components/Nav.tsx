"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { REPO_URL, TABLEAU_URL } from "@/lib/links";
import { GitHubIcon, ExternalIcon, DiscIcon } from "./icons";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/archive", label: "Archive" },
  { href: "/map", label: "Map" },
  { href: "/methodology", label: "Methodology" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight text-ink">
          <DiscIcon className="h-5 w-5 text-series" />
          AOTD Analytics
        </Link>
        <nav aria-label="Main" className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto">
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm transition-colors ${
                  active ? "bg-surface-3 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <a
            href={TABLEAU_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-baseline hover:text-ink md:inline-flex"
          >
            Tableau <ExternalIcon className="h-3 w-3" />
          </a>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="Source code on GitHub"
            className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-baseline hover:text-ink"
          >
            <GitHubIcon className="h-4 w-4" />
            <span className="hidden sm:inline">Code</span>
          </a>
        </div>
      </div>
    </header>
  );
}
