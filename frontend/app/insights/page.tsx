import { DashboardShell } from "@/components/layout/dashboard-shell";
import { InsightsViewer } from "@/components/insights-viewer";
import { ErrorState } from "@/components/error-state";
import { getAIInsights } from "@/lib/data";

export default function InsightsPage() {
  try {
    const insights = getAIInsights();

    return (
      <DashboardShell
        title="AI Insights"
        description="Executive summary and recommendations powered by Gemini"
      >
        <InsightsViewer insights={insights} />
      </DashboardShell>
    );
  } catch (error) {
    return (
      <DashboardShell title="AI Insights">
        <ErrorState
          message="Failed to load AI insights"
          hint={
            error instanceof Error
              ? error.message
              : "Run: python -m src.ai.run_ai_insights && python -m src.dashboard.export_json"
          }
        />
      </DashboardShell>
    );
  }
}
