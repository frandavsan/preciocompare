import { ExternalLink, Check, X } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Product } from "@/data/mockData";
import { formatPrice } from "@/data/mockData";

interface ComparisonTableProps {
  product: Product;
}

export function ComparisonTable({ product }: ComparisonTableProps) {
  const minPrice = Math.min(...product.prices.map((p) => p.price));

  return (
    <div className="structured-card overflow-hidden">
      <div className="p-4 border-b-2 border-border flex items-center gap-3">
        <div className="w-9 h-9 rounded-sm border-2 border-border bg-background overflow-hidden">
          <img src={product.imageUrl} alt={product.name} className="h-full w-full object-contain p-1" />
        </div>
        <div className="min-w-0">
          <h3 className="font-bold text-foreground text-sm leading-tight">{product.name}</h3>
          <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">{product.category}</span>
        </div>
      </div>
      <Table>
        <TableHeader>
          <TableRow className="border-border hover:bg-transparent">
            <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">Tienda</TableHead>
            <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium">Precio</TableHead>
            <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium text-center">Stock</TableHead>
            <TableHead className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-medium text-right">Link</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {product.prices
            .sort((a, b) => a.price - b.price)
            .map((sp, i) => (
              <TableRow key={sp.store} className={`border-border hover:bg-accent/40 ${i === 0 ? "bg-accent/30" : ""}`}>
                <TableCell className="text-sm">{sp.store}</TableCell>
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
                <TableCell className="text-center">
                  {sp.inStock ? (
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
            ))}
        </TableBody>
      </Table>
    </div>
  );
}
