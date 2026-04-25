import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, Check, X } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { BarChart, Bar, Cell } from "recharts";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { products, stores, formatPrice } from "@/data/mockData";
import type { Product, StorePrice } from "@/data/mockData";
import TopNav from "@/components/TopNav";

type SelectedComparisonPrice = StorePrice & {
  productName: string;
};

function findProduct(query: string): Product {
  const q = query.toLowerCase();
  const match = products.find(
    (p) => p.name.toLowerCase().includes(q) || q.includes(p.name.toLowerCase().split(" ")[0])
  );
  return match || products[0];
}

function getBestPromo(store: string, price: number): string {
  const installmentOptions: Record<string, number> = {
    "Mercado Libre": 12,
    Fravega: 9,
    Garbarino: 6,
    Musimundo: 12,
    Megatone: 18,
  };

  const installments = installmentOptions[store] || 6;
  const installmentPrice = formatPrice(Math.round(price / installments)).replace(/\$\s+/u, "$");
  return `${installments}x sin interes de ${installmentPrice}`;
}

function getPromoInstallments(store: string): number {
  const installmentOptions: Record<string, number> = {
    "Mercado Libre": 12,
    Fravega: 9,
    Garbarino: 6,
    Musimundo: 12,
    Megatone: 18,
  };

  return installmentOptions[store] || 6;
}

function parseSelectedComparisons(value: string | null): SelectedComparisonPrice[] {
  if (!value) return [];

  try {
    const parsed = JSON.parse(value) as Array<{ store?: unknown; name?: unknown; price?: unknown }>;
    if (!Array.isArray(parsed)) return [];

    return parsed
      .filter(
        (item) =>
          typeof item.store === "string" &&
          typeof item.name === "string" &&
          typeof item.price === "number" &&
          Number.isFinite(item.price)
      )
      .map((item, index) => ({
        store: item.store as string,
        productName: item.name as string,
        price: item.price as number,
        currency: "ARS",
        url: "#",
        inStock: true,
        freeShipping: index % 2 === 0,
      }));
  } catch {
    return [];
  }
}

