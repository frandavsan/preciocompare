const localFeatures = [
  {
    title: "Precios en ARS",
    description:
      "Trabajamos nativamente en pesos argentinos. Los valores que ves son los publicados por cada tienda, sin conversiones intermedias.",
  },
  {
    title: "Cuotas sin interés",
    description:
      "Mostramos los planes de cuotas sin interés cuando la tienda los expone, para que compares precio efectivo y no solo el sticker.",
  },
  {
    title: "Mercado Pago y bancos",
    description:
      "Capturamos promociones de Mercado Pago y planes bancarios cuando están disponibles en la página del producto.",
  },
  {
    title: "CABA y código postal",
    description:
      "Simulamos disponibilidad y envío para CABA o el código postal que indiques, cuando la tienda permite consultarlo.",
  },
]

const stores = [
  "Castillo",
  "Cetrogar",
  "Frávega",
  "Megatone",
  "Montes Hermanos",
  "OnCity",
]

export function Argentina() {
  return (
    <section id="clientes" className="relative">
      <div className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="grid gap-12 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <div className="flex items-center gap-3">
              <span className="h-px w-8 bg-primary/60" />
              <span className="label-mono-primary">Enfoque local</span>
            </div>

            <h2 className="mt-6 font-serif text-[2.25rem] leading-[1.1] tracking-tight text-foreground lg:text-[2.75rem]">
              Construido para tiendas{" "}
              <span className="text-primary">argentinas</span> de electrónica
            </h2>
            <span className="mt-3 block h-px w-12 bg-primary" />

            <p className="mt-6 max-w-md text-[15px] leading-relaxed text-muted-foreground">
              Compará precios reales entre tiendas argentinas. Buscá un modelo
              y revisá cómo aparece en cada competidor: precio, stock, cuotas
              y envío, todo en una sola pantalla.
            </p>

            <div className="mt-10 rounded-md border border-border bg-card p-6">
              <div className="flex items-center justify-between">
                <span className="label-mono">Tiendas indexadas</span>
                <span className="font-mono text-[11px] tabular-nums text-primary">
                  6
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {stores.map((s) => (
                  <span
                    key={s}
                    className="rounded-sm border border-border bg-background px-3 py-1 text-[12px] text-foreground/80"
                  >
                    {s}
                  </span>
                ))}
              </div>
              <p className="mt-4 text-[12px] leading-relaxed text-muted-foreground">
                Cobertura ampliable a pedido para retailers seleccionados.
              </p>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="grid grid-cols-1 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-2">
              {localFeatures.map((f, i) => (
                <article
                  key={f.title}
                  className="flex flex-col gap-3 bg-card p-7"
                >
                  <span className="label-mono">
                    {String(i + 1).padStart(2, "0")} · Local
                  </span>
                  <h3 className="font-serif text-lg leading-tight tracking-tight text-foreground">
                    {f.title}
                  </h3>
                  <p className="text-[14px] leading-relaxed text-muted-foreground">
                    {f.description}
                  </p>
                </article>
              ))}
            </div>

            <div className="mt-px grid grid-cols-2 gap-px overflow-hidden rounded-b-md border border-t-0 border-border bg-border md:grid-cols-3">
              {[
                { k: "Mercado", v: "Electrónica · Electro." },
                { k: "Moneda", v: "ARS" },
                { k: "Cobertura", v: "CABA · CP nacional" },
              ].map((t) => (
                <div key={t.k} className="bg-card p-5">
                  <span className="label-mono">{t.k}</span>
                  <p className="mt-2 font-serif text-base leading-tight tracking-tight text-foreground">
                    {t.v}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
