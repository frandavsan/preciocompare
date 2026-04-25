import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Info, Search } from "lucide-react";
import TopNav from "@/components/TopNav";
import { Checkbox } from "@/components/ui/checkbox";

const STORE_OPTIONS = [
  "Fravega",
  "Megatone",
  "OnCity",
  "Montes Hermanos",
  "Castillo",
  "Cetrogar",
] as const;

type StoreName = (typeof STORE_OPTIONS)[number];

type MockStoreResult = {
  id: string;
  name: string;
  detail: string;
  price: string;
};

type MockStoreGroup = {
  store: StoreName;
  results: MockStoreResult[];
};

const STORE_OPTIONS_TOP_GAP_REM = 0.6;
const STORE_OPTIONS_ROW_GAP_REM = 0.4;

const parseMockPrice = (price: string): number => {
  return Number(price.replace(/[^\d]/g, ""));
};

const MOCK_STORE_RESULTS: MockStoreGroup[] = [
  {
    store: "Fravega",
    results: [
      { id: "fravega-ps5-slim", name: "Sony PlayStation 5 Slim Digital", detail: "Consola digital - 1TB", price: "$949.000" },
    ],
  },
  {
    store: "Megatone",
    results: [
      { id: "megatone-ps5-slim", name: "PlayStation 5 Slim Digital Edition", detail: "18x sin interes disponible", price: "$959.000" },
      { id: "megatone-ps5-bundle", name: "PlayStation 5 Slim + DualSense", detail: "Bundle con control adicional", price: "$1.089.000" },
    ],
  },
  {
    store: "OnCity",
    results: [
      { id: "oncity-ps5-slim", name: "Sony PS5 Slim Digital", detail: "Entrega estimada 48 hs", price: "$939.999" },
      { id: "oncity-ps5-disc", name: "Sony PS5 Slim Standard", detail: "Version con lectora", price: "$1.049.999" },
      { id: "oncity-ps5-spiderman", name: "PS5 Slim Spider-Man Bundle", detail: "Incluye juego digital", price: "$1.129.999" },
    ],
  },
  {
    store: "Montes Hermanos",
    results: [
      { id: "montes-ps5-slim", name: "PlayStation 5 Slim Digital 1TB", detail: "Retiro en sucursal", price: "$969.500" },
    ],
  },
  {
    store: "Castillo",
    results: [
      { id: "castillo-ps5-slim", name: "Consola Sony PlayStation 5 Slim", detail: "Envio bonificado", price: "$979.900" },
      { id: "castillo-ps5-standard", name: "Consola Sony PlayStation 5 Standard", detail: "Stock limitado", price: "$1.069.900" },
    ],
  },
  {
    store: "Cetrogar",
    results: [
      { id: "cetrogar-ps5-slim", name: "Sony PlayStation 5 Slim Digital", detail: "Promocion bancaria activa", price: "$929.999" },
      { id: "cetrogar-ps5-bundle", name: "PlayStation 5 Slim + Auriculares", detail: "Combo gaming", price: "$1.119.999" },
    ],
  },
];