const ProductIntelligence = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const fromCABA = searchParams.get("caba") === "1";
  const postalCode = searchParams.get("postal_code") ?? "";
  const selectedComparisonPrices = useMemo(
    () => parseSelectedComparisons(searchParams.get("selected")),
    [searchParams]
  );
  const isSelectiveComparison = selectedComparisonPrices.length > 0;
  const [priceOrder, setPriceOrder] = useState<"asc" | "desc" | "promo">("asc");
  const [isPaymentAnalysisLoading, setIsPaymentAnalysisLoading] = useState(false);
  const [paymentAnalysisProgress, setPaymentAnalysisProgress] = useState(0);
  const paymentAnalysisTimeoutRef = useRef<number | null>(null);
  const paymentAnalysisIntervalRef = useRef<number | null>(null);
  const paymentAnalysisFinishRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (paymentAnalysisTimeoutRef.current !== null) {
        window.clearTimeout(paymentAnalysisTimeoutRef.current);
      }
      if (paymentAnalysisIntervalRef.current !== null) {
        window.clearInterval(paymentAnalysisIntervalRef.current);
      }
      if (paymentAnalysisFinishRef.current !== null) {
        window.clearTimeout(paymentAnalysisFinishRef.current);
      }
    };
  }, []);

  const product = useMemo(() => findProduct(query), [query]);
  const comparisonPrices = useMemo(
    () => (isSelectiveComparison ? selectedComparisonPrices : product.prices),
    [isSelectiveComparison, product.prices, selectedComparisonPrices]
  );
  const displayProductName = isSelectiveComparison ? query || "Productos seleccionados" : product.name;
  const displayCategory = isSelectiveComparison ? "Seleccion manual" : product.category;

  const cheapestFirstPrices = useMemo(
    () => [...comparisonPrices].sort((a, b) => a.price - b.price),
    [comparisonPrices]
  );

  const sortedPrices = useMemo(
    () => {
      if (priceOrder === "asc") return cheapestFirstPrices;
      if (priceOrder === "desc") return [...cheapestFirstPrices].reverse();

      return [...cheapestFirstPrices].sort((a, b) => {
        const promoDiff = getPromoInstallments(b.store) - getPromoInstallments(a.store);
        if (promoDiff !== 0) return promoDiff;
        return a.price - b.price;
      });
    },
    [cheapestFirstPrices, priceOrder]
  );

  const minPrice = cheapestFirstPrices[0]?.price || 0;
  const maxPrice = cheapestFirstPrices[cheapestFirstPrices.length - 1]?.price || 0;
  const avgPrice = Math.round(
    comparisonPrices.reduce((a, b) => a + b.price, 0) / comparisonPrices.length
  );
  const storesFound = comparisonPrices.length;

  const cheapVsAvg = (((minPrice - avgPrice) / avgPrice) * 100).toFixed(1);
  const expVsAvg = (((maxPrice - avgPrice) / avgPrice) * 100).toFixed(1);
  const minVsMax = (((minPrice - maxPrice) / maxPrice) * 100).toFixed(1);
  const avgToCheapestGap = `- ${(((avgPrice - minPrice) / avgPrice) * 100).toFixed(1)}%`;

  const dates = [...new Set(product.priceHistory.map((p) => p.date))];
  const lineData = dates.map((date) => {
    const entry: Record<string, string | number> = { date };
    product.priceHistory
      .filter((p) => p.date === date)
      .forEach((p) => {
        entry[p.store] = p.price;
      });
    return entry;
  });
  const storesInHistory = [...new Set(product.priceHistory.map((p) => p.store))];

  const barData = cheapestFirstPrices.map((sp) => ({
    store: sp.store.split(" ").slice(0, 2).join(" "),
    price: sp.price,
    fill: stores.find((s) => s.name === sp.store)?.color || "hsl(262, 52%, 47%)",
    isBest: sp.price === minPrice,
  }));

  const metrics = [
    { label: "Tiendas encontradas", value: storesFound.toString() },
    { label: "Precio promedio", value: formatPrice(avgPrice) },
    {
      label: "Mas bajo vs promedio",
      value: `- ${Math.abs(Number(cheapVsAvg)).toFixed(1)}%`,
      detail: `(${formatPrice(avgPrice - minPrice)})`,
      accent: true,
    },
    {
      label: "Mas alto vs promedio",
      value: `+ ${Math.abs(Number(expVsAvg)).toFixed(1)}%`,
      detail: `(${formatPrice(maxPrice - avgPrice)})`,
    },
    {
      label: "Brecha min-max",
      value: `- ${Math.abs(Number(minVsMax)).toFixed(1)}%`,
      detail: `(${formatPrice(maxPrice - minPrice)})`,
      accent: true,
    },
  ];

  const handlePaymentAnalysisRequest = () => {
    if (isPaymentAnalysisLoading) return;

    if (paymentAnalysisTimeoutRef.current !== null) {
      window.clearTimeout(paymentAnalysisTimeoutRef.current);
    }
    if (paymentAnalysisIntervalRef.current !== null) {
      window.clearInterval(paymentAnalysisIntervalRef.current);
    }
    if (paymentAnalysisFinishRef.current !== null) {
      window.clearTimeout(paymentAnalysisFinishRef.current);
    }

    setIsPaymentAnalysisLoading(true);
    setPaymentAnalysisProgress(0);

    const loadingMs = Math.floor(Math.random() * 3000) + 2000;
    const startedAt = Date.now();

    paymentAnalysisIntervalRef.current = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const ratio = Math.min(elapsed / loadingMs, 1);

      setPaymentAnalysisProgress((prev) => {
        const baseTarget = Math.floor(ratio * 100);
        const jumpSize = Math.floor(Math.random() * 9) + 3;
        const randomLead = Math.floor(Math.random() * 7);
        return Math.min(99, Math.max(prev, baseTarget + randomLead, prev + jumpSize));
      });
    }, 150);

    paymentAnalysisTimeoutRef.current = window.setTimeout(() => {
      if (paymentAnalysisIntervalRef.current !== null) {
        window.clearInterval(paymentAnalysisIntervalRef.current);
        paymentAnalysisIntervalRef.current = null;
      }

      setPaymentAnalysisProgress(100);
      paymentAnalysisFinishRef.current = window.setTimeout(() => {
        setIsPaymentAnalysisLoading(false);
        setPaymentAnalysisProgress(0);
        paymentAnalysisFinishRef.current = null;
      }, 500);
    }, loadingMs);
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-background paper-texture isolate">
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -left-[11rem] -top-[8rem] h-[24rem] w-[26rem] rounded-[42%_58%_62%_38%/56%_34%_66%_44%] bg-[radial-gradient(circle_at_65%_40%,hsl(278_70%_86%_/_0.5),hsl(258_55%_78%_/_0.24)_58%,transparent_72%)] blur-[6px]" />
        <div className="absolute left-[7rem] top-[4.5rem] h-[8rem] w-[8rem] rotate-12 rounded-[38%_62%_60%_40%/45%_42%_58%_55%] bg-[linear-gradient(135deg,hsl(278_72%_86%_/_0.42),hsl(252_56%_81%_/_0.14))]" />
        <div className="absolute -right-[6rem] -top-[2.5rem] h-[20rem] w-[24rem] rounded-[40%_60%_38%_62%/52%_42%_58%_48%] bg-[radial-gradient(circle_at_35%_45%,hsl(189_75%_82%_/_0.52),hsl(251_58%_84%_/_0.24)_58%,transparent_76%)]" />
        <div className="absolute -right-[7rem] bottom-[2rem] h-[22rem] w-[25rem] rounded-[46%_54%_36%_64%/41%_48%_52%_59%] bg-[radial-gradient(circle_at_32%_38%,hsl(179_54%_78%_/_0.54),hsl(193_56%_74%_/_0.2)_54%,transparent_76%)]" />
      </div>

      <TopNav activeSection="market-data" />

      <main className="relative z-10 max-w-[1560px] mx-auto px-3 lg:px-4 py-8">
        <div className="mb-5 flex items-center justify-between gap-4 px-1">
          <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-3.5 w-3.5" />
            <span className="font-mono text-[11px] tracking-wide">Volver</span>
          </Link>
          <div className="flex items-center gap-3">
            {fromCABA && (
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary border border-primary px-2 py-0.5 rounded-sm">
                CABA
              </span>
            )}
            {!fromCABA && postalCode && (
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-primary border border-primary px-2 py-0.5 rounded-sm">
                CP {postalCode}
              </span>
            )}
            <span className="font-mono text-[10px] text-muted-foreground tracking-wider hidden sm:block">
              SYNC: 30 MAR 2026
            </span>
          </div>
        </div>
        <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,2.35fr)_360px] xl:grid-rows-[auto_auto] gap-8 xl:gap-x-10 xl:gap-y-6 mb-6 items-start">
          <div className="relative py-4 lg:py-6 xl:col-start-1 xl:row-start-1">
            <div className="relative">
              <div className="section-eyebrow mb-4">Inteligencia de producto</div>
              <div className="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)] gap-8 xl:gap-12 items-start">
                <div className="relative mx-0 w-full max-w-[320px] aspect-square flex items-center justify-center">
                  <div className="absolute inset-1 rounded-[2.35rem] bg-card/90 soft-elevation" />
                  <div className="absolute inset-0 rounded-[2.5rem] border border-border/60 bg-gradient-to-br from-card/90 via-card/55 to-primary/5" />
                  <img
                    src={product.imageUrl}
                    alt={displayProductName}
                    className="relative h-full w-full rounded-[2.25rem] object-contain p-6 drop-shadow-[0_18px_24px_hsl(220_20%_14%_/_0.15)]"
                    loading="eager"
                  />
                </div>
                <div className="min-w-0 pt-3">
                  <div className="flex items-center gap-3 flex-wrap mb-5">
                    <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground border border-border px-2 py-0.5 rounded-sm bg-card/60">
                      {displayCategory}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground tracking-wide">
                      Consulta: "{query}"
                    </span>
                  </div>
                  <h1 className="text-4xl sm:text-[3.6rem] lg:text-[3.9rem] xl:text-[4.2rem] font-bold text-foreground leading-[0.95] tracking-tight max-w-[14ch] xl:max-w-[15ch] mb-4 text-left">
                    {displayProductName}
                  </h1>
                  <div className="primary-rule mb-5" />
                  <p className="text-sm lg:text-[15px] text-muted-foreground leading-[1.8] max-w-[42rem] mb-6">
                    Seguimiento consolidado del precio publicado, stock y variacion entre los principales retailers para este modelo.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 max-w-[64rem] xl:col-start-1 xl:row-start-2">
            <div className="structured-card soft-elevation p-4 bg-card/85 min-w-0 transform-gpu transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.025] hover:bg-card">
              <span className="font-mono block mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-medium">Mejor precio</span>
              <span className="block font-mono text-base lg:text-[1.05rem] font-semibold text-secondary leading-tight truncate">
                {formatPrice(minPrice)}
              </span>
            </div>
            <div className="structured-card soft-elevation p-4 bg-card/85 min-w-0 transform-gpu transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.025] hover:bg-card">
              <span className="font-mono block mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-medium">Promedio</span>
              <span className="block font-mono text-base lg:text-[1.05rem] font-semibold text-foreground leading-tight truncate">
                {formatPrice(avgPrice)}
              </span>
            </div>
            <div className="structured-card soft-elevation p-4 bg-card/85 min-w-0 transform-gpu transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.025] hover:bg-card">
              <span className="font-mono block mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-medium">Brecha</span>
              <div className="flex items-baseline gap-2 overflow-hidden">
                <span className="block font-mono text-base lg:text-[1.05rem] font-semibold text-foreground leading-tight shrink-0">
                  {avgToCheapestGap}
                </span>
                <span className="block font-mono text-[0.8rem] lg:text-[0.85rem] text-muted-foreground leading-tight truncate">
                  ({formatPrice(avgPrice - minPrice)})
                </span>
              </div>
            </div>
            <div className="structured-card soft-elevation p-4 bg-card/85 min-w-0 transform-gpu transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.025] hover:bg-card">
              <span className="font-mono block mb-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-medium">Tiendas</span>
              <span className="block font-mono text-base lg:text-[1.05rem] font-semibold text-foreground leading-tight">
                {storesFound}
              </span>
            </div>
          </div>

          <aside className="xl:col-start-2 xl:row-[1/3] xl:self-end">
            <div className="mb-3 flex items-center gap-3">
              <button
                type="button"
                onClick={handlePaymentAnalysisRequest}
                disabled={isPaymentAnalysisLoading}
                className="inline-flex items-center rounded-[0.55rem] bg-[hsl(262_90%_30%)] px-3.5 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(40_30%_99%)] transition-colors hover:bg-[hsl(262_90%_26%)] disabled:cursor-wait disabled:opacity-75"
              >
                Solicitar analisis de medios de pago
              </button>
              {isPaymentAnalysisLoading && (
                <div className="inline-flex items-center gap-2 text-muted-foreground">
                  <span className="h-4 w-4 animate-spin rounded-full border-[1.5px] border-border border-t-primary" />
                  <span className="font-mono text-[11px] tracking-[0.08em] tabular-nums">
                    {paymentAnalysisProgress}%
                  </span>
                </div>
              )}
            </div>
            <section className="structured-card soft-elevation p-5 transform-gpu transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.025] hover:bg-card">
              <div className="section-eyebrow mb-4">Metricas de mercado</div>
              <div className="space-y-3">
                {metrics.map((m) => (
                  <div key={m.label} className="flex items-start justify-between gap-4 border-b border-border/80 pb-3 last:border-b-0 last:pb-0">
                    <span className="editorial-label">{m.label}</span>
                    <div className="text-right pt-[1px]">
                      <span className={`block font-mono text-base font-semibold leading-none ${m.accent ? "text-secondary" : "text-foreground"}`}>
                        {m.value}
                      </span>
                      {m.detail && (
                        <span className="mt-1 block font-mono text-[0.75rem] text-muted-foreground leading-tight">
                          {m.detail}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </section>

        <section className="mb-8">
          <div className="section-eyebrow mb-1.5">Datos comparativos</div>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
            <div className="flex items-baseline gap-3 flex-wrap">
              <h2 className="text-xl font-bold text-foreground">Comparacion por tienda</h2>
              <span className="font-mono text-xs text-muted-foreground">- {storesFound} tiendas</span>
            </div>
            <div className="flex items-center gap-3 self-start sm:self-auto">
              <span className="editorial-label whitespace-nowrap">Ordenar</span>
              <Select value={priceOrder} onValueChange={(value: "asc" | "desc" | "promo") => setPriceOrder(value)}>
                <SelectTrigger className="h-9 w-[220px] border-border bg-card font-mono text-xs tracking-wide focus:ring-primary/20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="asc">Mas barato primero</SelectItem>
                  <SelectItem value="desc">Mas caro primero</SelectItem>
                  <SelectItem value="promo">Mejor promo</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="structured-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">Tienda</TableHead>
                  {isSelectiveComparison && (
                    <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">Producto seleccionado</TableHead>
                  )}
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">Precio</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">vs Promedio</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">vs Mas caro</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">Mejor promo</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium text-center">Disponible</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium text-center">Envio gratis?</TableHead>
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium text-right">Link</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedPrices.map((sp) => {
                  const diff = (((sp.price - avgPrice) / avgPrice) * 100).toFixed(1);
                  const diffVsMax = (((sp.price - maxPrice) / maxPrice) * 100).toFixed(1);
                  return (
                    <TableRow key={`${sp.store}-${"productName" in sp ? sp.productName : sp.price}`} className={`border-border hover:bg-accent/40 ${sp.price === minPrice ? "bg-accent/30" : ""}`}>
                      <TableCell className="text-sm font-medium">{sp.store}</TableCell>
                      {isSelectiveComparison && (
                        <TableCell className="max-w-[280px] text-sm text-foreground">
                          <span className="line-clamp-2">{"productName" in sp ? sp.productName : displayProductName}</span>
                        </TableCell>
                      )}
                      <TableCell>
                        <span className={`font-mono text-sm font-semibold ${sp.price === minPrice ? "text-secondary" : "text-foreground"}`}>
                          {formatPrice(sp.price)}
                        </span>
                        {sp.price === minPrice && (
                          <span className="ml-2 font-mono text-[9px] uppercase tracking-wider text-secondary border border-secondary px-1.5 py-0.5 rounded-sm font-medium">
                            Mejor
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className={`font-mono text-xs ${Number(diff) <= 0 ? "text-secondary" : "text-muted-foreground"}`}>
                          {Number(diff) > 0 ? "+" : ""}
                          {diff}%
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className={`font-mono text-xs ${Number(diffVsMax) <= 0 ? "text-secondary" : "text-muted-foreground"}`}>
                          {Number(diffVsMax) > 0 ? "+" : ""}
                          {diffVsMax}%
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-xs text-muted-foreground">
                          {getBestPromo(sp.store, sp.price)}
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        {sp.inStock ? (
                          <Check className="h-3.5 w-3.5 text-secondary mx-auto" />
                        ) : (
                          <X className="h-3.5 w-3.5 text-destructive mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {sp.freeShipping ? (
                          <Check className="h-3.5 w-3.5 text-secondary mx-auto" />
                        ) : (
                          <X className="h-3.5 w-3.5 text-destructive mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <a href={sp.url} className="text-primary hover:text-primary/70 transition-colors">
                          <ExternalLink className="h-3.5 w-3.5 inline" />
                        </a>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </section>

        <section className="mb-8">
          <div className="section-eyebrow mb-4">Analisis visual</div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="structured-card overflow-hidden">
              <div className="p-5 pb-0">
                <div className="module-header">
                  <span className="section-eyebrow block mb-1.5">Distribucion</span>
                  <h3 className="text-base font-bold text-foreground">Precio por tienda</h3>
                </div>
              </div>
              <div className="px-5 pb-5">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={barData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 12%, 90%)" />
                    <XAxis
                      dataKey="store"
                      tick={{ fill: "hsl(220, 10%, 46%)", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}
                      axisLine={{ stroke: "hsl(220, 12%, 82%)" }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: "hsl(220, 10%, 46%)", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}
                      axisLine={{ stroke: "hsl(220, 12%, 82%)" }}
                      tickLine={false}
                      tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(40, 30%, 99%)",
                        border: "2px solid hsl(220, 12%, 82%)",
                        borderRadius: "2px",
                        fontSize: "12px",
                        fontFamily: "'IBM Plex Mono', monospace",
                      }}
                      formatter={(value: number) => [formatPrice(value), "Precio"]}
                    />
                    <Bar dataKey="price" radius={[2, 2, 0, 0]}>
                      {barData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} opacity={entry.isBest ? 1 : 0.6} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="structured-card overflow-hidden">
              <div className="p-5 pb-0">
                <div className="module-header">
                  <span className="section-eyebrow block mb-1.5">Historial · 7 meses</span>
                  <h3 className="text-base font-bold text-foreground">Evolucion de precios</h3>
                </div>
              </div>
              <div className="relative px-5 pb-5">
                <div className="pointer-events-none select-none opacity-35 blur-[1.2px] grayscale">
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={lineData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 12%, 90%)" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: "hsl(220, 10%, 46%)", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}
                        axisLine={{ stroke: "hsl(220, 12%, 82%)" }}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: "hsl(220, 10%, 46%)", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}
                        axisLine={{ stroke: "hsl(220, 12%, 82%)" }}
                        tickLine={false}
                        tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
                      />
                      <Legend wrapperStyle={{ fontSize: "11px", fontFamily: "'IBM Plex Mono', monospace" }} />
                      {storesInHistory.map((storeName) => {
                        const storeData = stores.find((s) => s.name === storeName);
                        return (
                          <Line
                            key={storeName}
                            type="monotone"
                            dataKey={storeName}
                            stroke={storeData?.color || "hsl(262, 52%, 47%)"}
                            strokeWidth={1.5}
                            dot={false}
                            activeDot={{ r: 3, strokeWidth: 1 }}
                          />
                        );
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="absolute inset-x-5 bottom-5 top-0 flex items-center justify-center rounded-sm bg-card/55 backdrop-blur-[1px]">
                  <div className="border border-border/40 bg-card/85 px-5 py-3 text-center shadow-[0_18px_36px_hsl(220_20%_14%_/_0.06)]">
                    <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-primary">
                      No disponible
                    </span>
                    <span className="mt-1 block font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">
                      Proximamente
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

export default ProductIntelligence;
