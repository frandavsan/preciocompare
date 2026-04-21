import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { stores } from "@/data/mockData";
import type { Product } from "@/data/mockData";
import { formatPrice } from "@/data/mockData";

interface PriceHistoryChartProps {
  product: Product;
}

export function PriceHistoryChart({ product }: PriceHistoryChartProps) {
  const dates = [...new Set(product.priceHistory.map((p) => p.date))];
  const chartData = dates.map((date) => {
    const entry: Record<string, string | number> = { date };
    product.priceHistory
      .filter((p) => p.date === date)
      .forEach((p) => {
        entry[p.store] = p.price;
      });
    return entry;
  });

  const storesInHistory = [...new Set(product.priceHistory.map((p) => p.store))];

  return (
    <div className="structured-card overflow-hidden">
      <div className="p-5 pb-0">
        <div className="module-header">
          <span className="section-eyebrow block mb-1.5">Historial · 7 meses</span>
          <h3 className="text-base font-bold text-foreground">{product.name}</h3>
        </div>
      </div>
      <div className="px-5 pb-5">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(220, 12%, 90%)" />
            <XAxis
              dataKey="date"
              tick={{ fill: "hsl(220, 10%, 46%)", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}
              axisLine={{ stroke: "hsl(220, 12%, 82%)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "hsl(220, 10%, 46%)", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}
              axisLine={{ stroke: "hsl(220, 12%, 82%)" }}
              tickLine={false}
              tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(40, 30%, 99%)",
                border: "2px solid hsl(220, 12%, 82%)",
                borderRadius: "2px",
                color: "hsl(220, 20%, 14%)",
                fontSize: "12px",
                fontFamily: "'IBM Plex Mono', monospace",
              }}
              formatter={(value: number) => [formatPrice(value), ""]}
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
    </div>
  );
}
