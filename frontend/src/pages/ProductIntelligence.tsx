import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, Check, X } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { BarChart, Bar, Cell } from "recharts";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import TopNav from "@/components/TopNav";
import { useSearch } from "@/hooks/useSearch";
import {
  applySelection,
  autoSelectProducts,
  bestSinInteresCount,
  formatBestPromo,
  formatPrice,
  resolveImageUrl,
} from "@/lib/transforms";
import { getStoreColor, getStoreDisplayName } from "@/lib/stores";
import { ApiError, classifyError, downloadPricingExcel, type StoreStatus } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type SelectedSlot = { store: string; url: string };

interface ComparisonRow {
  storeKey: string;
  displayName: string;
  productName: string;
  price: number;
  url: string;
  available: boolean;
  freeShipping: boolean;
  bestPromo: string | null;
  bestPromoCount: number;
}

function parseSelectedSlots(value: string | null): SelectedSlot[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as Array<{ store?: unknown; url?: unknown }>;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => typeof item.store === "string" && typeof item.url === "string")
      .map((item) => ({ store: item.store as string, url: item.url as string }));
  } catch {
    return [];
  }
}

const formatDecimal = (value: number, digits = 1) =>
  new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);

// Inline label for the pricing-excel button. classifyError handles the generic
// transport cases; we override only the kinds where the user benefits from
// pricing-specific wording (404 = no matches in pricing stores; 503 = the
// generation pipeline failed) and tag 429 with its status code per the spec.
const messageForExcelError = (err: unknown): string => {
  if (err instanceof ApiError) {
    if (err.status === 404) return "Sin coincidencias en las tiendas.";
    if (err.status === 429) return "Demasiadas solicitudes (429). Esperá un momento.";
    if (err.status === 401) return "Sesión expirada.";
    if (err.status >= 500) return "No se pudo generar el Excel.";
  }
  const c = classifyError(err);
  if (c.kind === "network") return "Sin conexión.";
  return "No se pudo generar el Excel.";
};

const HISTORY_MONTHS = ["Sep", "Oct", "Nov", "Dic", "Ene", "Feb", "Mar"];
const LAST_RESULTS_PATH_KEY = "preciocompare:last-results-path";

// Hero image fallback order — VTEX CDNs (cetrogar/oncity/castillo) are the most
// reliable, followed by Montes Hermanos (also VTEX), then Fravega (often null),
// then Megatone (Doofinder thumbnails). Stores not listed are appended in the
// order they appear in `perStoreProducts`.
const STORE_IMAGE_PRIORITY = ["cetrogar", "oncity", "castillo", "monteshermanos", "fravega", "megatone"];

type StoreRowState = "ok" | "empty" | "errored";

const StatusDot = ({ state }: { state: StoreRowState }) => {
  const color =
    state === "errored" ? "bg-destructive"
    : state === "empty" ? "bg-muted-foreground/40"
    : "bg-secondary";
  return (
    <span
      className={`inline-block h-1.5 w-1.5 rounded-full ${color}`}
      aria-hidden="true"
    />
  );
};

const PageShell = ({ children }: { children: React.ReactNode }) => (
  <div className="relative min-h-screen overflow-x-hidden bg-background paper-texture isolate">
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
      <div className="absolute -left-[11rem] -top-[8rem] h-[24rem] w-[26rem] rounded-[42%_58%_62%_38%/56%_34%_66%_44%] bg-[radial-gradient(circle_at_65%_40%,hsl(278_70%_86%_/_0.5),hsl(258_55%_78%_/_0.24)_58%,transparent_72%)] blur-[6px]" />
      <div className="absolute left-[7rem] top-[4.5rem] h-[8rem] w-[8rem] rotate-12 rounded-[38%_62%_60%_40%/45%_42%_58%_55%] bg-[linear-gradient(135deg,hsl(278_72%_86%_/_0.42),hsl(252_56%_81%_/_0.14))]" />
      <div className="absolute -right-[6rem] -top-[2.5rem] h-[20rem] w-[24rem] rounded-[40%_60%_38%_62%/52%_42%_58%_48%] bg-[radial-gradient(circle_at_35%_45%,hsl(189_75%_82%_/_0.52),hsl(251_58%_84%_/_0.24)_58%,transparent_76%)]" />
      <div className="absolute -right-[7rem] bottom-[2rem] h-[22rem] w-[25rem] rounded-[46%_54%_36%_64%/41%_48%_52%_59%] bg-[radial-gradient(circle_at_32%_38%,hsl(179_54%_78%_/_0.54),hsl(193_56%_74%_/_0.2)_54%,transparent_76%)]" />
    </div>
    <TopNav activeSection="market-data" />
    {children}
  </div>
);

