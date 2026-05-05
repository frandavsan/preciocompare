import { Check, X } from "lucide-react"

type Row = {
  store: string
  price: string
  cuotas: string
  available: boolean
  freeShipping: boolean
  highlight?: boolean
}

const rows: Row[] = [
  { store: "Megatone", price: "$ 1.249.999", cuotas: "18× sin interés", available: true, freeShipping: true, highlight: true },
  { store: "Cetrogar", price: "$ 1.279.000", cuotas: "12× sin interés", available: true, freeShipping: true },
  { store: "Frávega", price: "$ 1.289.999", cuotas: "9× sin interés", available: true, freeShipping: false },
  { store: "Castillo", price: "$ 1.299.000", cuotas: "12× sin interés", available: true, freeShipping: true },
  { store: "OnCity", price: "$ 1.319.499", cuotas: "6× sin interés", available: true, freeShipping: false },
  { store: "Montes Hermanos", price: "—", cuotas: "—", available: false, freeShipping: false },
]

const metrics = [
  { label: "Mejor precio", value: "$ 1.249.999", positive: true },
  { label: "Promedio", value: "$ 1.287.499" },
  { label: "Brecha", value: "−5,3%", positive: true },
  { label: "Tiendas", value: "5/6" },
]

export function HeroDashboardPreview() {
  return (
    <div className="relative">
      <div className="rounded-md border border-border bg-card shadow-[0_30px_80px_-50px_#32077E40]">
        {/* Header — product summary */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <span className="label-mono-primary">Inteligencia de producto</span>
          <span className="label-mono">Sync · datos consultados</span>
        </div>

        <div className="flex flex-col gap-5 border-b border-border px-6 py-6 sm:flex-row sm:items-center">
          {/* Product image card */}
          <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-md border border-border bg-background">
            <img
              src="/products/galaxy-s24-ultra.jpg"
              alt="Samsung Galaxy S24 Ultra 256GB"
              className="h-full w-full rounded-md object-cover"
              crossOrigin="anonymous"
            />
          </div>

          <div className="flex-1">
            <p className="label-mono">Consulta · &quot;galaxy s24 ultra&quot;</p>
            <h3 className="mt-1.5 font-serif text-xl leading-tight tracking-tight text-foreground">
              Samsung Galaxy S24 Ultra 256GB
            </h3>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="rounded-sm border border-primary/30 bg-primary/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-primary">
                CABA
              </span>
              <span className="rounded-sm border border-border bg-background px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                6 tiendas indexadas
              </span>
            </div>
          </div>
        </div>

        {/* Metric strip */}
        <div className="grid grid-cols-2 gap-px border-b border-border bg-border lg:grid-cols-4">
          {metrics.map((m) => (
            <div key={m.label} className="bg-card p-4">
              <span className="label-mono">{m.label}</span>
              <p
                className={`mt-2 font-serif text-lg tracking-tight tabular-nums ${
                  m.positive ? "text-success" : "text-foreground"
                }`}
              >
                {m.value}
              </p>
            </div>
          ))}
        </div>

        {/* Comparison table */}
        <div className="overflow-x-auto px-2">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left">
                {["Tienda", "Precio", "Cuotas", "Disp.", "Envío"].map((h, i) => (
                  <th
                    key={h}
                    className={`label-mono px-4 py-3 font-normal ${
                      i === 1 || i === 2 ? "text-right" : ""
                    } ${i >= 3 ? "text-center" : ""}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.store}
                  className={`border-t border-border/70 ${
                    r.highlight ? "bg-accent/40" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          r.available ? "bg-success" : "bg-destructive/60"
                        }`}
                      />
                      <span className="text-[13px] text-foreground">
                        {r.store}
                      </span>
                      {r.highlight ? (
                        <span className="rounded-sm bg-success/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-success">
                          Mejor
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-[12px] tabular-nums text-foreground">
                    {r.price}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                    {r.cuotas}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {r.available ? (
                      <Check className="mx-auto h-3.5 w-3.5 text-success" strokeWidth={2} />
                    ) : (
                      <X className="mx-auto h-3.5 w-3.5 text-destructive" strokeWidth={2} />
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {r.freeShipping ? (
                      <Check className="mx-auto h-3.5 w-3.5 text-success" strokeWidth={2} />
                    ) : (
                      <X className="mx-auto h-3.5 w-3.5 text-destructive/70" strokeWidth={2} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-3.5">
          <span className="label-mono">v1.0.0 · data.live · 6 tiendas indexadas</span>
          <span className="label-mono-primary">Acceso privado</span>
        </div>
      </div>
    </div>
  )
}
