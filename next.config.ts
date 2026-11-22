import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server for the Docker image (Dockerfile.web).
  output: "standalone",
  // No image optimisation (the app has no next/image): sharp and its libvips binaries (LGPL-3.0) stay out
  // of the Docker image, so every shipped library is permissive (README, "Licencje").
  images: { unoptimized: true },
  outputFileTracingExcludes: {
    "*": ["node_modules/sharp/**", "node_modules/@img/**"],
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
