"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts"
import { Check, X } from "lucide-react"

const barData = [
  { store: "Megatone", price: 1249.999, color: "oklch(0.55 0.12 250)", best: true },
  { store: "Cetrogar", price: 1279.0, color: "oklch(0.65 0.14 15)" },
  { store: "Frávega", price: 1289.999, color: "oklch(0.65 0.1 165)" },
  { store: "Castillo", price: 1299.0, color: "#32077E" },
  { store: "OnCity", price: 1319.499, color: "oklch(0.7 0.06 260)" },
]

const tableRows = [
  {
    store: "Megatone",
    title: "BATIDORA DE MANO RAPIMIX AB103 450 W LILIANA",
    price: "$ 1.249.999",
    vsAvg: "−5,3%",
    promo: "18× sin interés de $ 69.444 (Banco Entre Rios)",
    available: true,
    freeShipping: true,
    best: true,
  },
  {
    store: "Cetrogar",
    title: "Samsung Galaxy S24 Ultra 256GB Titanio",
    price: "$ 1.279.000",
    vsAvg: "−3,1%",
    promo: "12× sin interés de $ 106.583 (Visa)",
    available: true,
    freeShipping: true,
  },
  {
    store: "Frávega",
    title: "Samsung Galaxy S24 Ultra 5G 256GB",
    price: "$ 1.289.999",
    vsAvg: "−2,4%",
    promo: "9× sin interés de $ 143.333 (Mercado Pago)",
    available: true,
    freeShipping: false,
  },
  {
    store: "Castillo",
    title: "Galaxy S24 Ultra 256GB Titanium Grey",
    price: "$ 1.299.000",
    vsAvg: "−1,7%",
    promo: "12× sin interés de $ 108.250 (Visa)",
    available: true,
    freeShipping: true,
  },
  {
    store: "OnCity",
    title: "S24 Ultra 256GB Snapdragon",
    price: "$ 1.319.499",
    vsAvg: "+0,1%",
    promo: "6× sin interés de $ 219.916",
    available: true,
    freeShipping: false,
  },
]

const marketMetrics = [
  { label: "Tiendas encontradas", value: "5", positive: false },
  { label: "Precio promedio", value: "$ 1.287.499", positive: false },
  { label: "Más bajo vs promedio", value: "−5,3% ($ 37.500)", positive: true },
  { label: "Más alto vs promedio", value: "+0,1% ($ 32.000)", positive: false },
  { label: "Brecha min-max", value: "−5,3% ($ 69.500)", positive: true },
]

