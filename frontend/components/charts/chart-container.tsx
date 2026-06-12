"use client";

import { ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface ChartContainerProps {
  title: string;
  description?: string;
  height?: number;
  children: React.ReactElement;
}

/** Wrapper providing consistent chart sizing and card layout */
export function ChartContainer({
  title,
  description,
  height = 320,
  children,
}: ChartContainerProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          {children}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
