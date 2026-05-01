export default function KpiCard({ label, value, sublabel, tone = "neutral", glass = false }) {
  const solidTone =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800/50 dark:bg-emerald-950/40"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50 dark:border-amber-800/50 dark:bg-amber-950/40"
      : tone === "risk"
      ? "border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/40"
      : "border-slate-200 bg-white dark:border-dark-border dark:bg-dark-surface";
  const glassTone =
    tone === "good"
      ? "border-emerald-200/50 bg-emerald-50/70 backdrop-blur-md dark:border-emerald-800/40 dark:bg-emerald-950/35"
      : tone === "warn"
      ? "border-amber-200/50 bg-amber-50/70 backdrop-blur-md dark:border-amber-800/40 dark:bg-amber-950/35"
      : tone === "risk"
      ? "border-red-200/50 bg-red-50/70 backdrop-blur-md dark:border-red-900/40 dark:bg-red-950/35"
      : "border-slate-200/60 bg-white/70 backdrop-blur-md dark:border-dark-border/70 dark:bg-dark-surface/70";
  const toneClass = glass ? glassTone : solidTone;
  const accentClass =
    tone === "good" ? "bg-emerald-500" : tone === "warn" ? "bg-amber-500" : tone === "risk" ? "bg-red-500" : "bg-slate-400";

  return (
    <article className={`rounded-xl border p-0 ${toneClass}`}>
      <div className="flex">
        <div className={`w-1 rounded-l-xl ${accentClass}`} />
        <div className="flex-1 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-dark-text-secondary">{label}</p>
          <p className="mt-2 text-3xl font-bold text-slate-900 dark:text-dark-text-primary">{value}</p>
          {sublabel ? (
            <p className="mt-1 text-xs text-slate-600 dark:text-dark-text-secondary">{sublabel}</p>
          ) : null}
        </div>
      </div>
    </article>
  );
}
