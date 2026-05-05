import type { Metadata } from "next"
import { AccessRequestForm } from "@/components/access/access-request-form"
import { BackgroundBlobs } from "@/components/site/background-blobs"
import { Navbar } from "@/components/site/navbar"

export const metadata: Metadata = {
  title: "Solicitar acceso | Inteligencia de precios retail",
  description:
    "Pedí acceso privado a PrecioCompare, una herramienta para comparar precios, stock, cuotas y envío entre competidores argentinos de electrónica.",
  alternates: { canonical: "/solicitar-acceso" },
  openGraph: {
    title: "Solicitar acceso a PrecioCompare",
    description:
      "Acceso privado para retailers argentinos de electrónica. Pedí tu acceso y revisamos el registro manualmente.",
    url: "/solicitar-acceso",
  },
}

const reassurances = [
  "Sin tarjeta.",
  "Sin compromiso.",
  "Acceso manual para negocios seleccionados.",
]

export default function SolicitarAccesoPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background">
      <BackgroundBlobs />
      <div className="relative z-10 flex min-h-screen flex-col">
        <Navbar showAccessCta={false} />

        <section className="flex flex-1 items-center">
          <div className="mx-auto grid w-full max-w-7xl gap-12 px-6 py-16 lg:grid-cols-12 lg:px-10 lg:py-20">
            <div className="flex flex-col justify-center lg:col-span-5">
              <div className="flex items-center gap-3">
                <span className="h-px w-8 bg-primary/60" />
                <span className="label-mono-primary">Acceso privado</span>
              </div>

              <h1 className="mt-7 max-w-xl font-serif text-[2.6rem] leading-[1.06] tracking-tight text-foreground sm:text-5xl lg:text-[3.55rem]">
                Solicitá acceso a PrecioCompare
              </h1>
              <span className="mt-3 block h-px w-12 bg-primary" />

              <p className="mt-7 max-w-md text-[15px] leading-relaxed text-muted-foreground">
                Contanos qué negocio tenés y te contactamos para revisar el
                registro y coordinar la activación de tu cuenta.
              </p>

              <ul className="mt-8 grid gap-2.5 text-[13px] text-muted-foreground">
                {reassurances.map((item) => (
                  <li key={item} className="flex items-center gap-2.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                    {item}
                  </li>
                ))}
              </ul>

            </div>

            <div className="lg:col-span-6 lg:col-start-7">
              <AccessRequestForm />
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
