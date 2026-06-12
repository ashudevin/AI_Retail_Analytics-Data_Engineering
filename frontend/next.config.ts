import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * Standard Next.js build for Vercel (NOT `output: "export"`).
   *
   * All pages are statically generated at build time (Server Components read
   * JSON from public/data via fs). Vercel serves them from the CDN — no
   * serverless cold starts, no routes-manifest mismatch.
   *
   * Do NOT set Vercel Output Directory to `out` — leave it empty/default.
   */
  images: { unoptimized: true },
};

export default nextConfig;
