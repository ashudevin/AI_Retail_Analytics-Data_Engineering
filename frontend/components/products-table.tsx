"use client";

import { useMemo, useState } from "react";
import type { Product } from "@/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { formatPercent } from "@/lib/utils";

type SortKey = "total_orders" | "reorder_rate" | "product_name";
type SortDir = "asc" | "desc";

interface ProductsTableProps {
  products: Product[];
  showOrders?: boolean;
}

export function ProductsTable({ products, showOrders = true }: ProductsTableProps) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>(
    showOrders ? "total_orders" : "reorder_rate"
  );
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    let rows = products;
    if (q) {
      rows = rows.filter(
        (p) =>
          p.product_name.toLowerCase().includes(q) ||
          String(p.product_id).includes(q)
      );
    }
    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc"
          ? av.localeCompare(bv)
          : bv.localeCompare(av);
      }
      return sortDir === "asc"
        ? Number(av) - Number(bv)
        : Number(bv) - Number(av);
    });
  }, [products, search, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="space-y-4">
      <Input
        placeholder="Search products by name or ID..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-md"
      />
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">#</th>
              <th className="px-4 py-3 text-left font-medium">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleSort("product_name")}
                >
                  Product {sortKey === "product_name" ? (sortDir === "asc" ? "↑" : "↓") : ""}
                </Button>
              </th>
              {showOrders && (
                <th className="px-4 py-3 text-right font-medium">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleSort("total_orders")}
                  >
                    Orders {sortKey === "total_orders" ? (sortDir === "asc" ? "↑" : "↓") : ""}
                  </Button>
                </th>
              )}
              <th className="px-4 py-3 text-right font-medium">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleSort("reorder_rate")}
                >
                  Reorder Rate {sortKey === "reorder_rate" ? (sortDir === "asc" ? "↑" : "↓") : ""}
                </Button>
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={showOrders ? 4 : 3} className="px-4 py-8 text-center text-muted-foreground">
                  No products match your search.
                </td>
              </tr>
            ) : (
              filtered.slice(0, 100).map((p, i) => (
                <tr key={p.product_id} className="border-b border-border/50 hover:bg-muted/30">
                  <td className="px-4 py-3 text-muted-foreground">{i + 1}</td>
                  <td className="px-4 py-3 font-medium">{p.product_name}</td>
                  {showOrders && (
                    <td className="px-4 py-3 text-right">
                      {p.total_orders?.toLocaleString() ?? "—"}
                    </td>
                  )}
                  <td className="px-4 py-3 text-right">
                    {formatPercent(p.reorder_rate)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {filtered.length > 100 && (
        <p className="text-xs text-muted-foreground">
          Showing top 100 of {filtered.length} results. Refine search to narrow down.
        </p>
      )}
    </div>
  );
}
