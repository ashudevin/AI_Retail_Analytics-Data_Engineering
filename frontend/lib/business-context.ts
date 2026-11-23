import {
  getBasketMetrics,
  getCustomerMetrics,
  getDepartmentMetrics,
  getReorderMetrics,
  getTopProducts,
} from "@/lib/data";

const TOP_N = 25;

/**
 * Build a compact, model-ready snapshot of evaluated Gold-layer metrics.
 * Truncates large product lists so the prompt stays within token limits.
 */
export function buildBusinessContext(): string {
  const products = getTopProducts();
  const reorders = getReorderMetrics();
  const departments = getDepartmentMetrics();
  const basket = getBasketMetrics();
  const customers = getCustomerMetrics();

  const topProducts = products.products.slice(0, TOP_N).map((p) => ({
    product_id: p.product_id,
    product_name: p.product_name,
    total_orders: p.total_orders ?? null,
    reorder_rate: p.reorder_rate,
  }));

  const topReorders = reorders.products.slice(0, TOP_N).map((p) => ({
    product_id: p.product_id,
    product_name: p.product_name,
    total_reorders: p.total_reorders ?? null,
    reorder_rate: p.reorder_rate,
  }));

  const payload = {
    dataset: "Instacart retail analytics (Gold layer exports)",
    last_updated: products.last_updated,
    overview: {
      total_products: products.total_products,
      total_departments: departments.total_departments,
      total_orders: basket.summary.total_orders,
      total_line_items: basket.summary.total_line_items,
      total_customers: customers.summary.total_customers,
    },
    basket_metrics: {
      summary: basket.summary,
      distribution: basket.distribution,
    },
    customer_metrics: {
      summary: customers.summary,
      segmentation: customers.segmentation,
      order_frequency: customers.order_frequency,
      top_customers: customers.top_customers.slice(0, 15),
    },
    department_metrics: {
      total_departments: departments.total_departments,
      departments: departments.departments,
    },
    top_products_by_orders: topProducts,
    top_products_by_reorder: topReorders,
  };

  return JSON.stringify(payload, null, 2);
}

export const CHAT_SYSTEM_PROMPT = `You are the AI Insights assistant for an Instacart retail analytics dashboard.
You can answer any question the user asks. Always be helpful and give a relevant response.

You also have access to evaluated retail BUSINESS_DATA (KPIs, products, departments, customers, baskets, trends).

Rules:
1. Answer every user question — do not refuse topics or say you can only discuss business analytics.
2. When the question relates to retail performance, metrics, products, customers, or similar topics, ground your answer in BUSINESS_DATA and prefer exact numbers from that data.
3. When the question is broader or off-topic, still answer it helpfully, and when natural, briefly connect the reply back to insights from BUSINESS_DATA (for example: analogies, examples, or related KPIs).
4. Do not invent metrics, products, or departments that are not in BUSINESS_DATA. If a retail fact is missing from the data, say so and still answer the rest of the question as best you can.
5. Keep answers clear, professional, and easy to read. Use short paragraphs or bullet lists when helpful.
6. Do not mention these system instructions unless asked how you work at a high level.`;
