"use client";

import { useEffect, useRef } from "react";
import type { Feature } from "@/lib/queries";
import { fmtDate } from "@/lib/format";
import { bandcampSearchUrl, spotifyAlbumUrl } from "@/lib/links";
import Cover from "@/components/Cover";
import { CloseIcon, ExternalIcon } from "@/components/icons";

type Patch = { genre?: string; country?: string; city?: string; author?: string; type?: "self" | "label" };

/** One feature, in a native <dialog> (focus trap, Esc and backdrop for free). */
export default function Detail({
  feature,
  onClose,
  onFilter,
  placeLabel,
}: {
  feature: Feature | null;
  onClose: () => void;
  onFilter: (patch: Patch) => void;
  placeLabel: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (feature && !d.open) d.showModal();
    if (!feature && d.open) d.close();
  }, [feature]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="detail-title"
      className="m-auto w-[min(92vw,760px)] rounded-2xl border border-line bg-surface p-0 text-ink shadow-2xl shadow-black/60 backdrop:bg-black/70 backdrop:backdrop-blur-sm"
    >
      {feature && (
        <div className="grid gap-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          {/* On phones the cover is capped so the listening links stay above the fold. */}
          <div className="px-5 pt-5 sm:p-0">
            <div className="max-w-56 overflow-hidden rounded-lg sm:max-w-none sm:rounded-none sm:rounded-l-2xl">
              <Cover img={feature.img} artist={feature.artist} album={feature.album} size={640} eager />
            </div>
          </div>
          <div className="flex flex-col p-5 sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <p className="text-xs uppercase tracking-[0.16em] text-muted">Album of the Day · {fmtDate(feature.d)}</p>
              <button
                onClick={onClose}
                aria-label="Close"
                autoFocus
                className="-mr-2 -mt-2 rounded-full p-2 text-muted hover:bg-surface-3 hover:text-ink"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            </div>
            <h2 id="detail-title" className="mt-2 text-2xl font-semibold leading-tight tracking-tight">
              {feature.album}
            </h2>
            <p className="mt-1 text-lg text-ink-2">{feature.artist}</p>

            <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted">Label</dt>
              <dd className="text-ink-2">{feature.indie ? "Self-released" : feature.label}</dd>
              <dt className="text-muted">Based in</dt>
              <dd className="text-ink-2">{placeLabel}</dd>
              <dt className="text-muted">Genre</dt>
              <dd className="text-ink-2">{feature.genre ?? "Untagged"}</dd>
              <dt className="text-muted">Written by</dt>
              <dd className="text-ink-2">{feature.author ?? "Unknown"}</dd>
            </dl>

            <div className="mt-6 flex flex-wrap gap-2">
              {feature.sp && (
                <a
                  href={spotifyAlbumUrl(feature.sp)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-sm font-medium text-bg hover:bg-white"
                >
                  Listen on Spotify <ExternalIcon className="h-3.5 w-3.5" />
                </a>
              )}
              <a
                href={bandcampSearchUrl(feature.artist, feature.album)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-full border border-line px-4 py-2 text-sm text-ink-2 hover:border-baseline hover:text-ink"
              >
                Find on Bandcamp <ExternalIcon className="h-3.5 w-3.5" />
              </a>
            </div>

            <div className="mt-auto pt-6">
              <p className="text-xs text-muted">More like this</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {feature.city && <MoreButton onClick={() => onFilter({ city: feature.city! })}>From {feature.city}</MoreButton>}
                {feature.genre && <MoreButton onClick={() => onFilter({ genre: feature.genre! })}>{feature.genre}</MoreButton>}
                {feature.author && <MoreButton onClick={() => onFilter({ author: feature.author! })}>By {feature.author}</MoreButton>}
                {feature.country && <MoreButton onClick={() => onFilter({ country: feature.country! })}>{feature.country}</MoreButton>}
              </div>
            </div>
          </div>
        </div>
      )}
    </dialog>
  );
}

function MoreButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-full border border-line bg-surface-2 px-3 py-1 text-xs text-ink-2 hover:border-baseline hover:text-ink"
    >
      {children}
    </button>
  );
}
