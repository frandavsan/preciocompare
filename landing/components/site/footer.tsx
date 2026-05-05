import Link from "next/link"

const seoLinks = [
  {
    label: "Comparador de precios · Argentina",
    href: "/comparador-precios-electronica-argentina",
  },
  {
    label: "Monitoreo de precios · Competencia",
    href: "/monitoreo-precios-competencia",
  },
  {
    label: "Cuotas y promociones bancarias",
    href: "/cuotas-promociones-retail-argentina",
  },
]

const productLinks = [
  { label: "Solicitar acceso", href: "/solicitar-acceso" },
  { label: "Producto", href: "/#producto" },
  { label: "Funcionalidades", href: "/#funcionalidades" },
]

export function Footer() {
  return (
    <footer className="border-t border-border bg-background/50">
      <div className="mx-auto max-w-7xl px-6 py-12 lg:px-10">
        <div className="grid gap-10 lg:grid-cols-3">
          <div>
            <p className="font-serif text-xl tracking-tight text-foreground">
              PrecioCompare
            </p>
            <p className="mt-3 max-w-xs text-[13px] leading-relaxed text-muted-foreground">
              Inteligencia de precios para retailers de electrónica en
              Argentina. Acceso privado.
            </p>
          </div>

          <div>
            <p className="label-mono">Soluciones</p>
            <ul className="mt-4 space-y-2.5">
              {seoLinks.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    className="text-[13px] text-muted-foreground transition-colors hover:text-primary"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="label-mono">Producto</p>
            <ul className="mt-4 space-y-2.5">
              {productLinks.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    className="text-[13px] text-muted-foreground transition-colors hover:text-primary"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            © 2026 PrecioCompare · Inteligencia de precios para retail
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Buenos Aires · Argentina
          </p>
        </div>
      </div>
    </footer>
  )
}
