import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ErrorState } from "@/components/error-state";
import { BarChartCard } from "@/components/charts/bar-chart-card";
import { PieChartCard } from "@/components/charts/pie-chart-card";
import { getDepartmentMetrics, getReorderMetrics } from "@/lib/data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/utils";

export default function DepartmentsPage() {
  try {
    const departments = getDepartmentMetrics();
    const reorder = getReorderMetrics();

    const rankingData = departments.departments.map((d) => ({
      department: d.department,
      sold: d.total_products_sold,
      customers: d.unique_customers,
    }));

    const pieData = departments.departments.slice(0, 6).map((d) => ({
      name: d.department,
      value: d.total_products_sold,
    }));

    // Avg reorder rate by department — join via product names in top reorder list
    const avgReorderByDept = departments.departments.slice(0, 10).map((d) => ({
      department: d.department,
      customers: d.unique_customers,
    }));

    return (
      <DashboardShell
        title="Department Analytics"
        description="Department rankings, distribution, and customer reach"
      >
        <div className="space-y-8">
          <div className="grid gap-6 lg:grid-cols-2">
            <BarChartCard
              title="Department Rankings"
              description="Total products sold"
              data={rankingData}
              xKey="department"
              yKey="sold"
            />
            <PieChartCard
              title="Product Distribution"
              description="Share of top 6 departments"
              data={pieData}
            />
          </div>

          <BarChartCard
            title="Unique Customers by Department"
            description="Customer reach per department"
            data={avgReorderByDept}
            xKey="department"
            yKey="customers"
            color="hsl(199, 89%, 48%)"
            height={360}
          />

          <Card>
            <CardHeader>
              <CardTitle>Department Performance Table</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-4 py-3 text-left">Rank</th>
                      <th className="px-4 py-3 text-left">Department</th>
                      <th className="px-4 py-3 text-right">Products Sold</th>
                      <th className="px-4 py-3 text-right">Unique Customers</th>
                    </tr>
                  </thead>
                  <tbody>
                    {departments.departments.map((d, i) => (
                      <tr
                        key={d.department}
                        className="border-b border-border/50 hover:bg-muted/30"
                      >
                        <td className="px-4 py-3 text-muted-foreground">{i + 1}</td>
                        <td className="px-4 py-3 font-medium capitalize">
                          {d.department}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {d.total_products_sold.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {d.unique_customers.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Reorder Performance — Top Products</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-sm text-muted-foreground">
                Highest reorder rates across the catalog (overall avg:{" "}
                {formatPercent(
                  reorder.products.reduce((s, p) => s + p.reorder_rate, 0) /
                    reorder.products.length
                )}
                )
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {reorder.products.slice(0, 6).map((p) => (
                  <div
                    key={p.product_id}
                    className="rounded-lg border border-border p-3"
                  >
                    <p className="text-sm font-medium">{p.product_name}</p>
                    <p className="text-lg font-bold text-primary">
                      {formatPercent(p.reorder_rate)}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </DashboardShell>
    );
  } catch (error) {
    return (
      <DashboardShell title="Departments">
        <ErrorState
          message="Failed to load department data"
          hint={error instanceof Error ? error.message : undefined}
        />
      </DashboardShell>
    );
  }
}
