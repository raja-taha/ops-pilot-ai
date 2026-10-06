const STYLES: Record<string, string> = {
  open: "bg-mist text-moss",
  investigating: "bg-amber-100 text-amber-900",
  awaiting_approval: "bg-orange-100 text-orange-900",
  remediating: "bg-sky-100 text-sky-900",
  resolved: "bg-emerald-100 text-emerald-900",
  closed: "bg-stone-200 text-stone-700",
  failed: "bg-red-100 text-red-800",
  proposed: "bg-amber-100 text-amber-900",
  approved: "bg-sky-100 text-sky-900",
  rejected: "bg-stone-200 text-stone-700",
  executed: "bg-emerald-100 text-emerald-900",
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-900",
  medium: "bg-amber-100 text-amber-900",
  low: "bg-mist text-moss",
};

export function StatusPill({ value }: { value: string }) {
  const cls = STYLES[value] || "bg-stone-200 text-stone-700";
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide ${cls}`}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}