const StatusPanel = ({
  eyebrow,
  title,
  description,
  spinner = false,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  spinner?: boolean;
}) => (
  <main className="relative z-10 mx-auto flex min-h-[60vh] max-w-[1560px] flex-col items-center justify-center px-3 lg:px-4 py-8">
    <div className="structured-card soft-elevation max-w-md bg-card/90 px-8 py-8 text-center">
      <div className="section-eyebrow mb-3 justify-center">{eyebrow}</div>
      <div className="flex items-center justify-center gap-3">
        {spinner && (
          <span className="h-4 w-4 animate-spin rounded-full border-[1.5px] border-border border-t-primary" />
        )}
        <h2 className="font-mono text-[12px] uppercase tracking-[0.18em] text-foreground">{title}</h2>
      </div>
      {description && (
        <p className="mt-3 font-mono text-[10px] tracking-wide text-muted-foreground">
          {description}
        </p>
      )}
      <Link
        to="/"
        className="mt-6 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-primary hover:text-primary/80"
      >
        <ArrowLeft className="h-3 w-3" />
        Volver
      </Link>
    </div>
  </main>
);

const ProductIntelligence = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const fromCABA = searchParams.get("caba") === "1";
  const postalCode = searchParams.get("postal_code") ?? "";
  // Landing canonicalizes CABA to "1425" before submitting; mirror that here so
  // the React Query key (and the backend cache path) match across the
  // Landing → ProductIntelligence navigation. Otherwise the second page
  // re-runs the full multi-store search.
  const effectivePostal = fromCABA ? "1425" : (postalCode || undefined);

  const selection = useMemo(
    () => parseSelectedSlots(searchParams.get("selected")),
    [searchParams],
  );
  const isSelectiveComparison = selection.length > 0;

  const { data, isLoading, error } = useSearch(query, {
    enabled: !!query,
    postalCode: effectivePostal,
  });

  const { session, signOut, token } = useAuth();
  const commerceName = useMemo(() => {
    const email = session?.user.email?.toLowerCase();
    if (!email) return "Mi comercio";
    return (
      window.localStorage.getItem(`preciocompare:commerce-name:${email}`)?.trim()
      || "Mi comercio"
    );
  }, [session?.user.email]);

  useEffect(() => {
    if (!query) return;
    window.sessionStorage.setItem(
      LAST_RESULTS_PATH_KEY,
      `${window.location.pathname}${window.location.search}`,
    );
  }, [query, searchParams]);

  const handledErrorRef = useRef<unknown>(null);
  useEffect(() => {
    if (!error || error === handledErrorRef.current) return;
    handledErrorRef.current = error;
    const classified = classifyError(error);
    if (classified.kind === "auth") {
      toast.error(classified.title, { description: classified.body });
      void signOut();
    } else if (classified.kind === "rate_limit" || classified.kind === "network") {
      toast.error(classified.title, { description: classified.body });
    }
  }, [error, signOut]);

  const [priceOrder, setPriceOrder] = useState<"asc" | "desc" | "promo">("asc");
  const [isPaymentAnalysisLoading, setIsPaymentAnalysisLoading] = useState(false);
  const [paymentAnalysisError, setPaymentAnalysisError] = useState<string | null>(null);

  const perStoreProducts = useMemo(() => {
    if (!data) return [];
    return isSelectiveComparison ? applySelection(data, selection) : autoSelectProducts(data);
  }, [data, isSelectiveComparison, selection]);

  const comparisonRows: ComparisonRow[] = useMemo(
    () =>
      perStoreProducts
        .filter((s) => s.product.price !== null)
        .map(({ storeKey, displayName, product }) => ({
          storeKey,
          displayName,
          productName: product.name,
          price: product.price as number,
          url: product.url,
          available: product.available,
          freeShipping: product.free_shipping,
          bestPromo: formatBestPromo(product),
          bestPromoCount: bestSinInteresCount(product) ?? 0,
        })),
    [perStoreProducts],
  );

  // Stores the user wanted to compare but that didn't produce a row — either
  // because the fetch failed (errored/timed out) or because the response had
  // no usable products. Surfaced as muted rows + colored chip so coverage
  // gaps are visible rather than silently dropping a column from the user's
  // mental tally.
  type UnavailableRow = {
    storeKey: string;
    displayName: string;
    state: Exclude<StoreRowState, "ok">;
    status: StoreStatus;
  };
  const intendedStoreKeys = useMemo(() => {
    if (!data) return new Set<string>();
    return isSelectiveComparison
      ? new Set(selection.map((s) => s.store))
      : new Set(Object.keys(data.store_status));
  }, [data, isSelectiveComparison, selection]);

  const unavailableStoreRows: UnavailableRow[] = useMemo(() => {
    if (!data) return [];
    const shownKeys = new Set(comparisonRows.map((r) => r.storeKey));
    const out: UnavailableRow[] = [];
    for (const key of intendedStoreKeys) {
      if (shownKeys.has(key)) continue;
      const info = data.store_status[key];
      if (!info) continue;
      out.push({
        storeKey: key,
        displayName: getStoreDisplayName(key),
        state: info.status === "ok" ? "empty" : "errored",
        status: info.status,
      });
    }
    return out;
  }, [data, intendedStoreKeys, comparisonRows]);

  const storeCounts = useMemo(() => {
    const errored = unavailableStoreRows.filter((r) => r.state === "errored").length;
    const empty = unavailableStoreRows.filter((r) => r.state === "empty").length;
    return {
      attempted: intendedStoreKeys.size,
      withResults: comparisonRows.length,
      errored,
      empty,
    };
  }, [intendedStoreKeys, comparisonRows, unavailableStoreRows]);

  const heroImageCandidates = useMemo(() => {
    const byStore = new Map<string, string>();
    for (const { storeKey, product } of perStoreProducts) {
      const resolved = resolveImageUrl(product.image_url);
      if (resolved && !byStore.has(storeKey)) byStore.set(storeKey, resolved);
    }
    const ordered: string[] = [];
    for (const key of STORE_IMAGE_PRIORITY) {
      const url = byStore.get(key);
      if (url) ordered.push(url);
    }
    for (const [key, url] of byStore) {
      if (!STORE_IMAGE_PRIORITY.includes(key)) ordered.push(url);
    }
    return ordered;
  }, [perStoreProducts]);

  const heroCandidatesKey = heroImageCandidates.join("|");
  const [imageIdx, setImageIdx] = useState(0);
  const [imageLoaded, setImageLoaded] = useState(false);

  useEffect(() => {
    setImageIdx(0);
    setImageLoaded(false);
  }, [heroCandidatesKey]);

  const currentHeroImage =
    imageIdx < heroImageCandidates.length ? heroImageCandidates[imageIdx] : null;

  const cheapestFirst = useMemo(
    () => [...comparisonRows].sort((a, b) => a.price - b.price),
    [comparisonRows],
  );

  const sortedRows = useMemo(() => {
    if (priceOrder === "asc") return cheapestFirst;
    if (priceOrder === "desc") return [...cheapestFirst].reverse();
    return [...cheapestFirst].sort((a, b) => {
      const promoDiff = b.bestPromoCount - a.bestPromoCount;
      if (promoDiff !== 0) return promoDiff;
      return a.price - b.price;
    });
  }, [cheapestFirst, priceOrder]);

  const minPrice = cheapestFirst[0]?.price ?? 0;
  const maxPrice = cheapestFirst[cheapestFirst.length - 1]?.price ?? 0;
  const avgPrice = comparisonRows.length
    ? Math.round(comparisonRows.reduce((acc, r) => acc + r.price, 0) / comparisonRows.length)
    : 0;
  const storesFound = comparisonRows.length;

  const cheapVsAvg = avgPrice ? ((minPrice - avgPrice) / avgPrice) * 100 : 0;
  const expVsAvg = avgPrice ? ((maxPrice - avgPrice) / avgPrice) * 100 : 0;
  const minVsMax = maxPrice ? ((minPrice - maxPrice) / maxPrice) * 100 : 0;
  const avgToCheapestGap = avgPrice
    ? `- ${formatDecimal(((avgPrice - minPrice) / avgPrice) * 100)}%`
    : "0,0%";

  const lineData = useMemo(() => {
    return HISTORY_MONTHS.map((date) => {
      const entry: Record<string, string | number> = { date };
      cheapestFirst.forEach((row) => {
        entry[row.displayName] = row.price;
      });
      return entry;
    });
  }, [cheapestFirst]);

  const barData = cheapestFirst.map((row) => ({
    store: row.displayName.split(" ").slice(0, 2).join(" "),
    price: row.price,
    fill: getStoreColor(row.storeKey),
    isBest: row.price === minPrice,
  }));

  // Pick the shortest name from the products actually being compared, but skip
  // it when it barely differs from the query in length (< 5 chars) — that
  // usually means the store echoed the query verbatim and the next-shortest
  // name carries the actual product detail (model code, capacity, etc.).
  const displayProductName = useMemo(() => {
    const names = perStoreProducts
      .map((p) => p.product.name)
      .filter((n): n is string => Boolean(n))
      .sort((a, b) => a.length - b.length);
    if (names.length === 0) return query || "Productos seleccionados";
    const queryLen = query.trim().length;
    const shortest = names[0];
    if (names.length > 1 && Math.abs(shortest.length - queryLen) < 5) {
      return names[1];
    }
    return shortest;
  }, [perStoreProducts, query]);
  const displayCategory = isSelectiveComparison ? "Seleccion manual" : "Seleccion automatica";

  const handlePaymentAnalysisRequest = async () => {
    if (isPaymentAnalysisLoading || !token || !query) return;
    setIsPaymentAnalysisLoading(true);
    setPaymentAnalysisError(null);
    try {
      const { blob, filename } = await downloadPricingExcel(query, token, commerceName);
      // Trigger a browser download via a transient anchor — no library needed.
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    } catch (err) {
      setPaymentAnalysisError(messageForExcelError(err));
      // 401 still has to clear the session — show the inline message and let
      // AuthContext route to /signin via the next render cycle.
      if (err instanceof ApiError && err.status === 401) void signOut();
    } finally {
      setIsPaymentAnalysisLoading(false);
    }
  };

  if (!query) {
    return (
      <PageShell>
        <StatusPanel
          eyebrow="Inteligencia de producto"
          title="Falta la consulta"
          description="Volve a Landing y enviá una busqueda para generar el analisis."
        />
      </PageShell>
    );
  }

  if (isLoading || (!data && !error)) {
    return (
      <PageShell>
        <StatusPanel
          eyebrow="Inteligencia de producto"
          title={`Cargando "${query}"`}
          description="Consultando precios y promociones en vivo."
          spinner
        />
      </PageShell>
    );
  }

  if (error) {
    const classified = classifyError(error);
    return (
      <PageShell>
        <StatusPanel
          eyebrow="Inteligencia de producto"
          title={classified.title}
          description={classified.body}
        />
      </PageShell>
    );
  }

  if (!comparisonRows.length) {
    return (
      <PageShell>
        <StatusPanel
          eyebrow="Inteligencia de producto"
          title={`Sin resultados para "${query}"`}
          description="Ninguna tienda devolvio productos con precio para esta consulta."
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
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
                  {currentHeroImage ? (
                    <>
                      {!imageLoaded && (
                        <span className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
                          <span className="h-6 w-6 animate-spin rounded-full border-[1.5px] border-border border-t-primary" />
                        </span>
                      )}
                      <img
                        key={currentHeroImage}
                        src={currentHeroImage}
                        alt={displayProductName}
                        className={`relative h-full w-full rounded-[2.25rem] object-contain p-6 drop-shadow-[0_18px_24px_hsl(220_20%_14%_/_0.15)] transition-opacity duration-200 ${imageLoaded ? "opacity-100" : "opacity-0"}`}
                        loading="eager"
                        onLoad={() => setImageLoaded(true)}
                        onError={() => {
                          setImageLoaded(false);
                          setImageIdx((i) => i + 1);
                        }}
                      />
                    </>
                  ) : (
                    <div className="relative flex h-full w-full items-center justify-center rounded-[2.25rem] p-6">
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground text-center">
                        Sin imagen<br />disponible
                      </span>
                    </div>
                  )}
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
                  <span className="font-mono text-[11px] tracking-[0.08em]">
                    Generando
                  </span>
                </div>
              )}
              {!isPaymentAnalysisLoading && paymentAnalysisError && (
                <span
                  role="alert"
                  className="font-mono text-[11px] leading-tight tracking-[0.08em] text-destructive"
                >
                  {paymentAnalysisError}
                </span>
              )}
            </div>
            <section className="structured-card soft-elevation p-5 transform-gpu transition-[transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.025] hover:bg-card">
              <div className="section-eyebrow mb-4">Metricas de mercado</div>
              <div className="space-y-3">
                {[
                  { label: "Tiendas encontradas", value: storesFound.toString() },
                  { label: "Precio promedio", value: formatPrice(avgPrice) },
                  {
                    label: "Mas bajo vs promedio",
                    value: `- ${formatDecimal(Math.abs(cheapVsAvg))}%`,
                    detail: `(${formatPrice(avgPrice - minPrice)})`,
                    accent: true,
                  },
                  {
                    label: "Mas alto vs promedio",
                    value: `+ ${formatDecimal(Math.abs(expVsAvg))}%`,
                    detail: `(${formatPrice(maxPrice - avgPrice)})`,
                  },
                  {
                    label: "Brecha min-max",
                    value: `- ${formatDecimal(Math.abs(minVsMax))}%`,
                    detail: `(${formatPrice(maxPrice - minPrice)})`,
                    accent: true,
                  },
                ].map((m) => (
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
              <span className="font-mono text-xs text-muted-foreground">
                {storeCounts.attempted} consultadas · {storeCounts.withResults} con resultados
                {storeCounts.errored > 0 && ` · ${storeCounts.errored} sin respuesta`}
                {storeCounts.empty > 0 && ` · ${storeCounts.empty} sin coincidencias`}
              </span>
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
                  <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">Producto seleccionado</TableHead>
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
                {sortedRows.map((row) => {
                  const diff = avgPrice ? ((row.price - avgPrice) / avgPrice) * 100 : 0;
                  const diffVsMax = maxPrice ? ((row.price - maxPrice) / maxPrice) * 100 : 0;
                  return (
                    <TableRow key={`${row.storeKey}-${row.url}`} className={`border-border hover:bg-accent/40 ${row.price === minPrice ? "bg-accent/30" : ""}`}>
                      <TableCell className="text-sm font-medium">
                        <span className="inline-flex items-center gap-2">
                          <StatusDot state="ok" />
                          {row.displayName}
                        </span>
                      </TableCell>
                      <TableCell className="max-w-[280px] text-sm text-foreground">
                        <span className="line-clamp-2">{row.productName}</span>
                      </TableCell>
                      <TableCell>
                        <span className={`font-mono text-sm font-semibold ${row.price === minPrice ? "text-secondary" : "text-foreground"}`}>
                          {formatPrice(row.price)}
                        </span>
                        {row.price === minPrice && (
                          <span className="ml-2 font-mono text-[9px] uppercase tracking-wider text-secondary border border-secondary px-1.5 py-0.5 rounded-sm font-medium">
                            Mejor
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className={`font-mono text-xs ${diff <= 0 ? "text-secondary" : "text-muted-foreground"}`}>
                          {diff > 0 ? "+" : ""}
                          {formatDecimal(diff)}%
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className={`font-mono text-xs ${diffVsMax < 0 ? "text-secondary" : "text-muted-foreground"}`}>
                          {diffVsMax > 0 ? "+" : ""}
                          {formatDecimal(diffVsMax)}%
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-xs text-muted-foreground">
                          {row.bestPromo ?? "—"}
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        {row.available ? (
                          <Check className="h-3.5 w-3.5 text-secondary mx-auto" />
                        ) : (
                          <X className="h-3.5 w-3.5 text-destructive mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {row.freeShipping ? (
                          <Check className="h-3.5 w-3.5 text-secondary mx-auto" />
                        ) : (
                          <X className="h-3.5 w-3.5 text-destructive mx-auto" />
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <a href={row.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary/70 transition-colors">
                          <ExternalLink className="h-3.5 w-3.5 inline" />
                        </a>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {unavailableStoreRows.map((row) => (
                  <TableRow
                    key={`unavailable-${row.storeKey}`}
                    className="border-border opacity-60 hover:bg-transparent"
                  >
                    <TableCell className="text-sm font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-2">
                        <StatusDot state={row.state} />
                        {row.displayName}
                      </span>
                    </TableCell>
                    <TableCell colSpan={7} className="text-sm italic text-muted-foreground">
                      {row.state === "empty"
                        ? "Sin resultados en esta tienda."
                        : row.status === "timeout"
                          ? "La tienda no respondio a tiempo."
                          : "No se pudo conectar con la tienda."}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">—</TableCell>
                  </TableRow>
                ))}
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
                      tickFormatter={(v) => `${formatDecimal(v / 1000000)}M`}
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
                        tickFormatter={(v) => `${formatDecimal(v / 1000000)}M`}
                      />
                      <Legend wrapperStyle={{ fontSize: "11px", fontFamily: "'IBM Plex Mono', monospace" }} />
                      {cheapestFirst.map((row) => (
                        <Line
                          key={row.storeKey}
                          type="monotone"
                          dataKey={row.displayName}
                          stroke={getStoreColor(row.storeKey)}
                          strokeWidth={1.5}
                          dot={false}
                          activeDot={{ r: 3, strokeWidth: 1 }}
                        />
                      ))}
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
    </PageShell>
  );
};

export default ProductIntelligence;
