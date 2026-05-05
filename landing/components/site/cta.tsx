import Link from "next/link"

export function CTA() {
  return (
    <section id="demo" className="relative">
      <div className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="relative overflow-hidden rounded-md border border-border bg-card px-8 py-16 lg:px-16 lg:py-20">
          <div
            aria-hidden
            className="pointer-events-none absolute -top-32 -right-32 h-[26rem] w-[26rem] rounded-full opacity-60 blur-3xl"
            style={{
              background:
                "radial-gradient(closest-side, oklch(0.85 0.08 300 / 0.45), transparent 70%)",
            }}
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -bottom-32 -left-20 h-[24rem] w-[24rem] rounded-full opacity-50 blur-3xl"
            style={{
              background:
                "radial-gradient(closest-side, oklch(0.9 0.06 175 / 0.45), transparent 70%)",
            }}
          />

          <div className="relative mx-auto flex max-w-3xl flex-col items-center text-center">
            <div className="flex items-center gap-3">
              <span className="label-mono-primary">Acceso privado</span>
            </div>

            <h2 className="mt-6 font-serif text-[2.25rem] leading-[1.1] tracking-tight text-foreground lg:text-[3rem]">
              Pensado para retailers que necesitan{" "}
              <span className="text-primary">decidir rápido</span> y con datos
            </h2>
            <span className="mt-3 block h-px w-12 bg-primary" />

            <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
              Acceso privado para negocios seleccionados. Si vendés electrónica
              en Argentina y necesitás comparar competidores sin armar
              planillas, escribinos y te damos acceso.
            </p>

            <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-center">
              <Link
                href="/solicitar-acceso"
                className="inline-flex h-11 items-center justify-center rounded-sm bg-primary px-7 font-mono text-[11px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Solicitar acceso
              </Link>
              <Link
                href="mailto:fs@preciocompare.com"
                className="inline-flex h-11 items-center justify-center rounded-sm border border-border bg-card px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-foreground transition-colors hover:border-primary/40 hover:text-primary"
              >
                Hablar con el equipo
              </Link>
            </div>

            <p className="mt-6 text-[12px] leading-relaxed text-muted-foreground">
              Buenos Aires · Argentina ·{" "}
              <span className="text-foreground">fs@preciocompare.com</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
