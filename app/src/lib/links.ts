/*
 * Spotify's CDN serves the same artwork at three sizes; the prefix picks one.
 * Using the 300px variant for grids keeps a page of 48 covers under 2 MB
 * without routing 2,000+ images through an image optimiser.
 */
const SIZE = { 640: "ab67616d0000b273", 300: "ab67616d00001e02", 64: "ab67616d00004851" } as const;

export const coverUrl = (hash: string, size: keyof typeof SIZE = 300) =>
  `https://i.scdn.co/image/${SIZE[size]}${hash}`;

export const spotifyAlbumUrl = (id: string) => `https://open.spotify.com/album/${id}`;

/** The warehouse keeps no article URL for the historic archive, so link to a Bandcamp search. */
export const bandcampSearchUrl = (artist: string, album: string) =>
  `https://bandcamp.com/search?q=${encodeURIComponent(`${artist} ${album}`)}&item_type=a`;

export const REPO_URL = "https://github.com/Joelb991/Bandcamp_Album-of-the-Day";
export const TABLEAU_URL = "https://public.tableau.com/views/bandcamp_aotd/Coverage";
export const PORTFOLIO_URL = process.env.NEXT_PUBLIC_PORTFOLIO_URL || "https://github.com/Joelb991";
export const AUTHOR = "Bryan Garcia";

export const repoFile = (path: string) => `${REPO_URL}/blob/main/${path}`;
