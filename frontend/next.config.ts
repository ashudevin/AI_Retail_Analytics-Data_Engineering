import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * Standard Next.js build for Vercel and Docker.
   * `standalone` enables minimal production Docker images.
   */
  output: "standalone",
  images: { unoptimized: true },
};

export default nextConfig;
