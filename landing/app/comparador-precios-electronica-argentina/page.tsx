import type { Metadata } from "next"
import Link from "next/link"
import { Check } from "lucide-react"
import { BackgroundBlobs } from "@/components/site/background-blobs"
import { Navbar } from "@/components/site/navbar"
import { Footer } from "@/components/site/footer"

export const metadata: Metadata = {
  title:
    "Comparador de precios para electrónica en Argentina",
  description:
    "Compará precios, cuotas, stock y envío entre las principales tiendas argentinas de electrónica desde un solo panel. Frávega, Cetrogar, Megatone, OnCity, Castillo y Montes Hermanos.",
  alternates: { canonical: "/comparador-precios-electronica-argentina" },
  openGraph: {
    title:
      "Comparador de precios de electrónica · Argentina",
    description:
      "Precio, cuotas, stock y envío entre tiendas argentinas de electrónica desde un solo panel.",
    url: "/comparador-precios-electronica-argentina",
  },
}

const stores = [
  "Frávega",
  "Cetrogar",
  "Megatone",
  "OnCity",
  "Castillo",
  "Montes Hermanos",
]

const compared = [
  {
    title: "Precio publicado",
    body:
      "Listamos el precio que cada tienda muestra al público, normalizado para que la comparación sea directa.",
  },
  {
    title: "Cuotas sin interés",
    body:
      "Capturamos las promociones bancarias y la cantidad de cuotas, porque eso cambia el precio real que paga el cliente.",
  },
  {
    title: "Stock y disponibilidad",
    body:
      "Indicamos si el modelo está disponible, agotado o no listado, sin tener que abrir cada catálogo.",
  },
  {
    title: "Envío",
    body:
      "Simulamos un envío estándar a CABA para detectar tiendas con envío gratis o costos altos no visibles en la lista.",
  },
]

export default function ComparadorPreciosPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background">
      <BackgroundBlobs />
      <div className="relative z-10 flex min-h-screen flex-col">
        <Navbar />

        <section className="mx-auto w-full max-w-5xl px-6 pt-16 pb-10 lg:px-10 lg:pt-24">
          <div className="flex items-center gap-3">
            <span className="h-px w-8 bg-primary/60" />
            <span className="label-mono-primary">Comparador · Argentina</span>
          </div>
          <h1 className="mt-7 max-w-3xl font-serif text-[2.4rem] leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-[3.4rem]">
            Comparar precios de electrónica entre{" "}
            <span className="text-primary">tiendas argentinas</span>, sin abrir
            cada una
          </h1>
          <span className="mt-3 block h-px w-12 bg-primary" />
          <p className="mt-7 max-w-2xl text-pretty text-[15px] leading-relaxed text-muted-foreground">
            PrecioCompare consolida precio, cuotas, stock y envío de los
            principales retailers argentinos de electrónica. En vez de revisar
            tienda por tienda, ves el panorama del modelo en un solo panel y
            tomás decisiones de pricing con datos.
          </p>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Tiendas indexadas
          </h2>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            Cubrimos las cadenas que más mueven volumen de electrónica en
            Argentina. La lista crece por pedido de los clientes activos.
          </p>
          <ul className="mt-6 grid gap-2.5 text-[14px] text-foreground sm:grid-cols-2 lg:grid-cols-3">
            {stores.map((s) => (
              <li key={s} className="flex items-center gap-2.5">
                <Check className="h-4 w-4 text-primary" strokeWidth={2} />
                {s}
              </li>
            ))}
          </ul>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Qué comparamos por modelo
          </h2>
          <div className="mt-6 grid gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-2">
            {compared.map((c) => (
              <div key={c.title} className="bg-card p-6">
                <p className="label-mono-primary">{c.title}</p>
                <p className="mt-3 text-[14px] leading-relaxed text-muted-foreground">
                  {c.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-5xl px-6 py-10 lg:px-10">
          <h2 className="font-serif text-2xl tracking-tight text-foreground lg:text-3xl">
            Pensado para retailers, no para consumidores
          </h2>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            No somos un comparador de ofertas para usuarios finales. Nuestros
            usuarios son tiendas argentinas que necesitan saber dónde está el
            mercado para fijar y ajustar sus precios. El acceso es privado y se
            aprueba caso por caso.
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
