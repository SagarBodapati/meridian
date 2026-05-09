"use client";

const BADGE_STYLES: Record<string, string> = {
  simple_factual:   "bg-slate-100 text-slate-600",
  multi_hop:        "bg-purple-100 text-purple-700",
  comparative:      "bg-blue-100 text-blue-700",
  trend_analysis:   "bg-emerald-100 text-emerald-700",
  calculation:      "bg-amber-100 text-amber-700",
  report_generation:"bg-rose-100 text-rose-700",
};

const LABELS: Record<string, string> = {
  simple_factual:   "Factual",
  multi_hop:        "Multi-hop",
  comparative:      "Comparative",
  trend_analysis:   "Trend",
  calculation:      "Calculation",
  report_generation:"Report",
};

export function QueryTypeBadge({ type }: { type: string }) {
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${BADGE_STYLES[type] || BADGE_STYLES.simple_factual}`}>
      {LABELS[type] || type}
    </span>
  );
}
