import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { BarChartCard } from "@/components/charts/bar-chart-card";
import { LineChartCard } from "@/components/charts/line-chart-card";
import { getBasketMetrics } from "@/lib/data";
import { ShoppingCart, TrendingUp, Minus, Maximize2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function BasketPage() {
  try {
    const data = getBasketMetrics();
    const { summary, distribution } = data;

    const distChart = distribution.map((d) => ({
      bucket: d.bucket,
      orders: d.orders,
    }));

    return (
      <DashboardShell
        title="Basket Analytics"
        description="Basket size analysis and purchase behavior"
      >
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              title="Mean Basket Size"
              value={String(summary.mean_basket_size)}
              icon={ShoppingCart}
              subtitle="Products per order (avg)"
            />
            <KpiCard
              title="Median Basket Size"
              value={String(summary.median_basket_size)}
              icon={TrendingUp}
              subtitle="Typical order size"
            />
            <KpiCard
              title="Min Basket"
              value={String(summary.min_basket_size)}
              icon={Minus}
            />
            <KpiCard
              title="Max Basket"
              value={String(summary.max_basket_size)}
              icon={Maximize2}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <BarChartCard
              title="Basket Size Distribution"
              description="Number of orders by basket size bucket"
              data={distChart}
              xKey="bucket"
              yKey="orders"
            />
            <LineChartCard
              title="Purchase Behavior Trend"
              description="Order volume across basket size ranges"
              data={distChart}
              xKey="bucket"
              yKey="orders"
              color="hsl(142, 76%, 36%)"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Key Shopping Trends</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-relaxed text-muted-foreground">
              <p>
                <strong className="text-foreground">
                  {summary.total_orders.toLocaleString()}
                </strong>{" "}
                total orders contain{" "}
                <strong className="text-foreground">
                  {summary.total_line_items.toLocaleString()}
                </strong>{" "}
                line items, averaging{" "}
                <strong className="text-foreground">
                  {summary.mean_basket_size}
                </strong>{" "}
                products per basket.
              </p>
              <p>
                The median basket of{" "}
                <strong className="text-foreground">
                  {summary.median_basket_size}
                </strong>{" "}
                items suggests most shoppers make focused, repeat purchases
                rather than large bulk orders.
              </p>
              <p>
                Standard deviation of{" "}
                <strong className="text-foreground">
                  {summary.std_basket_size}
                </strong>{" "}
                indicates moderate variability — a mix of quick top-up trips
                and larger grocery runs.
              </p>
            </CardContent>
          </Card>
        </div>
      </DashboardShell>
    );
  } catch (error) {
    return (
      <DashboardShell title="Basket Analytics">
        <ErrorState
          message="Failed to load basket data"
          hint={error instanceof Error ? error.message : undefined}
        />
      </DashboardShell>
    );
  }
}
