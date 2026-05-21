import type { ReactNode } from "react";

type Props = {
  label: string;
  value: string | number | boolean;
  tone?: "green" | "amber" | "red" | "blue";
  children?: ReactNode;
};

const tones = {
  green: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  amber: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  red: "border-red-500/40 bg-red-500/10 text-red-200",
  blue: "border-blue-500/40 bg-blue-500/10 text-blue-200",
};

export function StatusCard({ label, value, tone = "blue", children }: Props) {
  return (
    <section className={`rounded-lg border p-4 shadow-xl shadow-black/20 ${tones[tone]}`}>
      <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{label}</div>
      <div className="mt-3 text-2xl font-black text-white">{String(value)}</div>
      {children ? <div className="mt-3 text-sm text-slate-300">{children}</div> : null}
    </section>
  );
}
