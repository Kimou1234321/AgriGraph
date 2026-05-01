export default function KpiCard({ label, value, sublabel, tone = "neutral" }) {
  const toneClass =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50"
      : tone === "risk"
      ? "border-red-200 bg-red-50"
      : "border-slate-200 bg-white";
  const accentClass =
    tone === "good" ? "bg-emerald-500" : tone === "warn" ? "bg-amber-500" : tone === "risk" ? "bg-red-500" : "bg-slate-400";

  return (
    <article className={`rounded-xl border p-0 ${toneClass}`}>
      <div className="flex">
        <div className={`w-1 rounded-l-xl ${accentClass}`} />
        <div className="flex-1 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
          {sublabel ? <p className="mt-1 text-xs text-slate-600">{sublabel}</p> : null}
        </div>
      </div>
    </article>
  );
}

