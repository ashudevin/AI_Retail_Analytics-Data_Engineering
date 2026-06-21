import fs from "fs";
import path from "path";
import type {
  AIInsightsData,
  BasketMetricsData,
  CustomerMetricsData,
  DashboardOverview,
  DepartmentMetricsData,
  ReorderMetricsData,
  TopProductsData,
} from "@/types";

const DATA_DIR = process.env.DASHBOARD_DATA_DIR
  ? process.env.DASHBOARD_DATA_DIR
  : path.join(process.cwd(), "public", "data");

function readJson<T>(filename: string): T {
  const filePath = path.join(DATA_DIR, filename);
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `Data file not found: ${filename}. Run: python -m src.dashboard.export_json`
    );
  }
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

/** Load all dashboard datasets (Server Component — read at build/request time) */
export function getTopProducts(): TopProductsData {
  return readJson<TopProductsData>("top_products.json");
}

export function getReorderMetrics(): ReorderMetricsData {
  return readJson<ReorderMetricsData>("reorder_metrics.json");
}

export function getDepartmentMetrics(): DepartmentMetricsData {
  return readJson<DepartmentMetricsData>("department_metrics.json");
}

export function getBasketMetrics(): BasketMetricsData {
  return readJson<BasketMetricsData>("basket_metrics.json");
}

export function getCustomerMetrics(): CustomerMetricsData {
  return readJson<CustomerMetricsData>("customer_metrics.json");
}

export function getAIInsights(): AIInsightsData {
  return readJson<AIInsightsData>("ai_insights.json");
}

/** Aggregate home-page KPIs from exported JSON files */
export function getDashboardOverview(): DashboardOverview {
  const products = getTopProducts();
  const departments = getDepartmentMetrics();
  const basket = getBasketMetrics();
  const customers = getCustomerMetrics();
  const insights = getAIInsights();

  const kpi = insights.kpi_overview;
  return {
    total_customers:
      kpi.total_customers ?? customers.summary.total_customers,
    total_products:
      kpi.total_unique_products ?? products.total_products,
    total_departments:
      kpi.total_departments ?? departments.total_departments,
    total_transactions:
      kpi.total_orders ?? basket.summary.total_orders,
    total_line_items:
      kpi.total_line_items ?? basket.summary.total_line_items,
    last_updated: insights.last_updated || products.last_updated,
  };
}
