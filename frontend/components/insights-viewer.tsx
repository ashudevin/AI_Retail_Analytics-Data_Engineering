"use client";

import { Download } from "lucide-react";
import type { AIInsightsData } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";

interface InsightsViewerProps {
  insights: AIInsightsData;
}

const SECTION_LABELS: Record<string, string> = {
  executive_summary: "Executive Summary",
  top_performing_products: "Top Performing Products",
  most_reordered_products: "Most Reordered Products",
  best_performing_departments: "Best Performing Departments",
  customer_purchasing_trends: "Customer Purchasing Trends",
  basket_size_analysis: "Basket Size Analysis",
  key_business_recommendations: "Key Business Recommendations",
};

export function InsightsViewer({ insights }: InsightsViewerProps) {
  function downloadTxt() {
    const blob = new Blob([insights.full_text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "insights.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          <Badge>Model: {insights.model}</Badge>
          <Badge className="bg-transparent">Updated: {formatDate(insights.last_updated)}</Badge>
        </div>
        <Button variant="outline" onClick={downloadTxt}>
          <Download className="h-4 w-4" />
          Download insights.txt
        </Button>
      </div>

      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle>Executive Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap leading-relaxed text-sm">
            {insights.executive_summary}
          </p>
        </CardContent>
      </Card>

      {insights.recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Business Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed">
              {insights.recommendations.map((rec, i) => (
                <li key={i}>{rec}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {Object.entries(insights.sections).map(([key, content]) => {
        if (!content || key === "executive_summary") return null;
        return (
          <Card key={key}>
            <CardHeader>
              <CardTitle className="text-base">
                {SECTION_LABELS[key] ?? key.replace(/_/g, " ")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                {content}
              </p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
