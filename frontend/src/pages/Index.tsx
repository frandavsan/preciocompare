import { useState, useMemo } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { SearchBar } from "@/components/SearchBar";
import { ComparisonTable } from "@/components/ComparisonTable";
import { PriceDistributionChart } from "@/components/PriceDistributionChart";
import { PriceHistoryChart } from "@/components/PriceHistoryChart";
import { StatsCards } from "@/components/StatsCards";
import { products, categories, formatPrice } from "@/data/mockData";
import { Database, BarChart3, Layers } from "lucide-react";

const Index = () => {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const filtered = useMemo(() => {
    return products.filter((p) => {
      const matchSearch = p.name.toLowerCase().includes(search.toLowerCase());
      const matchCat = !selectedCategory || p.category === selectedCategory;
      return matchSearch && matchCat;
    });
  }, [search, selectedCategory]);

  const allPrices = products.flatMap((p) => p.prices);
  const lowestPrice = Math.min(...allPrices.map((p) => p.price));

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background paper-texture">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top bar */}
          <header className="h-11 flex items-center gap-4 border-b-2 border-border px-4 lg:px-6 shrink-0 bg-card">
            <SidebarTrigger />
            <SearchBar value={search} onChange={setSearch} />
            <span className="font-mono text-[10px] text-muted-foreground hidden md:block tracking-wider">
              SYNC: 30 MAR 2026
            </span>
          </header>

          <main className="flex-1 overflow-auto">
            {/* Hero module — product overview */}
            <section className="border-b-2 border-border bg-card hero-grid relative">
              <div className="p-8 lg:py-12 lg:px-10">
                {/* Eyebrow */}
                <div className="flex items-center gap-2.5 mb-5">
                  <div className="w-6 h-6 rounded-sm bg-primary flex items-center justify-center">
                    <Database className="h-3.5 w-3.5 text-primary-foreground" />
                  </div>
                  <span className="section-eyebrow">Módulo de inteligencia de precios</span>
                </div>

                {/* Title block */}
                <h1 className="text-4xl lg:text-5xl font-bold text-foreground leading-[1.1] tracking-tight mb-4">
                  Electrónica<br />Argentina
                </h1>
                <div className="primary-rule mb-5" />
                <p className="text-muted-foreground max-w-lg text-[15px] leading-[1.7]">
                  Comparación en tiempo real de precios en las principales tiendas del país. 
                  Analizá tendencias históricas y encontrá el mejor momento para comprar.
                </p>

                {/* Metadata row */}
                <div className="flex items-center gap-3 mt-7">
                  <div className="border-2 border-border bg-background px-3 py-1.5 rounded-sm">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground block">Productos</span>
                    <span className="font-mono text-sm font-semibold text-foreground">{products.length}</span>
                  </div>
                  <div className="border-2 border-border bg-background px-3 py-1.5 rounded-sm">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground block">Tiendas</span>
                    <span className="font-mono text-sm font-semibold text-foreground">5</span>
                  </div>
                  <div className="border-2 border-border bg-background px-3 py-1.5 rounded-sm">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground block">Mejor precio</span>
                    <span className="font-mono text-sm font-semibold text-secondary">{formatPrice(lowestPrice)}</span>
                  </div>
                  <div className="border-2 border-border bg-background px-3 py-1.5 rounded-sm">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground block">Rango temporal</span>
                    <span className="font-mono text-sm font-semibold text-foreground">7 meses</span>
                  </div>
                </div>
              </div>
            </section>

            {/* Main content */}
            <div className="p-5 lg:p-8 space-y-8 max-w-7xl">

              {/* Key metrics module */}
              <section>
                <div className="flex items-center gap-2.5 mb-4">
                  <BarChart3 className="h-4 w-4 text-primary" />
                  <span className="section-eyebrow">Métricas clave</span>
                </div>
                <StatsCards />
              </section>

              {/* Filter & explore module */}
              <section className="section-module">
                <div className="module-header flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <span className="section-eyebrow block mb-1.5">Explorar</span>
                    <h2 className="text-xl font-bold text-foreground">Filtrar por categoría</h2>
                  </div>
                  <span className="font-mono text-xs text-muted-foreground">
                    {filtered.length} de {products.length} productos
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => setSelectedCategory(null)}
                    className={`font-mono text-[11px] px-3 py-1.5 border-2 rounded-sm transition-colors tracking-wide ${
                      selectedCategory === null
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-background text-foreground hover:border-foreground"
                    }`}
                  >
                    TODOS
                  </button>
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={`font-mono text-[11px] px-3 py-1.5 border-2 rounded-sm transition-colors tracking-wide uppercase ${
                        selectedCategory === cat
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background text-foreground hover:border-foreground"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </section>

              {/* Analytics module */}
              <section>
                <div className="flex items-center gap-2.5 mb-4">
                  <BarChart3 className="h-4 w-4 text-primary" />
                  <span className="section-eyebrow">Análisis visual</span>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  <PriceDistributionChart products={filtered} />
                  {filtered.length > 0 && <PriceHistoryChart product={filtered[0]} />}
                </div>
              </section>

              {/* Comparison module */}
              <section>
                <div className="flex items-center gap-2.5 mb-1.5">
                  <Layers className="h-4 w-4 text-primary" />
                  <span className="section-eyebrow">Datos comparativos</span>
                </div>
                <div className="flex items-baseline gap-3 mb-5">
                  <h2 className="text-xl font-bold text-foreground">Comparación de precios</h2>
                  <span className="font-mono text-xs text-muted-foreground">
                    — {filtered.length} resultados
                  </span>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                  {filtered.map((product) => (
                    <ComparisonTable key={product.id} product={product} />
                  ))}
                </div>
              </section>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default Index;