export function DashboardPreview() {
  return (
    <section id="producto" className="relative border-t border-border">
      <div className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="flex flex-col items-start justify-between gap-6 lg:flex-row lg:items-end">
          <div>
            <div className="flex items-center gap-3">
              <span className="h-px w-8 bg-primary/60" />
              <span className="label-mono-primary">Inteligencia de producto</span>
            </div>
            <h2 className="mt-6 max-w-2xl font-serif text-[2.25rem] leading-[1.1] tracking-tight text-foreground lg:text-[2.75rem]">
              Una vista de mercado, por modelo
            </h2>
            <span className="mt-3 block h-px w-12 bg-primary" />
          </div>
          <p className="max-w-sm text-[15px] leading-relaxed text-muted-foreground">
            El panel real que ven los usuarios al consultar un producto:
            métricas de mercado, comparación por tienda y un análisis visual
            simple.
          </p>
        </div>

        <div className="mt-12 overflow-hidden rounded-md border border-border bg-card shadow-[0_30px_80px_-50px_#32077E40]">
          {/* Product header */}
          <div className="border-b border-border p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
              <div className="flex h-32 w-32 shrink-0 items-center justify-center rounded-md border border-border bg-background">
                <img
                  src="/products/galaxy-s24-ultra.jpg"
                  alt="Samsung Galaxy S24 Ultra"
                  className="h-full w-full rounded-md object-cover"
                  crossOrigin="anonymous"
                />
              </div>

              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-sm border border-primary/30 bg-primary/5 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-primary">
                    Selección manual
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    Consulta: &quot;galaxy s24 ultra 256gb&quot;
                  </span>
                </div>
                <h3 className="mt-3 max-w-2xl font-serif text-2xl leading-tight tracking-tight text-foreground lg:text-3xl">
                  Samsung Galaxy S24 Ultra 256GB Titanio
                </h3>
                <span className="mt-2 block h-px w-10 bg-primary" />
                <p className="mt-4 max-w-xl text-[14px] leading-relaxed text-muted-foreground">
                  Seguimiento consolidado del precio publicado, stock y cuotas
                  entre los principales retailers para este modelo.
                </p>
              </div>

              <button className="w-full self-start rounded-sm bg-primary px-5 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90 lg:mt-4 lg:w-auto">
                Solicitar análisis de medios de pago
              </button>
            </div>

            {/* Full-width metrics row */}
            <div className="mt-8 overflow-hidden rounded-md border border-border">
              <div className="border-b border-border px-4 py-2.5">
                <span className="label-mono">Métricas de mercado</span>
              </div>
              <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3 lg:grid-cols-5">
                {marketMetrics.map((m) => (
                  <div key={m.label} className="bg-card px-4 py-3">
                    <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      {m.label}
                    </dt>
                    <dd
                      className={`mt-2 font-mono text-[13px] tabular-nums ${
                        m.positive ? "text-success" : "text-foreground"
                      }`}
                    >
                      {m.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>

          {/* Quick stat cards */}
          <div className="grid grid-cols-2 gap-px border-b border-border bg-border lg:grid-cols-4">
            {[
              { k: "Mejor precio", v: "$ 1.249.999", positive: true },
              { k: "Promedio", v: "$ 1.287.499" },
              { k: "Brecha", v: "−5,3% ($ 69.500)", positive: true },
              { k: "Tiendas", v: "5/6" },
            ].map((s) => (
              <div key={s.k} className="bg-card p-6">
                <span className="label-mono">{s.k}</span>
                <p
                  className={`mt-3 font-serif text-2xl tracking-tight tabular-nums ${
                    s.positive ? "text-success" : "text-foreground"
                  }`}
                >
                  {s.v}
                </p>
              </div>
            ))}
          </div>

          {/* Comparison table */}
          <div className="border-b border-border p-6 lg:p-8">
            <div className="flex items-center justify-between">
              <div>
                <span className="label-mono-primary">Datos comparativos</span>
                <h3 className="mt-2 font-serif text-xl leading-tight tracking-tight text-foreground">
                  Comparación por tienda
                </h3>
              </div>
              <span className="label-mono">5 con resultados · 6 consultadas</span>
            </div>

            <div className="mt-6 overflow-x-auto rounded-md border border-border">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-background">
                    {[
                      "Tienda",
                      "Producto seleccionado",
                      "Precio",
                      "Vs prom.",
                      "Mejor promo",
                      "Disp.",
                      "Envío",
                    ].map((h, i) => (
                      <th
                        key={h}
                        className={`label-mono px-4 py-3 font-normal ${
                          i === 2 || i === 3 ? "text-right" : ""
                        } ${i >= 5 ? "text-center" : ""}`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((r) => (
                    <tr key={r.store} className="border-b border-border last:border-0">
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-success" />
                          <span className="text-[13px] text-foreground">
                            {r.store}
                          </span>
                        </div>
                      </td>
                      <td className="max-w-[18rem] px-4 py-3.5 text-[12px] text-muted-foreground">
                        {r.title}
                      </td>
                      <td className="px-4 py-3.5 text-right font-mono text-[12px] tabular-nums text-foreground">
                        <div className="inline-flex items-center gap-2">
                          {r.price}
                          {r.best ? (
                            <span className="rounded-sm bg-success/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-success">
                              Mejor
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td
                        className={`px-4 py-3.5 text-right font-mono text-[12px] tabular-nums ${
                          r.vsAvg.startsWith("−")
                            ? "text-success"
                            : "text-muted-foreground"
                        }`}
                      >
                        {r.vsAvg}
                      </td>
                      <td className="max-w-[18rem] px-4 py-3.5 text-[12px] text-muted-foreground">
                        {r.promo}
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        {r.available ? (
                          <Check className="mx-auto h-3.5 w-3.5 text-success" strokeWidth={2} />
                        ) : (
                          <X className="mx-auto h-3.5 w-3.5 text-destructive" strokeWidth={2} />
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-center">
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
          </div>

          {/* Visual analysis */}
          <div className="grid grid-cols-1 gap-px bg-border lg:grid-cols-2">
            <div className="bg-card p-6 lg:p-8">
              <span className="label-mono-primary">Distribución</span>
              <h3 className="mt-2 font-serif text-xl leading-tight tracking-tight text-foreground">
                Precio por tienda
              </h3>

              <div className="mt-6 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={barData}
                    margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid
                      stroke="oklch(0.92 0.005 270)"
                      strokeDasharray="2 4"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="store"
                      stroke="oklch(0.52 0.02 260)"
                      tickLine={false}
                      axisLine={false}
                      fontSize={10}
                      tickMargin={8}
                    />
                    <YAxis
                      stroke="oklch(0.52 0.02 260)"
                      tickLine={false}
                      axisLine={false}
                      fontSize={10}
                      width={42}
                      tickFormatter={(v) => `${v.toFixed(1)}M`}
                      domain={[1.2, 1.35]}
                    />
                    <Bar dataKey="price" radius={[4, 4, 0, 0]}>
                      {barData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Historial — próximamente */}
            <div className="relative overflow-hidden bg-card p-6 lg:p-8">
              <div className="flex items-center justify-between">
                <div>
                  <span className="label-mono">Historial · 7 meses</span>
                  <h3 className="mt-2 font-serif text-xl leading-tight tracking-tight text-foreground">
                    Evolución de precios
                  </h3>
                </div>
                <span className="rounded-sm border border-primary/30 bg-primary/5 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-primary">
                  Próximamente
                </span>
              </div>

              <div className="relative mt-6 h-64 overflow-hidden rounded-md border border-border">
                {/* Mock blurred chart preview */}
                <svg
                  className="absolute inset-0 h-full w-full opacity-30 blur-[6px]"
                  viewBox="0 0 320 200"
                  preserveAspectRatio="none"
                  aria-hidden
                >
                  <path
                    d="M0,140 C40,120 60,150 90,130 C120,110 140,140 170,115 C200,90 220,120 250,95 C280,75 300,95 320,80 L320,200 L0,200 Z"
                    fill="#32077E40"
                  />
                  <path
                    d="M0,140 C40,120 60,150 90,130 C120,110 140,140 170,115 C200,90 220,120 250,95 C280,75 300,95 320,80"
                    stroke="#32077E"
                    strokeWidth="1.5"
                    fill="none"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center bg-card/60">
                  <div className="rounded-md border border-border bg-card px-4 py-3 text-center">
                    <p className="label-mono">No disponible</p>
                    <p className="mt-1 font-serif text-base tracking-tight text-foreground">
                      Seguimiento de precios
                    </p>
                    <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-primary">
                      Próximamente
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-4">
            <span className="label-mono">Sync · datos consultados al solicitar la búsqueda</span>
            <span className="label-mono-primary">v1.0.0 · 6 tiendas indexadas</span>
          </div>
        </div>
      </div>
    </section>
  )
}
