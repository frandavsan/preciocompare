import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Info, Search } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import TopNav from "@/components/TopNav";

const STORE_OPTIONS = [
  "Fravega",
  "Megatone",
  "OnCity",
  "Montes Hermanos",
  "Castillo",
  "Cetrogar",
] as const;

const STORE_OPTIONS_TOP_GAP_REM = 0.6;
const STORE_OPTIONS_ROW_GAP_REM = 0.4;

const Landing = () => {
  const [query, setQuery] = useState("");
  const [fromCABA, setFromCABA] = useState(false);
  const [searchAllStores, setSearchAllStores] = useState(true);
  const [selectedStores, setSelectedStores] = useState<string[]>([...STORE_OPTIONS]);
  const [isStoresOpen, setIsStoresOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const navigate = useNavigate();
  const timeoutRef = useRef<number | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    setLoadingProgress(0);

    const params = new URLSearchParams({ q: query.trim() });
    if (fromCABA) params.set("caba", "1");

    const loadingMs = Math.floor(Math.random() * 3000) + 3000;
    const startedAt = Date.now();

    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
    }

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
      navigate(`/producto?${params.toString()}`);
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

      <main className="relative z-10 flex-1 flex items-center justify-center px-6 pt-2">
        <div className="w-full max-w-4xl -mt-16">
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
          </form>

          <div className="mb-8 space-y-4">
            <div className="flex items-start gap-2.5">
              <Checkbox
                id="caba"
                checked={fromCABA}
                onCheckedChange={(checked) => setFromCABA(checked === true)}
                className="mt-0.5"
              />
              <div>
                <label htmlFor="caba" className="block cursor-pointer text-sm leading-tight text-foreground">
                  Shopping from CABA
                </label>
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

          <div className="font-mono text-[10px] tracking-wide text-muted-foreground">
            <span className="uppercase">Ejemplos:</span>{" "}
            <span className="text-foreground/60">MacBook Air M3 15 256GB · PlayStation 5 Slim · iPhone 15 128GB</span>
          </div>
        </div>
      </main>

      <footer className="relative z-10 h-9 flex items-center justify-center border-t-2 border-border bg-card/90 backdrop-blur-[2px] shrink-0">
        <span className="font-mono text-[10px] tracking-wide text-muted-foreground">v1.0.0 · data.mock · 5 tiendas indexadas</span>
      </footer>
    </div>
  );
};

export default Landing;
