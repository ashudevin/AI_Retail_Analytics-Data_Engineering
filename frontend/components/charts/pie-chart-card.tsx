"use client";

import { Cell, Pie, PieChart, Tooltip, Legend } from "recharts";
import { ChartContainer } from "./chart-container";

const COLORS = [
  "hsl(221, 83%, 53%)",
  "hsl(142, 76%, 36%)",
  "hsl(262, 83%, 58%)",
  "hsl(24, 95%, 53%)",
  "hsl(199, 89%, 48%)",
  "hsl(340, 82%, 52%)",
];

interface PieChartCardProps {
  title: string;
  description?: string;
  data: { name: string; value: number }[];
  height?: number;
}

export function PieChartCard({
  title,
  description,
  data,
  height,
}: PieChartCardProps) {
  return (
    <ChartContainer title={title} description={description} height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={({ name, percent }) =>
            `${name} (${(percent * 100).toFixed(0)}%)`
          }
        >
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ChartContainer>
  );
}
