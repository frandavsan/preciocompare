import Link from "next/link"
import { Check } from "lucide-react"
import { HeroDashboardPreview } from "./hero-dashboard-preview"

export function Hero() {
  return (
    <section id="inteligencia" className="relative">
      <div className="mx-auto max-w-7xl px-6 pt-16 pb-24 lg:px-10 lg:pt-24 lg:pb-32">
        <div className="grid gap-14 lg:grid-cols-12 lg:gap-12">
          {/* Left: copy */}
          <div className="lg:col-span-6 xl:col-span-5">
            <div className="flex items-center gap-3">
              <span className="h-px w-8 bg-primary/60" />
              <span className="label-mono-primary">
                Modulo de inteligencia · Argentina
              </span>
            </div>

            <h1 className="mt-8 text-balance font-serif text-[2.5rem] leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-[3.75rem]">
              Inteligencia de precios para electrónica en{" "}
              <span className="text-primary">Argentina</span>
            </h1>

            <span className="mt-3 block h-px w-12 bg-primary" />

            <p className="mt-7 max-w-xl text-pretty text-[15px] leading-relaxed text-muted-foreground">
              Buscá un producto, seleccioná la coincidencia correcta y compará
              precio, stock, cuotas y envío entre competidores argentinos
              desde un solo panel.
            </p>

            <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link
                href="/solicitar-acceso"
                className="inline-flex h-11 items-center justify-center rounded-sm bg-primary px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Solicitar acceso
              </Link>
              <Link
                href="#producto"
                className="inline-flex h-11 items-center justify-center rounded-sm border border-border bg-card px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-foreground transition-colors hover:border-primary/40 hover:text-primary"
              >
                Ver producto
              </Link>
            </div>

            <ul className="mt-9 flex flex-col gap-2.5 text-[13px] text-muted-foreground">
              {[
                "6 tiendas argentinas indexadas",
                "Cuotas sin interés cuando están disponibles",
                "Simulación de envío en CABA",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2.5">
                  <Check className="h-3.5 w-3.5 text-primary" strokeWidth={2} />
                  {item}
                </li>
              ))}
            </ul>

            <div className="mt-12 flex items-center gap-5 border-t border-border pt-6">
              <span className="label-mono">Tiendas indexadas</span>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-serif text-[15px] text-foreground/70">
                <span>Frávega</span>
                <span className="text-foreground/25">·</span>
                <span>Megatone</span>
                <span className="text-foreground/25">·</span>
                <span>Cetrogar</span>
                <span className="text-foreground/25">·</span>
                <span>Castillo</span>
              </div>
            </div>
          </div>

          {/* Right: dashboard preview */}
          <div className="lg:col-span-6 xl:col-span-7">
            <HeroDashboardPreview />
          </div>
        </div>
      </div>
    </section>
  )
}
