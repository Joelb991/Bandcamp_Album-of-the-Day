import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The app lives in a subfolder of the pipeline repo; pin the root so a
  // lockfile further up the tree is never mistaken for this project's.
  turbopack: { root: __dirname },
};

export default nextConfig;
