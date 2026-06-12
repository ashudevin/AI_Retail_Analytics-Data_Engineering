"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Home" },
  { href: "/products/", label: "Products" },
  { href: "/departments/", label: "Depts" },
  { href: "/customers/", label: "Customers" },
  { href: "/basket/", label: "Basket" },
  { href: "/insights/", label: "AI" },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-border bg-card px-2 py-2 md:hidden">
      {links.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium",
            pathname === href || (href !== "/" && pathname.startsWith(href))
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-accent"
          )}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
