import {
  Search,
  Table2,
  ListChecks,
  CreditCard,
  Truck,
  FileSpreadsheet,
  LineChart,
} from "lucide-react"

type Feature = {
  label: string
  icon: typeof Search
  title: string
  description: string
  badge?: string
  muted?: boolean
}

const features: Feature[] = [
  {
    label: "01 · Búsqueda",
    icon: Search,
    title: "Búsqueda por modelo",
    description:
      "Ingresá marca, modelo o SKU y consultá resultados comparables entre tiendas.",
  },
  {
    label: "02 · Comparación",
    icon: Table2,
    title: "Comparación por tienda",
    description:
      "Revisá precio publicado, disponibilidad, cuotas y envío en una tabla consolidada.",
  },
  {
    label: "03 · Selección",
    icon: ListChecks,
    title: "Selección manual",
    description:
      "Cuando los nombres no coinciden perfecto, elegí manualmente qué producto comparar por tienda.",
  },
  {
    label: "04 · Cuotas",
    icon: CreditCard,
    title: "Cuotas y promociones",
    description:
      "Mostramos las mejores cuotas disponibles cuando la tienda expone esa información.",
  },
  {
    label: "05 · Envío",
    icon: Truck,
    title: "Envío y disponibilidad",
    description:
      "Simulamos disponibilidad y envío para CABA o código postal cuando el sitio permite consultarlo.",
  },
  {
    label: "06 · Reporte",
    icon: FileSpreadsheet,
    title: "Reporte de medios de pago",
    description:
      "Solicitá un análisis en Excel de planes de pago para profundizar condiciones comerciales.",
  },
]

export function Features() {
  return (
    <section id="funcionalidades" className="relative">
      <div className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="grid gap-12 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <div className="flex items-center gap-3">
              <span className="h-px w-8 bg-primary/60" />
              <span className="label-mono-primary">Funcionalidades</span>
            </div>
            <h2 className="mt-6 font-serif text-[2.25rem] leading-[1.1] tracking-tight text-foreground lg:text-[2.75rem]">
              Lo que hace PrecioCompare hoy
            </h2>
            <span className="mt-3 block h-px w-12 bg-primary" />
            <p className="mt-6 max-w-md text-[15px] leading-relaxed text-muted-foreground">
              Pensado para retailers que necesitan decidir rápido y con datos
              reales del mercado argentino. Sin promesas vacías: sólo lo que
              ya está funcionando.
            </p>
          </div>

          <div className="lg:col-span-8">
            <div className="grid grid-cols-1 gap-px overflow-hidden rounded-md border border-border bg-border md:grid-cols-2">
              {features.map((feature) => (
                <FeatureCard key={feature.title} {...feature} />
              ))}
              <FeatureCard
                label="07 · Roadmap"
                icon={LineChart}
                title="Historial de precios"
                description="Seguimiento temporal de precios para detectar movimientos del mercado."
                badge="Próximamente"
                muted
              />
              <div className="hidden bg-card md:block">
                <div className="flex h-full flex-col justify-between p-8">
                  <span className="label-mono">Acceso</span>
                  <p className="font-serif text-xl leading-tight text-foreground/70">
                    Privado para negocios seleccionados.
                  </p>
                  <span className="label-mono-primary">Solicitar invitación</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function FeatureCard({ label, icon: Icon, title, description, badge, muted }: Feature) {
  return (
    <article className="group relative flex flex-col gap-5 bg-card p-7 transition-colors hover:bg-accent/20">
      <div className="flex items-start justify-between">
        <span className="label-mono">{label}</span>
        {badge ? (
          <span className="rounded-sm border border-primary/30 bg-primary/5 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-primary">
            {badge}
          </span>
        ) : null}
      </div>

      <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background">
        <Icon
          className={`h-4 w-4 ${muted ? "text-muted-foreground" : "text-primary"}`}
          strokeWidth={1.5}
        />
      </div>

      <div>
        <h3
          className={`font-serif text-xl leading-tight tracking-tight ${
            muted ? "text-foreground/70" : "text-foreground"
          }`}
        >
          {title}
        </h3>
        <p className="mt-2.5 text-[14px] leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
    </article>
  )
}
