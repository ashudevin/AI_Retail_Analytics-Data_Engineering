import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { BarChartCard } from "@/components/charts/bar-chart-card";
import { PieChartCard } from "@/components/charts/pie-chart-card";
import { getCustomerMetrics } from "@/lib/data";
import { formatNumber } from "@/lib/utils";
import { Users, Repeat, ShoppingCart, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CustomersPage() {
  try {
    const data = getCustomerMetrics();
    const { summary, segmentation, order_frequency, top_customers } = data;

    const segPie = segmentation.map((s) => ({
      name: s.segment,
      value: s.customers,
    }));

    const freqChart = order_frequency.map((f) => ({
      orders: `${f.orders} orders`,
      customers: f.customers,
    }));

    return (
      <DashboardShell
        title="Customer Analytics"
        description="Order frequency, segmentation, and purchasing behavior"
      >
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              title="Total Customers"
              value={formatNumber(summary.total_customers)}
              icon={Users}
            />
            <KpiCard
              title="Avg Orders / Customer"
              value={String(summary.avg_orders_per_customer)}
              icon={Repeat}
            />
            <KpiCard
              title="Avg Basket Size"
              value={String(summary.avg_basket_size)}
              icon={ShoppingCart}
            />
            <KpiCard
              title="Power Users (21+)"
              value={`${summary.power_user_pct}%`}
              icon={Zap}
              subtitle="Customers with 21+ orders"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <PieChartCard
              title="Customer Segmentation"
              description="Distribution by order frequency"
              data={segPie}
            />
            <BarChartCard
              title="Order Frequency Distribution"
              description="Customers by number of orders"
              data={freqChart}
              xKey="orders"
              yKey="customers"
              color="hsl(24, 95%, 53%)"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Segmentation Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-4 py-3 text-left">Segment</th>
                      <th className="px-4 py-3 text-right">Customers</th>
                      <th className="px-4 py-3 text-right">%</th>
                      <th className="px-4 py-3 text-right">Avg Basket</th>
                      <th className="px-4 py-3 text-right">Avg Products</th>
                    </tr>
                  </thead>
                  <tbody>
                    {segmentation.map((s) => (
                      <tr
                        key={s.segment}
                        className="border-b border-border/50 hover:bg-muted/30"
                      >
                        <td className="px-4 py-3 font-medium">{s.segment}</td>
                        <td className="px-4 py-3 text-right">
                          {s.customers.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right">{s.percentage}%</td>
                        <td className="px-4 py-3 text-right">
                          {s.avg_basket_size}
                        </td>
                        <td className="px-4 py-3 text-right">{s.avg_products}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Top Customers by Order Volume</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-4 py-3 text-left">User ID</th>
                      <th className="px-4 py-3 text-right">Total Orders</th>
                      <th className="px-4 py-3 text-right">Total Products</th>
                      <th className="px-4 py-3 text-right">Avg Basket Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {top_customers.slice(0, 15).map((c) => (
                      <tr
                        key={c.user_id}
                        className="border-b border-border/50 hover:bg-muted/30"
                      >
                        <td className="px-4 py-3 font-mono text-muted-foreground">
                          {c.user_id}
                        </td>
                        <td className="px-4 py-3 text-right">{c.total_orders}</td>
                        <td className="px-4 py-3 text-right">
                          {c.total_products.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {c.avg_basket_size.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      </DashboardShell>
    );
  } catch (error) {
    return (
      <DashboardShell title="Customers">
        <ErrorState
          message="Failed to load customer data"
          hint={error instanceof Error ? error.message : undefined}
        />
      </DashboardShell>
    );
  }
}
