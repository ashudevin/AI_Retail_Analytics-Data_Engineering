import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ProductsTable } from "@/components/products-table";
import { ErrorState } from "@/components/error-state";
import { BarChartCard } from "@/components/charts/bar-chart-card";
import { getTopProducts, getReorderMetrics } from "@/lib/data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ProductsPage() {
  try {
    const topProducts = getTopProducts();
    const reorderMetrics = getReorderMetrics();

    const topSellingChart = topProducts.products.slice(0, 10).map((p) => ({
      name: p.product_name.length > 16
        ? `${p.product_name.slice(0, 16)}…`
        : p.product_name,
      orders: p.total_orders ?? 0,
    }));

    const topReorderChart = reorderMetrics.products.slice(0, 10).map((p) => ({
      name: p.product_name.length > 16
        ? `${p.product_name.slice(0, 16)}…`
        : p.product_name,
      rate: Math.round(p.reorder_rate * 100),
    }));

    return (
      <DashboardShell
        title="Product Analytics"
        description="Top selling and most reordered products"
      >
        <div className="space-y-8">
          <div className="grid gap-6 lg:grid-cols-2">
            <BarChartCard
              title="Top Selling Products"
              data={topSellingChart}
              xKey="name"
              yKey="orders"
            />
            <BarChartCard
              title="Highest Reorder Rate (%)"
              data={topReorderChart}
              xKey="name"
              yKey="rate"
              color="hsl(262, 83%, 58%)"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Top Selling Products</CardTitle>
            </CardHeader>
            <CardContent>
              <ProductsTable products={topProducts.products} showOrders />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Most Reordered Products</CardTitle>
            </CardHeader>
            <CardContent>
              <ProductsTable
                products={reorderMetrics.products}
                showOrders={false}
              />
            </CardContent>
          </Card>
        </div>
      </DashboardShell>
    );
  } catch (error) {
    return (
      <DashboardShell title="Products">
        <ErrorState
          message="Failed to load product data"
          hint={error instanceof Error ? error.message : undefined}
        />
      </DashboardShell>
    );
  }
}
