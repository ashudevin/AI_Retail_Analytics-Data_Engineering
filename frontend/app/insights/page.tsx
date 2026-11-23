import { DashboardShell } from "@/components/layout/dashboard-shell";
import { InsightsChatbot } from "@/components/insights-chatbot";

export default function InsightsPage() {
  return (
    <DashboardShell
      title="BizMind"
      description="Ask anything — answers stay grounded in your retail analytics when relevant"
    >
      <InsightsChatbot />
    </DashboardShell>
  );
}
