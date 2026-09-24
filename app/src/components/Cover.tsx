import { coverUrl } from "@/lib/links";
import { DiscIcon } from "./icons";

/**
 * Album art from Spotify's CDN, or - for the ~20% of features Spotify doesn't
 * carry - a typographic tile that says so, rather than a broken image.
 */
export default function Cover({
  img,
  artist,
  album,
  size = 300,
  className = "",
  eager = false,
}: {
  img: string | null;
  artist: string;
  album: string;
  size?: 640 | 300 | 64;
  className?: string;
  eager?: boolean;
}) {
  if (img) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- Spotify's CDN already serves sized variants
      <img
        src={coverUrl(img, size)}
        alt={`Cover of ${album} by ${artist}`}
        loading={eager ? "eager" : "lazy"}
        decoding="async"
        className={`aspect-square w-full bg-surface-3 object-cover ${className}`}
      />
    );
  }
  return (
    <div
      role="img"
      aria-label={`${album} by ${artist} (no cover art available)`}
      className={`flex aspect-square w-full flex-col justify-between bg-linear-to-br from-surface-3 to-surface-2 p-3 ${className}`}
    >
      <DiscIcon className="h-5 w-5 text-muted/70" />
      <div>
        <p className="line-clamp-3 text-sm font-semibold leading-snug text-ink-2">{album}</p>
        <p className="mt-1 text-[10px] uppercase tracking-wider text-muted">Not on Spotify</p>
      </div>
    </div>
  );
}
