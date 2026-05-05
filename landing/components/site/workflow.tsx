import { Search, ListChecks, BarChart3 } from "lucide-react"

const steps = [
  {
    number: "I",
    icon: Search,
    label: "Paso uno",
    title: "Buscar producto",
    description:
      "Escribí una búsqueda como “Samsung S24 Ultra 256GB” o “AB103”. PrecioCompare consulta cada tienda indexada y devuelve coincidencias.",
    chips: ["Marca", "Modelo", "SKU"],
  },
  {
    number: "II",
    icon: ListChecks,
    label: "Paso dos",
    title: "Seleccionar coincidencias",
    description:
      "Confirmá qué resultado corresponde en cada tienda, especialmente cuando los nombres varían. Selección manual disponible.",
    chips: ["Selección manual", "Coincidencia exacta"],
  },
  {
    number: "III",
    icon: BarChart3,
    label: "Paso tres",
    title: "Analizar comparación",
    description:
      "Revisá mejor precio, promedio, brecha, cuotas, stock, envío y links directos a cada tienda en una sola tabla.",
    chips: ["Precio", "Cuotas", "Stock", "Envío"],
  },
]

export function Workflow() {
  return (
    <section className="relative border-y border-border bg-accent/10">
      <div className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="flex flex-col items-start justify-between gap-8 lg:flex-row lg:items-end">
          <div className="max-w-xl">
            <div className="flex items-center gap-3">
              <span className="h-px w-8 bg-primary/60" />
              <span className="label-mono-primary">Flujo de trabajo</span>
            </div>
            <h2 className="mt-6 font-serif text-[2.25rem] leading-[1.1] tracking-tight text-foreground lg:text-[2.75rem]">
              De la búsqueda a la decisión, en tres pasos
            </h2>
            <span className="mt-3 block h-px w-12 bg-primary" />
          </div>
          <p className="max-w-sm text-[15px] leading-relaxed text-muted-foreground">
            Diseñado para dueños de retail y category managers que necesitan
            comparar competidores rápido, sin armar planillas.
          </p>
        </div>

        <div className="mt-14 grid gap-px overflow-hidden rounded-md border border-border bg-border md:grid-cols-3">
          {steps.map((step) => (
            <article
              key={step.number}
              className="relative flex flex-col gap-6 bg-card p-8 lg:p-10"
            >
              <div className="flex items-center justify-between">
                <span className="font-serif text-4xl text-primary/80">
                  {step.number}
                </span>
                <step.icon
                  className="h-5 w-5 text-foreground/40"
                  strokeWidth={1.5}
                />
              </div>

              <div>
                <span className="label-mono">{step.label}</span>
                <h3 className="mt-3 font-serif text-xl leading-tight tracking-tight text-foreground">
                  {step.title}
                </h3>
                <p className="mt-3 text-[14px] leading-relaxed text-muted-foreground">
                  {step.description}
                </p>
              </div>

              <div className="mt-auto flex flex-wrap gap-2 border-t border-border pt-4">
                {step.chips.map((chip) => (
                  <span
                    key={chip}
                    className="rounded-sm border border-border bg-background px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground"
                  >
                    {chip}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
