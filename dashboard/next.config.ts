import { config } from "dotenv";
import type { NextConfig } from "next";

// Local dev: one .env at the repo root serves both scraper/ and dashboard/.
// On Vercel the file doesn't exist and env vars come from project settings.
config({ path: "../.env", quiet: true });

const nextConfig: NextConfig = {
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
