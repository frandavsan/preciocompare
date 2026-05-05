import Link from "next/link"
import { ArrowDown } from "lucide-react"

export function LandingIntro() {
  return (
    <section className="relative flex min-h-[38rem] items-center overflow-hidden lg:min-h-[calc(72svh-4rem)]">
      <div className="relative mx-auto flex w-full max-w-5xl flex-col items-center px-6 py-14 text-center lg:px-10 lg:py-16">
        <div className="flex items-center gap-3">
          <span className="h-px w-8 bg-primary/60" />
          <span className="label-mono-primary">Inteligencia retail</span>
          <span className="h-px w-8 bg-primary/60" />
        </div>

        <h1 className="mt-8 font-serif text-[4.5rem] leading-none text-foreground sm:text-[6rem] lg:text-[8rem]">
          PrecioCompare
        </h1>
        <span className="mt-5 block h-px w-16 bg-primary" />

        <p className="mt-7 max-w-2xl text-[16px] leading-relaxed text-muted-foreground sm:text-[18px]">
          Inteligencia de precios para retailers de electrónica en Argentina.
          Compará competidores, cuotas, stock y envío con un solo click.
        </p>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
          <Link
            href="/solicitar-acceso"
            className="inline-flex h-11 items-center justify-center rounded-sm bg-primary px-7 font-mono text-[11px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Solicitar acceso
          </Link>
          <Link
            href="#inteligencia"
            className="inline-flex h-11 items-center justify-center rounded-sm border border-border bg-card/75 px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-foreground backdrop-blur transition-colors hover:border-primary/40 hover:text-primary"
          >
            Ver producto
          </Link>
        </div>

        <Link
          href="#inteligencia"
          aria-label="Ver la información de producto"
          className="mt-12 inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card/70 text-primary shadow-sm backdrop-blur transition-colors hover:border-primary/40 hover:bg-card"
        >
          <ArrowDown className="h-4 w-4" strokeWidth={1.75} />
        </Link>
      </div>
    </section>
  )
}
