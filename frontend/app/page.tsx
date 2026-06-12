import {
  Users,
  Package,
  Building2,
  ShoppingBag,
  Layers,
  Clock,
} from "lucide-react";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { KpiCard } from "@/components/kpi-card";
import { ErrorState } from "@/components/error-state";
import { BarChartCard } from "@/components/charts/bar-chart-card";
import { getDashboardOverview, getTopProducts, getDepartmentMetrics } from "@/lib/data";
import { formatDate, formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  try {
    const overview = getDashboardOverview();
    const topProducts = getTopProducts();
    const departments = getDepartmentMetrics();

    const topChartData = topProducts.products.slice(0, 8).map((p) => ({
      name: p.product_name.length > 18
        ? `${p.product_name.slice(0, 18)}…`
        : p.product_name,
      orders: p.total_orders ?? 0,
    }));

    const deptChartData = departments.departments.slice(0, 8).map((d) => ({
      name: d.department,
      sold: d.total_products_sold,
    }));

    return (
      <DashboardShell
        title="Overview"
        description="AI-Powered Retail Analytics — Instacart Market Basket"
      >
        <div className="space-y-8">
          <Card className="border-primary/20 bg-gradient-to-r from-primary/5 to-transparent">
            <CardHeader>
              <CardTitle>Project Overview</CardTitle>
            </CardHeader>
            <CardContent className="text-sm leading-relaxed text-muted-foreground">
              End-to-end data engineering pipeline: PySpark ingestion (Bronze),
              data quality &amp; transformation (Silver), business KPI aggregation
              (Gold), Gemini AI insights, and this static analytics dashboard —
              deployed on Vercel with zero backend cold starts.
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <KpiCard
              title="Total Customers"
              value={formatNumber(overview.total_customers)}
              icon={Users}
              subtitle="Unique shoppers in dataset"
            />
            <KpiCard
              title="Total Products"
              value={formatNumber(overview.total_products)}
              icon={Package}
              subtitle="Unique SKUs analyzed"
            />
            <KpiCard
              title="Departments"
              value={String(overview.total_departments)}
              icon={Building2}
              subtitle="Product categories"
            />
            <KpiCard
              title="Total Transactions"
              value={formatNumber(overview.total_transactions)}
              icon={ShoppingBag}
              subtitle="Completed orders"
            />
            <KpiCard
              title="Line Items"
              value={formatNumber(overview.total_line_items)}
              icon={Layers}
              subtitle="Products added to carts"
            />
            <KpiCard
              title="Last Refresh"
              value={formatDate(overview.last_updated)}
              icon={Clock}
              subtitle="Gold layer export timestamp"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <BarChartCard
              title="Top Selling Products"
              description="Highest order volume"
              data={topChartData}
              xKey="name"
              yKey="orders"
            />
            <BarChartCard
              title="Top Departments"
              description="Products sold by department"
              data={deptChartData}
              xKey="name"
              yKey="sold"
              color="hsl(142, 76%, 36%)"
            />
          </div>
        </div>
      </DashboardShell>
    );
  } catch (error) {
    return (
      <DashboardShell title="Overview">
        <ErrorState
          message="Failed to load dashboard data"
          hint={
            error instanceof Error
              ? error.message
              : "Run: python -m src.dashboard.export_json"
          }
        />
      </DashboardShell>
    );
  }
}
