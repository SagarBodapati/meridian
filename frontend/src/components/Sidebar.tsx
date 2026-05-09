"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { TrendingUp, MessageSquare, Search, BarChart2, Settings } from "lucide-react";
import { IngestPanel } from "./Research/IngestPanel";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/",          icon: MessageSquare, label: "Research Chat" },
  { href: "/search",    icon: Search,        label: "Document Search" },
  { href: "/analytics", icon: BarChart2,     label: "Analytics" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 flex-shrink-0 flex flex-col border-r border-slate-200 bg-white h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-100">
        <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <TrendingUp size={14} className="text-white" />
        </div>
        <div>
          <p className="font-bold text-slate-800 text-sm leading-tight">Meridian</p>
          <p className="text-[10px] text-slate-400 leading-tight">Financial Research Copilot</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-2 py-3 flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === href
                ? "bg-brand-50 text-brand-700 font-medium"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
            )}
          >
            <Icon size={15} />
            {label}
          </Link>
        ))}
      </nav>

      {/* Divider */}
      <div className="mx-4 border-t border-slate-100 my-2" />

      {/* Ingest panel */}
      <div className="px-3 flex-1 overflow-y-auto">
        <IngestPanel />
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-100">
        <p className="text-[10px] text-slate-400 text-center">
          Powered by Claude · voyage-finance-2
        </p>
      </div>
    </aside>
  );
}
