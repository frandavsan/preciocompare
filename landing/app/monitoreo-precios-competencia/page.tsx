import type { Metadata } from "next"
import Link from "next/link"
import { BackgroundBlobs } from "@/components/site/background-blobs"
import { Navbar } from "@/components/site/navbar"
import { Footer } from "@/components/site/footer"

export const metadata: Metadata = {
  title:
    "Monitoreo de precios de competidores en Argentina",
  description:
    "Software para retailers de electrónica en Argentina que necesitan monitorear precios, stock y promociones de la competencia sin armar planillas.",
  alternates: { canonical: "/monitoreo-precios-competencia" },
  openGraph: {
    title: "Monitoreo de precios de competidores · Argentina",
    description:
      "Vista consolidada de precios, cuotas y stock entre competidores argentinos de electrónica.",
    url: "/monitoreo-precios-competencia",
  },
}

const reasons = [
  {
    title: "Reaccionar a tiempo",
    body:
      "Cuando un competidor mueve el precio o lanza una cuota agresiva, lo ves en el día — no a la semana siguiente cuando cae la venta.",
  },
  {
    title: "Decidir con datos, no con intuición",
    body:
      "Mirar tres tiendas a mano sesga la decisión. Comparar el modelo contra todo el mercado da contexto real para fijar el precio.",
  },
  {
    title: "Justificar márgenes",
    body:
      "Ante una caída de demanda o un margen ajustado, un panel con la posición vs. promedio del mercado deja claro si el problema es interno o de mercado.",
  },
]

const tracked = [
  "Precio publicado y precio efectivo con cuotas",
  "Promociones bancarias activas y cantidad de cuotas",
  "Disponibilidad y rotación entre tiendas",
  "Costo y opciones de envío",
  "Variantes y nombres distintos del mismo modelo",
]

export default function MonitoreoPreciosPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background">
      <BackgroundBlobs />
      <div className="relative z-10 flex min-h-screen flex-col">
        <Navbar />

        <section className="mx-auto w-full max-w-5xl px-6 pt-16 pb-10 lg:px-10 lg:pt-24">
          <div className="flex items-center gap-3">
            <span className="h-px w-8 bg-primary/60" />
            <span className="label-mono-primary">Monitoreo · B2B</span>
          </div>
          <h1 className="mt-7 max-w-3xl font-serif text-[2.4rem] leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-[3.4rem]">
            Monitorear precios de la{" "}
            <span className="text-primary">competencia</span> sin armar
            planillas
          </h1>
          <span className="mt-3 block h-px w-12 bg-primary" />
          <p className="mt-7 max-w-2xl text-pretty text-[15px] leading-relaxed text-muted-foreground">
            Mirar los precios de la competencia tienda por tienda no escala.
            PrecioCompare automatiza el seguimiento de precios, stock y
            promociones bancarias entre los principales retailers argentinos de
            electrónica, y los presenta en un panel pensado para decisiones de
            pricing.
          </p>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Por qué un retailer monitorea precios
          </h2>
          <div className="mt-6 grid gap-px overflow-hidden rounded-md border border-border bg-border lg:grid-cols-3">
            {reasons.map((r) => (
              <div key={r.title} className="bg-card p-6">
                <p className="label-mono-primary">{r.title}</p>
                <p className="mt-3 text-[14px] leading-relaxed text-muted-foreground">
                  {r.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Qué seguimos por modelo
          </h2>
          <ul className="mt-6 space-y-3 text-[15px] leading-relaxed text-muted-foreground">
            {tracked.map((t) => (
              <li key={t} className="flex gap-3">
                <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Cómo se ve en la práctica
          </h2>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            Cargás el modelo, elegís la coincidencia entre las tiendas (porque
            cada cadena lo nombra distinto) y obtenés precio, cuotas, stock y
            envío comparados. Cuando un competidor mueve el precio, la próxima
            consulta lo refleja sin trabajo manual.
          </p>
          <div className="mt-7">
            <Link
              href="/solicitar-acceso"
              className="inline-flex h-11 items-center justify-center rounded-sm bg-primary px-7 font-mono text-[11px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Solicitar acceso
            </Link>
          </div>
        </section>

        <Footer />
      </div>
    </main>
  )
}
