import type { MetadataRoute } from "next"

const SITE_URL = "https://preciocompare.com"

// Required by output: 'export' — opts the route into static generation.
export const dynamic = "force-static"

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date()
  const routes: Array<{
    path: string
    changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"]
    priority: number
  }> = [
    { path: "/", changeFrequency: "weekly", priority: 1.0 },
    { path: "/solicitar-acceso", changeFrequency: "monthly", priority: 0.9 },
    {
      path: "/comparador-precios-electronica-argentina",
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      path: "/monitoreo-precios-competencia",
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      path: "/cuotas-promociones-retail-argentina",
      changeFrequency: "monthly",
      priority: 0.8,
    },
  ]

  return routes.map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified: now,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }))
}
