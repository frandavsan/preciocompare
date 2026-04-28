import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Info, Search } from "lucide-react";
import { toast } from "sonner";
import TopNav from "@/components/TopNav";
import { Checkbox } from "@/components/ui/checkbox";
import { STORE_KEYS, type StoreKey, getStoreDisplayName } from "@/lib/stores";
import {
  searchToStoreGroups,
  autoSelectProducts,
  formatPrice,
  type StoreGroup,
} from "@/lib/transforms";
import { useSearch } from "@/hooks/useSearch";
import { ApiError, classifyError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const STORE_OPTIONS_TOP_GAP_REM = 0.6;
const STORE_OPTIONS_ROW_GAP_REM = 0.4;

const buildSelectedParam = (
  entries: { storeKey: string; url: string }[],
): string => JSON.stringify(entries.map((e) => ({ store: e.storeKey, url: e.url })));

// Wraps a list and caps its visible height to the bottom of the Nth child,
// so at most `maxItems` rows are visible — the rest scroll inside the box.
// Measured (not estimated) so it stays correct when names wrap to 2+ lines.
const ScrollCappedList = ({
  maxItems,
  itemCount,
  children,
  className = "",
}: {
  maxItems: number;
  itemCount: number;
  children: ReactNode;
  className?: string;
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const [maxHeight, setMaxHeight] = useState<number | undefined>(undefined);

  useLayoutEffect(() => {
    if (itemCount <= maxItems) {
      setMaxHeight(undefined);
      return;
    }
    const node = ref.current;
    if (!node) return;
    const measure = () => {
      const items = node.children;
      if (items.length < maxItems) return;
      const nth = items[maxItems - 1] as HTMLElement;
      const containerTop = node.getBoundingClientRect().top;
      const nthBottom = nth.getBoundingClientRect().bottom;
      setMaxHeight(nthBottom - containerTop);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    for (const child of Array.from(node.children)) ro.observe(child);
    return () => ro.disconnect();
  }, [itemCount, maxItems]);

  return (
    <div
      ref={ref}
      className={`${className} ${maxHeight !== undefined ? "overflow-y-auto pr-1" : ""}`}
      style={maxHeight !== undefined ? { maxHeight } : undefined}
    >
      {children}
    </div>
  );
};

const Landing = () => {
  const navigate = useNavigate();
  const { signOut } = useAuth();

  const [query, setQuery] = useState("");
  const [selectiveSearch, setSelectiveSearch] = useState(true);
  const [fromCABA, setFromCABA] = useState(false);
  const [postalCode, setPostalCode] = useState("");
  const [searchAllStores, setSearchAllStores] = useState(true);
  const [selectedStoreKeys, setSelectedStoreKeys] = useState<readonly StoreKey[]>(STORE_KEYS);
  const [isStoresOpen, setIsStoresOpen] = useState(false);
  const [hasSearchStarted, setHasSearchStarted] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [openResultStores, setOpenResultStores] = useState<string[]>([]);
  const [selectedProductsByStore, setSelectedProductsByStore] = useState<Record<string, string>>({});

  const [submittedQuery, setSubmittedQuery] = useState("");
  const [submittedPostal, setSubmittedPostal] = useState<string | undefined>(undefined);
  const [submittedSelective, setSubmittedSelective] = useState(true);
  const [submittedFromCABA, setSubmittedFromCABA] = useState(false);
  const [submitToken, setSubmitToken] = useState(0);

  const [elapsedSec, setElapsedSec] = useState(0);
  const [cooldownEndsAt, setCooldownEndsAt] = useState<number | null>(null);
  const [cooldownSec, setCooldownSec] = useState(0);

  const intervalRef = useRef<number | null>(null);
  const handledTokenRef = useRef(0);

  const { data, isFetching, error } = useSearch(submittedQuery, {
    enabled: submitToken > 0,
    postalCode: submittedPostal,
  });

  const isLoading = isFetching;

  // Side-effects for auth/transport-level errors. Inline messages handle
  // server/unknown errors; this hook only fires for the kinds the user
  // can't recover from inline (auth, rate limit, network).
  const handledErrorRef = useRef<unknown>(null);
  useEffect(() => {
    if (!error || error === handledErrorRef.current) return;
    handledErrorRef.current = error;
    const classified = classifyError(error);
    if (classified.kind === "auth") {
      toast.error(classified.title, { description: classified.body });
      void signOut();
    } else if (classified.kind === "rate_limit") {
      toast.error(classified.title, { description: classified.body });
      const wait =
        error instanceof ApiError && error.retryAfterSeconds
          ? error.retryAfterSeconds
          : 60;
      setCooldownEndsAt(Date.now() + wait * 1000);
    } else if (classified.kind === "network") {
      toast.error(classified.title, { description: classified.body });
    }
  }, [error, signOut]);

  // Drive the cooldown countdown — clears itself when the deadline passes.
  useEffect(() => {
    if (cooldownEndsAt === null) {
      setCooldownSec(0);
      return;
    }
    const tick = () => {
      const remainingMs = cooldownEndsAt - Date.now();
      if (remainingMs <= 0) {
        setCooldownEndsAt(null);
        setCooldownSec(0);
      } else {
        setCooldownSec(Math.ceil(remainingMs / 1000));
      }
    };
    tick();
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [cooldownEndsAt]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) window.clearInterval(intervalRef.current);
    };
  }, []);

  // Tick an elapsed-seconds counter while a fetch is in flight. We show real
  // elapsed time instead of a synthetic % bar — broad queries take 25-30s and
  // a fake ramp lies in both directions (pegs at 99% on slow runs, never hits
  // 100 on fast ones).
  useEffect(() => {
    if (!isFetching) {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }
    setElapsedSec(0);
    const startedAt = Date.now();
    const id = window.setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 250);
    intervalRef.current = id;
    return () => {
      window.clearInterval(id);
      if (intervalRef.current === id) intervalRef.current = null;
    };
  }, [isFetching]);

  // Drive completion exactly once per submit, when the fetch settles.
  useEffect(() => {
    if (submitToken === 0) return;
    if (handledTokenRef.current === submitToken) return;
    if (isFetching) return;
    if (!data && !error) return;

    handledTokenRef.current = submitToken;
    if (error || !data) return;

    if (submittedSelective) {
      setShowResults(true);
      const groups = searchToStoreGroups(data, selectedStoreKeys);
      setOpenResultStores(
        groups.filter((g) => g.results.length > 0).slice(0, 2).map((g) => g.storeKey),
      );
    } else {
      const auto = autoSelectProducts(data).filter((s) =>
        selectedStoreKeys.includes(s.storeKey as StoreKey),
      );
      const params = new URLSearchParams({ q: submittedQuery });
      params.set(
        "selected",
        buildSelectedParam(auto.map((s) => ({ storeKey: s.storeKey, url: s.product.url }))),
      );
      if (submittedFromCABA) params.set("caba", "1");
      else if (submittedPostal) params.set("postal_code", submittedPostal);
      navigate(`/producto?${params.toString()}`);
    }
  }, [
    submitToken,
    isFetching,
    data,
    error,
    submittedSelective,
    submittedQuery,
    submittedFromCABA,
    submittedPostal,
    selectedStoreKeys,
    navigate,
  ]);

  const handleSearchAllStoresChange = (checked: boolean) => {
    setSearchAllStores(checked);
    setSelectedStoreKeys(checked ? STORE_KEYS : []);
  };

  const handleStoreToggle = (storeKey: StoreKey, checked: boolean) => {
    setSelectedStoreKeys((prev) => {
      const next = checked ? [...prev, storeKey] : prev.filter((k) => k !== storeKey);
      const normalized = STORE_KEYS.filter((k) => next.includes(k));
      setSearchAllStores(normalized.length === STORE_KEYS.length);
      return normalized;
    });
  };

  const handleResultStoreToggle = (storeKey: string) => {
    setOpenResultStores((prev) =>
      prev.includes(storeKey) ? prev.filter((k) => k !== storeKey) : [...prev, storeKey],
    );
  };

  // Derive visible store groups from real API data + the current store filter.
  const visibleStoreResults: StoreGroup[] = useMemo(() => {
    if (!data) return [];
    return searchToStoreGroups(data, selectedStoreKeys);
  }, [data, selectedStoreKeys]);

  const selectedProductCount = Object.keys(selectedProductsByStore).length;

  // Drop selections / open accordions for stores that get unchecked.
  useEffect(() => {
    const selected = new Set<string>(selectedStoreKeys);
    setOpenResultStores((prev) => {
      const next = prev.filter((s) => selected.has(s));
      return next.length === prev.length ? prev : next;
    });
    setSelectedProductsByStore((prev) => {
      const next = Object.fromEntries(
        Object.entries(prev).filter(([s]) => selected.has(s)),
      );
      return Object.keys(next).length === Object.keys(prev).length ? prev : next;
    });
  }, [selectedStoreKeys]);

  const handleCompareSelection = () => {
    if (selectedProductCount === 0 || !data) return;

    const entries: { storeKey: string; url: string }[] = [];
    for (const group of visibleStoreResults) {
      const chosenUrl = selectedProductsByStore[group.storeKey];
      if (!chosenUrl) continue;
      const match = group.results.find((r) => r.url === chosenUrl);
      if (match) entries.push({ storeKey: group.storeKey, url: match.url });
    }
    if (!entries.length) return;

    const params = new URLSearchParams({ q: submittedQuery || query.trim() });
    params.set("selected", buildSelectedParam(entries));
    if (submittedFromCABA || fromCABA) {
      params.set("caba", "1");
    } else {
      const cp = (submittedPostal ?? postalCode).trim();
      if (cp) params.set("postal_code", cp);
    }
    navigate(`/producto?${params.toString()}`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isFetching || cooldownSec > 0) return;

    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    const trimmedPostal = postalCode.trim();
    // CABA → send "1425" explicitly so the backend bypasses cache and runs a
    // live shipping simulation (matches the terminal's behavior).
    const effectivePostal = fromCABA ? "1425" : (trimmedPostal || undefined);

    setSubmittedQuery(trimmed);
    setSubmittedPostal(effectivePostal);
    setSubmittedSelective(selectiveSearch);
    setSubmittedFromCABA(fromCABA);
    setHasSearchStarted(selectiveSearch);
    setShowResults(false);
    setOpenResultStores([]);
    setSelectedProductsByStore({});
    setSubmitToken((t) => t + 1);
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background paper-texture flex flex-col isolate">
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -left-[16%] -top-[24%] h-[42rem] w-[42rem] rounded-full bg-[radial-gradient(circle_at_58%_42%,hsl(272_81%_74%_/_0.5),hsl(262_90%_38%_/_0.22)_52%,transparent_74%)] blur-[132px]" />
        <div className="absolute -right-[14%] -top-[8%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle_at_38%_42%,hsl(252_78%_80%_/_0.22),hsl(262_90%_38%_/_0.1)_58%,transparent_76%)] blur-[120px]" />
        <div className="absolute -bottom-[22%] -right-[12%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle_at_38%_38%,hsl(177_62%_72%_/_0.4),hsl(179_98%_21%_/_0.16)_56%,transparent_76%)] blur-[128px]" />
      </div>
      <TopNav activeSection="intelligence" />

      <main className="relative z-10 flex-1 overflow-y-auto px-6 pt-2">
        <div
          className={`mx-auto flex min-h-[calc(100vh-9rem)] w-full max-w-4xl flex-col items-center pb-16 transition-[padding] duration-500 ease-out ${
            hasSearchStarted ? "justify-start pt-8" : "justify-center"
          }`}
        >
          <div className="w-full">
            <div className="section-eyebrow mb-4">Modulo de busqueda</div>

            <h1 className="text-3xl sm:text-4xl font-bold text-foreground leading-[1.15] tracking-tight mb-3">
              Inteligencia de precios
              <br />
              para electronica en Argentina
            </h1>

            <div className="primary-rule mb-5" />

            <p className="text-muted-foreground text-[15px] leading-[1.7] mb-8 max-w-md">
              Busca un producto y compara su precio entre las principales tiendas del pais.
            </p>

            <div className="mb-4 flex items-start gap-2 text-muted-foreground">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <p className="text-xs leading-5">
                Inserta la marca del producto seguida por el codigo del modelo. Por ejemplo: Drean LCFDR0314SG0
              </p>
            </div>

            <form onSubmit={handleSubmit} className="mb-4">
              <div className="flex items-start gap-3">
                <div className="flex flex-1 border-2 border-border bg-card rounded-sm overflow-hidden focus-within:border-primary transition-colors">
                  <div className="flex items-center pl-4 text-muted-foreground">
                    <Search className="h-4 w-4" />
                  </div>
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ej: Samsung Galaxy S24 Ultra 256GB"
                    className="flex-1 bg-transparent px-3 py-3.5 text-sm text-foreground placeholder:text-muted-foreground outline-none font-sans"
                  />
                </div>
                <div className="flex min-w-[92px] flex-col items-center">
                  <button
                    type="submit"
                    disabled={isLoading || cooldownSec > 0}
                    className="w-full shrink-0 bg-primary px-5 py-3.5 font-mono text-[11px] font-medium uppercase tracking-[0.15em] text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-90"
                  >
                    {cooldownSec > 0
                      ? `Esperá ${cooldownSec}s`
                      : isLoading
                        ? "Buscando"
                        : "Buscar"}
                  </button>
                  <div className="mt-2 min-h-[22px] flex items-center justify-center">
                    {isLoading && (
                      <div className="inline-flex items-center gap-2 text-muted-foreground">
                        <span className="h-4 w-4 animate-spin rounded-full border-[1.5px] border-border border-t-primary" />
                        <span className="font-mono text-[11px] tracking-[0.08em] tabular-nums">
                          {elapsedSec}s
                        </span>
                      </div>
                  )}
                </div>
              </div>
            </div>
            {isLoading && (
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/70">
                <div className="h-full w-full rounded-full bg-primary animate-pulse" />
              </div>
            )}
            {!isLoading && error && (
              <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.12em] text-destructive">
                {classifyError(error).body}
              </p>
            )}
          </form>

            <div className="mb-8 space-y-4">
              <div className="flex items-start gap-2.5">
                <Checkbox
                  id="selective-search"
                  checked={selectiveSearch}
                  onCheckedChange={(checked) => setSelectiveSearch(checked === true)}
                  className="mt-0.5"
                />
                <div>
                  <label htmlFor="selective-search" className="block cursor-pointer text-sm leading-tight text-foreground">
                    Busqueda selectiva
                  </label>
                  <span className="mt-1 block max-w-[34rem] font-mono text-[10px] leading-4 tracking-wide text-muted-foreground">
                    Permite seleccionar manualmente los productos a comparar. Conveniente utilizar cuando el nombre de modelo es corto o inespecifico (ej: &quot;S26&quot;).
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Checkbox
                  id="caba"
                  checked={fromCABA}
                  onCheckedChange={(checked) => setFromCABA(checked === true)}
                  className="mt-0.5"
                />
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <label htmlFor="caba" className="block cursor-pointer text-sm leading-tight text-foreground">
                      Shopping from CABA
                    </label>
                    {!fromCABA && (
                      <input
                        type="text"
                        inputMode="numeric"
                        value={postalCode}
                        onChange={(e) => setPostalCode(e.target.value)}
                        placeholder="Codigo Postal"
                        className="h-7 w-32 rounded-sm border border-border bg-card/80 px-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-primary focus:bg-card"
                      />
                    )}
                  </div>
                  <span className="mt-0.5 block font-mono text-[10px] tracking-wide text-muted-foreground">
                    Simular busqueda con envio y disponibilidad en CABA
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Checkbox
                  id="search-all-stores"
                  checked={searchAllStores}
                  onCheckedChange={(checked) => handleSearchAllStoresChange(checked === true)}
                  className="mt-0.5"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <label htmlFor="search-all-stores" className="block cursor-pointer text-sm leading-tight text-foreground">
                      Search all stores
                    </label>
                    <button
                      type="button"
                      onClick={() => setIsStoresOpen((prev) => !prev)}
                      className="inline-flex h-4 w-4 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                      aria-expanded={isStoresOpen}
                      aria-controls="store-options"
                      aria-label="Toggle store options"
                    >
                      <ChevronDown className={`h-3 w-3 transition-transform ${isStoresOpen ? "rotate-180" : ""}`} />
                    </button>
                  </div>
                  {isStoresOpen && (
                    <div
                      id="store-options"
                      className="ml-0.5 flex flex-col"
                      style={{
                        marginTop: `${STORE_OPTIONS_TOP_GAP_REM}rem`,
                        rowGap: `${STORE_OPTIONS_ROW_GAP_REM}rem`,
                      }}
                    >
                      {STORE_KEYS.map((storeKey) => (
                        <label key={storeKey} className="flex items-center gap-2.5 text-[12px] text-foreground">
                          <Checkbox
                            checked={selectedStoreKeys.includes(storeKey)}
                            onCheckedChange={(checked) => handleStoreToggle(storeKey, checked === true)}
                            className="h-4 w-4"
                          />
                          <span className="leading-[1.2]">{getStoreDisplayName(storeKey)}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {!hasSearchStarted && (
              <div className="font-mono text-[10px] tracking-wide text-muted-foreground">
                <span className="uppercase">Ejemplos:</span>{" "}
                <span className="text-foreground/60">MacBook Air M3 15 256GB · PlayStation 5 Slim · iPhone 15 128GB</span>
              </div>
            )}
          </div>

          <section
            className={`w-full max-w-3xl transition-all duration-500 ease-out ${
              showResults ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-4 opacity-0"
            }`}
            aria-live="polite"
          >
            {showResults && (
              <div className="space-y-3">
                <div className="mb-4">
                  <div className="section-eyebrow mb-1.5">Resultados encontrados</div>
                  <p className="text-sm text-muted-foreground">
                    Selecciona el producto que queres usar para generar el analisis de inteligencia de precios.
                  </p>
                </div>

                {visibleStoreResults.length > 0 ? (
                  visibleStoreResults.map((group) => {
                    const isOpen = openResultStores.includes(group.storeKey);
                    const headerCount =
                      group.status === "error" || group.status === "timeout"
                        ? "error"
                        : group.results.length === 0
                          ? "sin resultados"
                          : `${group.results.length} ${group.results.length === 1 ? "resultado" : "resultados"}`;
                    return (
                      <div key={group.storeKey} className="structured-card bg-card/85 p-4">
                        <button
                          type="button"
                          onClick={() => handleResultStoreToggle(group.storeKey)}
                          className="flex w-full items-center justify-between gap-4 text-left"
                          aria-expanded={isOpen}
                        >
                          <span className="font-mono text-[12px] uppercase tracking-[0.14em] text-foreground">
                            {group.displayName} ({headerCount})
                          </span>
                          <span className="inline-flex h-7 w-7 items-center justify-center rounded-sm bg-muted/70 text-primary transition-colors hover:bg-muted">
                            <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                          </span>
                        </button>

                        {isOpen && (
                          <div className="mt-4">
                            {group.results.length === 0 ? (
                              <div className="rounded-sm bg-background/55 px-3 py-3 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                                {group.status === "error" || group.status === "timeout"
                                  ? "La tienda no respondio en esta busqueda."
                                  : "Sin resultados para esta tienda."}
                              </div>
                            ) : (
                              <ScrollCappedList
                                maxItems={5}
                                itemCount={group.results.length}
                                className="space-y-2"
                              >
                                {group.results.map((result) => (
                                  <label
                                    key={result.url}
                                    className="flex cursor-pointer items-start gap-3 rounded-sm bg-background/55 px-3 py-3 transition-colors hover:bg-background/85"
                                  >
                                    <Checkbox
                                      checked={selectedProductsByStore[group.storeKey] === result.url}
                                      onCheckedChange={(checked) =>
                                        setSelectedProductsByStore((prev) => {
                                          if (checked === true) {
                                            return { ...prev, [group.storeKey]: result.url };
                                          }
                                          const rest = { ...prev };
                                          delete rest[group.storeKey];
                                          return rest;
                                        })
                                      }
                                      className="mt-0.5"
                                    />
                                    <div className="min-w-0 flex-1">
                                      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                                        <span className="text-sm font-medium text-foreground">{result.name}</span>
                                        <span className="font-mono text-xs font-semibold text-secondary">
                                          {formatPrice(result.price)}
                                        </span>
                                      </div>
                                      {result.detail && (
                                        <span className="mt-1 block font-mono text-[10px] tracking-wide text-muted-foreground">
                                          {result.detail}
                                        </span>
                                      )}
                                    </div>
                                  </label>
                                ))}
                              </ScrollCappedList>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="structured-card bg-card/85 p-5 text-sm text-muted-foreground">
                    No hay tiendas seleccionadas. Activa al menos una tienda para ver resultados.
                  </div>
                )}

                <div className="pt-4">
                  <button
                    type="button"
                    onClick={handleCompareSelection}
                    disabled={selectedProductCount === 0}
                    className="flex w-full items-center justify-center bg-primary px-5 py-4 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary-foreground transition-all duration-200 hover:bg-primary/90 active:scale-[0.99] disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
                  >
                    Comparar
                  </button>
                  {selectedProductCount === 0 ? (
                    <p className="mt-2 text-center font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      Selecciona al menos un producto para continuar
                    </p>
                  ) : (
                    <p className="mt-2 text-center font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      {selectedProductCount} {selectedProductCount === 1 ? "producto seleccionado" : "productos seleccionados"}
                    </p>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      </main>

      <footer className="relative z-10 h-9 flex items-center justify-center border-t-2 border-border bg-card/90 backdrop-blur-[2px] shrink-0">
        <span className="font-mono text-[10px] tracking-wide text-muted-foreground">
          v1.0.0 · data.live · {STORE_KEYS.length} tiendas indexadas
        </span>
      </footer>
    </div>
  );
};

export default Landing;
