import { fileURLToPath } from "url"
import { dirname } from "path"

// Pin Turbopack to this directory so it doesn't infer the parent Vite app's
// package-lock.json as the workspace root and emit a multi-lockfile warning.
const __dirname = dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: __dirname,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
