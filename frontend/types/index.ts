/** Type definitions for dashboard JSON data exports */

export interface Product {
  product_id: number;
  product_name: string;
  total_orders?: number;
  total_reorders?: number;
  reorder_rate: number;
}

export interface TopProductsData {
  last_updated: string;
  total_products: number;
  products: Product[];
}

export interface ReorderMetricsData {
  last_updated: string;
  total_products: number;
  products: Product[];
}

export interface Department {
  department: string;
  total_products_sold: number;
  unique_customers: number;
}

export interface DepartmentMetricsData {
  last_updated: string;
  total_departments: number;
  departments: Department[];
}

export interface BasketSummary {
  total_orders: number;
  total_line_items: number;
  mean_basket_size: number;
  median_basket_size: number;
  min_basket_size: number;
  max_basket_size: number;
  std_basket_size: number;
}

export interface BasketDistribution {
  bucket: string;
  orders: number;
}

export interface BasketMetricsData {
  last_updated: string;
  summary: BasketSummary;
  distribution: BasketDistribution[];
}

export interface CustomerSummary {
  total_customers: number;
  avg_orders_per_customer: number;
  median_orders_per_customer: number;
  avg_products_per_customer: number;
  avg_basket_size: number;
  single_order_customer_pct: number;
  power_user_pct: number;
}

export interface CustomerSegment {
  segment: string;
  customers: number;
  percentage: number;
  avg_basket_size: number;
  avg_products: number;
}

export interface CustomerRecord {
  user_id: number;
  total_orders: number;
  total_products: number;
  avg_basket_size: number;
}

export interface CustomerMetricsData {
  last_updated: string;
  summary: CustomerSummary;
  segmentation: CustomerSegment[];
  order_frequency: { orders: number; customers: number }[];
  top_customers: CustomerRecord[];
}

export interface AIInsightsData {
  last_updated: string;
  model: string;
  executive_summary: string;
  sections: Record<string, string>;
  recommendations: string[];
  full_text: string;
  kpi_overview: {
    total_unique_products?: number;
    total_departments?: number;
    total_orders?: number;
    total_customers?: number;
    total_line_items?: number;
  };
}

export interface DashboardOverview {
  total_customers: number;
  total_products: number;
  total_departments: number;
  total_transactions: number;
  total_line_items: number;
  last_updated: string;
}
