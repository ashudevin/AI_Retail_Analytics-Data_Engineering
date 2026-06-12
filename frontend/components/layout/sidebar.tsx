"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Brain,
  Home,
  Package,
  ShoppingCart,
  Users,
  Building2,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Overview", icon: Home },
  { href: "/products/", label: "Products", icon: Package },
  { href: "/departments/", label: "Departments", icon: Building2 },
  { href: "/customers/", label: "Customers", icon: Users },
  { href: "/basket/", label: "Basket Analytics", icon: ShoppingCart },
  { href: "/insights/", label: "AI Insights", icon: Brain },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 border-r border-border bg-card md:flex md:flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-border px-6">
        <BarChart3 className="h-6 w-6 text-primary" />
        <div>
          <p className="text-sm font-bold leading-tight">Retail Analytics</p>
          <p className="text-xs text-muted-foreground">AI-Powered Dashboard</p>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-4">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-4">
        <p className="text-xs text-muted-foreground">
          Instacart Market Basket Analysis
        </p>
        <p className="text-xs text-muted-foreground">PySpark → Gold → AI</p>
      </div>
    </aside>
  );
}
