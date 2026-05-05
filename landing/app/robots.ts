import type { MetadataRoute } from "next"

const SITE_URL = "https://preciocompare.com"

// Required by output: 'export' — opts the route into static generation.
export const dynamic = "force-static"

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  }
}
