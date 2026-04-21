import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { stores } from "@/data/mockData";
import type { Product } from "@/data/mockData";
import { formatPrice } from "@/data/mockData";

interface PriceDistributionChartProps {
  products: Product[];
}

export function PriceDistributionChart({ products }: PriceDistributionChartProps) {
  const storeAverages = stores.map((store) => {
    const prices = products
      .flatMap((p) => p.prices)
      .filter((p) => p.store === store.name)
      .map((p) => p.price);
    const avg = prices.length > 0 ? prices.reduce((a, b) => a + b, 0) / prices.length : 0;
    return { name: store.name, value: Math.round(avg), color: store.color };
  });

  return (
    <div className="structured-card overflow-hidden">
      <div className="p-5 pb-0">
        <div className="module-header">
          <span className="section-eyebrow block mb-1.5">Distribución</span>
          <h3 className="text-base font-bold text-foreground">Precio promedio por tienda</h3>
        </div>
      </div>
      <div className="px-5 pb-5">
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie
              data={storeAverages}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={88}
              paddingAngle={2}
              dataKey="value"
              stroke="hsl(220, 12%, 82%)"
              strokeWidth={1}
            >
              {storeAverages.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(40, 30%, 99%)",
                border: "2px solid hsl(220, 12%, 82%)",
                borderRadius: "2px",
                color: "hsl(220, 20%, 14%)",
                fontSize: "12px",
                fontFamily: "'IBM Plex Mono', monospace",
              }}
              formatter={(value: number) => [formatPrice(value), "Promedio"]}
            />
            <Legend
              wrapperStyle={{ fontSize: "11px", fontFamily: "'IBM Plex Mono', monospace" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
