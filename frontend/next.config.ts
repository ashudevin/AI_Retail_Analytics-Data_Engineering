import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export for Vercel — zero backend, instant cold-start-free loads
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
