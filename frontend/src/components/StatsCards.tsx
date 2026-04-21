import { TrendingDown, TrendingUp, Package, Store } from "lucide-react";
import { products, stores, formatPrice } from "@/data/mockData";

export function StatsCards() {
  const allPrices = products.flatMap((p) => p.prices);
  const totalProducts = products.length;
  const totalStores = stores.length;
  const avgPrice = Math.round(allPrices.reduce((a, b) => a + b.price, 0) / allPrices.length);
  const lowestPrice = Math.min(...allPrices.map((p) => p.price));

  const stats = [
    { label: "Productos", value: totalProducts.toString(), icon: Package, color: "text-primary" },
    { label: "Tiendas", value: totalStores.toString(), icon: Store, color: "text-secondary" },
    { label: "Precio promedio", value: formatPrice(avgPrice), icon: TrendingUp, color: "text-foreground" },
    { label: "Precio más bajo", value: formatPrice(lowestPrice), icon: TrendingDown, color: "text-secondary" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <div key={stat.label} className="structured-card p-5">
          <div className="flex items-center gap-2 mb-1">
            <stat.icon className={`h-3.5 w-3.5 ${stat.color}`} />
            <span className="editorial-label">{stat.label}</span>
          </div>
          <p className={`text-2xl font-bold font-mono mt-2 ${stat.color}`}>{stat.value}</p>
        </div>
      ))}
    </div>
  );
}
