import type { Metadata } from "next"
import Link from "next/link"
import { BackgroundBlobs } from "@/components/site/background-blobs"
import { Navbar } from "@/components/site/navbar"
import { Footer } from "@/components/site/footer"

export const metadata: Metadata = {
  title:
    "Cuotas y promociones bancarias en retail argentino",
  description:
    "Compará cuotas sin interés, promociones bancarias y financiación entre tiendas argentinas de electrónica. La cuota cambia el precio real — verlo en un solo panel.",
  alternates: { canonical: "/cuotas-promociones-retail-argentina" },
  openGraph: {
    title: "Cuotas sin interés y promociones · Retail AR",
    description:
      "Comparar cuotas y promociones bancarias entre competidores argentinos de electrónica.",
    url: "/cuotas-promociones-retail-argentina",
  },
}

const points = [
  {
    title: "El precio publicado no es el precio real",
    body:
      "En Argentina, las cuotas sin interés y las promociones bancarias hacen que dos tiendas con el mismo precio publicado tengan precios efectivos muy distintos para el cliente.",
  },
  {
    title: "Las promociones cambian rápido",
    body:
      "Días del banco, ciclos del Hot Sale, temporadas con tarjetas específicas. Si solo mirás el precio del catálogo, te perdés la mitad del juego.",
  },
  {
    title: "El cliente compara cuotas, no etiquetas",
    body:
      "El comportamiento real de compra mira la cuota mensual, el banco emisor y la financiación. Los retailers que ignoran ese plano pierden ventas que parecían ganadas.",
  },
]

export default function CuotasPromocionesPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background">
      <BackgroundBlobs />
      <div className="relative z-10 flex min-h-screen flex-col">
        <Navbar />

        <section className="mx-auto w-full max-w-5xl px-6 pt-16 pb-10 lg:px-10 lg:pt-24">
          <div className="flex items-center gap-3">
            <span className="h-px w-8 bg-primary/60" />
            <span className="label-mono-primary">Cuotas · Promos · Argentina</span>
          </div>
          <h1 className="mt-7 max-w-3xl font-serif text-[2.4rem] leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-[3.4rem]">
            Las cuotas cambian el{" "}
            <span className="text-primary">precio real</span> — comparalas en
            un solo lugar
          </h1>
          <span className="mt-3 block h-px w-12 bg-primary" />
          <p className="mt-7 max-w-2xl text-pretty text-[15px] leading-relaxed text-muted-foreground">
            En el retail argentino, las cuotas sin interés y las promociones
            bancarias mueven la decisión del cliente más que el precio
            publicado. PrecioCompare captura las cuotas activas en cada tienda
            y las muestra junto al precio para que la comparación sea
            comparable de verdad.
          </p>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Por qué importa para un retailer
          </h2>
          <div className="mt-6 grid gap-px overflow-hidden rounded-md border border-border bg-border lg:grid-cols-3">
            {points.map((p) => (
              <div key={p.title} className="bg-card p-6">
                <p className="label-mono-primary">{p.title}</p>
                <p className="mt-3 text-[14px] leading-relaxed text-muted-foreground">
                  {p.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Qué capturamos por modelo
          </h2>
          <ul className="mt-6 space-y-3 text-[15px] leading-relaxed text-muted-foreground">
            <li className="flex gap-3">
              <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>Cuotas sin interés disponibles y la cantidad por cada banco emisor.</span>
            </li>
            <li className="flex gap-3">
              <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>Cuota mensual estimada para que la comparación sea entendible al instante.</span>
            </li>
            <li className="flex gap-3">
              <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>Mejor promoción detectada por modelo, ordenada por costo financiero.</span>
            </li>
            <li className="flex gap-3">
              <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>Identificamos si una tienda no tiene cuotas activas, lo que muchas veces explica una caída de ventas.</span>
            </li>
          </ul>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Pensado para tomar decisiones rápidas
          </h2>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            Si tu tienda tiene un precio competitivo pero los competidores
            ofrecen 12 cuotas sin interés, estás perdiendo igual. PrecioCompare
            te muestra el cuadro completo para que la decisión de pricing y
            financiación sea coherente.
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