const Landing = () => {
  const [query, setQuery] = useState("");
  const [selectiveSearch, setSelectiveSearch] = useState(true);
  const [fromCABA, setFromCABA] = useState(false);
  const [postalCode, setPostalCode] = useState("");
  const [searchAllStores, setSearchAllStores] = useState(true);
  const [selectedStores, setSelectedStores] = useState<string[]>([...STORE_OPTIONS]);
  const [isStoresOpen, setIsStoresOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [hasSearchStarted, setHasSearchStarted] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [openResultStores, setOpenResultStores] = useState<string[]>([]);
  const [selectedProductsByStore, setSelectedProductsByStore] = useState<Record<string, string>>({});
  const timeoutRef = useRef<number | null>(null);
  const intervalRef = useRef<number | null>(null);
  const completionRef = useRef<number | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
      }
      if (completionRef.current !== null) {
        window.clearTimeout(completionRef.current);
      }
    };
  }, []);

  const handleSearchAllStoresChange = (checked: boolean) => {
    setSearchAllStores(checked);
    setSelectedStores(checked ? [...STORE_OPTIONS] : []);
  };

  const handleStoreToggle = (store: string, checked: boolean) => {
    setSelectedStores((prev) => {
      const next = checked ? [...prev, store] : prev.filter((item) => item !== store);
      const normalized = STORE_OPTIONS.filter((item) => next.includes(item));
      setSearchAllStores(normalized.length === STORE_OPTIONS.length);
      return normalized;
    });
  };

  const handleResultStoreToggle = (store: string) => {
    setOpenResultStores((prev) =>
      prev.includes(store) ? prev.filter((item) => item !== store) : [...prev, store]
    );
  };

  const visibleStoreResults = MOCK_STORE_RESULTS.filter((group) => selectedStores.includes(group.store));
  const selectedProductCount = Object.keys(selectedProductsByStore).length;

  const handleCompareSelection = () => {
    if (selectedProductCount === 0) return;

    const selectedProducts = MOCK_STORE_RESULTS.flatMap((group) =>
      group.results
        .filter((result) => selectedProductsByStore[group.store] === result.id)
        .map((result) => ({
          store: group.store,
          name: result.name,
          price: parseMockPrice(result.price),
        }))
    );
    const params = new URLSearchParams({ q: query.trim() });
    params.set("selected", JSON.stringify(selectedProducts));
    if (fromCABA) {
      params.set("caba", "1");
    } else if (postalCode.trim()) {
      params.set("postal_code", postalCode.trim());
    }
    navigate(`/producto?${params.toString()}`);
  };

  useEffect(() => {
    const selectedStoreSet = new Set(selectedStores);

    setOpenResultStores((prev) => {
      const next = prev.filter((store) => selectedStoreSet.has(store));
      return next.length === prev.length ? prev : next;
    });

    setSelectedProductsByStore((prev) => {
      const next = Object.fromEntries(
        Object.entries(prev).filter(([store]) => selectedStoreSet.has(store))
      );
      return Object.keys(next).length === Object.keys(prev).length ? prev : next;
    });
  }, [selectedStores]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
    }
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
    }
    if (completionRef.current !== null) {
      window.clearTimeout(completionRef.current);
    }

    setHasSearchStarted(selectiveSearch);
    setShowResults(false);
    setOpenResultStores([]);
    setSelectedProductsByStore({});
    setIsLoading(true);
    setLoadingProgress(0);

    const loadingMs = Math.floor(Math.random() * 3000) + 3000;
    const startedAt = Date.now();

    intervalRef.current = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      const ratio = Math.min(elapsed / loadingMs, 1);

      setLoadingProgress((prev) => {
        const baseTarget = Math.floor(ratio * 100);
        const jumpSize = Math.floor(Math.random() * 8) + 2;
        const randomLead = Math.floor(Math.random() * 6);
        return Math.min(99, Math.max(prev, baseTarget + randomLead, prev + jumpSize));
      });
    }, 180);

    timeoutRef.current = window.setTimeout(() => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }

      setLoadingProgress(100);
      completionRef.current = window.setTimeout(() => {
        setIsLoading(false);
        if (selectiveSearch) {
          setShowResults(true);
          setOpenResultStores(visibleStoreResults.slice(0, 2).map((group) => group.store));
        } else {
          const params = new URLSearchParams({ q: query.trim() });
          if (fromCABA) {
            params.set("caba", "1");
          } else if (postalCode.trim()) {
            params.set("postal_code", postalCode.trim());
          }
          navigate(`/producto?${params.toString()}`);
        }
        completionRef.current = null;
      }, 350);
    }, loadingMs);
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
                    disabled={isLoading}
                    className="w-full shrink-0 bg-primary px-5 py-3.5 font-mono text-[11px] font-medium uppercase tracking-[0.15em] text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-90"
                  >
                    {isLoading ? "Buscando" : "Buscar"}
                  </button>
                  <div className="mt-2 min-h-[22px] flex items-center justify-center">
                    {isLoading && (
                      <div className="inline-flex items-center gap-2 text-muted-foreground">
                        <span className="h-4 w-4 animate-spin rounded-full border-[1.5px] border-border border-t-primary" />
                        <span className="font-mono text-[11px] tracking-[0.08em] tabular-nums">
                          {loadingProgress}%
                        </span>
                      </div>
                  )}
                </div>
              </div>
            </div>
            {isLoading && (
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/70">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-200 ease-out"
                  style={{ width: `${loadingProgress}%` }}
                />
              </div>
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
                      {STORE_OPTIONS.map((store) => (
                        <label key={store} className="flex items-center gap-2.5 text-[12px] text-foreground">
                          <Checkbox
                            checked={selectedStores.includes(store)}
                            onCheckedChange={(checked) => handleStoreToggle(store, checked === true)}
                            className="h-4 w-4"
                          />
                          <span className="leading-[1.2]">{store}</span>
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
                    const isOpen = openResultStores.includes(group.store);
                    return (
                      <div key={group.store} className="structured-card bg-card/85 p-4">
                        <button
                          type="button"
                          onClick={() => handleResultStoreToggle(group.store)}
                          className="flex w-full items-center justify-between gap-4 text-left"
                          aria-expanded={isOpen}
                        >
                          <span className="font-mono text-[12px] uppercase tracking-[0.14em] text-foreground">
                            {group.store} ({group.results.length} {group.results.length === 1 ? "resultado" : "resultados"})
                          </span>
                          <span className="inline-flex h-7 w-7 items-center justify-center rounded-sm bg-muted/70 text-primary transition-colors hover:bg-muted">
                            <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                          </span>
                        </button>

                        {isOpen && (
                          <div className="mt-4 space-y-2">
                            {group.results.map((result) => (
                              <label
                                key={result.id}
                                className="flex cursor-pointer items-start gap-3 rounded-sm bg-background/55 px-3 py-3 transition-colors hover:bg-background/85"
                              >
                                <Checkbox
                                  checked={selectedProductsByStore[group.store] === result.id}
                                  onCheckedChange={(checked) =>
                                    setSelectedProductsByStore((prev) => {
                                      if (checked === true) {
                                        return { ...prev, [group.store]: result.id };
                                      }

                                      const rest = { ...prev };
                                      delete rest[group.store];
                                      return rest;
                                    })
                                  }
                                  className="mt-0.5"
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                                    <span className="text-sm font-medium text-foreground">{result.name}</span>
                                    <span className="font-mono text-xs font-semibold text-secondary">{result.price}</span>
                                  </div>
                                </div>
                              </label>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="structured-card bg-card/85 p-5 text-sm text-muted-foreground">
                    No hay tiendas seleccionadas. Activa al menos una tienda para ver resultados mock.
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
        <span className="font-mono text-[10px] tracking-wide text-muted-foreground">v1.0.0 · data.mock · 5 tiendas indexadas</span>
      </footer>
    </div>
  );
};

export default Landing;
